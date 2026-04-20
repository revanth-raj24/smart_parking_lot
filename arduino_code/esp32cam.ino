/*
 * ESP32-CAM Smart Parking System
 * Production Firmware v2.0 — Backend Integrated
 *
 * Hardware: ESP32-CAM (AI-Thinker), IR Sensor, SG90 Servo
 * Set MODE to MODE_ENTRY or MODE_EXIT before uploading.
 *
 * Required libraries (install via Arduino Library Manager):
 *   - ArduinoJson by Benoit Blanchon (v6.x)
 *   - ESP32 board package by Espressif
 */

#include "esp_camera.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "SPIFFS.h"

// ==================== CONFIGURATION ====================

#define MODE_ENTRY  1
#define MODE_EXIT   2
#define MODE        MODE_ENTRY   // ← Change to MODE_EXIT for exit gate

const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Backend base URL — update after deployment
const char* BACKEND_BASE = "http://YOUR_SERVER_IP:8000";

#if MODE == MODE_ENTRY
  const char* BACKEND_EVENT_URL = "http://YOUR_SERVER_IP:8000/api/esp32/entry-event";
#else
  const char* BACKEND_EVENT_URL = "http://YOUR_SERVER_IP:8000/api/esp32/exit-event";
#endif

// ── Pin Definitions ──────────────────────────────────────────────────────────
#define IR_SENSOR_PIN    13
#define SERVO_PWM_PIN    14
#define LED_FLASH_PIN    4

// ── Servo Parameters ─────────────────────────────────────────────────────────
#define SERVO_FREQ       50
#define SERVO_RESOLUTION 16
#define SERVO_CHANNEL    0
#define SERVO_MIN_US     500
#define SERVO_MAX_US     2500
#define GATE_OPEN_ANGLE  90
#define GATE_CLOSE_ANGLE 0
#define GATE_OPEN_MS     5000

// ── IR Sensor ────────────────────────────────────────────────────────────────
#define IR_ACTIVE_STATE  LOW
#define IR_DEBOUNCE_MS   50
#define IR_SAMPLES       5

// ── Camera (AI-Thinker ESP32-CAM) ────────────────────────────────────────────
#define PWDN_GPIO_NUM    32
#define RESET_GPIO_NUM   -1
#define XCLK_GPIO_NUM    0
#define SIOD_GPIO_NUM    26
#define SIOC_GPIO_NUM    27
#define Y9_GPIO_NUM      35
#define Y8_GPIO_NUM      34
#define Y7_GPIO_NUM      39
#define Y6_GPIO_NUM      36
#define Y5_GPIO_NUM      21
#define Y4_GPIO_NUM      19
#define Y3_GPIO_NUM      18
#define Y2_GPIO_NUM      5
#define VSYNC_GPIO_NUM   25
#define HREF_GPIO_NUM    23
#define PCLK_GPIO_NUM    22

#define IMAGE_PATH       "/last_capture.jpg"
#define HTTP_TIMEOUT_MS  15000

// ==================== GLOBALS ====================

WebServer server(80);
camera_fb_t* lastFrame     = NULL;
bool cameraReady           = false;
bool vehiclePresent        = false;
unsigned long lastDetectMs = 0;
unsigned long gateOpenedMs = 0;
bool gateOpen              = false;

// ==================== FUNCTION PROTOTYPES ====================

bool initCamera();
bool captureImage();
bool readIR();
void setGate(bool open);
void connectWiFi();
void handleEntry();
void handleExit();
bool sendEventToBackend(String& outStatus, String& outMessage);
void handleRoot();
void handleCapture();

// ==================== SETUP ====================

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);
  Serial.begin(115200);
  Serial.println("\n=== ESP32-CAM Smart Parking v2.0 ===");
#if MODE == MODE_ENTRY
  Serial.println("Mode: ENTRY GATE");
#else
  Serial.println("Mode: EXIT GATE");
#endif

  if (!SPIFFS.begin(true)) Serial.println("[ERROR] SPIFFS init failed");

  pinMode(IR_SENSOR_PIN, INPUT_PULLUP);
  pinMode(LED_FLASH_PIN, OUTPUT);
  digitalWrite(LED_FLASH_PIN, LOW);

  ledcSetup(SERVO_CHANNEL, SERVO_FREQ, SERVO_RESOLUTION);
  ledcAttachPin(SERVO_PWM_PIN, SERVO_CHANNEL);
  setGate(false);

  cameraReady = initCamera();
  Serial.println(cameraReady ? "[OK] Camera ready" : "[ERROR] Camera init failed");

  connectWiFi();

  if (WiFi.status() == WL_CONNECTED) {
    server.on("/", handleRoot);
    server.on("/capture", handleCapture);
    // Admin-triggered gate control endpoints
    server.on("/gate/open",  []() { setGate(true);  server.send(200, "text/plain", "opened"); });
    server.on("/gate/close", []() { setGate(false); server.send(200, "text/plain", "closed"); });
    server.onNotFound([]() { server.send(404, "text/plain", "Not found"); });
    server.begin();
    Serial.print("[OK] Web server at http://");
    Serial.println(WiFi.localIP());
  }

  Serial.println("=== System ready — monitoring for vehicles ===");
}

// ==================== MAIN LOOP ====================

void loop() {
  if (WiFi.status() == WL_CONNECTED) server.handleClient();

  if (gateOpen && (millis() - gateOpenedMs >= GATE_OPEN_MS)) {
    setGate(false);
    Serial.println("[GATE] Auto-closed after timeout");
  }

#if MODE == MODE_ENTRY
  handleEntry();
#else
  handleExit();
#endif

  delay(50);
}

// ==================== GATE LOGIC ====================

void handleEntry() {
  bool detected = readIR();

  if (detected && !vehiclePresent) {
    vehiclePresent = true;
    lastDetectMs   = millis();
    Serial.println("==============================");
    Serial.println("[ENTRY] Vehicle detected");

    if (captureImage()) {
      String status, message;
      bool allow = sendEventToBackend(status, message);
      Serial.printf("[ENTRY] Response: %s — %s\n", status.c_str(), message.c_str());

      if (allow) {
        setGate(true);
      } else {
        Serial.println("[GATE] DENIED: " + message);
      }
    } else {
      Serial.println("[ENTRY] Image capture failed — gate stays closed");
    }
    Serial.println("==============================");
  }

  if (!detected && vehiclePresent && (millis() - lastDetectMs > 1000)) {
    vehiclePresent = false;
    Serial.println("[ENTRY] Zone cleared");
  }
}

void handleExit() {
  bool detected = readIR();

  if (detected && !vehiclePresent) {
    vehiclePresent = true;
    lastDetectMs   = millis();
    Serial.println("==============================");
    Serial.println("[EXIT] Vehicle detected");

    if (captureImage()) {
      String status, message;
      bool allow = sendEventToBackend(status, message);
      Serial.printf("[EXIT] Response: %s — %s\n", status.c_str(), message.c_str());

      if (allow) {
        setGate(true);
      } else {
        Serial.println("[GATE] DENIED: " + message);
      }
    } else {
      Serial.println("[EXIT] Image capture failed — gate stays closed");
    }
    Serial.println("==============================");
  }

  if (!detected && vehiclePresent && (millis() - lastDetectMs > 1000)) {
    vehiclePresent = false;
    Serial.println("[EXIT] Zone cleared");
  }
}

// ==================== BACKEND HTTP POST ====================

bool sendEventToBackend(String& outStatus, String& outMessage) {
  if (WiFi.status() != WL_CONNECTED) {
    outStatus = "DENY"; outMessage = "No WiFi"; return false;
  }

  File file = SPIFFS.open(IMAGE_PATH, FILE_READ);
  if (!file) {
    outStatus = "DENY"; outMessage = "No image file"; return false;
  }

  size_t   fileSize = file.size();
  uint8_t* buf      = (uint8_t*)malloc(fileSize);
  if (!buf) {
    file.close();
    outStatus = "DENY"; outMessage = "Out of memory"; return false;
  }
  file.read(buf, fileSize);
  file.close();

  String boundary = "ESP32ParkBoundary";
  String partHead = "--" + boundary + "\r\n"
                    "Content-Disposition: form-data; name=\"image\"; filename=\"capture.jpg\"\r\n"
                    "Content-Type: image/jpeg\r\n\r\n";
  String partTail = "\r\n--" + boundary + "--\r\n";
  int    totalLen = partHead.length() + fileSize + partTail.length();

  HTTPClient http;
  http.begin(BACKEND_EVENT_URL);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);

  // Build full body in memory (images are small enough on PSRAM boards)
  uint8_t* body = (uint8_t*)malloc(totalLen);
  if (!body) {
    free(buf);
    outStatus = "DENY"; outMessage = "Body alloc failed"; return false;
  }

  int offset = 0;
  memcpy(body + offset, partHead.c_str(), partHead.length()); offset += partHead.length();
  memcpy(body + offset, buf, fileSize);                        offset += fileSize;
  memcpy(body + offset, partTail.c_str(), partTail.length());

  free(buf);

  int httpCode = http.POST(body, totalLen);
  free(body);

  if (httpCode <= 0) {
    Serial.printf("[HTTP] Connection error: %s\n", http.errorToString(httpCode).c_str());
    http.end();
    outStatus = "DENY"; outMessage = "Connection failed"; return false;
  }

  String response = http.getString();
  http.end();
  Serial.println("[HTTP] " + String(httpCode) + " — " + response);

  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, response) != DeserializationError::Ok) {
    outStatus = "DENY"; outMessage = "Invalid JSON response"; return false;
  }

  outStatus  = doc["status"].as<String>();
  outMessage = doc["message"].as<String>();

  return (outStatus == "ALLOW");
}

// ==================== CAMERA ====================

bool initCamera() {
  camera_config_t cfg;
  cfg.ledc_channel = LEDC_CHANNEL_0; cfg.ledc_timer = LEDC_TIMER_0;
  cfg.pin_d0 = Y2_GPIO_NUM; cfg.pin_d1 = Y3_GPIO_NUM;
  cfg.pin_d2 = Y4_GPIO_NUM; cfg.pin_d3 = Y5_GPIO_NUM;
  cfg.pin_d4 = Y6_GPIO_NUM; cfg.pin_d5 = Y7_GPIO_NUM;
  cfg.pin_d6 = Y8_GPIO_NUM; cfg.pin_d7 = Y9_GPIO_NUM;
  cfg.pin_xclk     = XCLK_GPIO_NUM;  cfg.pin_pclk  = PCLK_GPIO_NUM;
  cfg.pin_vsync    = VSYNC_GPIO_NUM; cfg.pin_href  = HREF_GPIO_NUM;
  cfg.pin_sscb_sda = SIOD_GPIO_NUM;  cfg.pin_sscb_scl = SIOC_GPIO_NUM;
  cfg.pin_pwdn     = PWDN_GPIO_NUM;  cfg.pin_reset = RESET_GPIO_NUM;
  cfg.xclk_freq_hz = 20000000;
  cfg.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    cfg.frame_size = FRAMESIZE_UXGA; cfg.jpeg_quality = 10; cfg.fb_count = 2;
    Serial.println("[CAM] PSRAM detected — high quality");
  } else {
    cfg.frame_size = FRAMESIZE_SVGA; cfg.jpeg_quality = 12; cfg.fb_count = 1;
    Serial.println("[CAM] No PSRAM — standard quality");
  }

  if (esp_camera_init(&cfg) != ESP_OK) return false;

  sensor_t* s = esp_camera_sensor_get();
  if (s) {
    s->set_whitebal(s, 1);
    s->set_awb_gain(s, 1);
    s->set_exposure_ctrl(s, 1);
    s->set_gain_ctrl(s, 1);
    s->set_brightness(s, 1);  // Slightly brighter for plate reads
  }
  return true;
}

bool captureImage() {
  if (!cameraReady) return false;
  if (lastFrame) { esp_camera_fb_return(lastFrame); lastFrame = NULL; }

  // Discard stale buffered frame
  camera_fb_t* stale = esp_camera_fb_get();
  if (stale) esp_camera_fb_return(stale);
  delay(150);

  lastFrame = esp_camera_fb_get();
  if (!lastFrame) { Serial.println("[CAM] fb_get failed"); return false; }

  Serial.printf("[CAM] %dx%d — %d bytes\n", lastFrame->width, lastFrame->height, lastFrame->len);

  File f = SPIFFS.open(IMAGE_PATH, FILE_WRITE);
  if (!f) { Serial.println("[CAM] SPIFFS write failed"); return false; }
  f.write(lastFrame->buf, lastFrame->len);
  f.close();
  return true;
}

// ==================== IR SENSOR ====================

bool readIR() {
  int hits = 0;
  for (int i = 0; i < IR_SAMPLES; i++) {
    if (digitalRead(IR_SENSOR_PIN) == IR_ACTIVE_STATE) hits++;
    delay(IR_DEBOUNCE_MS / IR_SAMPLES);
  }
  return hits >= (IR_SAMPLES / 2 + 1);
}

// ==================== SERVO ====================

void setGate(bool open) {
  int angle  = open ? GATE_OPEN_ANGLE : GATE_CLOSE_ANGLE;
  int pulse  = map(angle, 0, 180, SERVO_MIN_US, SERVO_MAX_US);
  int duty   = (pulse * 65535) / 20000;
  ledcWrite(SERVO_CHANNEL, duty);
  delay(500);
  gateOpen = open;
  if (open) gateOpenedMs = millis();
  Serial.printf("[SERVO] Gate %s (%d°)\n", open ? "OPEN" : "CLOSED", angle);
}

// ==================== WIFI ====================

void connectWiFi() {
  Serial.print("[WiFi] Connecting");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 20 && WiFi.status() != WL_CONNECTED; i++) {
    delay(500); Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("[WiFi] IP: " + WiFi.localIP().toString());
  } else {
    Serial.println("[WiFi] Failed — continuing offline");
  }
}

// ==================== WEB SERVER ====================

void handleRoot() {
  String html =
    "<!DOCTYPE html><html><head>"
    "<meta name='viewport' content='width=device-width,initial-scale=1'>"
    "<title>ESP32-CAM Parking</title>"
    "<style>"
    "body{font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;text-align:center;padding:20px}"
    "h2{color:#4ade80;margin-bottom:4px}"
    ".badge{display:inline-block;padding:4px 14px;border-radius:20px;font-weight:bold;margin:4px}"
    ".green{background:#166534;color:#4ade80}.red{background:#7f1d1d;color:#f87171}"
    "img{max-width:95%;border:2px solid #4ade80;border-radius:8px;margin:16px 0}"
    "button{padding:10px 22px;margin:6px;font-size:1em;border:none;border-radius:6px;cursor:pointer;font-weight:bold}"
    ".btn-g{background:#4ade80;color:#000}.btn-r{background:#f87171;color:#000}"
    "</style></head><body>"
    "<h2>ESP32-CAM Smart Parking</h2>";

#if MODE == MODE_ENTRY
  html += "<p><span class='badge green'>ENTRY GATE</span></p>";
#else
  html += "<p><span class='badge green'>EXIT GATE</span></p>";
#endif

  html += "<p>Gate: <span class='badge " + String(gateOpen ? "green'>OPEN" : "red'>CLOSED") + "</span></p>";
  html += "<p>Vehicle: <span class='badge " + String(vehiclePresent ? "green'>PRESENT" : "red'>ABSENT") + "</span></p>";
  html += "<img src='/capture' id='feed'>";
  html +=
    "<p>"
    "<a href='/gate/open'><button class='btn-g'>Force Open</button></a>"
    "<a href='/gate/close'><button class='btn-r'>Force Close</button></a>"
    "</p>"
    "<script>setInterval(()=>{"
    "  document.getElementById('feed').src='/capture?t='+Date.now();"
    "},3000);</script>"
    "</body></html>";

  server.send(200, "text/html", html);
}

void handleCapture() {
  if (lastFrame) {
    server.send_P(200, "image/jpeg", (const char*)lastFrame->buf, lastFrame->len);
    return;
  }
  File f = SPIFFS.open(IMAGE_PATH, FILE_READ);
  if (!f) { server.send(404, "text/plain", "No image available"); return; }
  server.streamFile(f, "image/jpeg");
  f.close();
}
