"""
Run an I²C gateway (BME280 / any I²C sensor).

Usage:
  DEVICE_ID=<uuid> DEVICE_TOKEN=<token> \
  I2C_BUS=1 I2C_ADDR=0x76 \
  uv run examples/run_i2c.py
"""

import logging
import os

from iot26_edge import IoT26Gateway
from iot26_edge.protocols import I2CDriver

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")

gw = IoT26Gateway(
    device_id    = os.environ["DEVICE_ID"],
    device_token = os.environ["DEVICE_TOKEN"],
    api_base     = os.environ.get("IOT26_API",   "http://localhost:8443"),
    mqtt_broker  = os.environ.get("MQTT_BROKER", "localhost"),
    driver = I2CDriver(
        bus            = int(os.environ.get("I2C_BUS",  "1")),
        device_address = os.environ.get("I2C_ADDR", "0x76"),
    ),
)
gw.run()
