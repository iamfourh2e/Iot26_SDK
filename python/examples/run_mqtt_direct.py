"""
Run an MQTT Direct gateway (ESP32 / commercial nodes that self-publish).

Usage:
  DEVICE_ID=<uuid> DEVICE_TOKEN=<token> \
  MQTT_BROKER=localhost \
  uv run examples/run_mqtt_direct.py

No polling loop needed — the driver subscribes to sensor topics
and caches the latest value for each. The gateway publishes
batch readings to IoT26 on its own poll interval.
"""

import logging
import os

from iot26_edge import IoT26Gateway
from iot26_edge.protocols import MQTTDirectDriver

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")

broker = os.environ.get("MQTT_BROKER", "localhost")

gw = IoT26Gateway(
    device_id    = os.environ["DEVICE_ID"],
    device_token = os.environ["DEVICE_TOKEN"],
    api_base     = os.environ.get("IOT26_API", "http://localhost:8443"),
    mqtt_broker  = broker,
    driver       = MQTTDirectDriver(broker=broker, client_id="iot26-direct-gw"),
    poll_interval= 10,   # collect + forward every 10s
)
gw.run()
