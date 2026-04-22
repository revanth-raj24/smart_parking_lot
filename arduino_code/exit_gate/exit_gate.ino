/*
 * Smart Parking System — EXIT GATE Firmware v3.0
 * Hardware : ESP32-CAM (AI-Thinker) + IR Sensor + SG90 Servo
 * Strategy : Event-driven. Camera is OFF until IR fires. No streaming.
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
#include <ArduinoJson.h>

// ── User Config ───────────────────────────────────────────────────────────────
#define WIFI_SSID      "Projects"
#define WIFI_PASSWORD  "12345678@"

// Replace 192.168.x.x with your FastAPI server's local IP after running backend
#define BACKEND_URL    "http://192.168.1.16:8000/api/esp32/exit-event"

// ── Pin Definitions ───────────────────────────────────────────────────────────
#define IR_SENSOR_PIN   14   // Safe GPIO on AI-Thinker (not shared with camera)
#define SERVO_PWM_PIN   15   // Safe GPIO for PWM output
#define LED_FLASH_PIN    4   // Onboard flash — kept LOW always to reduce heat

// ── AI-Thinker Camera Pins (fixed layout — do not change) ────────────────────
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
#define GATE_OPEN_ANGLE    0
#define GATE_CLOSE_ANGLE  90
#define GATE_OPEN_MS    5000   // Auto-close timeout (ms)
#define SERVO_MIN_US     500
#define SERVO_MAX_US    2500
#define SERVO_FREQ        50   // Standard servo: 50 Hz

// ── IR Sensor ─────────────────────────────────────────────────────────────────
#define IR_ACTIVE_STATE  LOW   // Most IR modules pull LOW when blocked
#define IR_SAMPLES         3   // Majority-vote across 3 reads
#define IR_DEBOUNCE_MS    60   // Total debounce window (spread across samples)
#define ZONE_CLEAR_MS   1500   // Time sensor must be clear before resetting

// ── Network ───────────────────────────────────────────────────────────────────
#define HTTP_TIMEOUT_MS  8000
#define HTTP_RETRY_MAX       2   // Retry once on connection failure

// ── State ─────────────────────────────────────────────────────────────────────
static bool          vehiclePresent = false;
static bool          gateOpen       = false;
static unsigned long lastDetectMs   = 0;
static unsigned long gateOpenedMs   = 0;

// ── Prototypes ────────────────────────────────────────────────────────────────
void connectWiFi();
bool initCamera();
bool captureAndSend(String& outStatus);
bool postImage(const uint8_t* buf, size_t len, String& outStatus);
void controlGate(bool open);
bool readIR();

// =============================================================================
// SETUP
// =============================================================================

void setup() {
  // Brownout disabled: camera init causes a brief current spike that triggers
  // the brownout detector on boards without adequate decoupling.
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(115200);
  Serial.println("\n=== EXIT GATE v3.0 — Event-Driven ===");

  pinMode(LED_FLASH_PIN, OUTPUT);
  digitalWrite(LED_FLASH_PIN, LOW);  // Flash OFF — single biggest heat source

  pinMode(IR_SENSOR_PIN, INPUT_PULLUP);

  // Servo: attach LEDC channel, close gate on boot
  if (!ledcAttach(SERVO_PWM_PIN, SERVO_FREQ, 16)) {
    Serial.println("[ERROR] LEDC attach failed — check SERVO_PWM_PIN");
  }
  controlGate(false);

  connectWiFi();

  Serial.println("=== System ready — camera OFF, monitoring IR ===");
  Serial.printf("[PINS] IR: GPIO%d | Servo: GPIO%d\n", IR_SENSOR_PIN, SERVO_PWM_PIN);
}

// =============================================================================
// MAIN LOOP
// =============================================================================

void loop() {
  // ── Auto-close gate after timeout ────────────────────────────────────────
  if (gateOpen && (millis() - gateOpenedMs >= GATE_OPEN_MS)) {
    controlGate(false);
    Serial.println("[GATE] Auto-closed");
  }

  bool detected = readIR();

  // ── Rising edge: new vehicle arrives ─────────────────────────────────────
  if (detected && !vehiclePresent) {
    vehiclePresent = true;
    lastDetectMs   = millis();

    Serial.println("──────────────────────────────────");
    Serial.println("[IR] TRIGGERED — vehicle detected at exit");

    String status;
    bool sent = captureAndSend(status);

    if (sent) {
      Serial.println("[BACKEND] Response: " + status);
      if (status == "ALLOW") {
        controlGate(true);
      } else {
        Serial.println("[GATE] DENIED by backend — unpaid/unregistered vehicle");
      }
    } else {
      Serial.println("[ERROR] Capture/send failed — gate stays closed");
    }
    Serial.println("──────────────────────────────────");
  }

  // ── Falling edge: vehicle leaves zone (debounced) ────────────────────────
  if (!detected && vehiclePresent && (millis() - lastDetectMs > ZONE_CLEAR_MS)) {
    vehiclePresent = false;
    Serial.println("[IR] Zone cleared — ready for next vehicle");
  }

  delay(100);  // 10 Hz poll; saves CPU and reduces heat vs tight loop
}

// =============================================================================
// CAPTURE + SEND
// Camera is initialized fresh per event and de-initialized after.
// This guarantees the sensor is cold (no accumulated heat) between events.
// =============================================================================

bool captureAndSend(String& outStatus) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Not connected — aborting");
    outStatus = "DENY";
    return false;
  }

  // Power camera on, configure, and init
  if (!initCamera()) {
    Serial.println("[CAM] Init failed");
    outStatus = "ERROR";
    return false;
  }

  // Discard first frame — sensor AEC (auto-exposure) needs one frame to settle
  camera_fb_t* stale = esp_camera_fb_get();
  if (stale) esp_camera_fb_return(stale);
  delay(60);  // ~1 frame at 10MHz XCLK; AEC locks in this window

  // Capture the real frame
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[CAM] Frame buffer get failed");
    esp_camera_deinit();
    outStatus = "ERROR";
    return false;
  }

  Serial.printf("[CAM] Captured %dx%d — %d bytes\n", fb->width, fb->height, fb->len);

  // POST with retry — network can have transient hiccups
  bool success = false;
  for (int attempt = 1; attempt <= HTTP_RETRY_MAX; attempt++) {
    Serial.printf("[HTTP] Attempt %d/%d\n", attempt, HTTP_RETRY_MAX);
    if (postImage(fb->buf, fb->len, outStatus)) {
      success = true;
      break;
    }
    if (attempt < HTTP_RETRY_MAX) delay(800);
  }

  esp_camera_fb_return(fb);

  // De-init camera: cuts ~150mA draw and resets thermal state for next event
  esp_camera_deinit();
  Serial.println("[CAM] De-initialized (thermal standby)");

  return success;
}

// =============================================================================
// HTTP POST — multipart/form-data directly from frame buffer
// No SPIFFS: avoids a flash write + read cycle (~10ms + wear saved per event)
// =============================================================================

bool postImage(const uint8_t* imgBuf, size_t imgLen, String& outStatus) {
  const String boundary = "SmartParkExit";
  const String partHead = "--" + boundary + "\r\n"
                          "Content-Disposition: form-data; name=\"image\"; filename=\"plate.jpg\"\r\n"
                          "Content-Type: image/jpeg\r\n\r\n";
  const String partTail = "\r\n--" + boundary + "--\r\n";

  size_t   totalLen = partHead.length() + imgLen + partTail.length();
  uint8_t* body     = (uint8_t*)malloc(totalLen);
  if (!body) {
    Serial.println("[HTTP] malloc failed — not enough heap");
    outStatus = "ERROR";
    return false;
  }

  // Assemble multipart body in one contiguous buffer
  size_t offset = 0;
  memcpy(body + offset, partHead.c_str(), partHead.length()); offset += partHead.length();
  memcpy(body + offset, imgBuf,           imgLen);            offset += imgLen;
  memcpy(body + offset, partTail.c_str(), partTail.length());

  HTTPClient http;
  http.begin(BACKEND_URL);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);

  int code = http.POST(body, totalLen);
  free(body);

  if (code <= 0) {
    Serial.printf("[HTTP] Connection error: %s\n", http.errorToString(code).c_str());
    http.end();
    outStatus = "ERROR";
    return false;
  }

  String response = http.getString();
  http.end();
  Serial.printf("[HTTP] %d — %s\n", code, response.c_str());

  StaticJsonDocument<256> doc;
  if (deserializeJson(doc, response) != DeserializationError::Ok) {
    Serial.println("[HTTP] JSON parse failed — raw: " + response);
    outStatus = "ERROR";
    return false;
  }

  outStatus = doc["status"].as<String>();
  return (outStatus == "ALLOW" || outStatus == "DENY");
}

// =============================================================================
// CAMERA INIT — Optimized settings
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

  // 10 MHz (default is 20 MHz): halves sensor clock, cuts ~30% heat,
  // still produces clean frames for license plate OCR at this resolution.
  cfg.xclk_freq_hz = 10000000;

  cfg.pixel_format = PIXFORMAT_JPEG;

  // CIF 352×288: ~40% smaller payload than VGA, still sufficient for
  // license plate OCR. Upgrade to FRAMESIZE_VGA if accuracy drops
  // in poor lighting.
  cfg.frame_size   = FRAMESIZE_CIF;

  // Quality 12: aggressive JPEG compression (~8–20 KB per frame).
  // Lower = smaller file = faster upload. Vision OCR handles Q12 well.
  // Go to 10 for faster upload, 15 if OCR misreads characters.
  cfg.jpeg_quality = 12;

  // 1 buffer + GRAB_LATEST: always get the most recent sensor frame,
  // minimal RAM footprint. fb_count=2 only needed for streaming.
  cfg.fb_count  = 1;
  cfg.grab_mode = CAMERA_GRAB_LATEST;

  if (esp_camera_init(&cfg) != ESP_OK) {
    return false;
  }

  // Disable DSP post-processing: sharpening + denoising add ~5 ms/frame
  // and extra heat with no benefit for OCR on still captures.
  sensor_t* s = esp_camera_sensor_get();
  if (s) {
    s->set_whitebal(s, 1);       // Auto white balance — needed for varied lighting
    s->set_awb_gain(s, 1);       // AWB gain on
    s->set_exposure_ctrl(s, 1);  // Auto exposure — essential for outdoor use
    s->set_aec2(s, 0);           // AEC DSP off — single frame, not video
    s->set_gain_ctrl(s, 1);      // Auto gain on
    s->set_brightness(s, 0);
    s->set_contrast(s, 0);
    s->set_saturation(s, 0);
    s->set_sharpness(s, 0);      // Sharpening DSP off — saves heat + time
    s->set_denoise(s, 0);        // Denoise DSP off
  }

  Serial.println("[CAM] Init OK — CIF 352×288, Q12, 10 MHz XCLK");
  return true;
}

// =============================================================================
// SERVO GATE CONTROL
// =============================================================================

void controlGate(bool open) {
  int angle = open ? GATE_OPEN_ANGLE : GATE_CLOSE_ANGLE;
  int pulse = map(angle, 0, 180, SERVO_MIN_US, SERVO_MAX_US);
  // LEDC 16-bit at 50 Hz: period = 20 ms = 20000 µs
  int duty  = (int)((long)pulse * 65535L / 20000L);

  ledcWrite(SERVO_PWM_PIN, duty);
  delay(350);  // Give servo time to reach position before state update

  gateOpen = open;
  if (open) gateOpenedMs = millis();

  Serial.printf("[SERVO] Gate %s (%d°)\n", open ? "OPEN" : "CLOSED", angle);
}

// =============================================================================
// IR SENSOR — Majority-vote debounce
// 3 reads within IR_DEBOUNCE_MS window; 2/3 must agree to report detected.
// Prevents single-noise spikes from triggering a capture event.
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

  // 15 dBm: adequate for home/office LAN, ~25% less power than 20 dBm max.
  // Reduces WiFi module heat without affecting throughput on a local network.
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
    Serial.println("[WiFi] FAILED — check SSID/password. System runs in offline mode.");
  }
}
