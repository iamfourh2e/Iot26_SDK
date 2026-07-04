"""
MQTT Direct driver.

For sensors that publish directly to MQTT (ESP32, commercial nodes).
This driver subscribes to the sensor's topic and extracts the value via json_path.

Because readings arrive asynchronously, the driver caches the latest value per
topic and read() returns the most recent cached value.

channel_props keys:
  mqtt_sub_topic  str   Full MQTT topic to subscribe to
  json_path       str   Dot-separated key path into JSON payload, e.g. 'sensors.flow'
                        Leave empty to treat the whole payload as a number.
  value_type      str   'float' | 'int' | 'bool' | 'string'  (default 'float')

Device-level connection_props:
  broker        str   MQTT broker host (falls back to IoT26Client broker)
  topic_prefix  str   Shared prefix for all subscriptions (optional)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from .base import ProtocolDriver
from ..client import DeviceChannel

log = logging.getLogger(__name__)


class MQTTDirectDriver(ProtocolDriver):
    """
    MQTT Direct driver — subscribe, cache last value, return on read().

    Args:
        broker:   MQTT broker host
        port:     MQTT broker port
        client_id: Unique MQTT client ID
        keepalive: Keepalive interval in seconds
    """

    def __init__(
        self,
        broker:    str = "localhost",
        port:      int = 1883,
        client_id: str = "iot26-mqtt-direct",
        keepalive: int = 60,
    ) -> None:
        try:
            import paho.mqtt.client as mqtt_mod
            self._mqtt_mod = mqtt_mod
        except ImportError:
            raise ImportError("Install paho-mqtt: pip install paho-mqtt")

        self._broker    = broker
        self._port      = port
        self._client_id = client_id
        self._keepalive = keepalive

        self._cache: dict[str, float | None] = {}   # topic → latest value
        self._lock  = threading.Lock()
        self._mqttc = None

    def connect(self) -> None:
        self._mqttc = self._mqtt_mod.Client(
            self._mqtt_mod.CallbackAPIVersion.VERSION2, client_id=self._client_id,
        )
        self._mqttc.on_connect    = self._on_connect
        self._mqttc.on_message    = self._on_message
        self._mqttc.on_disconnect = self._on_disconnect
        self._mqttc.connect(self._broker, self._port, keepalive=self._keepalive)
        self._mqttc.loop_start()
        log.info("MQTT Direct driver connecting → %s:%d", self._broker, self._port)

    def subscribe_channel(self, channel: DeviceChannel) -> None:
        """Subscribe to a channel's topic. Call after connect()."""
        topic = channel.props.get("mqtt_sub_topic", "")
        if not topic:
            log.warning("Channel %r has no mqtt_sub_topic", channel.name)
            return
        if self._mqttc and self._mqttc.is_connected():
            self._mqttc.subscribe(topic, qos=0)
            log.info("Subscribed MQTT Direct → %s", topic)
        with self._lock:
            self._cache.setdefault(topic, None)

    def read(self, channel: DeviceChannel) -> float | None:
        """Return the most recently received value for this channel, or None."""
        topic = channel.props.get("mqtt_sub_topic", "")
        with self._lock:
            return self._cache.get(topic)

    def close(self) -> None:
        if self._mqttc:
            self._mqttc.loop_stop()
            self._mqttc.disconnect()

    # ── MQTT callbacks ────────────────────────────────────────────────────────

    def _on_connect(self, client, *_args) -> None:
        # Re-subscribe on reconnect
        with self._lock:
            for topic in self._cache:
                client.subscribe(topic, qos=0)

    def _on_disconnect(self, *_args) -> None:
        log.warning("MQTT Direct broker disconnected — will auto-reconnect")

    def _on_message(self, _client, _ud, msg) -> None:
        topic = msg.topic
        try:
            value = self._extract(msg.payload)
            with self._lock:
                self._cache[topic] = value
            log.debug("MQTT Direct %s → %s", topic, value)
        except Exception as e:
            log.error("Failed to extract value from %s: %s", topic, e)

    def _extract(self, payload: bytes) -> float | None:
        """Parse payload and extract value via json_path."""
        # Try JSON first
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Plain numeric payload
            return float(payload.decode().strip())

        # Find the subscribed channel to know json_path
        # (We do a reverse lookup — this is called inside on_message)
        # Return raw dict; caller must use extract_value() after read() if they want json_path.
        # Actual extraction happens per-channel in the driver below.
        return None  # raw data stored; processed in extract_from_dict

    @staticmethod
    def extract_value(raw: Any, json_path: str, value_type: str = "float") -> float | None:
        """
        Extract a leaf from a nested dict using dot-notation json_path.

        Example: extract_value({"sensors": {"flow": 42.5}}, "sensors.flow") → 42.5
        """
        if raw is None:
            return None
        try:
            if not json_path:
                return float(raw)
            obj = raw
            for key in json_path.split("."):
                obj = obj[key]
            if value_type == "bool":
                return 1.0 if obj else 0.0
            return float(obj)
        except (KeyError, TypeError, ValueError) as e:
            log.error("json_path %r extraction failed: %s", json_path, e)
            return None


class MQTTDirectDriverFull(MQTTDirectDriver):
    """
    Extended version that stores the full parsed JSON payload per topic
    so per-channel json_path extraction works correctly in read().
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._raw_cache: dict[str, Any] = {}

    def _on_message(self, _client, _ud, msg) -> None:
        topic = msg.topic
        try:
            data = json.loads(msg.payload)
        except Exception:
            try:
                data = float(msg.payload.decode().strip())
            except Exception:
                log.error("Cannot parse payload on %s", topic)
                return
        with self._lock:
            self._raw_cache[topic] = data

    def read(self, channel: DeviceChannel) -> float | None:
        cp        = channel.props
        topic     = cp.get("mqtt_sub_topic", "")
        json_path = cp.get("json_path", "")
        vtype     = cp.get("value_type", "float")

        with self._lock:
            raw = self._raw_cache.get(topic)
        return MQTTDirectDriver.extract_value(raw, json_path, vtype)
