const { IoT26Client } = require('./index.js'); // Use the local SDK wrapper

async function main() {
  const client = new IoT26Client({
    deviceId: 'your-device-uuid',
    deviceToken: 'your-device-token',
    broker: 'mqtt://localhost:1883'
  });

  // Listen for downlink commands from the widget
  client.onCommand(async (cmd) => {
    console.log(`Received command action: ${cmd.action}`);
    
    if (cmd.action === 'custom') {
      console.log('Processing custom action command...');
      
      // PUBLISH UPLINK: Report the new state back to sync the Widget UI!
      console.log('Publishing uplink to update the widget UI...');
      await client.publishReadings([
        { sensorId: 'valve-sensor-uuid', value: 1.0, unit: 'state' }
      ]);
      console.log('Uplink published successfully!');
    }
  });

  try {
    await client.connect();
    console.log('Connected to IoT26 MQTT broker!');

    // Periodically publish routine telemetry
    setInterval(async () => {
      console.log('Publishing routine telemetry...');
      await client.publishReadings([
        { sensorId: 'temp-sensor-uuid', value: 24.5, unit: 'C' },
        { sensorId: 'hum-sensor-uuid', value: 60.0, unit: '%' }
      ]);
    }, 10000);

  } catch (err) {
    console.error('Failed to connect:', err);
  }
}

main();
