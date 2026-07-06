import 'dart:io';
import '../lib/iot26_client.dart'; // Import the local SDK wrapper

void main() async {
  final client = Iot26Client(Iot26Config(
    deviceId: 'your-device-uuid',
    deviceToken: 'your-device-token',
    broker: 'localhost',
    port: 1883,
  ));

  // Register command listener
  client.commands.listen((Iot26Command cmd) {
    print('Received command action: ${cmd.action}');

    if (cmd.action == 'custom') {
      print('Processing custom command...');

      // PUBLISH UPLINK: Report the new state back to the dashboard widget!
      print('Publishing uplink to sync widget UI...');
      client.publishReadings([
        Iot26Reading(sensorId: 'valve-sensor-uuid', value: 1.0, unit: 'state'),
      ]);
      print('Uplink published successfully!');
    }
  });

  // Connect to the broker
  try {
    await client.connect();
    print('Connected to IoT26 MQTT broker!');
  } catch (e) {
    print('Failed to connect: $e');
    exit(1);
  }

  // Simulate periodic routine telemetry
  while (true) {
    await Future.delayed(Duration(seconds: 10));
    print('Publishing routine telemetry...');
    client.publishReadings([
      Iot26Reading(sensorId: 'temp-sensor-uuid', value: 24.5, unit: 'C'),
      Iot26Reading(sensorId: 'hum-sensor-uuid', value: 60.0, unit: '%'),
    ]);
  }
}
