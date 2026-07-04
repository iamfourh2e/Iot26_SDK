/// IoT26 Dart SDK — Dynamic Config & Button Example
///
/// Usage:
///   dart run example/button_example.dart
///
/// Environment variables:
///   IOT26_DEVICE_ID     (required)
///   IOT26_DEVICE_TOKEN  (required)

import 'dart:io';
import 'dart:convert';
import 'dart:async';
import 'package:iot26_client/iot26_client.dart';

void main() async {
  final deviceId = Platform.environment['IOT26_DEVICE_ID'];
  final deviceToken = Platform.environment['IOT26_DEVICE_TOKEN'];

  if (deviceId == null || deviceToken == null) {
    stderr.writeln(
        'Missing required environment variables: IOT26_DEVICE_ID or IOT26_DEVICE_TOKEN');
    exit(1);
  }

  // 1. Fetch Configuration via REST API
  print('Fetching dynamic configuration...');

  final clientHttp = HttpClient();
  final request = await clientHttp
      .getUrl(Uri.parse('https://<iot26_url>/v1/devices/$deviceId/config'));
  request.headers.add('Authorization', 'Bearer $deviceToken');

  final response = await request.close();

  if (response.statusCode != 200) {
    stderr.writeln('API returned status ${response.statusCode}');
    exit(1);
  }

  final responseBody = await response.transform(utf8.decoder).join();
  final config = jsonDecode(responseBody);

  // 2. Parse Button Sensor configuration
  String buttonSensorId = 'fallback-button-id';
  int pollIntervalSecs = config['poll_interval_seconds'] ?? 5;

  final sensors = config['sensors'] as List<dynamic>? ?? [];
  for (final sensor in sensors) {
    final name = (sensor['name'] as String? ?? '').toLowerCase();
    if (name.contains('button')) {
      buttonSensorId = sensor['sensor_id'];
      final props = sensor['channel_props'] ?? {};
      print(
          'Found button sensor! ID: $buttonSensorId, Assigned GPIO Pin: ${props['pin'] ?? 4}');
    }
  }

  // 3. Connect MQTT Client
  final mqttClient = Iot26Client(Iot26Config(
    deviceId: deviceId,
    deviceToken: deviceToken,
    broker: '<iot26_url>',
    port: 8883,
    debug: false,
  ));

  // 4. Handle Downlink Commands (Mirroring C++ Example)
  mqttClient.commands.listen((cmd) {
    print('Received command from dashboard: ${cmd.action}');
    final raw = cmd.raw as Map<String, dynamic>? ?? {};

    switch (cmd.action) {
      case 'reload_config':
        print('-> Reloading configuration...');
        break;
      case 'write_register':
        print(
            '-> Modbus Write: Slave ${raw['slave'] ?? 1}, Reg ${raw['register'] ?? 0} = ${raw['value'] ?? 0}');
        break;
      case 'read_register':
        print(
            '-> Modbus Read: Slave ${raw['slave'] ?? 1}, Reg ${raw['register'] ?? 0}, Count ${raw['value'] ?? 1}');
        break;
      case 'trigger_ota':
        print('-> Trigger OTA Update from: ${raw['url'] ?? 'unknown'}');
        break;
      case 'custom':
        final custom = raw['custom'] as Map<String, dynamic>? ?? {};
        if (custom.containsKey('valve'))
          print(
              '-> Toggle Switch/Valve: ${custom['valve'] != 0 ? 'ON' : 'OFF'}');
        if (custom.containsKey('dimmer'))
          print('-> Dimmer Level: ${custom['dimmer']}%');
        if (custom.containsKey('color'))
          print('-> Set RGB Color: ${custom['color']}');
        if (custom.containsKey('lock'))
          print('-> Electronic Lock: ${custom['lock']}');
        if (custom.containsKey('ir_blaster'))
          print('-> Blast IR Code: ${custom['ir_blaster']}');
        if (custom.containsKey('ptz')) {
          final ptz = custom['ptz'] as Map<String, dynamic>? ?? {};
          print(
              '-> PTZ Camera Move to X:${ptz['pan'] ?? 0}, Y:${ptz['tilt'] ?? 0}');
        }
        if (custom.containsKey('display'))
          print('-> LCD Display Text: ${custom['display']}');
        if (custom.containsKey('calibrate')) {
          final cal = custom['calibrate'] as Map<String, dynamic>? ?? {};
          print(
              '-> Sensor Calibration [${cal['type'] ?? 'unknown'}]: ${cal['value'] ?? 0}');
        }
        break;
    }
  });

  await mqttClient.connect();
  print('Configuration applied. Polling every $pollIntervalSecs seconds');

  // 5. Simulate Button Polling Loop
  Timer.periodic(Duration(seconds: pollIntervalSecs), (timer) {
    print('[HARDWARE] Button pressed! Publishing telemetry...');
    mqttClient.publishReadings([
      Iot26Reading(
        sensorId: buttonSensorId,
        value: 1.0,
        unit: 'click',
      )
    ]);
  });
}
