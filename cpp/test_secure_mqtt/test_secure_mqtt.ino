#include "IoT26Client.h" // Make sure this is in your libraries folder or the sketch folder
#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>

// ── WiFi Configuration ─────────────────────────────────────────────
const char *ssid = "Reaksmey";
const char *password = "015427757";

// ── IoT26 Configuration ────────────────────────────────────────────
// Replace these with your actual Device ID and Token from the dashboard
const char *DEVICE_ID = "ae27a883-5fa2-423d-b039-0516cc2efa62";
const char *DEVICE_TOKEN =
    "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9."
    "eyJkZXZpY2VfaWQiOiJhZTI3YTg4My01ZmEyLTQyM2QtYjAzOS0wNTE2Y2MyZWZhNjIiLCJvcm"
    "dfaWQiOiJvcmdfM0QxVkdkVHlLYUZDdXROcFNSSDhtQ0U0d1g3IiwicHJvdG9jb2xfdHlwZSI6"
    "Im1vZGJ1c190Y3AiLCJwcm90b2NvbHMiOm51bGwsInN1YiI6ImFlMjdhODgzLTVmYTItNDIzZC"
    "1iMDM5LTA1MTZjYzJlZmE2MiIsImV4cCI6MTgxNDcwMDEyMiwiaWF0IjoxNzgzMTY0MTIyfQ."
    "NA-Wek8JrYLMt0rHBSEtKFpkee6k95dxTfyuVo8kgAuzNrpoV6DnKtzBPXHX0RHCGIEjDViV_"
    "le-rYFtJhB2BQ";

// The production server address and MQTTS port
const char *MQTT_BROKER = "<iot26_url>";
const uint16_t MQTT_PORT = 8883;

// 1. We must use WiFiClientSecure to connect to port 8883 (TLS)
WiFiClientSecure secureClient;

// 2. Initialize the IoT26 Client
IoT26Client iot26(DEVICE_ID, DEVICE_TOKEN, MQTT_BROKER, MQTT_PORT);

// Timer for sending test telemetry
unsigned long lastPublish = 0;
const long publishInterval = 5000; // publish every 5 seconds
uint8_t RELAY_I2C_ADDR = 0x20;
// Dynamic Sensor Configuration extracted from JSON
String buttonSensorId = "";
int buttonPin = -1;
String valveSensorId = ""; // Dynamically populated from backend config

// ── Fetch Gateway Config via REST API ────────────────────────────
void fetchDeviceConfig() {
  HTTPClient http;
  String url =
      "https://<iot26_url>/v1/devices/" + String(DEVICE_ID) + "/config";

  // Note: We pass secureClient to use the setInsecure() configuration
  http.begin(secureClient, url);
  http.addHeader("Authorization", "Bearer " + String(DEVICE_TOKEN));

  Serial.println("\nFetching config from IoT26 API...");
  int httpCode = http.GET();

  if (httpCode == HTTP_CODE_OK) {
    String payload = http.getString();

    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, payload);

    if (!error) {
      Serial.println("Config parsed successfully!");

      const char *gwInterfaces = doc["connection_props"]["gateway_interfaces"];
      // parsing config
      JsonObject cp = doc["connection_props"];
      if (!cp["i2c_relay_i2c_address"].isNull()) {
        if (cp["i2c_relay_i2c_address"].is<const char *>()) {
          RELAY_I2C_ADDR = (uint8_t)strtol(
              cp["i2c_relay_i2c_address"].as<const char *>(), NULL, 16);
        } else {
          RELAY_I2C_ADDR = cp["i2c_relay_i2c_address"].as<uint8_t>();
        }
      } else {
        RELAY_I2C_ADDR = 0x20;
      }
      // parsing sensors
      JsonArray sensors = doc["sensors"];
      for (JsonObject sensor : sensors) {
        const char *sensorId = sensor["sensor_id"];
        const char *name = sensor["name"];

        JsonObject channelProps = sensor["channel_props"];

        Serial.printf(" - Sensor: %s (ID: %s)\n", name ? name : "Unknown",
                      sensorId);

        // Check if this sensor is our Button
        if (String(name).equalsIgnoreCase("button") ||
            String(name).equalsIgnoreCase("push button")) {
          buttonSensorId = sensorId;
          buttonPin =
              channelProps["pin"] | 4; // Default to GPIO 4 if not provided
          pinMode(buttonPin, INPUT_PULLUP);
          Serial.printf("   -> Configured as Button on GPIO %d\n", buttonPin);
        } else if (String(name).equalsIgnoreCase("valve") ||
                   String(name).equalsIgnoreCase("relay") ||
                   String(name).equalsIgnoreCase("switch")) {
          valveSensorId = sensorId;
          Serial.printf("   -> Mapped Valve to sensor ID: %s\n", valveSensorId.c_str());
        } else {
          int slaveAddr = channelProps["slave_addr"] | 1;
          int modbusReg = channelProps["register"] | 0;
          Serial.printf("   -> Slave: %d, Register: %d\n", slaveAddr,
                        modbusReg);
        }
      }
    } else {
      Serial.printf("JSON parse failed: %s\n", error.c_str());
    }
  } else {
    Serial.printf("HTTP Request failed, error code: %d\n", httpCode);
  }

  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- IoT26 ESP32 Secure MQTT Test ---");

  // ── Connect to WiFi ────────────────────────────────────────────
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected.");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  // ── Configure TLS Security ─────────────────────────────────────
  // For testing, we skip verifying the server certificate.
  // In production, use secureClient.setCACert(root_ca);
  secureClient.setInsecure();

  // Fetch initial config via HTTPS
  fetchDeviceConfig();

  // ── Connect to IoT26 ───────────────────────────────────────────
  iot26.begin(secureClient);

  // Optional: Listen for downlink commands from the dashboard
  iot26.onCommand([](const JsonDocument &cmd) {
    const char *action = cmd["action"];
    Serial.print("Received command from dashboard: ");
    Serial.println(action);

    if (String(action) == "reload_config") {
      fetchDeviceConfig();
    } else if (String(action) == "write_register") {
      int slave = cmd["slave"] | 1;
      int reg = cmd["register"] | 0;
      int val = cmd["value"] | 0;
      Serial.printf("-> Modbus Write: Slave %d, Reg %d = %d\n", slave, reg,
                    val);
      // TODO: Execute physical modbus RTU write here

    } else if (String(action) == "read_register") {
      int slave = cmd["slave"] | 1;
      int reg = cmd["register"] | 0;
      int count = cmd["value"] | 1;
      Serial.printf("-> Modbus Read: Slave %d, Reg %d, Count %d\n", slave, reg,
                    count);
      // TODO: Execute physical modbus RTU read here and publish result back
    } else if (String(action) == "trigger_ota") {
      const char *url = cmd["url"];
      Serial.printf("-> Trigger OTA Update from: %s\n", url ? url : "unknown");
      // TODO: Start HTTPUpdate over WiFi
    } else if (String(action) == "custom") {
      JsonObjectConst custom = cmd["custom"];

      // Parse Smart Controls
      if (!custom["valve"].isNull()) {
        int state = custom["valve"];
        Serial.printf("-> Toggle Switch/Valve: %s\n", state ? "ON" : "OFF");
        // digitalWrite(RELAY_PIN, state ? HIGH : LOW);
        
        // PUBLISH UPLINK: Report the new state back to the backend
        // This makes sure the Dashboard UI widget instantly updates its visual state
        if (valveSensorId != "") {
          IoT26Reading uplink[] = {{valveSensorId.c_str(), (float)state, "state"}};
          iot26.publishReadings(uplink, 1);
        } else {
          Serial.println("-> Cannot publish valve uplink: No sensor mapped from config!");
        }
      }
      if (!custom["dimmer"].isNull()) {
        int level = custom["dimmer"];
        Serial.printf("-> Dimmer Level: %d%%\n", level);
        // analogWrite(PWM_PIN, map(level, 0, 100, 0, 255));
      }
      if (!custom["color"].isNull()) {
        const char *hex = custom["color"];
        Serial.printf("-> Set RGB Color: %s\n", hex);
      }
      if (!custom["lock"].isNull()) {
        const char *lockState = custom["lock"];
        Serial.printf("-> Electronic Lock: %s\n", lockState);
      }
      if (!custom["ir_blaster"].isNull()) {
        const char *code = custom["ir_blaster"];
        Serial.printf("-> Blast IR Code: %s\n", code);
      }
      if (!custom["ptz"].isNull()) {
        int pan = custom["ptz"]["pan"] | 0;
        int tilt = custom["ptz"]["tilt"] | 0;
        Serial.printf("-> PTZ Camera Move to X:%d, Y:%d\n", pan, tilt);
      }
      if (!custom["display"].isNull()) {
        const char *text = custom["display"];
        Serial.printf("-> LCD Display Text: %s\n", text);
      }
      if (!custom["calibrate"].isNull()) {
        const char *type = custom["calibrate"]["type"];
        int val = custom["calibrate"]["value"] | 0;
        Serial.printf("-> Sensor Calibration [%s]: %d\n",
                      type ? type : "unknown", val);
      }
    }
  });
}

void loop() {
  // This keeps the MQTT connection alive and handles incoming messages
  iot26.loop();

  // ── Hardware Button Polling & Debouncing ───────────────────────
  static int lastButtonState = HIGH;
  static unsigned long lastDebounceTime = 0;
  const unsigned long debounceDelay = 50;

  // Only poll if the button was successfully configured via the JSON API
  if (buttonPin != -1 && iot26.isConnected()) {
    int reading = digitalRead(buttonPin);

    // Reset debounce timer if state changed (due to noise or press)
    if (reading != lastButtonState) {
      lastDebounceTime = millis();
    }

    if ((millis() - lastDebounceTime) > debounceDelay) {
      static int buttonState = HIGH;

      // If the state has stabilized to a new state
      if (reading != buttonState) {
        buttonState = reading;

        // Button Pressed (Assuming INPUT_PULLUP, LOW = pressed)
        if (buttonState == LOW) {
          Serial.println(
              "\n[HARDWARE] Button Pressed! Publishing telemetry...");

          // Use the dynamic sensor ID fetched from the API
          IoT26Reading readings[] = {{buttonSensorId.c_str(), 1.0f, "click"}};

          bool success = iot26.publishReadings(readings, 1);
          if (success) {
            Serial.println(" -> Publish successful!");
          } else {
            Serial.println(" -> Publish failed.");
          }
        }
      }
    }
    lastButtonState = reading;
  }
}
