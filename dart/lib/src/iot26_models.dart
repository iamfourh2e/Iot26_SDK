/// IoT26 Dart/Flutter client library models.
library iot26_client;

/// A single sensor measurement.
class Iot26Reading {
  /// Sensor UUID matching the IoT26 device configuration.
  final String sensorId;

  /// Scaled engineering value.
  final double value;

  /// Unit string, e.g. '°C', '%RH', 'Pa'.
  final String unit;

  const Iot26Reading({
    required this.sensorId,
    required this.value,
    required this.unit,
  });

  Map<String, dynamic> toJson() => {
        'sensor_id': sensorId,
        'value': value,
        'unit': unit,
      };

  @override
  String toString() => 'Iot26Reading($sensorId=$value $unit)';
}

/// A downlink command received from IoT26.
class Iot26Command {
  /// Command action, e.g. 'reload_config', 'restart', 'set_poll_interval'.
  final String action;

  /// Full parsed JSON payload for action-specific fields.
  final Map<String, dynamic> raw;

  const Iot26Command({required this.action, required this.raw});

  factory Iot26Command.fromJson(Map<String, dynamic> json) =>
      Iot26Command(action: json['action'] as String? ?? '', raw: json);

  @override
  String toString() => 'Iot26Command(action=$action)';
}
