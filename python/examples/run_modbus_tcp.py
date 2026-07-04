"""
Run a Modbus TCP gateway against the local simulator.

Usage:
  cd edge
  uv sync --extra modbus
  DEVICE_ID=<uuid> DEVICE_TOKEN=<token> uv run examples/run_modbus_tcp.py
"""

import logging
import os

from iot26_edge import IoT26Gateway
from iot26_edge.protocols import ModbusTCPDriver

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")

gw = IoT26Gateway(
    device_id    = os.environ["DEVICE_ID"],
    device_token = os.environ["DEVICE_TOKEN"],
    api_base     = os.environ.get("IOT26_API",   "http://localhost:8443"),
    mqtt_broker  = os.environ.get("MQTT_BROKER", "localhost"),
    driver = ModbusTCPDriver(
        host    = os.environ.get("MODBUS_HOST", "127.0.0.1"),
        port    = int(os.environ.get("MODBUS_PORT", "5020")),  # simulator port
        timeout = 3.0,
    ),
)
gw.run()
