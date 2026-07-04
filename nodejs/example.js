/**
 * IoT26 Node.js SDK — Dynamic Config & Button Example
 *
 * Usage:
 *   IOT26_DEVICE_ID=<uuid>  \
 *   IOT26_DEVICE_TOKEN=<token> \
 *   node example_button.js
 */

'use strict';

const https = require('https');
const { IoT26Client } = require('./index');

const deviceId = process.env.IOT26_DEVICE_ID;
const deviceToken = process.env.IOT26_DEVICE_TOKEN;

if (!deviceId || !deviceToken) {
  console.error("Missing IOT26_DEVICE_ID or IOT26_DEVICE_TOKEN");
  process.exit(1);
}

// 1. Fetch Configuration via REST API
const options = {
  hostname: '<iot26_url>',
  path: `/v1/devices/${deviceId}/config`,
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${deviceToken}`
  }
};

console.log("Fetching dynamic configuration...");

const req = https.request(options, res => {
  let data = '';
  res.on('data', chunk => { data += chunk; });
  res.on('end', async () => {
    if (res.statusCode !== 200) {
      console.error(`API Error: ${res.statusCode} ${data}`);
      process.exit(1);
    }
    
    const config = JSON.parse(data);
    
    // 2. Parse Button Sensor configuration
    let buttonSensorId = 'fallback-button-id';
    let pollIntervalMs = (config.poll_interval_seconds || 5) * 1000;
    
    for (const sensor of (config.sensors || [])) {
      if ((sensor.name || '').toLowerCase().includes('button')) {
        buttonSensorId = sensor.sensor_id;
        console.log(`Found button sensor! ID: ${buttonSensorId}, Assigned GPIO Pin: ${sensor.channel_props?.pin || 4}`);
      }
    }

    // 3. Connect MQTT Client
    const client = new IoT26Client({
      deviceId,
      deviceToken,
      broker: 'mqtts://<iot26_url>:8883',
      debug: false
    });

    // 4. Handle Downlink Commands (Mirroring C++ Example)
    client.onCommand((cmd) => {
      console.log(`Received command from dashboard: ${cmd.action}`);
      const raw = cmd.raw || {};

      switch (cmd.action) {
        case 'reload_config':
          console.log('-> Reloading configuration...');
          break;
        case 'write_register':
          console.log(`-> Modbus Write: Slave ${raw.slave || 1}, Reg ${raw.register || 0} = ${raw.value || 0}`);
          break;
        case 'read_register':
          console.log(`-> Modbus Read: Slave ${raw.slave || 1}, Reg ${raw.register || 0}, Count ${raw.value || 1}`);
          break;
        case 'trigger_ota':
          console.log(`-> Trigger OTA Update from: ${raw.url || 'unknown'}`);
          break;
        case 'custom':
          const custom = raw.custom || {};
          if (custom.valve !== undefined) console.log(`-> Toggle Switch/Valve: ${custom.valve ? 'ON' : 'OFF'}`);
          if (custom.dimmer !== undefined) console.log(`-> Dimmer Level: ${custom.dimmer}%`);
          if (custom.color !== undefined) console.log(`-> Set RGB Color: ${custom.color}`);
          if (custom.lock !== undefined) console.log(`-> Electronic Lock: ${custom.lock}`);
          if (custom.ir_blaster !== undefined) console.log(`-> Blast IR Code: ${custom.ir_blaster}`);
          if (custom.ptz !== undefined) console.log(`-> PTZ Camera Move to X:${custom.ptz.pan || 0}, Y:${custom.ptz.tilt || 0}`);
          if (custom.display !== undefined) console.log(`-> LCD Display Text: ${custom.display}`);
          if (custom.calibrate !== undefined) console.log(`-> Sensor Calibration [${custom.calibrate.type || 'unknown'}]: ${custom.calibrate.value || 0}`);
          break;
      }
    });

    await client.connect();
    console.log(`Configuration applied. Polling every ${pollIntervalMs}ms`);

    // 5. Simulate Button Polling Loop
    setInterval(() => {
      // Simulate reading a hardware GPIO state
      console.log("[HARDWARE] Button pressed! Publishing telemetry...");
      client.publishTelemetry([{
        sensorId: buttonSensorId,
        value: 1.0,
        unit: 'click'
      }]);
    }, pollIntervalMs);

  });
});

req.on('error', error => {
  console.error("Failed to fetch config:", error);
});

req.end();
