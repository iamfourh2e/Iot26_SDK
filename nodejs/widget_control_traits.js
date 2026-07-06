/**
 * Widget Control Traits — Node.js SDK Example
 *
 * Shows how to publish sensor readings with metadata_json to power the
 * IoT26 Widget Builder's UI control components.
 *
 * Widget UI Component → metadata_json field + values:
 *
 *   Toggle (Relay)  → {"mode": "on"} | {"mode": "off"}
 *   AC Mode         → {"mode": "cool"} | {"mode": "heat"} | {"mode": "off"}
 *   Door / Motor    → {"motor": "open"} | {"motor": "stop"} | {"motor": "close"}
 *   Brightness      → plain numeric value (no metadata needed)
 *   Display Text    → {"display": "Hello World"}
 *
 * The widget reads metadata_json from the latest sensor reading and highlights
 * the matching button. State persists across refreshes via the DB snapshot.
 *
 * Usage:
 *   IOT26_DEVICE_ID=<uuid> IOT26_DEVICE_TOKEN=<token> node widget_control_traits.js
 */

'use strict';

const { IoT26Client } = require('./index.js');

// ── Configuration ─────────────────────────────────────────────────────────────

const DEVICE_ID    = process.env.IOT26_DEVICE_ID    || 'your-device-uuid';
const DEVICE_TOKEN = process.env.IOT26_DEVICE_TOKEN || 'your-device-token';
const BROKER       = process.env.IOT26_BROKER       || 'mqtt://localhost:1883';

// ── Sensor IDs — replace with UUIDs from your IoT26 sensor config ─────────────

const SENSOR_RELAY      = 'relay-sensor-uuid';      // Toggle widget (on/off)
const SENSOR_AC_MODE    = 'ac-mode-sensor-uuid';    // AC widget    (cool/heat/off)
const SENSOR_DOOR_MOTOR = 'door-motor-sensor-uuid'; // Door widget  (open/stop/close)
const SENSOR_BRIGHTNESS = 'brightness-sensor-uuid'; // Slider widget (0–100%)
const SENSOR_DISPLAY    = 'display-sensor-uuid';    // Display text widget

// ── Device state (simulated — replace with real hardware reads) ───────────────

const state = {
  relay:      'off',    // 'on' | 'off'
  acMode:     'off',    // 'cool' | 'heat' | 'off'
  doorMotor:  'close',  // 'open' | 'stop' | 'close'
  brightness: 75,       // 0–100
  displayMsg: 'Hello!',
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function buildReadings() {
  return [
    // Toggle/Relay: mode = "on" or "off"
    {
      sensorId: SENSOR_RELAY,
      value:    state.relay === 'on' ? 1.0 : 0.0,
      unit:     'state',
      metadataJson: JSON.stringify({ mode: state.relay }),
    },

    // AC Mode: mode = "cool" | "heat" | "off"
    {
      sensorId:     SENSOR_AC_MODE,
      value:        1.0,
      unit:         'state',
      metadataJson: JSON.stringify({ mode: state.acMode }),
    },

    // Door / Motor: motor = "open" | "stop" | "close"
    {
      sensorId:     SENSOR_DOOR_MOTOR,
      value:        1.0,
      unit:         'state',
      metadataJson: JSON.stringify({ motor: state.doorMotor }),
    },

    // Brightness: plain numeric value — slider reads the value directly
    {
      sensorId: SENSOR_BRIGHTNESS,
      value:    state.brightness,
      unit:     '%',
    },

    // Display text: display = "any text"
    {
      sensorId:     SENSOR_DISPLAY,
      value:        1.0,
      unit:         'text',
      metadataJson: JSON.stringify({ display: state.displayMsg }),
    },
  ];
}

async function publishAll(client) {
  await client.publishReadings(buildReadings());
  console.log(`↑ State pushed  relay=${state.relay} ac=${state.acMode} door=${state.doorMotor} brightness=${state.brightness} display="${state.displayMsg}"`);
}

// ── Command handler ───────────────────────────────────────────────────────────

function makeCommandHandler(client) {
  return async (cmd) => {
    console.log(`↓ Command received: action=${cmd.action}`);

    if (cmd.action !== 'custom') {
      console.log(`  Ignoring non-custom action: ${cmd.action}`);
      return;
    }

    const custom = (cmd.raw && cmd.raw.custom) ? cmd.raw.custom : {};

    // ── Relay ──────────────────────────────────────────────────────────────
    if (custom.relay !== undefined) {
      state.relay = custom.relay ? 'on' : 'off';
      console.log(`  Relay → ${state.relay}`);
      await client.publishReadings([{
        sensorId:     SENSOR_RELAY,
        value:        state.relay === 'on' ? 1.0 : 0.0,
        unit:         'state',
        metadataJson: JSON.stringify({ mode: state.relay }),
      }]);
    }

    // ── AC Mode ────────────────────────────────────────────────────────────
    if (custom.ac_mode !== undefined) {
      const validModes = ['cool', 'heat', 'off'];
      if (validModes.includes(custom.ac_mode)) {
        state.acMode = custom.ac_mode;
        console.log(`  AC mode → ${state.acMode}`);
        await client.publishReadings([{
          sensorId:     SENSOR_AC_MODE,
          value:        1.0,
          unit:         'state',
          metadataJson: JSON.stringify({ mode: state.acMode }),
        }]);
      }
    }

    // ── Door / Motor ───────────────────────────────────────────────────────
    if (custom.motor !== undefined) {
      const validPos = ['open', 'stop', 'close'];
      if (validPos.includes(custom.motor)) {
        state.doorMotor = custom.motor;
        console.log(`  Door motor → ${state.doorMotor}`);
        await client.publishReadings([{
          sensorId:     SENSOR_DOOR_MOTOR,
          value:        1.0,
          unit:         'state',
          metadataJson: JSON.stringify({ motor: state.doorMotor }),
        }]);
      }
    }

    // ── Brightness ─────────────────────────────────────────────────────────
    if (custom.brightness !== undefined) {
      state.brightness = parseFloat(custom.brightness);
      console.log(`  Brightness → ${state.brightness}%`);
      await client.publishReadings([{
        sensorId: SENSOR_BRIGHTNESS,
        value:    state.brightness,
        unit:     '%',
      }]);
    }

    // ── Display text ───────────────────────────────────────────────────────
    if (custom.display !== undefined) {
      state.displayMsg = String(custom.display);
      console.log(`  Display → "${state.displayMsg}"`);
      await client.publishReadings([{
        sensorId:     SENSOR_DISPLAY,
        value:        1.0,
        unit:         'text',
        metadataJson: JSON.stringify({ display: state.displayMsg }),
      }]);
    }
  };
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  const client = new IoT26Client({
    deviceId:    DEVICE_ID,
    deviceToken: DEVICE_TOKEN,
    broker:      BROKER,
  });

  client.onCommand(makeCommandHandler(client));

  await client.connect();
  console.log('✓ Connected to IoT26 MQTT broker');

  // Push initial state so the widget immediately shows correct button highlights
  console.log('Publishing initial device state...');
  await publishAll(client);

  console.log('Running — widget reflects state in real time. Press Ctrl+C to stop.');

  // Re-publish heartbeat state every 30 s
  setInterval(() => publishAll(client), 30_000);
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
