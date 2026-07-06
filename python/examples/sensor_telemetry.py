"""
Normal Sensor Telemetry — Python SDK Example
============================================

This example shows how to publish continuous numeric sensor readings to IoT26.
These are "display-only" sensors — they have no UI control buttons. The IoT26
dashboard shows them as charts, gauges, or value tiles.

Common sensor types:

  ┌─────────────────────┬──────────┬──────────────────────────────────────┐
  │ Sensor Type         │ Unit     │ Notes                                │
  ├─────────────────────┼──────────┼──────────────────────────────────────┤
  │ Flow rate           │ L/min    │ Water / gas flow meters              │
  │ Temperature         │ °C / °F  │ DS18B20, NTC, thermocouples          │
  │ Humidity            │ %RH      │ DHT11/22, SHT31                      │
  │ Pressure            │ Pa / bar │ BMP280, MPX5500                      │
  │ Water level         │ mm / %   │ Ultrasonic, float switch             │
  │ Energy (power)      │ W / kW   │ CT clamp, PZEM-004T                  │
  │ Total energy        │ kWh      │ Cumulative energy meter              │
  │ CO₂ / Gas           │ ppm      │ MQ-135, SCD40                        │
  │ Soil moisture       │ %        │ Capacitive soil sensors              │
  │ Lux / UV            │ lux      │ BH1750, VEML6070                     │
  │ pH                  │ pH       │ Analog pH probe                      │
  │ Turbidity           │ NTU      │ Water quality sensors                │
  └─────────────────────┴──────────┴──────────────────────────────────────┘

No metadata_json is needed for pure numeric sensors.

Usage:
    pip install iot26-edge
    IOT26_DEVICE_ID=<uuid> IOT26_DEVICE_TOKEN=<token> python sensor_telemetry.py
"""

import logging
import math
import os
import time
import random
from iot26_edge.client import IoT26Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sensor_telemetry")

# ── Configuration ────────────────────────────────────────────────────────────

DEVICE_ID    = os.environ.get("IOT26_DEVICE_ID",    "your-device-uuid")
DEVICE_TOKEN = os.environ.get("IOT26_DEVICE_TOKEN", "your-device-token")
MQTT_BROKER  = os.environ.get("IOT26_BROKER",       "localhost")
API_BASE     = os.environ.get("IOT26_API_BASE",      "http://localhost:8443")

# ── Sensor IDs — replace with UUIDs from your IoT26 sensor config ───────────
# Find these in your IoT26 dashboard under the device's sensor list.

SENSOR_FLOW_RATE    = "flow-rate-sensor-uuid"    # L/min  — water/gas flow meter
SENSOR_TEMPERATURE  = "temperature-sensor-uuid"  # °C     — ambient temperature
SENSOR_HUMIDITY     = "humidity-sensor-uuid"     # %RH    — relative humidity
SENSOR_PRESSURE     = "pressure-sensor-uuid"     # Pa     — atmospheric/pipe pressure
SENSOR_WATER_LEVEL  = "water-level-sensor-uuid"  # mm     — tank water level
SENSOR_POWER        = "power-sensor-uuid"        # W      — real-time power draw
SENSOR_ENERGY       = "energy-sensor-uuid"       # kWh    — cumulative energy
SENSOR_CO2          = "co2-sensor-uuid"          # ppm    — CO₂ concentration
SENSOR_SOIL         = "soil-moisture-sensor-uuid"# %      — soil moisture
SENSOR_PH           = "ph-sensor-uuid"           # pH     — water pH

POLL_INTERVAL_S = 5  # publish every 5 seconds


# ── Simulated hardware reads (replace with real sensor driver calls) ─────────

_t = 0  # time counter for synthetic waveforms

def read_flow_rate() -> float:
    """Water flow rate in L/min. Simulate a steady flow with noise."""
    return round(12.5 + random.gauss(0, 0.3), 2)

def read_temperature() -> float:
    """Ambient temperature in °C. Simulate a slow sine wave."""
    global _t
    return round(25.0 + 3.0 * math.sin(_t / 60.0), 2)

def read_humidity() -> float:
    """Relative humidity in %RH."""
    return round(60.0 + random.gauss(0, 1.5), 1)

def read_pressure() -> float:
    """Atmospheric pressure in Pa. Simulate small fluctuations."""
    return round(101325 + random.gauss(0, 50), 0)

def read_water_level() -> float:
    """Water tank level in mm (0 = empty, 1000 = full)."""
    return round(750 + random.gauss(0, 5), 1)

def read_power() -> float:
    """Real-time power draw in Watts."""
    return round(250.0 + random.gauss(0, 10), 1)

def read_energy(total_kwh: float) -> float:
    """Cumulative energy in kWh — increment each interval."""
    return round(total_kwh + (read_power() / 1000.0) * (POLL_INTERVAL_S / 3600.0), 4)

def read_co2() -> float:
    """CO₂ concentration in ppm. Normal outdoor air ~415 ppm."""
    return round(450 + random.gauss(0, 20), 0)

def read_soil_moisture() -> float:
    """Soil moisture in %. 0 = dry, 100 = saturated."""
    return round(45.0 + random.gauss(0, 2), 1)

def read_ph() -> float:
    """Water pH. 7.0 = neutral, typical tap water 6.5–8.5."""
    return round(7.2 + random.gauss(0, 0.05), 2)


# ── Main publish loop ────────────────────────────────────────────────────────

def main():
    client = IoT26Client(
        device_id=DEVICE_ID,
        device_token=DEVICE_TOKEN,
        api_base=API_BASE,
        mqtt_broker=MQTT_BROKER,
        mqtt_port=1883,
    )

    client.connect_mqtt()
    time.sleep(1.5)  # wait for MQTT handshake

    log.info("Connected. Publishing sensor telemetry every %ds. Ctrl+C to stop.", POLL_INTERVAL_S)

    global _t
    total_energy_kwh = 1234.5  # starting cumulative energy value

    try:
        while True:
            _t += POLL_INTERVAL_S

            flow   = read_flow_rate()
            temp   = read_temperature()
            hum    = read_humidity()
            pres   = read_pressure()
            level  = read_water_level()
            power  = read_power()
            energy = read_energy(total_energy_kwh)
            co2    = read_co2()
            soil   = read_soil_moisture()
            ph     = read_ph()

            total_energy_kwh = energy

            # ── Publish all readings in one batch ────────────────────────────
            # No metadata_json needed for pure numeric sensors.
            # The dashboard will display these as charts / gauges / value tiles.
            client.publish_batch([
                {"sensor_id": SENSOR_FLOW_RATE,   "value": flow,   "unit": "L/min"},
                {"sensor_id": SENSOR_TEMPERATURE,  "value": temp,   "unit": "°C"},
                {"sensor_id": SENSOR_HUMIDITY,     "value": hum,    "unit": "%RH"},
                {"sensor_id": SENSOR_PRESSURE,     "value": pres,   "unit": "Pa"},
                {"sensor_id": SENSOR_WATER_LEVEL,  "value": level,  "unit": "mm"},
                {"sensor_id": SENSOR_POWER,        "value": power,  "unit": "W"},
                {"sensor_id": SENSOR_ENERGY,       "value": energy, "unit": "kWh"},
                {"sensor_id": SENSOR_CO2,          "value": co2,    "unit": "ppm"},
                {"sensor_id": SENSOR_SOIL,         "value": soil,   "unit": "%"},
                {"sensor_id": SENSOR_PH,           "value": ph,     "unit": "pH"},
            ])

            log.info(
                "flow=%.1f L/min  temp=%.1f°C  hum=%.0f%%RH  level=%.0fmm  "
                "power=%.0fW  energy=%.3fkWh  CO₂=%.0fppm  soil=%.0f%%  pH=%.2f",
                flow, temp, hum, level, power, energy, co2, soil, ph
            )

            time.sleep(POLL_INTERVAL_S)

    except KeyboardInterrupt:
        log.info("Shutting down.")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
