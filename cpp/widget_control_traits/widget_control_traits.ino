/**
 * @file widget_control_traits.ino
 * @brief IoT26 Widget Control Traits — ESP32 / Arduino SDK Example
 *
 * Demonstrates how to publish sensor readings with metadata_json to power
 * the IoT26 Widget Builder's UI control components on an ESP32.
 *
 * Widget UI Component → metadata_json field + values:
 *
 *   Toggle (Relay)  → {"mode": "on"} | {"mode": "off"}
 *   AC Mode         → {"mode": "cool"} | {"mode": "heat"} | {"mode": "off"}
 *   Door / Motor    → {"motor": "open"} | {"motor": "stop"} | {"motor": "close"}
 *   Brightness      → plain numeric value 0–100 (no metadata needed)
 *   Display Text    → {"display": "Hello World"}
 *
 * The widget reads metadata_json from the latest sensor reading and highlights
 * the matching button. State also persists across browser refreshes.
 *
 * Required libraries (install via Arduino Library Manager):
 *   - PubSubClient   (knolleary)
 *   - ArduinoJson    (bblanchon)
 *
 * Hardware: ESP32 (any variant)
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include "IoT26Client.h"   // Place IoT26Client.h + IoT26Client.cpp in sketch folder

// ── WiFi ──────────────────────────────────────────────────────────────────────

const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// ── IoT26 — replace with values from your IoT26 dashboard ─────────────────────

const char* DEVICE_ID    = "your-device-uuid";
const char* DEVICE_TOKEN = "your-device-jwt-token";
const char* MQTT_BROKER  = "your-iot26-broker.com";
const uint16_t MQTT_PORT = 8883;           // 8883 = TLS, 1883 = plain

// ── Sensor IDs — replace with UUIDs from your IoT26 sensor config ─────────────

const char* SENSOR_RELAY      = "relay-sensor-uuid";      // Toggle widget
const char* SENSOR_AC_MODE    = "ac-mode-sensor-uuid";    // AC Mode widget
const char* SENSOR_DOOR_MOTOR = "door-motor-sensor-uuid"; // Door widget
const char* SENSOR_BRIGHTNESS = "brightness-sensor-uuid"; // Slider widget
const char* SENSOR_DISPLAY    = "display-sensor-uuid";    // Display text widget

// ── Device state ──────────────────────────────────────────────────────────────

enum RelayState   { RELAY_OFF, RELAY_ON };
enum ACMode       { AC_OFF, AC_COOL, AC_HEAT };
enum MotorState   { MOTOR_CLOSE, MOTOR_STOP, MOTOR_OPEN };

RelayState  relayState  = RELAY_OFF;
ACMode      acMode      = AC_OFF;
MotorState  motorState  = MOTOR_CLOSE;
float       brightness  = 75.0f;
String      displayText = "Hello!";

// ── IoT26 client ──────────────────────────────────────────────────────────────

WiFiClientSecure secureClient;
IoT26Client      iot26(DEVICE_ID, DEVICE_TOKEN, MQTT_BROKER, MQTT_PORT);

unsigned long lastPublish = 0;
const long    PUBLISH_INTERVAL_MS = 30000;  // heartbeat every 30 s

// ── Helpers ───────────────────────────────────────────────────────────────────

// Build metadata_json strings for each trait.
// Uses a small stack buffer — safe for embedded.

String relayMetadata() {
  return relayState == RELAY_ON
    ? String("{\"mode\":\"on\"}")
    : String("{\"mode\":\"off\"}");
}

String acMetadata() {
  switch (acMode) {
    case AC_COOL:  return String("{\"mode\":\"cool\"}");
    case AC_HEAT:  return String("{\"mode\":\"heat\"}");
    default:       return String("{\"mode\":\"off\"}");
  }
}

String motorMetadata() {
  switch (motorState) {
    case MOTOR_OPEN:  return String("{\"motor\":\"open\"}");
    case MOTOR_STOP:  return String("{\"motor\":\"stop\"}");
    default:          return String("{\"motor\":\"close\"}");
  }
}

String displayMetadata() {
  // Escape quotes in the display text (simplified — keep text simple)
  return String("{\"display\":\"") + displayText + String("\"}");
}

// Push ALL current states to IoT26 in one batch.
void publishAllStates() {
  IoT26Reading readings[] = {
    // Relay: value=1 (on) or 0 (off) + metadata mode
    {
      SENSOR_RELAY,
      relayState == RELAY_ON ? 1.0f : 0.0f,
      "state",
      relayMetadata().c_str()
    },

    // AC Mode: metadata mode = "cool" | "heat" | "off"
    {
      SENSOR_AC_MODE,
      1.0f,
      "state",
      acMetadata().c_str()
    },

    // Door / Motor: metadata motor = "open" | "stop" | "close"
    {
      SENSOR_DOOR_MOTOR,
      1.0f,
      "state",
      motorMetadata().c_str()
    },

    // Brightness: plain numeric value — slider widget reads value directly
    {
      SENSOR_BRIGHTNESS,
      brightness,
      "%",
      nullptr   // no metadata needed for slider
    },

    // Display: metadata display = "any text"
    {
      SENSOR_DISPLAY,
      1.0f,
      "text",
      displayMetadata().c_str()
    },
  };

  bool ok = iot26.publishReadings(readings, 5);
  Serial.printf("↑ publishAllStates → %s  relay=%s ac=%s door=%s brightness=%.0f\n",
    ok ? "OK" : "FAIL",
    relayState == RELAY_ON ? "on" : "off",
    acMode == AC_COOL ? "cool" : acMode == AC_HEAT ? "heat" : "off",
    motorState == MOTOR_OPEN ? "open" : motorState == MOTOR_STOP ? "stop" : "close",
    brightness
  );
}

// ── Command handler ───────────────────────────────────────────────────────────

void handleCommand(const JsonDocument& cmd) {
  const char* action = cmd["action"];
  Serial.printf("↓ Command: action=%s\n", action ? action : "(null)");

  if (String(action) != "custom") {
    Serial.println("  Ignoring non-custom action");
    return;
  }

  JsonObjectConst custom = cmd["custom"];

  // ── Relay ──────────────────────────────────────────────────────────────────
  if (!custom["relay"].isNull()) {
    relayState = custom["relay"].as<bool>() ? RELAY_ON : RELAY_OFF;
    const char* st = relayState == RELAY_ON ? "on" : "off";
    Serial.printf("  Relay → %s\n", st);
    String meta = relayMetadata();
    IoT26Reading r[] = {{SENSOR_RELAY, relayState == RELAY_ON ? 1.0f : 0.0f, "state", meta.c_str()}};
    iot26.publishReadings(r, 1);
  }

  // ── AC Mode ────────────────────────────────────────────────────────────────
  if (!custom["ac_mode"].isNull()) {
    String mode = custom["ac_mode"].as<String>();
    if (mode == "cool")       acMode = AC_COOL;
    else if (mode == "heat")  acMode = AC_HEAT;
    else                      acMode = AC_OFF;
    Serial.printf("  AC mode → %s\n", mode.c_str());
    String meta = acMetadata();
    IoT26Reading r[] = {{SENSOR_AC_MODE, 1.0f, "state", meta.c_str()}};
    iot26.publishReadings(r, 1);
  }

  // ── Door / Motor ───────────────────────────────────────────────────────────
  if (!custom["motor"].isNull()) {
    String pos = custom["motor"].as<String>();
    if (pos == "open")        motorState = MOTOR_OPEN;
    else if (pos == "stop")   motorState = MOTOR_STOP;
    else                      motorState = MOTOR_CLOSE;
    Serial.printf("  Door motor → %s\n", pos.c_str());
    String meta = motorMetadata();
    IoT26Reading r[] = {{SENSOR_DOOR_MOTOR, 1.0f, "state", meta.c_str()}};
    iot26.publishReadings(r, 1);
  }

  // ── Brightness slider ──────────────────────────────────────────────────────
  if (!custom["brightness"].isNull()) {
    brightness = custom["brightness"].as<float>();
    Serial.printf("  Brightness → %.0f%%\n", brightness);
    IoT26Reading r[] = {{SENSOR_BRIGHTNESS, brightness, "%", nullptr}};
    iot26.publishReadings(r, 1);
  }

  // ── Display text ───────────────────────────────────────────────────────────
  if (!custom["display"].isNull()) {
    displayText = custom["display"].as<String>();
    Serial.printf("  Display → \"%s\"\n", displayText.c_str());
    String meta = displayMetadata();
    IoT26Reading r[] = {{SENSOR_DISPLAY, 1.0f, "text", meta.c_str()}};
    iot26.publishReadings(r, 1);
  }
}

// ── Arduino setup / loop ──────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- IoT26 Widget Control Traits Example ---");

  // Connect to WiFi
  Serial.printf("Connecting to WiFi: %s\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\nWiFi connected. IP: %s\n", WiFi.localIP().toString().c_str());

  // Skip TLS cert verification for development.
  // In production use: secureClient.setCACert(root_ca);
  secureClient.setInsecure();

  iot26.begin(secureClient);
  iot26.onCommand(handleCommand);

  // Push initial state on boot so the widget immediately shows correct buttons
  Serial.println("Publishing initial device state...");
  publishAllStates();

  Serial.println("Setup complete — ready for commands from the widget.");
}

void loop() {
  // MUST be called every loop iteration — maintains MQTT + handles messages
  iot26.loop();

  // Heartbeat: re-publish current state every PUBLISH_INTERVAL_MS
  unsigned long now = millis();
  if (now - lastPublish >= PUBLISH_INTERVAL_MS) {
    lastPublish = now;
    publishAllStates();
  }
}
