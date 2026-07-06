/**
 * @file sensor_telemetry.ino
 * @brief IoT26 Normal Sensor Telemetry — ESP32 / Arduino SDK Example
 *
 * Shows how to publish continuous numeric sensor readings (flow, temperature,
 * humidity, pressure, water level, power, energy, CO₂, soil moisture, pH)
 * to IoT26. These are "display-only" sensors shown as charts, gauges, and
 * value tiles. No metadata_json is needed.
 *
 * Common sensor types:
 *   Flow rate     L/min  — water/gas flow meters (YF-S201, FS300A)
 *   Temperature   °C     — DS18B20, NTC thermistor, MAX6675 thermocouple
 *   Humidity      %RH    — DHT11, DHT22, SHT31
 *   Pressure      Pa     — BMP280, BMP388, MPX5500
 *   Water level   mm     — HC-SR04 ultrasonic, float switch
 *   Power         W      — PZEM-004T, CT clamp + ADS1115
 *   Energy        kWh    — cumulative energy (integrate power over time)
 *   CO₂ / gas     ppm    — MQ-135, SCD40, MH-Z19B
 *   Soil moisture %      — capacitive soil sensor (DFRobot, Graywater)
 *   pH            pH     — analog pH probe + ADC
 *
 * Required libraries (install via Arduino Library Manager):
 *   - PubSubClient  (knolleary)
 *   - ArduinoJson   (bblanchon)
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
const uint16_t MQTT_PORT = 8883;  // 8883 = TLS, 1883 = plain

// ── Sensor IDs — replace with UUIDs from your IoT26 sensor config ─────────────

const char* SENSOR_FLOW_RATE    = "flow-rate-sensor-uuid";     // L/min
const char* SENSOR_TEMPERATURE  = "temperature-sensor-uuid";   // °C
const char* SENSOR_HUMIDITY     = "humidity-sensor-uuid";      // %RH
const char* SENSOR_PRESSURE     = "pressure-sensor-uuid";      // Pa
const char* SENSOR_WATER_LEVEL  = "water-level-sensor-uuid";   // mm
const char* SENSOR_POWER        = "power-sensor-uuid";         // W
const char* SENSOR_ENERGY       = "energy-sensor-uuid";        // kWh
const char* SENSOR_CO2          = "co2-sensor-uuid";           // ppm
const char* SENSOR_SOIL         = "soil-moisture-sensor-uuid"; // %
const char* SENSOR_PH           = "ph-sensor-uuid";            // pH

const long PUBLISH_INTERVAL_MS = 5000; // publish every 5 seconds

// ── IoT26 client ──────────────────────────────────────────────────────────────

WiFiClientSecure secureClient;
IoT26Client      iot26(DEVICE_ID, DEVICE_TOKEN, MQTT_BROKER, MQTT_PORT);

unsigned long lastPublish    = 0;
float         totalEnergyKWh = 1234.5f; // starting cumulative value

// ── Simulated reads — replace each function with your real sensor driver ──────
// Example integrations shown in comments for common ESP32 libraries.

float readFlowRate() {
  // Real: use a pulse-counting ISR on a YF-S201 flow meter
  // float freq = pulseCount / (interval_s);
  // return freq / 7.5f;  // YF-S201: 7.5 pulses/s = 1 L/min
  return 12.5f + ((float)random(-30, 30) / 100.0f);
}

float readTemperature() {
  // Real: #include <OneWire.h> + <DallasTemperature.h>
  // sensors.requestTemperatures();
  // return sensors.getTempCByIndex(0);
  return 25.0f + 3.0f * sinf((float)millis() / 60000.0f);
}

float readHumidity() {
  // Real: #include <DHT.h>
  // return dht.readHumidity();
  return 60.0f + ((float)random(-15, 15) / 10.0f);
}

float readPressure() {
  // Real: #include <Adafruit_BMP280.h>
  // return bmp.readPressure();  // returns Pa
  return 101325.0f + ((float)random(-50, 50));
}

float readWaterLevel() {
  // Real: HC-SR04 ultrasonic distance → convert to mm
  // long duration = pulseIn(ECHO_PIN, HIGH);
  // return (duration / 2.0f) * 0.0343f * 10.0f;  // cm → mm
  return 750.0f + ((float)random(-50, 50) / 10.0f);
}

float readPower() {
  // Real: PZEM-004T via SoftwareSerial
  // return pzem.power();  // Watts
  return 250.0f + ((float)random(-100, 100) / 10.0f);
}

float readCO2() {
  // Real: SCD40 via I²C
  // uint16_t co2; float temp, hum;
  // scd4x.readMeasurement(co2, temp, hum);
  // return (float)co2;
  return 450.0f + (float)random(-20, 40);
}

float readSoilMoisture() {
  // Real: capacitive soil sensor → analogRead → map to 0–100%
  // int raw = analogRead(SOIL_PIN);  // 0–4095 on ESP32
  // return map(raw, WET_VALUE, DRY_VALUE, 100, 0);
  return 45.0f + ((float)random(-20, 20) / 10.0f);
}

float readPH() {
  // Real: analog pH probe → ADC → voltage → pH
  // float voltage = analogRead(PH_PIN) * 3.3f / 4095.0f;
  // return 7.0f + (2.5f - voltage) * 3.5f;  // calibration varies by probe
  return 7.2f + ((float)random(-5, 5) / 100.0f);
}

float incrementEnergy(float power, unsigned long intervalMs) {
  float deltaKWh = (power / 1000.0f) * (intervalMs / 3600000.0f);
  return totalEnergyKWh + deltaKWh;
}

// ── Arduino setup / loop ──────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- IoT26 Sensor Telemetry Example ---");

  // Connect WiFi
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

  // No onCommand handler needed for pure telemetry devices.
  // Add one if this device also receives control commands from a widget.

  Serial.printf("Setup complete — publishing every %ldms.\n", PUBLISH_INTERVAL_MS);
}

void loop() {
  // MUST be called every loop iteration — maintains MQTT connection
  iot26.loop();

  unsigned long now = millis();
  if (now - lastPublish < PUBLISH_INTERVAL_MS) return;

  unsigned long elapsed = now - lastPublish;
  lastPublish = now;

  // ── Read all sensors ───────────────────────────────────────────────────────
  float flow   = readFlowRate();
  float temp   = readTemperature();
  float hum    = readHumidity();
  float pres   = readPressure();
  float level  = readWaterLevel();
  float power  = readPower();
  float energy = incrementEnergy(power, elapsed);
  float co2    = readCO2();
  float soil   = readSoilMoisture();
  float ph     = readPH();

  totalEnergyKWh = energy;

  // ── Publish all readings in one batch ─────────────────────────────────────
  // No metadata_json needed for pure numeric sensors.
  // The dashboard displays them as charts, gauges, or value tiles.
  IoT26Reading readings[] = {
    {SENSOR_FLOW_RATE,   flow,   "L/min", nullptr},
    {SENSOR_TEMPERATURE, temp,   "°C",    nullptr},
    {SENSOR_HUMIDITY,    hum,    "%RH",   nullptr},
    {SENSOR_PRESSURE,    pres,   "Pa",    nullptr},
    {SENSOR_WATER_LEVEL, level,  "mm",    nullptr},
    {SENSOR_POWER,       power,  "W",     nullptr},
    {SENSOR_ENERGY,      energy, "kWh",   nullptr},
    {SENSOR_CO2,         co2,    "ppm",   nullptr},
    {SENSOR_SOIL,        soil,   "%",     nullptr},
    {SENSOR_PH,          ph,     "pH",    nullptr},
  };

  bool ok = iot26.publishReadings(readings, 10);

  Serial.printf(
    "↑ %s  flow=%.1f L/min  temp=%.1f°C  hum=%.0f%%  level=%.0fmm  "
    "power=%.0fW  energy=%.3fkWh  CO₂=%.0fppm  soil=%.0f%%  pH=%.2f\n",
    ok ? "OK" : "FAIL",
    flow, temp, hum, level, power, energy, co2, soil, ph
  );
}
