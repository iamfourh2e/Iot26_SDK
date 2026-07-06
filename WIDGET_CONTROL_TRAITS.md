# IoT26 SDK — Sensor Publishing Guide

This guide covers two types of sensor publishing:

1. **Normal Sensor Telemetry** — Numeric readings (flow, temperature, humidity, etc.) shown as charts, gauges, and value tiles. No `metadata_json` needed.
2. **Widget Control Traits** — State readings with `metadata_json` that power interactive control buttons (relay, AC mode, door, brightness, display).

---

## How It Works

```
 Your Device (ESP32 / Python / Go / Node.js / Dart)
       │
       │  1. Receives command (downlink)
       │     MQTT topic: devices/{device_id}/commands
       │     Payload: {"action":"custom","custom":{"motor":"open"}}
       │
       ▼
 Execute hardware action (move motor, toggle relay, etc.)
       │
       │  2. Publishes confirmed state (uplink)
       │     MQTT topic: devices/{device_id}/ingest
       │     Payload: {"token":"...","readings":[
       │       {"sensor_id":"...","value":1.0,"unit":"state",
       │        "metadata_json":"{\"motor\":\"open\"}"}
       │     ]}
       │
       ▼
 IoT26 Backend
       │  3. Saves reading to PostgreSQL (persists state)
       │  4. Broadcasts over WebSocket to all open widget sessions
       │
       ▼
 Widget Dashboard (browser)
       │  5. Receives WebSocket message → highlights "Open" button
       │  6. On page refresh → fetches last reading from DB → restores state
```

---

## UI Component Reference

Each UI component reads a specific field from `metadata_json` attached to the
sensor reading. Attach your sensor ID to the matching control in Widget Builder.

### 1. Toggle / Relay

Highlights **ON** or **OFF** button.

| metadata_json         | Button highlighted |
|-----------------------|--------------------|
| `{"mode": "on"}`      | **ON**             |
| `{"mode": "off"}`     | **OFF**            |

**Publish example (Python):**
```python
client.publish_batch([{
    "sensor_id": "relay-sensor-uuid",
    "value":     1.0,
    "unit":      "state",
    "metadata_json": '{"mode": "on"}',
}])
```

---

### 2. AC Mode

Highlights **Cool**, **Heat**, or **Off** button.

| metadata_json         | Button highlighted |
|-----------------------|--------------------|
| `{"mode": "cool"}`    | **Cool**           |
| `{"mode": "heat"}`    | **Heat**           |
| `{"mode": "off"}`     | **Off**            |

**Publish example (Go):**
```go
client.PublishReadings([]iot26client.Reading{{
    SensorID:     "ac-mode-sensor-uuid",
    Value:        1.0,
    Unit:         "state",
    MetadataJSON: `{"mode":"cool"}`,
}})
```

---

### 3. Door / Motor

Highlights **Open**, **Stop**, or **Close** button.

| metadata_json          | Button highlighted |
|------------------------|--------------------|
| `{"motor": "open"}`    | **Open**           |
| `{"motor": "stop"}`    | **Stop**           |
| `{"motor": "close"}`   | **Close**          |

**Publish example (Node.js):**
```js
await client.publishReadings([{
  sensorId:     'door-motor-sensor-uuid',
  value:        1.0,
  unit:         'state',
  metadataJson: JSON.stringify({ motor: 'open' }),
}]);
```

---

### 4. Brightness Slider

Reads the plain **numeric `value`** directly. No `metadata_json` needed.
Range: `0.0` – `100.0`.

| value  | Slider position |
|--------|-----------------|
| `0.0`  | 0% (leftmost)   |
| `75.0` | 75%             |
| `100.0`| 100% (rightmost)|

**Publish example (Dart):**
```dart
client.publishReadings([
  Iot26Reading(sensorId: 'brightness-sensor-uuid', value: 75.0, unit: '%'),
]);
```

---

### 5. Display Text

Renders the string value inside `metadata_json["display"]` on screen.

| metadata_json                | Shown in widget  |
|------------------------------|------------------|
| `{"display": "Hello World"}` | **Hello World**  |
| `{"display": "23.5 °C"}`     | **23.5 °C**      |

**Publish example (Arduino/ESP32):**
```cpp
IoT26Reading r[] = {{
  "display-sensor-uuid",
  1.0f,
  "text",
  "{\"display\":\"Hello World\"}"
}};
iot26.publishReadings(r, 1);
```

---

## The Command → Uplink Pattern

The most important pattern for control widgets is the **command–uplink loop**:

1. User presses a button in the widget → backend sends a **downlink command** to your device.
2. Your device executes the action on real hardware.
3. Your device **publishes an uplink reading** with the confirmed new state.
4. The widget receives the uplink over WebSocket and updates immediately.

> **Why publish an uplink after every command?**
> The widget does NOT optimistically update its state when a command is sent.
> It only highlights a button when it receives a sensor reading from your device.
> This ensures the UI always reflects what the hardware _actually_ did, not what
> was asked of it. It also saves the confirmed state to the database so it
> persists across browser refreshes and server restarts.

### Downlink command payload (what your device receives)

```json
{
  "action": "custom",
  "custom": {
    "relay":      true,
    "ac_mode":    "cool",
    "motor":      "open",
    "brightness": 80,
    "display":    "Hello IoT26"
  }
}
```

Only the fields relevant to the pressed button are included.

---

## Example Files

### Normal Sensor Telemetry

| Language     | File                                                      |
|--------------|-----------------------------------------------------------|
| **Python**   | `python/examples/sensor_telemetry.py`                     |
| **Go**       | `go/example/sensor_telemetry/main.go`                     |
| **Node.js**  | `nodejs/sensor_telemetry.js`                              |
| **Dart**     | `dart/example/sensor_telemetry.dart`                      |
| **Arduino**  | `cpp/sensor_telemetry/sensor_telemetry.ino`               |

Each file demonstrates:
- Publishing 10 common sensor types (flow, temperature, humidity, pressure, water level, power, energy, CO₂, soil, pH)
- Simulated reads with comments showing how to plug in real sensor driver code
- Cumulative energy accumulation over time
- Batch publishing for efficiency

### Widget Control Traits

| Language     | File                                                             |
|--------------|------------------------------------------------------------------|
| **Python**   | `python/examples/widget_control_traits.py`                       |
| **Go**       | `go/example/widget_control_traits/main.go`                       |
| **Node.js**  | `nodejs/widget_control_traits.js`                                |
| **Dart**     | `dart/example/widget_control_traits.dart`                        |
| **Arduino**  | `cpp/widget_control_traits/widget_control_traits.ino`            |

Each file demonstrates:
- Publishing initial state on boot/connect (so widget shows correct state immediately)
- Handling all five downlink custom fields (`relay`, `ac_mode`, `motor`, `brightness`, `display`)
- Publishing targeted uplink readings after each command to confirm state
- Heartbeat re-publish every 30 s to keep state fresh in the database

---

## Quick Start (Python)

```bash
# 1. Install the SDK
pip install iot26-edge

# 2a. Run normal sensor telemetry
IOT26_DEVICE_ID=your-device-uuid \
IOT26_DEVICE_TOKEN=your-device-token \
python python/examples/sensor_telemetry.py

# 2b. Run widget control traits
IOT26_DEVICE_ID=your-device-uuid \
IOT26_DEVICE_TOKEN=your-device-token \
python python/examples/widget_control_traits.py
```

## Quick Start (Go)

```bash
# Normal sensor telemetry
cd go/example/sensor_telemetry
IOT26_DEVICE_ID=your-device-uuid IOT26_DEVICE_TOKEN=your-device-token go run main.go

# Widget control traits
cd go/example/widget_control_traits
IOT26_DEVICE_ID=your-device-uuid IOT26_DEVICE_TOKEN=your-device-token go run main.go
```

## Quick Start (Node.js)

```bash
cd nodejs

# Normal sensor telemetry
IOT26_DEVICE_ID=your-device-uuid IOT26_DEVICE_TOKEN=your-device-token node sensor_telemetry.js

# Widget control traits
IOT26_DEVICE_ID=your-device-uuid IOT26_DEVICE_TOKEN=your-device-token node widget_control_traits.js
```

## Quick Start (Dart)

```bash
cd dart

# Normal sensor telemetry
IOT26_DEVICE_ID=your-device-uuid IOT26_DEVICE_TOKEN=your-device-token dart run example/sensor_telemetry.dart

# Widget control traits
IOT26_DEVICE_ID=your-device-uuid IOT26_DEVICE_TOKEN=your-device-token dart run example/widget_control_traits.dart
```

## Quick Start (Arduino / ESP32)

1. Copy `cpp/IoT26/IoT26Client.h` and `cpp/IoT26/IoT26Client.cpp` into your sketch folder.
2. Choose your sketch:
   - **Telemetry only:** `cpp/sensor_telemetry/sensor_telemetry.ino`
   - **Control widget:** `cpp/widget_control_traits/widget_control_traits.ino`
3. Update `WIFI_SSID`, `WIFI_PASSWORD`, `DEVICE_ID`, `DEVICE_TOKEN`, `MQTT_BROKER`, and all `SENSOR_*` constants.
4. Flash to your ESP32.

> **Tip:** The Arduino telemetry example includes commented hints for popular sensor libraries (DHT, DS18B20, BMP280, PZEM-004T, HC-SR04) showing exactly how to swap out the simulated reads for real hardware.

---

## Sensor ID Setup in Widget Builder

1. Open **Widget Builder** in the IoT26 dashboard.
2. Add a **Control Widget** and select your target device.
3. For each control (Relay, AC, Door, Brightness, Display), click **Bind Sensor** and select the matching sensor from your device.
4. The sensor IDs shown there are what you put in the `SENSOR_*` constants above.

---

## State Persistence

The IoT26 backend automatically:

- **Saves every reading to PostgreSQL** — state survives server restarts.
- **Sends a snapshot on WebSocket connect** — when a user opens or refreshes the widget, the backend immediately pushes the last known reading for each bound sensor before any live event arrives. The widget restores its button highlights instantly, with no wait needed.
- **Caches readings in memory** — for low-latency reconnects within the same server session.
