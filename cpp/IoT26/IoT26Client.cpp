/**
 * @file IoT26Client.cpp
 * @brief Arduino/ESP32 implementation of the IoT26 client library.
 */

#include "IoT26Client.h"

// ── Constructor ───────────────────────────────────────────────────────────────

IoT26Client::IoT26Client(const char* deviceId,
                         const char* deviceToken,
                         const char* mqttBroker,
                         uint16_t    mqttPort)
    : _deviceId(deviceId),
      _deviceToken(deviceToken),
      _mqttBroker(mqttBroker),
      _mqttPort(mqttPort)
{
    // Pre-build topic strings and client ID
    snprintf(_ingestTopic,  sizeof(_ingestTopic),  "devices/%s/ingest",   _deviceId);
    snprintf(_commandTopic, sizeof(_commandTopic),  "devices/%s/commands", _deviceId);
    snprintf(_clientId,     sizeof(_clientId),      "iot26-%.*s", 8, _deviceId);
}

// ── Public methods ────────────────────────────────────────────────────────────

void IoT26Client::begin(Client& netClient) {
    _mqtt.setClient(netClient);
    _mqtt.setServer(_mqttBroker, _mqttPort);
    _mqtt.setKeepAlive(_keepAlive);
    _mqtt.setBufferSize(1024);   // room for larger payloads

    // Bind internal message handler
    _mqtt.setCallback([this](char* topic, byte* payload, unsigned int len) {
        this->_onMessage(topic, payload, len);
    });
}

bool IoT26Client::connect() {
    if (_mqtt.connected()) return true;

    Serial.printf("[IoT26] Connecting to broker %s:%d …\n", _mqttBroker, _mqttPort);

    bool ok = _mqtt.connect(_clientId);
    if (ok) {
        Serial.printf("[IoT26] Connected. Subscribing to %s\n", _commandTopic);
        _mqtt.subscribe(_commandTopic, 1 /*QoS*/);
    } else {
        Serial.printf("[IoT26] Connect failed, rc=%d\n", _mqtt.state());
    }
    return ok;
}

bool IoT26Client::publishReadings(const IoT26Reading* readings, size_t count) {
    if (!_mqtt.connected()) {
        Serial.println("[IoT26] Not connected — cannot publish");
        return false;
    }
    if (count == 0) return true;

    // Build JSON: {"token":"…","readings":[…]}
    // Use dynamic sizing: base overhead ~30 bytes + ~80 bytes per reading
    const size_t capacity = JSON_OBJECT_SIZE(2)
                          + JSON_ARRAY_SIZE(count)
                          + count * JSON_OBJECT_SIZE(3)
                          + 512;  // string pool
    DynamicJsonDocument doc(capacity);

    doc["token"] = _deviceToken;
    JsonArray arr = doc.createNestedArray("readings");

    for (size_t i = 0; i < count; i++) {
        JsonObject r = arr.createNestedObject();
        r["sensor_id"] = readings[i].sensor_id;
        r["value"]     = readings[i].value;
        r["unit"]      = readings[i].unit;
    }

    // Serialise to a stack buffer (up to 1 KB) or heap
    String payload;
    serializeJson(doc, payload);

    Serial.print("[IoT26] Publish payload: ");
    Serial.println(payload);

    bool ok = _mqtt.publish(_ingestTopic, payload.c_str(), /*retain=*/false);
    if (ok) {
        Serial.printf("[IoT26] Published %u reading(s) → %s\n", (unsigned)count, _ingestTopic);
    } else {
        Serial.printf("[IoT26] Publish failed (rc=%d)\n", _mqtt.state());
    }
    return ok;
}

void IoT26Client::onCommand(CommandCallback cb) {
    _cmdCb = cb;
}

void IoT26Client::loop() {
    if (!_mqtt.connected()) {
        unsigned long now = millis();
        if (now - _lastReconnectAttempt >= _reconnectInterval) {
            _lastReconnectAttempt = now;
            _reconnect();
        }
    }
    _mqtt.loop();
}

bool IoT26Client::isConnected() {
    return _mqtt.connected();
}

void IoT26Client::setKeepAlive(uint16_t seconds) {
    _keepAlive = seconds;
}

void IoT26Client::setReconnectInterval(unsigned long ms) {
    _reconnectInterval = ms;
}

// ── Private methods ───────────────────────────────────────────────────────────

void IoT26Client::_onMessage(char* topic, byte* payload, unsigned int len) {
    // Guard — only handle commands topic
    if (strcmp(topic, _commandTopic) != 0) return;

    DynamicJsonDocument doc(512);
    DeserializationError err = deserializeJson(doc, payload, len);
    if (err) {
        Serial.printf("[IoT26] Command parse error: %s\n", err.c_str());
        return;
    }

    const char* action = doc["action"] | "<none>";
    Serial.printf("[IoT26] Command received: action=%s\n", action);

    if (_cmdCb) {
        _cmdCb(doc);
    }
}

bool IoT26Client::_reconnect() {
    Serial.println("[IoT26] Attempting reconnect …");
    return connect();
}
