"""
Run a Modbus RTU (RS-485 serial) gateway.

Usage:
  DEVICE_ID=<uuid> DEVICE_TOKEN=<token> \
  SERIAL_PORT=/dev/ttyUSB0 BAUD=9600 \
  uv run examples/run_modbus_rtu.py
"""

import logging
import os

from iot26_edge import IoT26Gateway
from iot26_edge.protocols import ModbusRTUDriver

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")

gw = IoT26Gateway(
    device_id    = os.environ["DEVICE_ID"],
    device_token = os.environ["DEVICE_TOKEN"],
    api_base     = os.environ.get("IOT26_API",   "http://localhost:8443"),
    mqtt_broker  = os.environ.get("MQTT_BROKER", "localhost"),
    driver = ModbusRTUDriver(
        port     = os.environ.get("SERIAL_PORT", "/dev/ttyUSB0"),
        baudrate = int(os.environ.get("BAUD", "9600")),
        parity   = os.environ.get("PARITY", "N"),
        stopbits = int(os.environ.get("STOP_BITS", "1")),
        timeout  = 1.0,
    ),
)
gw.run()
