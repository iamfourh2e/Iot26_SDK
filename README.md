# IoT26 SDK

Client libraries for connecting **any device or service** to the
[IoT26](https://<iot26_url>) IoT platform over MQTT. Note: Please Replace
<iot26_url> with the actual url All SDKs share the same wire protocol — swap
languages without changing your backend pipeline.

---

## Table of Contents

1. [Platform Endpoints](#platform-endpoints)
2. [Wire Protocol](#wire-protocol)
3. [Authentication](#authentication)
4. [SDK Quickstarts](#sdk-quickstarts)
   - [C++ / Arduino / ESP32](#c--arduino--esp32)
   - [Go](#go)
   - [Node.js](#nodejs)
   - [Dart / Flutter](#dart--flutter)
5. [TLS / MQTTS (Production)](#tls--mqtts-production)
6. [Publish Loop Pattern](#publish-loop-pattern)
7. [Downlink Commands](#downlink-commands)
8. [Troubleshooting](#troubleshooting)

---

## Platform Endpoints

> Use these values when connecting to the **production** IoT26 platform.

| Protocol                  | Host                  | Port     | Use case                               |
| ------------------------- | --------------------- | -------- | -------------------------------------- |
| **MQTTS** _(recommended)_ | `<iot26_url>`         | **8883** | All production devices — encrypted TLS |
| MQTT (plain)              | `<iot26_url>`         | **1883** | Local / dev only — **not encrypted**   |
| REST API                  | `https://<iot26_url>` | 443      | Device registration, config fetch      |

> **Always use port 8883 (MQTTS) in production.** Port 1883 is unencrypted and
> should only be used during local development.

---

## Wire Protocol

Every SDK speaks the same JSON-over-MQTT protocol.

### Publish readings → `devices/{device_id}/ingest` (QoS 1)

```json
{
    "token": "<device_token>",
    "readings": [
        { "sensor_id": "<sensor-uuid>", "value": 23.5, "unit": "°C" },
        { "sensor_id": "<sensor-uuid>", "value": 61.0, "unit": "%RH" },
        { "sensor_id": "<sensor-uuid>", "value": 1013.2, "unit": "hPa" }
    ]
}
```

| Field                  | Type     | Description                                |
| ---------------------- | -------- | ------------------------------------------ |
| `token`                | `string` | Device JWT / API token — required for auth |
| `readings`             | `array`  | One or more sensor readings                |
| `readings[].sensor_id` | `string` | UUID of the sensor in IoT26 dashboard      |
| `readings[].value`     | `number` | Scaled engineering value                   |
| `readings[].unit`      | `string` | Unit label, e.g. `°C`, `%RH`, `Pa`, `kW`   |

### Receive commands ← `devices/{device_id}/commands` (QoS 1)

```json
{ "action": "reload_config" }
{ "action": "restart" }
{ "action": "set_poll_interval", "interval": 30 }
{ "action": "set_value", "sensor_id": "<uuid>", "value": 42.0 }
```

---

## Authentication

| Channel         | Method                                                        |
| --------------- | ------------------------------------------------------------- |
| **MQTT ingest** | `token` field in every publish payload                        |
| **REST API**    | `Authorization: Bearer <device_token>` header                 |
| **REST API**    | `X-Org-Id: <org_id>` header (required alongside Bearer token) |

Obtain `device_id` and `device_token` from **IoT26 Dashboard → Devices → API
Token**.

---

## SDK Quickstarts

### C++ / Arduino / ESP32

**Library location:** [`cpp/IoT26/`](./cpp/IoT26/)

#### PlatformIO — `platformio.ini`

```ini
[env:esp32dev]
platform  = espressif32
board     = esp32dev
framework = arduino
lib_deps  =
    knolleary/PubSubClient @ ^2.8
    bblanchon/ArduinoJson  @ ^7
```

#### Plain MQTT (development / local broker)

```cpp
#include <WiFi.h>
#include "IoT26Client.h"

WiFiClient  wifi;
IoT26Client iot26(
    "your-device-uuid",          // device_id from IoT26 dashboard
    "eyJhbGci...",               // device_token from IoT26 dashboard
    "<iot26_url>",   // broker host
    1883                         // port — use 8883 + WiFiClientSecure in production
);

void setup() {
    Serial.begin(115200);
    WiFi.begin("SSID", "PASSWORD");
    while (WiFi.status() != WL_CONNECTED) delay(500);

    iot26.begin(wifi);
    iot26.onCommand([](const JsonDocument& cmd) {
        const char* action = cmd["action"];
        Serial.printf("[CMD] action=%s\n", action);
    });
    iot26.connect();
}

void loop() {
    IoT26Reading readings[] = {
        { "temp-sensor-uuid", 25.3f, "°C"  },
        { "hum-sensor-uuid",  61.0f, "%RH" },
    };
    iot26.publishReadings(readings, 2);
    iot26.loop();   // must be called every loop() iteration
    delay(10000);   // publish every 10 s
}
```

#### MQTTS / TLS (production)

```cpp
#include <WiFiClientSecure.h>
#include "IoT26Client.h"

WiFiClientSecure wifiSecure;
IoT26Client iot26(
    "your-device-uuid",
    "eyJhbGci...",
    "<iot26_url>",
    8883                         // MQTTS port
);

void setup() {
    WiFi.begin("SSID", "PASSWORD");
    while (WiFi.status() != WL_CONNECTED) delay(500);

    // Accept the broker's certificate from the system root CAs.
    // To pin your own CA cert, use wifiSecure.setCACert(ca_cert_pem);
    wifiSecure.setInsecure();    // or load CA: wifiSecure.setCACert(rootCA);

    iot26.begin(wifiSecure);     // <-- pass the secure client
    iot26.connect();
}
```

---

### Go

**Module:** [`go/iot26client`](./go/iot26client)

#### Install

```bash
cd sdk/go
go mod tidy
```

#### Minimal example

```go
package main

import (
    "context"
    "fmt"
    "log"
    "time"

    "github.com/iamfourh2e/IOT2026/sdk/go/iot26client"
)

func main() {
    client, err := iot26client.New(iot26client.Config{
        DeviceID:    "your-device-uuid",
        DeviceToken: "eyJhbGci...",
        Broker:      "ssl://<iot26_url>:8883", // production MQTTS
    })
    if err != nil {
        log.Fatal(err)
    }
    defer client.Disconnect()

    client.OnCommand(func(cmd iot26client.Command) {
        fmt.Println("command:", cmd.Action)
    })

    err = client.PublishReadings([]iot26client.Reading{
        {SensorID: "temp-sensor-uuid", Value: 23.5, Unit: "°C"},
        {SensorID: "hum-sensor-uuid",  Value: 61.0, Unit: "%RH"},
    })
    if err != nil {
        log.Fatal(err)
    }
}
```

#### Continuous publish loop

```go
ctx, cancel := context.WithCancel(context.Background())
defer cancel()

err = client.RunForever(ctx, 10*time.Second, func() []iot26client.Reading {
    return []iot26client.Reading{
        {SensorID: "temp-sensor-uuid", Value: readTemperature(), Unit: "°C"},
    }
})
```

#### Environment-based config (recommended for production)

```bash
export IOT26_DEVICE_ID=your-device-uuid
export IOT26_DEVICE_TOKEN=eyJhbGci...
export IOT26_BROKER=ssl://<iot26_url>:8883

go run ./example
```

```go
// In your code:
broker := os.Getenv("IOT26_BROKER")   // defaults to tcp://localhost:1883 in example
```

---

### Node.js

**Package:** [`nodejs/`](./nodejs/)

#### Install

```bash
cd sdk/nodejs
npm install
```

#### Minimal example

```js
const { IoT26Client } = require("./index");

const client = new IoT26Client({
    deviceId: "your-device-uuid",
    deviceToken: "eyJhbGci...",
    broker: "mqtts://<iot26_url>:8883", // production MQTTS
    debug: false,
});

await client.connect();

client.onCommand((cmd) => {
    console.log("command received:", cmd.action, cmd.raw);
});

await client.publishReadings([
    { sensorId: "temp-sensor-uuid", value: 23.5, unit: "°C" },
    { sensorId: "hum-sensor-uuid", value: 61.0, unit: "%RH" },
]);
```

#### Continuous publish loop

```js
const loop = client.startPublishLoop(() => [
    { sensorId: "temp-sensor-uuid", value: readTemperature(), unit: "°C" },
], 10_000); // every 10 seconds

// To stop:
loop.stop();
await client.disconnect();
```

#### Environment-based config

```bash
export IOT26_DEVICE_ID=your-device-uuid
export IOT26_DEVICE_TOKEN=eyJhbGci...
export IOT26_BROKER=mqtts://<iot26_url>:8883

node example.js
```

#### Node-RED integration

Use the **MQTT Out** node with:

| Setting | Value                        |
| ------- | ---------------------------- |
| Broker  | `<iot26_url>`                |
| Port    | `8883`                       |
| TLS     | Enabled                      |
| Topic   | `devices/<device_id>/ingest` |
| QoS     | 1                            |

Payload (Function node):

```js
const readings = [{
    sensor_id: msg.sensor_id,
    value: msg.payload,
    unit: msg.unit,
}];
msg.payload = JSON.stringify({ token: env.get("DEVICE_TOKEN"), readings });
return msg;
```

---

### Dart / Flutter

**Package:** [`dart/`](./dart/)

#### Add dependency (`pubspec.yaml`)

```yaml
dependencies:
    iot26_client:
        path: ../sdk/dart # or publish to pub.dev
    mqtt_client: ^10.0.0
```

#### Install

```bash
cd sdk/dart
dart pub get
```

#### Minimal example

```dart
import 'package:iot26_client/iot26_client.dart';

Future<void> main() async {
  final transport = Iot26MqttTransport(Iot26Config(
    deviceId:    'your-device-uuid',
    deviceToken: 'eyJhbGci...',
    broker:      '<iot26_url>',
    port:        8883,       // production MQTTS
    useTls:      true,
    debug:       false,
  ));

  await transport.connect();

  transport.commands.listen((cmd) {
    print('command: ${cmd.action}');
  });

  await transport.publish([
    Iot26Reading(sensorId: 'temp-sensor-uuid', value: 23.5,  unit: '°C'),
    Iot26Reading(sensorId: 'hum-sensor-uuid',  value: 61.0,  unit: '%RH'),
  ]);
}
```

#### Flutter — periodic publish

```dart
Timer.periodic(const Duration(seconds: 10), (_) async {
  await transport.publish([
    Iot26Reading(sensorId: sensorId, value: await readSensor(), unit: '°C'),
  ]);
});
```

#### Environment-based config (Dart CLI / server)

```bash
export IOT26_BROKER=<iot26_url>
export IOT26_PORT=8883
export IOT26_DEVICE_ID=your-device-uuid
export IOT26_DEVICE_TOKEN=eyJhbGci...

dart run example/main.dart
```

---

## TLS / MQTTS (Production)

The production broker terminates TLS at port **8883** using a valid Let's
Encrypt certificate. No custom CA certificate is required — the standard system
root CAs are sufficient.

| SDK         | Production broker string                        | TLS notes                                                           |
| ----------- | ----------------------------------------------- | ------------------------------------------------------------------- |
| **C++**     | host: `<iot26_url>`, port: `8883`               | Use `WiFiClientSecure`; call `setInsecure()` or `setCACert(rootCA)` |
| **Go**      | `ssl://<iot26_url>:8883`                        | System CAs used automatically when `TLSConfig` is `nil`             |
| **Node.js** | `mqtts://<iot26_url>:8883`                      | System CAs used automatically; pass `tlsOptions` for custom CA      |
| **Dart**    | host `<iot26_url>`, port `8883`, `useTls: true` | System CAs used automatically                                       |

### Custom CA (if needed)

```go
// Go — custom CA cert
caCert, _ := os.ReadFile("ca.crt")
pool := x509.NewCertPool()
pool.AppendCertsFromPEM(caCert)

client, _ := iot26client.New(iot26client.Config{
    Broker: "ssl://<iot26_url>:8883",
    TLSConfig: &tls.Config{RootCAs: pool},
    ...
})
```

```js
// Node.js — custom CA cert
const fs = require('fs');
const client = new IoT26Client({
    broker: 'mqtts://<iot26_url>:8883',
    tlsOptions: { ca: fs.readFileSync('ca.crt') },
    ...
});
```

---

## Publish Loop Pattern

All SDKs provide a built-in publish loop. For languages that don't, use this
pattern:

```
1. Connect to broker
2. Register command handler
3. Loop every N seconds:
   a. Read sensor(s)
   b. publishReadings([...])
   c. Handle any errors (log + continue — do not crash)
4. On signal/shutdown: disconnect cleanly
```

**Recommended publish interval:** 10–60 seconds for most sensors. Real-time
sensors can publish as fast as 1 second.

---

## Downlink Commands

The platform can push commands to your device via
`devices/{device_id}/commands`. Register a handler to act on them:

| Action              | Extra fields                              | Description                                     |
| ------------------- | ----------------------------------------- | ----------------------------------------------- |
| `reload_config`     | —                                         | Re-fetch device config from the REST API        |
| `restart`           | —                                         | Restart the device or edge agent process        |
| `set_poll_interval` | `"interval": <seconds>`                   | Change publish frequency at runtime             |
| `set_value`         | `"sensor_id": "..."`, `"value": <number>` | Override a sensor value (e.g. actuator control) |

**Example handler (Go):**

```go
client.OnCommand(func(cmd iot26client.Command) {
    switch cmd.Action {
    case "restart":
        os.Exit(0)
    case "set_poll_interval":
        var body struct{ Interval int `json:"interval"` }
        _ = json.Unmarshal(cmd.Raw, &body)
        ticker.Reset(time.Duration(body.Interval) * time.Second)
    }
})
```

---

## Troubleshooting

### Connection refused / timeout

- Check that port **8883** is not blocked by your firewall or ISP.
- Verify `device_id` and `device_token` are correct (Dashboard → Devices).
- For plain MQTT on port 1883: confirm the server is reachable with
  `mosquitto_pub -h <iot26_url> -p 1883 -t test -m hello`.

### TLS handshake failure (C++ / ESP32)

- Call `wifiSecure.setInsecure()` if you don't have the root CA stored on the
  device (accepts any valid cert).
- Or flash the ISRG Root X1 PEM as `rootCA` and use
  `wifiSecure.setCACert(rootCA)`.
- Ensure the ESP32 system clock is set correctly (NTP) — TLS validation fails if
  the clock is wrong.

### Readings not appearing on the dashboard

1. Confirm `sensor_id` in the payload **exactly matches** the sensor UUID in
   IoT26 Dashboard → Sensors.
2. Check the device token has not expired or been revoked (Dashboard → Devices →
   Tokens).
3. Enable debug logging in your SDK and verify the publish succeeds (QoS-1
   acknowledgement received).
4. Check backend logs:
   `ssh iot26 'journalctl -u iot26-backend -n 50 --no-pager'`.

### Commands not received

- Confirm you subscribed **before** calling `loop()` or entering the main loop —
  all SDKs do this automatically in `connect()` / `begin()`.
- The SDK subscribes to `devices/{device_id}/commands` at QoS 1. Verify the
  exact device ID matches the one on the dashboard.

### MQTT client ID conflict

If two devices use the same `device_id`, the broker will disconnect the older
connection. Each physical device must have a unique `device_id`.

---

## Related

| Resource            | Link                                                        |
| ------------------- | ----------------------------------------------------------- |
| IoT26 Dashboard     | [https://<iot26_url>](https://<iot26_url>)                  |
| REST API docs       | `https://<iot26_url>/v1/`                                   |
| Backend source      | [`backend/`](../backend/)                                   |
| Edge agent (Python) | [`edge/`](../edge/)                                         |
| GitHub              | [iamfourh2e/IOT2026](https://github.com/iamfourh2e/IOT2026) |
