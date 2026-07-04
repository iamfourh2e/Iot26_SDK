/// IoT26 Dart/Flutter client library.
///
/// Exports [Iot26Client] as the primary high-level API, plus
/// [Iot26Reading], [Iot26Command], [Iot26Config] for type usage.
///
/// Example:
/// ```dart
/// import 'package:iot26_client/iot26_client.dart';
///
/// final client = Iot26Client(Iot26Config(
///   deviceId:    'your-device-uuid',
///   deviceToken: 'eyJhbGci...',
///   broker:      'your-broker.com',
/// ));
///
/// await client.connect();
/// client.commands.listen((cmd) => print('Command: ${cmd.action}'));
///
/// await client.publishReadings([
///   Iot26Reading(sensorId: 'sensor-uuid', value: 23.5, unit: '°C'),
/// ]);
/// ```
library iot26_client;

import 'dart:async';

import 'src/iot26_mqtt.dart';

export 'src/iot26_models.dart';
export 'src/iot26_mqtt.dart' show Iot26Config;

/// High-level IoT26 client for Dart/Flutter.
///
/// Wraps [Iot26MqttTransport] with a friendly API including:
/// - [connect] / [disconnect]
/// - [publishReadings]
/// - [commands] stream
/// - [startPublishLoop] for periodic publishing
class Iot26Client {
  final Iot26MqttTransport _transport;

  /// Stream of [Iot26Command] objects received from IoT26.
  ///
  /// Subscribe to this stream to handle downlink commands:
  /// ```dart
  /// client.commands.listen((cmd) {
  ///   if (cmd.action == 'restart') { /* ... */ }
  /// });
  /// ```
  Stream<Iot26Command> get commands => _transport.commands;

  /// Create a new [Iot26Client] from the given [config].
  Iot26Client(Iot26Config config) : _transport = Iot26MqttTransport(config);

  /// Connect to the MQTT broker. Must be awaited before publishing.
  Future<void> connect() => _transport.connect();

  /// Publish a batch of [readings] to IoT26.
  ///
  /// Throws if not connected.
  Future<void> publishReadings(List<Iot26Reading> readings) =>
      _transport.publish(readings);

  /// Disconnect from the broker and close the [commands] stream.
  void disconnect() => _transport.disconnect();

  /// Start a periodic publish loop.
  ///
  /// Calls [readingsFn] on each tick and publishes the returned readings.
  /// Returns a [Timer] that can be cancelled with [Timer.cancel].
  ///
  /// Example:
  /// ```dart
  /// final timer = client.startPublishLoop(
  ///   interval: const Duration(seconds: 10),
  ///   readingsFn: () => [Iot26Reading(...)],
  /// );
  ///
  /// // Later:
  /// timer.cancel();
  /// ```
  Timer startPublishLoop({
    required Duration interval,
    required List<Iot26Reading> Function() readingsFn,
    void Function(Object error)? onError,
  }) {
    return Timer.periodic(interval, (_) async {
      try {
        await publishReadings(readingsFn());
      } catch (e) {
        if (onError != null) {
          onError(e);
        } else {
          // ignore: avoid_print
          print('[IoT26] Publish error: $e');
        }
      }
    });
  }
}
