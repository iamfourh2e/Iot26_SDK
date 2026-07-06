/**
 * Normal Sensor Telemetry — Node.js SDK Example
 *
 * Shows how to publish continuous numeric sensor readings (flow, temperature,
 * humidity, pressure, water level, power, energy, CO₂, soil moisture, pH)
 * to IoT26. These are "display-only" sensors shown as charts, gauges, and
 * value tiles on the dashboard. No metadata_json is needed.
 *
 * Common sensor types:
 *   Flow rate     L/min  — water/gas flow meters
 *   Temperature   °C     — DS18B20, NTC, thermocouples
 *   Humidity      %RH    — DHT22, SHT31
 *   Pressure      Pa     — BMP280, MPX5500
 *   Water level   mm     — ultrasonic, float switch
 *   Power         W      — CT clamp, PZEM-004T
 *   Energy        kWh    — cumulative energy meter
 *   CO₂ / gas     ppm    — MQ-135, SCD40
 *   Soil moisture %      — capacitive soil sensor
 *   pH            pH     — analog pH probe
 *
 * Usage:
 *   IOT26_DEVICE_ID=<uuid> IOT26_DEVICE_TOKEN=<token> node sensor_telemetry.js
 */

'use strict';

const { IoT26Client } = require('./index.js');

// ── Configuration ─────────────────────────────────────────────────────────────

const DEVICE_ID    = process.env.IOT26_DEVICE_ID    || 'your-device-uuid';
const DEVICE_TOKEN = process.env.IOT26_DEVICE_TOKEN || 'your-device-token';
const BROKER       = process.env.IOT26_BROKER       || 'mqtt://localhost:1883';

const POLL_INTERVAL_MS = 5000; // publish every 5 seconds

// ── Sensor IDs — replace with UUIDs from your IoT26 sensor config ─────────────

const SENSOR_FLOW_RATE    = 'flow-rate-sensor-uuid';     // L/min
const SENSOR_TEMPERATURE  = 'temperature-sensor-uuid';   // °C
const SENSOR_HUMIDITY     = 'humidity-sensor-uuid';      // %RH
const SENSOR_PRESSURE     = 'pressure-sensor-uuid';      // Pa
const SENSOR_WATER_LEVEL  = 'water-level-sensor-uuid';   // mm
const SENSOR_POWER        = 'power-sensor-uuid';         // W
const SENSOR_ENERGY       = 'energy-sensor-uuid';        // kWh
const SENSOR_CO2          = 'co2-sensor-uuid';           // ppm
const SENSOR_SOIL         = 'soil-moisture-sensor-uuid'; // %
const SENSOR_PH           = 'ph-sensor-uuid';            // pH

// ── Simulated hardware reads (replace with real sensor driver calls) ───────────

let tick = 0;
let totalEnergyKWh = 1234.5;

const gauss = (mean, std) => mean + std * (Math.random() + Math.random() - 1) * Math.sqrt(6) / 3;
const round = (v, d) => Math.round(v * 10 ** d) / 10 ** d;

function readFlowRate()     { return round(gauss(12.5, 0.3), 2); }
function readTemperature()  { return round(25.0 + 3.0 * Math.sin(tick / 60.0), 2); }
function readHumidity()     { return round(gauss(60.0, 1.5), 1); }
function readPressure()     { return round(gauss(101325, 50), 0); }
function readWaterLevel()   { return round(gauss(750, 5), 1); }
function readPower()        { return round(gauss(250.0, 10), 1); }
function readCO2()          { return round(gauss(450, 20), 0); }
function readSoilMoisture() { return round(gauss(45.0, 2), 1); }
function readPH()           { return round(gauss(7.2, 0.05), 2); }
function incrementEnergy(power) {
  const deltaKWh = (power / 1000.0) * (POLL_INTERVAL_MS / 3_600_000);
  return round(totalEnergyKWh + deltaKWh, 4);
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  const client = new IoT26Client({
    deviceId:    DEVICE_ID,
    deviceToken: DEVICE_TOKEN,
    broker:      BROKER,
  });

  await client.connect();
  console.log('✓ Connected to IoT26 MQTT broker');
  console.log(`Publishing sensor telemetry every ${POLL_INTERVAL_MS / 1000}s. Ctrl+C to stop.`);

  setInterval(async () => {
    tick += POLL_INTERVAL_MS / 1000;

    const flow   = readFlowRate();
    const temp   = readTemperature();
    const hum    = readHumidity();
    const pres   = readPressure();
    const level  = readWaterLevel();
    const power  = readPower();
    const energy = incrementEnergy(power);
    const co2    = readCO2();
    const soil   = readSoilMoisture();
    const ph     = readPH();

    totalEnergyKWh = energy;

    // ── Publish all readings in one batch ──────────────────────────────────
    // No metadataJson needed for pure numeric sensors.
    // The dashboard displays them as charts, gauges, or value tiles.
    await client.publishReadings([
      { sensorId: SENSOR_FLOW_RATE,   value: flow,   unit: 'L/min' },
      { sensorId: SENSOR_TEMPERATURE, value: temp,   unit: '°C' },
      { sensorId: SENSOR_HUMIDITY,    value: hum,    unit: '%RH' },
      { sensorId: SENSOR_PRESSURE,    value: pres,   unit: 'Pa' },
      { sensorId: SENSOR_WATER_LEVEL, value: level,  unit: 'mm' },
      { sensorId: SENSOR_POWER,       value: power,  unit: 'W' },
      { sensorId: SENSOR_ENERGY,      value: energy, unit: 'kWh' },
      { sensorId: SENSOR_CO2,         value: co2,    unit: 'ppm' },
      { sensorId: SENSOR_SOIL,        value: soil,   unit: '%' },
      { sensorId: SENSOR_PH,          value: ph,     unit: 'pH' },
    ]);

    console.log(
      `flow=${flow} L/min  temp=${temp}°C  hum=${hum}%  level=${level}mm  ` +
      `power=${power}W  energy=${energy}kWh  CO₂=${co2}ppm  soil=${soil}%  pH=${ph}`
    );
  }, POLL_INTERVAL_MS);
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
