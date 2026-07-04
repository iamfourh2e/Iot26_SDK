/// IoT26 MQTT transport layer for Dart/Flutter.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:mqtt_client/mqtt_client.dart';
import 'package:mqtt_client/mqtt_server_client.dart';

import 'iot26_models.dart';

export 'iot26_models.dart';

/// Configuration for [Iot26MqttTransport].
class Iot26Config {
  /// Device UUID from IoT26 dashboard.
  final String deviceId;

  /// Device JWT / API token from IoT26 dashboard.
  final String deviceToken;

  /// MQTT broker hostname (no scheme, no port).
  final String broker;

  /// MQTT broker port. Defaults to 1883. Use 8883 for MQTTS.
  final int port;

  /// If true, uses a secure (TLS) connection.
  final bool useTls;

  /// Optional SecurityContext for custom CA certificates.
  final SecurityContext? securityContext;

  /// Keep-alive interval in seconds (default 60).
  final int keepAlive;

  /// Whether to log debug information to the console.
  final bool debug;

  const Iot26Config({
    required this.deviceId,
    required this.deviceToken,
    required this.broker,
    this.port = 1883,
    this.useTls = false,
    this.securityContext,
    this.keepAlive = 60,
    this.debug = false,
  });
}

/// Low-level MQTT transport — used internally by [Iot26Client].
/// You can use this class directly if you need fine-grained control.
class Iot26MqttTransport {
  final Iot26Config _cfg;
  late final MqttServerClient _client;

  /// Stream of downlink [Iot26Command] objects.
  final StreamController<Iot26Command> _commandController =
      StreamController<Iot26Command>.broadcast();

  Stream<Iot26Command> get commands => _commandController.stream;

  String get _ingestTopic  => 'devices/${_cfg.deviceId}/ingest';
  String get _commandTopic => 'devices/${_cfg.deviceId}/commands';

  Iot26MqttTransport(this._cfg) {
    final clientId = 'iot26-dart-${_cfg.deviceId.substring(0, 8)}'
        '-${DateTime.now().millisecondsSinceEpoch}';

    _client = MqttServerClient.withPort(_cfg.broker, clientId, _cfg.port)
      ..keepAlivePeriod = _cfg.keepAlive
      ..autoReconnect   = true
      ..logging(on: _cfg.debug)
      ..onConnected          = _onConnected
      ..onDisconnected       = _onDisconnected
      ..onAutoReconnected    = _onAutoReconnected;

    if (_cfg.useTls) {
      _client.secure = true;
      if (_cfg.securityContext != null) {
        _client.securityContext = _cfg.securityContext!;
      }
    }
  }

  /// Connect to the MQTT broker.
  Future<void> connect() async {
    _log('Connecting to ${_cfg.broker}:${_cfg.port}');

    final connMsg = MqttConnectMessage()
        .withClientIdentifier(_client.clientIdentifier)
        .startClean();
    _client.connectionMessage = connMsg;

    final status = await _client.connect();
    if (status?.state != MqttConnectionState.connected) {
      throw Exception('IoT26: MQTT connect failed — state: ${status?.state}');
    }

    // Subscribe to commands
    _client.subscribe(_commandTopic, MqttQos.atLeastOnce);

    // Route incoming messages
    _client.updates?.listen(_onMessage);
  }

  /// Publish a batch of readings.
  Future<void> publish(List<Iot26Reading> readings) async {
    if (readings.isEmpty) return;
    if (_client.connectionStatus?.state != MqttConnectionState.connected) {
      throw Exception('IoT26: not connected');
    }

    final payload = jsonEncode({
      'token':    _cfg.deviceToken,
      'readings': readings.map((r) => r.toJson()).toList(),
    });

    final builder = MqttClientPayloadBuilder()..addString(payload);
    _client.publishMessage(
      _ingestTopic,
      MqttQos.atLeastOnce,
      builder.payload!,
      retain: false,
    );
    _log('Published ${readings.length} reading(s) → $_ingestTopic');
  }

  /// Cleanly disconnect from the broker.
  void disconnect() {
    _client.disconnect();
    _commandController.close();
  }

  // ── MQTT callbacks ──────────────────────────────────────────────────────────

  void _onConnected() {
    _log('Connected to broker');
  }

  void _onDisconnected() {
    _log('Disconnected from broker — will auto-reconnect');
  }

  void _onAutoReconnected() {
    _log('Auto-reconnected. Re-subscribing to $_commandTopic');
    _client.subscribe(_commandTopic, MqttQos.atLeastOnce);
  }

  void _onMessage(List<MqttReceivedMessage<MqttMessage>> messages) {
    for (final msg in messages) {
      if (msg.topic != _commandTopic) continue;
      final pubMsg = msg.payload as MqttPublishMessage;
      final raw    = MqttPublishPayload.bytesToStringAsString(pubMsg.payload.message);
      try {
        final json = jsonDecode(raw) as Map<String, dynamic>;
        final cmd  = Iot26Command.fromJson(json);
        _log('Command received: action=${cmd.action}');
        _commandController.add(cmd);
      } catch (e) {
        _log('Command parse error: $e');
      }
    }
  }

  void _log(String msg) {
    if (_cfg.debug) print('[IoT26] $msg');
  }
}
