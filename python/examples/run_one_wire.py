"""
Run a 1-Wire gateway (DS18B20 temperature probes).

Usage:
  DEVICE_ID=<uuid> DEVICE_TOKEN=<token> uv run examples/run_one_wire.py

Prerequisites on Raspberry Pi:
  # /boot/config.txt:  dtoverlay=w1-gpio
  # After reboot:      ls /sys/bus/w1/devices/
"""

import logging
import os

from iot26_edge import IoT26Gateway
from iot26_edge.protocols import OneWireDriver

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")

driver = OneWireDriver(bus_path=os.environ.get("W1_BUS", "/sys/bus/w1/devices"))

# Print detected probes at startup
driver.connect()
probes = driver.list_devices()
print(f"Detected 1-Wire probes: {probes}")

gw = IoT26Gateway(
    device_id    = os.environ["DEVICE_ID"],
    device_token = os.environ["DEVICE_TOKEN"],
    api_base     = os.environ.get("IOT26_API",   "http://localhost:8443"),
    mqtt_broker  = os.environ.get("MQTT_BROKER", "localhost"),
    driver       = driver,
    poll_interval= 10,
)
gw.run()
