"""
IoT26 API + MQTT client.

Handles:
- Fetching device / channel config from the IoT26 REST API
- Publishing batch readings to the MQTT ingest topic
- Subscribing to downlink commands
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable

import paho.mqtt.client as mqtt
import requests

log = logging.getLogger(__name__)


class DeviceChannel:
    """One sensor channel attached to a device, parsed from API response."""

    def __init__(self, sensor_id: str, name: str, channel_props: dict[str, Any]) -> None:
        self.sensor_id     = sensor_id
        self.name          = name
        self.props         = channel_props

        # Universal decode fields
        self.scale_factor  = float(channel_props.get("scale_factor", channel_props.get("scale", 1.0)))
        self.offset        = float(channel_props.get("offset", 0.0))
        self.unit          = channel_props.get("unit", "")
        self.enabled       = channel_props.get("enabled", True)

    def apply_scale(self, raw: float) -> float:
        """Apply scale_factor + offset: final = raw × scale_factor + offset."""
        return raw * self.scale_factor + self.offset

    def __repr__(self) -> str:
        return f"<DeviceChannel {self.name!r} unit={self.unit!r}>"


class IoT26Client:
    """
    Combines the IoT26 REST API (channel config) and MQTT publisher
    (batch ingest + downlink commands).
    """

    def __init__(
        self,
        device_id:    str,
        device_token: str,
        api_base:     str = "http://localhost:8443",
        mqtt_broker:  str = "localhost",
        mqtt_port:    int = 1883,
    ) -> None:
        self.device_id    = device_id
        self.device_token = device_token
        self.api_base     = api_base.rstrip("/")
        self.mqtt_broker  = mqtt_broker
        self.mqtt_port    = mqtt_port

        self._mqttc: mqtt.Client | None = None
        self._command_callbacks: list[Callable[[dict], None]] = []

    # ── REST ─────────────────────────────────────────────────────────────────

    def fetch_channels(self) -> list[DeviceChannel]:
        """Pull device config from IoT26 API and return parsed channels."""
        url = f"{self.api_base}/v1/devices/{self.device_id}"
        r = requests.get(
            url,
            headers={"Authorization": f"Bearer {self.device_token}"},
            timeout=15,
        )
        r.raise_for_status()
        data    = r.json()
        sensors = data.get("sensors", [])

        channels: list[DeviceChannel] = []
        for s in sensors:
            cp = s.get("channel_props") or {}
            ch = DeviceChannel(
                sensor_id    = s["sensor_id"],
                name         = s.get("name", s["sensor_id"]),
                channel_props= cp,
            )
            if ch.enabled:
                channels.append(ch)
            else:
                log.debug("Channel %r disabled, skipping", ch.name)

        log.info("Fetched %d active channels from IoT26", len(channels))
        return channels

    def fetch_poll_interval(self) -> int:
        """Return device poll_interval_seconds from API (default 5)."""
        url = f"{self.api_base}/v1/devices/{self.device_id}"
        try:
            r = requests.get(url, headers={"Authorization": f"Bearer {self.device_token}"}, timeout=10)
            r.raise_for_status()
            return int(r.json().get("poll_interval_seconds", 5))
        except Exception:
            return 5

    # ── MQTT ─────────────────────────────────────────────────────────────────

    def connect_mqtt(self) -> None:
        """Connect to the MQTT broker and start the background loop."""
        client_id = f"iot26-edge-{self.device_id[:8]}"
        self._mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self._mqttc.on_connect    = self._on_connect
        self._mqttc.on_disconnect = self._on_disconnect
        self._mqttc.on_message    = self._on_message

        self._mqttc.connect(self.mqtt_broker, self.mqtt_port, keepalive=60)
        self._mqttc.loop_start()
        log.info("MQTT connecting → %s:%d", self.mqtt_broker, self.mqtt_port)

    def publish_batch(self, readings: list[dict[str, Any]]) -> None:
        """
        Publish a batch of readings to devices/{device_id}/ingest.

        Each reading: {"sensor_id": str, "value": float, "unit": str}
        """
        if not readings:
            return
        if self._mqttc is None or not self._mqttc.is_connected():
            log.warning("MQTT not connected — dropping %d readings", len(readings))
            return

        topic   = f"devices/{self.device_id}/ingest"
        payload = json.dumps({
            "token":    self.device_token,
            "readings": readings,
        })
        info = self._mqttc.publish(topic, payload, qos=1)
        info.wait_for_publish(timeout=5)
        log.info("⬆ Published %d readings → %s", len(readings), topic)

    def on_command(self, callback: Callable[[dict], None]) -> None:
        """Register a callback for downlink commands received from the server."""
        self._command_callbacks.append(callback)

    def disconnect(self) -> None:
        if self._mqttc:
            self._mqttc.loop_stop()
            self._mqttc.disconnect()

    # ── MQTT callbacks ────────────────────────────────────────────────────────

    def _on_connect(self, client: mqtt.Client, *_args) -> None:
        topic = f"devices/{self.device_id}/commands"
        client.subscribe(topic, qos=1)
        log.info("MQTT connected. Subscribed to %s", topic)

    def _on_disconnect(self, _client, _ud, _flags, rc, *_args) -> None:
        log.warning("MQTT disconnected rc=%s — will auto-reconnect", rc)

    def _on_message(self, _client, _ud, msg: mqtt.MQTTMessage) -> None:
        try:
            cmd = json.loads(msg.payload)
            log.info("⬇ Command received: %s", cmd)
            for cb in self._command_callbacks:
                cb(cmd)
        except Exception as e:
            log.error("Failed to parse command: %s", e)
