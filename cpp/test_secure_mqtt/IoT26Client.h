/**
 * @file IoT26Client.h
 * @brief Arduino/ESP32 client library for the IoT26 IoT platform.
 *
 * Publishes sensor readings to IoT26 and receives downlink commands
 * over MQTT. Works with any Arduino-compatible WiFiClient or WiFiClientSecure.
 *
 * Wire protocol:
 *   Publish  → devices/{device_id}/ingest   QoS 1
 *   Subscribe← devices/{device_id}/commands QoS 1
 *
 * Payload format (ingest):
 *   {
 *     "token": "<device_token>",
 *     "readings": [
 *       {"sensor_id": "abc123", "value": 23.5, "unit": "°C"},
 *       ...
 *     ]
 *   }
 *
 * Usage:
 *   #include <WiFi.h>
 *   #include "IoT26Client.h"
 *
 *   WiFiClient wifiClient;
 *   IoT26Client iot26("device-uuid", "eyJhbGci...", "your-broker.com");
 *
 *   void setup() {
 *     WiFi.begin(SSID, PASSWORD);
 *     while (WiFi.status() != WL_CONNECTED) delay(500);
 *     iot26.begin(wifiClient);
 *     iot26.onCommand([](const JsonDocument& cmd) {
 *       Serial.println(cmd["action"].as<const char*>());
 *     });
 *   }
 *
 *   void loop() {
 *     IoT26Reading readings[] = {
 *       {"temp_sensor_id",     25.3f, "°C", nullptr},
 *       {"humidity_sensor_id", 61.0f, "%",  "{\"room\": \"A1\"}"},
 *     };
 *     iot26.publishReadings(readings, 2);
 *     iot26.loop();
 *     delay(10000);
 *   }
 */

#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <functional>

// ── Data structures ───────────────────────────────────────────────────────────

/**
 * @brief One sensor reading to publish.
 */
struct IoT26Reading {
    const char* sensor_id;    ///< UUID or name matching IoT26 sensor config
    float       value;        ///< Scaled engineering value
    const char* unit;         ///< Unit string, e.g. "°C", "%RH", "Pa"
    const char* metadataJson; ///< Optional JSON metadata (pass nullptr or "" to omit)
};

// ── Client class ──────────────────────────────────────────────────────────────

class IoT26Client {
public:
    /**
     * @brief Callback type for downlink commands.
     * The JsonDocument contains the full command object, e.g.:
     *   { "action": "reload_config" }
     *   { "action": "set_poll_interval", "interval": 30 }
     */
    using CommandCallback = std::function<void(const JsonDocument&)>;

    /**
     * @brief Construct the client (does NOT open any connection).
     *
     * @param deviceId    Device UUID from IoT26 dashboard
     * @param deviceToken Device JWT / API token from IoT26 dashboard
     * @param mqttBroker  MQTT broker hostname or IP
     * @param mqttPort    MQTT broker port (1883 plain, 8883 TLS)
     */
    IoT26Client(const char* deviceId,
                const char* deviceToken,
                const char* mqttBroker,
                uint16_t    mqttPort = 1883);

    /**
     * @brief Attach a network client and initialise PubSubClient.
     * Call this AFTER WiFi/Ethernet is connected.
     *
     * @param netClient  A WiFiClient or WiFiClientSecure instance
     */
    void begin(Client& netClient);

    /**
     * @brief Connect (or reconnect) to the MQTT broker.
     *
     * @return true  Successfully connected
     * @return false Connection failed
     */
    bool connect();

    /**
     * @brief Publish a batch of sensor readings.
     *
     * Builds the JSON payload and publishes to devices/{id}/ingest at QoS 1.
     *
     * @param readings  Array of IoT26Reading structs
     * @param count     Number of elements in the array
     * @return true     Published successfully
     * @return false    Not connected or publish failed
     */
    bool publishReadings(const IoT26Reading* readings, size_t count);

    /**
     * @brief Register a callback for downlink commands from IoT26.
     *
     * The callback fires when the broker delivers a message on
     * devices/{id}/commands. Only one callback is supported at a time.
     *
     * @param cb  Lambda or function pointer matching CommandCallback
     */
    void onCommand(CommandCallback cb);

    /**
     * @brief Must be called in the Arduino loop() function.
     *
     * Maintains the MQTT connection and processes incoming messages.
     * Reconnects automatically on disconnection.
     */
    void loop();

    /** @brief Returns true if currently connected to the broker. */
    bool isConnected();

    /**
     * @brief Set the MQTT keep-alive interval in seconds (default: 60).
     * Must be called before begin().
     */
    void setKeepAlive(uint16_t seconds);

    /**
     * @brief Set the reconnect cooldown in milliseconds (default: 5000).
     * Prevents hammering the broker when offline.
     */
    void setReconnectInterval(unsigned long ms);

private:
    const char*  _deviceId;
    const char*  _deviceToken;
    const char*  _mqttBroker;
    uint16_t     _mqttPort;
    uint16_t     _keepAlive        = 60;
    unsigned long _reconnectInterval = 5000UL;
    unsigned long _lastReconnectAttempt = 0;

    PubSubClient   _mqtt;
    CommandCallback _cmdCb;

    char _ingestTopic[96];    // "devices/<id>/ingest"
    char _commandTopic[96];   // "devices/<id>/commands"
    char _clientId[48];       // "iot26-<first-8-chars-of-id>"

    /**
     * @brief Internal MQTT message handler — parses JSON and fires _cmdCb.
     */
    void _onMessage(char* topic, byte* payload, unsigned int len);

    /**
     * @brief Attempt one reconnection cycle.
     * @return true if now connected
     */
    bool _reconnect();
};
