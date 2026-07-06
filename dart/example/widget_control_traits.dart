/// Widget Control Traits — Dart SDK Example
///
/// Shows how to publish sensor readings with metadataJson to power the
/// IoT26 Widget Builder's UI control components.
///
/// Widget UI Component → metadataJson field + values:
///
///   Toggle (Relay)  → {"mode": "on"} | {"mode": "off"}
///   AC Mode         → {"mode": "cool"} | {"mode": "heat"} | {"mode": "off"}
///   Door / Motor    → {"motor": "open"} | {"motor": "stop"} | {"motor": "close"}
///   Brightness      → plain numeric value (no metadata needed)
///   Display Text    → {"display": "Hello World"}
///
/// Usage:
///   dart run example/widget_control_traits.dart

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import '../lib/iot26_client.dart';

// ── Sensor IDs — replace with UUIDs from your IoT26 sensor config ─────────────

const sensorRelay      = 'relay-sensor-uuid';      // Toggle widget (on/off)
const sensorACMode     = 'ac-mode-sensor-uuid';    // AC widget    (cool/heat/off)
const sensorDoorMotor  = 'door-motor-sensor-uuid'; // Door widget  (open/stop/close)
const sensorBrightness = 'brightness-sensor-uuid'; // Slider widget (0–100%)
const sensorDisplay    = 'display-sensor-uuid';    // Display text widget

// ── Device state (simulated — replace with real hardware reads) ───────────────

class DeviceState {
  String relay      = 'off';    // 'on' | 'off'
  String acMode     = 'off';    // 'cool' | 'heat' | 'off'
  String doorMotor  = 'close';  // 'open' | 'stop' | 'close'
  double brightness = 75.0;     // 0–100
  String displayMsg = 'Hello!';
}

final state = DeviceState();

// ── Helpers ───────────────────────────────────────────────────────────────────

List<Iot26Reading> buildReadings() {
  return [
    // Toggle/Relay: mode = "on" or "off"
    Iot26Reading(
      sensorId: sensorRelay,
      value:    state.relay == 'on' ? 1.0 : 0.0,
      unit:     'state',
      metadataJson: jsonEncode({'mode': state.relay}),
    ),

    // AC Mode: mode = "cool" | "heat" | "off"
    Iot26Reading(
      sensorId:     sensorACMode,
      value:        1.0,
      unit:         'state',
      metadataJson: jsonEncode({'mode': state.acMode}),
    ),

    // Door / Motor: motor = "open" | "stop" | "close"
    Iot26Reading(
      sensorId:     sensorDoorMotor,
      value:        1.0,
      unit:         'state',
      metadataJson: jsonEncode({'motor': state.doorMotor}),
    ),

    // Brightness: plain numeric value — slider reads the value directly
    Iot26Reading(
      sensorId: sensorBrightness,
      value:    state.brightness,
      unit:     '%',
    ),

    // Display text: display = "any text"
    Iot26Reading(
      sensorId:     sensorDisplay,
      value:        1.0,
      unit:         'text',
      metadataJson: jsonEncode({'display': state.displayMsg}),
    ),
  ];
}

Future<void> publishAll(Iot26Client client) async {
  client.publishReadings(buildReadings());
  print('↑ State pushed  relay=${state.relay} ac=${state.acMode} '
        'door=${state.doorMotor} brightness=${state.brightness.toInt()} '
        'display="${state.displayMsg}"');
}

// ── Command handler ───────────────────────────────────────────────────────────

void handleCommand(Iot26Client client, Iot26Command cmd) {
  print('↓ Command received: action=${cmd.action}');

  if (cmd.action != 'custom') {
    print('  Ignoring non-custom action: ${cmd.action}');
    return;
  }

  final custom = (cmd.payload?['custom'] as Map<String, dynamic>?) ?? {};

  // ── Relay ──────────────────────────────────────────────────────────────────
  if (custom.containsKey('relay')) {
    state.relay = (custom['relay'] as bool) ? 'on' : 'off';
    print('  Relay → ${state.relay}');
    client.publishReadings([
      Iot26Reading(
        sensorId:     sensorRelay,
        value:        state.relay == 'on' ? 1.0 : 0.0,
        unit:         'state',
        metadataJson: jsonEncode({'mode': state.relay}),
      ),
    ]);
  }

  // ── AC Mode ────────────────────────────────────────────────────────────────
  if (custom.containsKey('ac_mode')) {
    final mode = custom['ac_mode'] as String;
    if (['cool', 'heat', 'off'].contains(mode)) {
      state.acMode = mode;
      print('  AC mode → ${state.acMode}');
      client.publishReadings([
        Iot26Reading(
          sensorId:     sensorACMode,
          value:        1.0,
          unit:         'state',
          metadataJson: jsonEncode({'mode': state.acMode}),
        ),
      ]);
    }
  }

  // ── Door / Motor ───────────────────────────────────────────────────────────
  if (custom.containsKey('motor')) {
    final pos = custom['motor'] as String;
    if (['open', 'stop', 'close'].contains(pos)) {
      state.doorMotor = pos;
      print('  Door motor → ${state.doorMotor}');
      client.publishReadings([
        Iot26Reading(
          sensorId:     sensorDoorMotor,
          value:        1.0,
          unit:         'state',
          metadataJson: jsonEncode({'motor': state.doorMotor}),
        ),
      ]);
    }
  }

  // ── Brightness ─────────────────────────────────────────────────────────────
  if (custom.containsKey('brightness')) {
    state.brightness = (custom['brightness'] as num).toDouble();
    print('  Brightness → ${state.brightness.toInt()}%');
    client.publishReadings([
      Iot26Reading(
        sensorId: sensorBrightness,
        value:    state.brightness,
        unit:     '%',
      ),
    ]);
  }

  // ── Display text ───────────────────────────────────────────────────────────
  if (custom.containsKey('display')) {
    state.displayMsg = custom['display'].toString();
    print('  Display → "${state.displayMsg}"');
    client.publishReadings([
      Iot26Reading(
        sensorId:     sensorDisplay,
        value:        1.0,
        unit:         'text',
        metadataJson: jsonEncode({'display': state.displayMsg}),
      ),
    ]);
  }
}

// ── Main ──────────────────────────────────────────────────────────────────────

void main() async {
  final client = Iot26Client(Iot26Config(
    deviceId:    Platform.environment['IOT26_DEVICE_ID']    ?? 'your-device-uuid',
    deviceToken: Platform.environment['IOT26_DEVICE_TOKEN'] ?? 'your-device-token',
    broker:      Platform.environment['IOT26_BROKER']       ?? 'localhost',
    port:        1883,
  ));

  // Register command handler
  client.commands.listen((cmd) => handleCommand(client, cmd));

  // Connect to broker
  try {
    await client.connect();
    print('✓ Connected to IoT26 MQTT broker');
  } catch (e) {
    print('✗ Failed to connect: $e');
    exit(1);
  }

  // Push initial state so the widget immediately shows correct button highlights
  print('Publishing initial device state...');
  await publishAll(client);

  print('Running — widget reflects state in real time. Press Ctrl+C to stop.');

  // Re-publish heartbeat state every 30 s
  Timer.periodic(const Duration(seconds: 30), (_) => publishAll(client));
}
