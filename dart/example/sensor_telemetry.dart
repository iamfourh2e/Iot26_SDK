/// Normal Sensor Telemetry — Dart SDK Example
///
/// Shows how to publish continuous numeric sensor readings (flow, temperature,
/// humidity, pressure, water level, power, energy, CO₂, soil moisture, pH)
/// to IoT26. These are "display-only" sensors shown as charts, gauges, and
/// value tiles. No metadataJson is needed.
///
/// Common sensor types:
///   Flow rate     L/min  — water/gas flow meters
///   Temperature   °C     — DS18B20, NTC, thermocouples
///   Humidity      %RH    — DHT22, SHT31
///   Pressure      Pa     — BMP280, MPX5500
///   Water level   mm     — ultrasonic, float switch
///   Power         W      — CT clamp, PZEM-004T
///   Energy        kWh    — cumulative energy meter
///   CO₂ / gas     ppm    — MQ-135, SCD40
///   Soil moisture %      — capacitive soil sensor
///   pH            pH     — analog pH probe
///
/// Usage:
///   dart run example/sensor_telemetry.dart

import 'dart:async';
import 'dart:io';
import 'dart:math';
import '../lib/iot26_client.dart';

// ── Sensor IDs — replace with UUIDs from your IoT26 sensor config ─────────────

const sensorFlowRate    = 'flow-rate-sensor-uuid';     // L/min
const sensorTemperature = 'temperature-sensor-uuid';   // °C
const sensorHumidity    = 'humidity-sensor-uuid';      // %RH
const sensorPressure    = 'pressure-sensor-uuid';      // Pa
const sensorWaterLevel  = 'water-level-sensor-uuid';   // mm
const sensorPower       = 'power-sensor-uuid';         // W
const sensorEnergy      = 'energy-sensor-uuid';        // kWh
const sensorCO2         = 'co2-sensor-uuid';           // ppm
const sensorSoil        = 'soil-moisture-sensor-uuid'; // %
const sensorPH          = 'ph-sensor-uuid';            // pH

const pollInterval = Duration(seconds: 5);

// ── Simulated hardware reads (replace with real sensor driver calls) ───────────

final _rng = Random();
double _tick = 0;
double _totalEnergyKWh = 1234.5;

double _gauss(double mean, double std) {
  // Box–Muller approximation
  double u = 0, v = 0;
  while (u == 0) u = _rng.nextDouble();
  while (v == 0) v = _rng.nextDouble();
  return mean + std * sqrt(-2.0 * log(u)) * cos(2.0 * pi * v);
}

double _round(double v, int d) {
  final p = pow(10, d);
  return (v * p).roundToDouble() / p;
}

double readFlowRate()     => _round(_gauss(12.5, 0.3), 2);
double readTemperature()  => _round(25.0 + 3.0 * sin(_tick / 60.0), 2);
double readHumidity()     => _round(_gauss(60.0, 1.5), 1);
double readPressure()     => _round(_gauss(101325, 50), 0);
double readWaterLevel()   => _round(_gauss(750, 5), 1);
double readPower()        => _round(_gauss(250.0, 10), 1);
double readCO2()          => _round(_gauss(450, 20), 0);
double readSoilMoisture() => _round(_gauss(45.0, 2), 1);
double readPH()           => _round(_gauss(7.2, 0.05), 2);

double incrementEnergy(double power) {
  final deltaKWh = power / 1000.0 * (pollInterval.inSeconds / 3600.0);
  return _round(_totalEnergyKWh + deltaKWh, 4);
}

// ── Main ──────────────────────────────────────────────────────────────────────

void main() async {
  final client = Iot26Client(Iot26Config(
    deviceId:    Platform.environment['IOT26_DEVICE_ID']    ?? 'your-device-uuid',
    deviceToken: Platform.environment['IOT26_DEVICE_TOKEN'] ?? 'your-device-token',
    broker:      Platform.environment['IOT26_BROKER']       ?? 'localhost',
    port: 1883,
  ));

  try {
    await client.connect();
    print('✓ Connected to IoT26 MQTT broker');
    print('Publishing sensor telemetry every ${pollInterval.inSeconds}s. Ctrl+C to stop.');
  } catch (e) {
    print('✗ Failed to connect: $e');
    exit(1);
  }

  Timer.periodic(pollInterval, (_) {
    _tick += pollInterval.inSeconds;

    final flow   = readFlowRate();
    final temp   = readTemperature();
    final hum    = readHumidity();
    final pres   = readPressure();
    final level  = readWaterLevel();
    final power  = readPower();
    final energy = incrementEnergy(power);
    final co2    = readCO2();
    final soil   = readSoilMoisture();
    final ph     = readPH();

    _totalEnergyKWh = energy;

    // ── Publish all readings in one batch ──────────────────────────────────
    // No metadataJson needed for pure numeric sensors.
    // The dashboard displays them as charts, gauges, or value tiles.
    client.publishReadings([
      Iot26Reading(sensorId: sensorFlowRate,    value: flow,   unit: 'L/min'),
      Iot26Reading(sensorId: sensorTemperature, value: temp,   unit: '°C'),
      Iot26Reading(sensorId: sensorHumidity,    value: hum,    unit: '%RH'),
      Iot26Reading(sensorId: sensorPressure,    value: pres,   unit: 'Pa'),
      Iot26Reading(sensorId: sensorWaterLevel,  value: level,  unit: 'mm'),
      Iot26Reading(sensorId: sensorPower,       value: power,  unit: 'W'),
      Iot26Reading(sensorId: sensorEnergy,      value: energy, unit: 'kWh'),
      Iot26Reading(sensorId: sensorCO2,         value: co2,    unit: 'ppm'),
      Iot26Reading(sensorId: sensorSoil,        value: soil,   unit: '%'),
      Iot26Reading(sensorId: sensorPH,          value: ph,     unit: 'pH'),
    ]);

    print(
      'flow=$flow L/min  temp=$temp°C  hum=$hum%  level=${level}mm  '
      'power=${power}W  energy=${energy}kWh  CO₂=${co2}ppm  soil=$soil%  pH=$ph'
    );
  });
}
