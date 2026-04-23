/*
 * Smart Parking System — ENTRY GATE Firmware v4.0
 * Architecture : Server-as-Master / ESP32-as-Slave
 * Hardware     : ESP32-CAM (AI-Thinker) + IR Sensor + SG90 Servo
 *
 * Role change from v3:
 *   v3 (wrong): ESP32 captures + POSTs image → server decides → ESP32 acts
 *   v4 (correct): ESP32 signals trigger → server fetches image → server decides → server commands gate
 *
 * ESP32 exposes an HTTP server (port 80) with three endpoints:
 *   GET  /capture  — returns buffered JPEG (captured at IR trigger time)
 *   POST /gate     — {"action":"open"|"close"} — controls servo
 *   GET  /status   — device health JSON
 *
 * On boot: registers device IP with server via POST /api/iot/register
 * On IR  : captures image to PSRAM buffer, then fires lightweight trigger
 *          POST /api/iot/trigger {"device_id":"entry","ip":"<self IP>"}
 *          Server responds 202, then calls back /capture and /gate asynchronously.
 *
 * Libraries (Arduino Library Manager):
 *   • ArduinoJson by Benoit Blanchon v6.x
 *   • ESP32 board package by Espressif
 */

#include "esp_camera.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <ArduinoJson.h>

// ── User Config ───────────────────────────────────────────────────────────────
#define WIFI_SSID       "Projects"
#define WIFI_PASSWORD   "12345678@"
#define SERVER_BASE_URL "http://192.168.1.16:8000"

// Device identity — do NOT change on the exit-gate unit
#define DEVICE_ID   "entry"
#define GATE_TYPE   "entry"

// ── Pin Definitions ───────────────────────────────────────────────────────────
#define IR_SENSOR_PIN   14
#define SERVO_PWM_PIN   15
#define LED_FLASH_PIN    4   // kept LOW always

// ── AI-Thinker Camera Pins (fixed layout) ────────────────────────────────────
#define PWDN_GPIO_NUM   32
#define RESET_GPIO_NUM  -1
#define XCLK_GPIO_NUM    0
#define SIOD_GPIO_NUM   26
#define SIOC_GPIO_NUM   27
#define Y9_GPIO_NUM     35
#define Y8_GPIO_NUM     34
#define Y7_GPIO_NUM     39
#define Y6_GPIO_NUM     36
#define Y5_GPIO_NUM     21
#define Y4_GPIO_NUM     19
#define Y3_GPIO_NUM     18
#define Y2_GPIO_NUM      5
#define VSYNC_GPIO_NUM  25
#define HREF_GPIO_NUM   23
#define PCLK_GPIO_NUM   22

// ── Gate & Servo ──────────────────────────────────────────────────────────────
#define GATE_OPEN_ANGLE   90
#define GATE_CLOSE_ANGLE   0
#define GATE_OPEN_MS    5000
#define SERVO_MIN_US     500
#define SERVO_MAX_US    2500
#define SERVO_FREQ        50

// ── IR Sensor ─────────────────────────────────────────────────────────────────
#define IR_ACTIVE_STATE  LOW
#define IR_SAMPLES         3
#define IR_DEBOUNCE_MS    60
#define ZONE_CLEAR_MS   1500

// ── Network ───────────────────────────────────────────────────────────────────
#define HTTP_TIMEOUT_TRIGGER_MS  3000   // Short: server must respond 202 fast
#define HTTP_TIMEOUT_REGISTER_MS 5000
#define WEBSERVER_PORT             80

// ── Frame buffer (PSRAM) ──────────────────────────────────────────────────────
static uint8_t* g_frame_buf  = nullptr;
static size_t   g_frame_len  = 0;
static bool     g_frame_ready = false;

// ── Gate state ────────────────────────────────────────────────────────────────
static bool          gateOpen     = false;
static unsigned long gateOpenedMs = 0;

// ── IR state ──────────────────────────────────────────────────────────────────
static bool          vehiclePresent = false;
static unsigned long lastDetectMs   = 0;

// ── HTTP server (slave endpoints) ────────────────────────────────────────────
WebServer server(WEBSERVER_PORT);

// ── Prototypes ────────────────────────────────────────────────────────────────
void  connectWiFi();
bool  initCamera();
bool  captureToBuffer();
void  sendTrigger();
void  registerWithServer();
void  controlGate(bool open);
bool  readIR();
void  handleCapture();
void  handleGate();
void  handleStatus();


// =============================================================================
// SETUP
// =============================================================================

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(115200);
  Serial.println("\n=== ENTRY GATE v4.0 — Slave Mode ===");

  pinMode(LED_FLASH_PIN, OUTPUT);
  digitalWrite(LED_FLASH_PIN, LOW);
  pinMode(IR_SENSOR_PIN, INPUT_PULLUP);

  if (!ledcAttach(SERVO_PWM_PIN, SERVO_FREQ, 16)) {
    Serial.println("[ERROR] LEDC attach failed");
  }
  controlGate(false);

  connectWiFi();

  // ── Start slave HTTP server ───────────────────────────────────────────────
  server.on("/capture", HTTP_GET,  handleCapture);
  server.on("/gate",    HTTP_POST, handleGate);
  server.on("/status",  HTTP_GET,  handleStatus);
  server.begin();
  Serial.printf("[HTTP] Slave server listening on port %d\n", WEBSERVER_PORT);

  // ── Register with master ──────────────────────────────────────────────────
  registerWithServer();

  Serial.println("=== Ready — monitoring IR, serving HTTP ===");
}


// =============================================================================
// MAIN LOOP
// =============================================================================

void loop() {
  // Service slave HTTP endpoints first (server is master — it calls us)
  server.handleClient();

  // Auto-close gate after timeout
  if (gateOpen && (millis() - gateOpenedMs >= GATE_OPEN_MS)) {
    controlGate(false);
    Serial.println("[GATE] Auto-closed");
  }

  bool detected = readIR();

  // Rising edge: vehicle arrives
  if (detected && !vehiclePresent) {
    vehiclePresent = true;
    lastDetectMs   = millis();

    Serial.println("──────────────────────────────────");
    Serial.println("[IR] Vehicle detected — capturing");

    if (captureToBuffer()) {
      Serial.printf("[CAM] Frame buffered: %u bytes — notifying server\n", g_frame_len);
      // Notify master (fire short POST, get 202, return to loop fast)
      sendTrigger();
      // Master will call /capture and /gate via server.handleClient()
    } else {
      Serial.println("[CAM] Capture failed — keeping gate closed");
    }

    Serial.println("──────────────────────────────────");
  }

  // Falling edge: zone cleared
  if (!detected && vehiclePresent && (millis() - lastDetectMs > ZONE_CLEAR_MS)) {
    vehiclePresent = false;
    Serial.println("[IR] Zone cleared — ready for next vehicle");
  }

  delay(20);   // 50 Hz loop — keeps handleClient() responsive
}


// =============================================================================
// SLAVE ENDPOINT: GET /capture
// Master calls this to pull the JPEG that was buffered at IR-trigger time.
// =============================================================================

void handleCapture() {
  if (!g_frame_ready || !g_frame_buf || g_frame_len == 0) {
    server.send(404, "text/plain", "No frame available");
    Serial.println("[HTTP] /capture — no frame");
    return;
  }

  // Send binary JPEG via raw WiFiClient to avoid String null-byte truncation
  WiFiClient client = server.client();
  client.print("HTTP/1.1 200 OK\r\n"
               "Content-Type: image/jpeg\r\n"
               "Content-Length: ");
  client.print((uint32_t)g_frame_len);
  client.print("\r\n"
               "Connection: close\r\n"
               "\r\n");

  const uint8_t* p = g_frame_buf;
  size_t remaining = g_frame_len;
  while (remaining > 0) {
    size_t chunk = (remaining > 1460) ? 1460 : remaining;   // TCP MSS
    client.write(p, chunk);
    p         += chunk;
    remaining -= chunk;
  }

  Serial.printf("[HTTP] /capture → %u bytes served\n", g_frame_len);
  // Do NOT clear g_frame_ready here; master may retry /capture on error
}


// =============================================================================
// SLAVE ENDPOINT: POST /gate
// Master sends {"action":"open"|"close"} to command the physical gate.
// =============================================================================

void handleGate() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Method Not Allowed");
    return;
  }

  String body = server.arg("plain");
  StaticJsonDocument<64> doc;
  DeserializationError err = deserializeJson(doc, body);

  if (err) {
    server.send(400, "application/json", "{\"error\":\"bad JSON\"}");
    Serial.println("[HTTP] /gate — bad JSON");
    return;
  }

  const char* action = doc["action"] | "close";
  bool open = (strcmp(action, "open") == 0);
  controlGate(open);

  // After gate is opened, clear frame buffer — event is complete
  if (open) {
    g_frame_ready = false;
  }

  server.send(200, "application/json",
              String("{\"status\":\"ok\",\"gate\":\"") + action + "\"}");
  Serial.printf("[HTTP] /gate → %s\n", action);
}


// =============================================================================
// SLAVE ENDPOINT: GET /status
// =============================================================================

void handleStatus() {
  String ip = WiFi.localIP().toString();
  String json =
    "{\"device_id\":\"" DEVICE_ID "\","
    "\"gate_type\":\"" GATE_TYPE "\","
    "\"ip\":\"" + ip + "\","
    "\"gate_open\":" + (gateOpen ? "true" : "false") + ","
    "\"frame_ready\":" + (g_frame_ready ? "true" : "false") + ","
    "\"frame_bytes\":" + String(g_frame_len) + ","
    "\"heap_free\":" + String(ESP.getFreeHeap()) + ","
    "\"uptime_ms\":" + String(millis()) + "}";

  server.send(200, "application/json", json);
}


// =============================================================================
// CAPTURE TO PSRAM BUFFER
// Captured at IR-trigger time so the frame is ready before master calls /capture.
// =============================================================================

bool captureToBuffer() {
  if (!initCamera()) {
    Serial.println("[CAM] Init failed");
    return false;
  }

  // Discard first frame — AEC (auto-exposure) needs one frame to settle
  camera_fb_t* stale = esp_camera_fb_get();
  if (stale) esp_camera_fb_return(stale);
  delay(60);

  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[CAM] Frame buffer get failed");
    esp_camera_deinit();
    return false;
  }

  Serial.printf("[CAM] Captured %dx%d — %d bytes\n", fb->width, fb->height, fb->len);

  // Allocate PSRAM (4 MB on AI-Thinker), fall back to heap
  if (g_frame_buf) {
    free(g_frame_buf);
    g_frame_buf = nullptr;
  }
  g_frame_buf = (uint8_t*)ps_malloc(fb->len);
  if (!g_frame_buf) g_frame_buf = (uint8_t*)malloc(fb->len);

  if (!g_frame_buf) {
    Serial.println("[CAM] Buffer alloc failed — not enough RAM");
    esp_camera_fb_return(fb);
    esp_camera_deinit();
    return false;
  }

  memcpy(g_frame_buf, fb->buf, fb->len);
  g_frame_len   = fb->len;
  g_frame_ready = true;

  esp_camera_fb_return(fb);
  esp_camera_deinit();   // de-init cuts ~150 mA and resets thermal state
  Serial.println("[CAM] De-initialized (thermal standby)");
  return true;
}


// =============================================================================
// SEND TRIGGER — lightweight notification to master (no image)
// Short timeout (3 s): server MUST respond 202 quickly so ESP32 can return
// to loop() and serve the master's /capture callback.
// =============================================================================

void sendTrigger() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[TRIGGER] WiFi not connected — skipping");
    return;
  }

  StaticJsonDocument<128> doc;
  doc["device_id"] = DEVICE_ID;
  doc["ip"]        = WiFi.localIP().toString();
  String body;
  serializeJson(doc, body);

  HTTPClient http;
  http.begin(SERVER_BASE_URL "/api/iot/trigger");
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(HTTP_TIMEOUT_TRIGGER_MS);

  int code = http.POST(body);
  if (code == 200 || code == 202) {
    Serial.printf("[TRIGGER] Acknowledged (HTTP %d) — master is orchestrating\n", code);
  } else if (code > 0) {
    Serial.printf("[TRIGGER] Unexpected HTTP %d\n", code);
  } else {
    Serial.printf("[TRIGGER] Connection error: %s\n", http.errorToString(code).c_str());
  }
  http.end();
  // Return immediately — master will call back via /capture and /gate
}


// =============================================================================
// REGISTER WITH MASTER SERVER
// Called on boot so the server knows this device's current IP.
// =============================================================================

void registerWithServer() {
  if (WiFi.status() != WL_CONNECTED) return;

  StaticJsonDocument<128> doc;
  doc["device_id"] = DEVICE_ID;
  doc["gate_type"] = GATE_TYPE;
  doc["ip"]        = WiFi.localIP().toString();
  doc["port"]      = WEBSERVER_PORT;
  String body;
  serializeJson(doc, body);

  HTTPClient http;
  http.begin(SERVER_BASE_URL "/api/iot/register");
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(HTTP_TIMEOUT_REGISTER_MS);

  int code = http.POST(body);
  if (code > 0) {
    Serial.printf("[REGISTER] Registered with server (HTTP %d)\n", code);
    Serial.printf("[REGISTER] IP: %s, device_id: %s\n",
                  WiFi.localIP().toString().c_str(), DEVICE_ID);
  } else {
    Serial.printf("[REGISTER] Failed: %s — server may register via trigger\n",
                  http.errorToString(code).c_str());
  }
  http.end();
}


// =============================================================================
// CAMERA INIT
// =============================================================================

bool initCamera() {
  camera_config_t cfg = {};
  cfg.ledc_channel = LEDC_CHANNEL_0;
  cfg.ledc_timer   = LEDC_TIMER_0;
  cfg.pin_d0  = Y2_GPIO_NUM;  cfg.pin_d1 = Y3_GPIO_NUM;
  cfg.pin_d2  = Y4_GPIO_NUM;  cfg.pin_d3 = Y5_GPIO_NUM;
  cfg.pin_d4  = Y6_GPIO_NUM;  cfg.pin_d5 = Y7_GPIO_NUM;
  cfg.pin_d6  = Y8_GPIO_NUM;  cfg.pin_d7 = Y9_GPIO_NUM;
  cfg.pin_xclk     = XCLK_GPIO_NUM;
  cfg.pin_pclk     = PCLK_GPIO_NUM;
  cfg.pin_vsync    = VSYNC_GPIO_NUM;
  cfg.pin_href     = HREF_GPIO_NUM;
  cfg.pin_sscb_sda = SIOD_GPIO_NUM;
  cfg.pin_sscb_scl = SIOC_GPIO_NUM;
  cfg.pin_pwdn     = PWDN_GPIO_NUM;
  cfg.pin_reset    = RESET_GPIO_NUM;
  cfg.xclk_freq_hz = 10000000;   // 10 MHz — cuts heat vs default 20 MHz
  cfg.pixel_format = PIXFORMAT_JPEG;
  cfg.frame_size   = FRAMESIZE_CIF;   // 352×288 — good for OCR, ~40% smaller than VGA
  cfg.jpeg_quality = 12;
  cfg.fb_count     = 1;
  cfg.grab_mode    = CAMERA_GRAB_LATEST;

  if (esp_camera_init(&cfg) != ESP_OK) return false;

  sensor_t* s = esp_camera_sensor_get();
  if (s) {
    s->set_whitebal(s, 1);
    s->set_awb_gain(s, 1);
    s->set_exposure_ctrl(s, 1);
    s->set_aec2(s, 0);
    s->set_gain_ctrl(s, 1);
    s->set_brightness(s, 0);
    s->set_contrast(s, 0);
    s->set_saturation(s, 0);
    s->set_sharpness(s, 0);
    s->set_denoise(s, 0);
  }
  return true;
}


// =============================================================================
// SERVO GATE CONTROL
// =============================================================================

void controlGate(bool open) {
  int angle = open ? GATE_OPEN_ANGLE : GATE_CLOSE_ANGLE;
  int pulse = map(angle, 0, 180, SERVO_MIN_US, SERVO_MAX_US);
  int duty  = (int)((long)pulse * 65535L / 20000L);

  ledcWrite(SERVO_PWM_PIN, duty);
  delay(350);

  gateOpen = open;
  if (open) gateOpenedMs = millis();

  Serial.printf("[SERVO] Gate %s (%d°)\n", open ? "OPEN" : "CLOSED", angle);
}


// =============================================================================
// IR SENSOR — Majority-vote debounce (2 of 3 reads must agree)
// =============================================================================

bool readIR() {
  int hits = 0;
  for (int i = 0; i < IR_SAMPLES; i++) {
    if (digitalRead(IR_SENSOR_PIN) == IR_ACTIVE_STATE) hits++;
    delay(IR_DEBOUNCE_MS / IR_SAMPLES);
  }
  return (hits >= (IR_SAMPLES / 2 + 1));
}


// =============================================================================
// WIFI
// =============================================================================

void connectWiFi() {
  Serial.print("[WiFi] Connecting to " WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setTxPower(WIFI_POWER_15dBm);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 30 && WiFi.status() != WL_CONNECTED; i++) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("[WiFi] Connected — IP: " + WiFi.localIP().toString());
  } else {
    Serial.println("[WiFi] FAILED — running in offline mode");
  }
}
