"""
IoT26 Gateway — orchestrates protocol drivers and MQTT publishing.

Fetches channel config from IoT26 API, dispatches to the correct protocol
driver based on device protocol_type, scales values, and publishes batches.

Usage::

    from iot26_edge import IoT26Gateway
    from iot26_edge.protocols import ModbusTCPDriver

    gw = IoT26Gateway(
        device_id    = "your-device-uuid",
        device_token = "eyJhbGci...",
        api_base     = "http://localhost:8443",
        mqtt_broker  = "localhost",
        driver       = ModbusTCPDriver(host="127.0.0.1", port=5020),
        poll_interval= 5,       # seconds, overrides API value if set
    )
    gw.run()  # blocks forever

Or with auto-detection from API protocol_type::

    gw = IoT26Gateway.from_env()    # reads DEVICE_ID + DEVICE_TOKEN from env
    gw.run()
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from typing import Any

from .client   import IoT26Client, DeviceChannel
from .protocols.base import ProtocolDriver

log = logging.getLogger(__name__)


class IoT26Gateway:
    """
    Main gateway class.

    Args:
        device_id:      Device UUID from IoT26 dashboard
        device_token:   Device JWT token from IoT26 dashboard
        api_base:       IoT26 REST API base URL
        mqtt_broker:    MQTT broker host
        mqtt_port:      MQTT broker port
        driver:         A ``ProtocolDriver`` instance (ModbusTCPDriver, I2CDriver, …)
        poll_interval:  Override poll interval in seconds (None = use API value)
        reload_interval:How often (seconds) to re-fetch channel config (default 300)
    """

    def __init__(
        self,
        device_id:       str,
        device_token:    str,
        driver:          ProtocolDriver,
        api_base:        str = "http://localhost:8443",
        mqtt_broker:     str = "localhost",
        mqtt_port:       int = 1883,
        poll_interval:   int | None = None,
        reload_interval: int = 300,
    ) -> None:
        self.driver          = driver
        self._poll_override  = poll_interval
        self._reload_interval = reload_interval
        self._running        = False

        self.client = IoT26Client(
            device_id    = device_id,
            device_token = device_token,
            api_base     = api_base,
            mqtt_broker  = mqtt_broker,
            mqtt_port    = mqtt_port,
        )
        self.client.on_command(self._handle_command)

        self._channels: list[DeviceChannel] = []
        self._last_reload = 0.0

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the gateway. Blocks until SIGINT/SIGTERM or stop() is called."""
        _setup_signals(self.stop)
        self._running = True

        log.info("IoT26 Gateway starting up")
        self._reload_channels()

        self._connect_driver_with_retry()
        self.client.connect_mqtt()

        # For MQTT Direct: subscribe driver to channels
        from .protocols.mqtt_direct import MQTTDirectDriverFull
        if isinstance(self.driver, MQTTDirectDriverFull):
            for ch in self._channels:
                self.driver.subscribe_channel(ch)

        poll = self._poll_override or self.client.fetch_poll_interval()
        log.info("Poll interval: %ds | Config reload: every %ds", poll, self._reload_interval)

        try:
            while self._running:
                self._maybe_reload()
                batch = self._poll_all()
                if batch:
                    self.client.publish_batch(batch)
                time.sleep(poll)
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    def stop(self) -> None:
        """Request a clean shutdown."""
        log.info("Shutdown requested")
        self._running = False

    def poll_once(self) -> list[dict[str, Any]]:
        """Single poll cycle — useful for testing or one-shot scripts."""
        self._reload_channels()
        self._connect_driver_with_retry()
        return self._poll_all()

    # ── Internal ─────────────────────────────────────────────────────────────

    _MAX_BACKOFF = 60       # seconds cap for reconnect wait
    _FAIL_LIMIT  = 5        # consecutive None reads before reconnect

    def _connect_driver_with_retry(self) -> None:
        """Connect driver with exponential backoff. Blocks until connected or gateway stops."""
        delay = 1
        attempt = 0
        while self._running:
            try:
                self.driver.connect()
                self._consecutive_fails = 0
                log.info("Driver connected successfully")
                return
            except Exception as e:
                attempt += 1
                log.error("Driver connect failed (attempt %d): %s — retrying in %ds", attempt, e, delay)
                time.sleep(delay)
                delay = min(delay * 2, self._MAX_BACKOFF)

    def _poll_all(self) -> list[dict[str, Any]]:
        batch: list[dict[str, Any]] = []
        all_failed = True

        for ch in self._channels:
            try:
                raw = self.driver.read(ch)
                if raw is None:
                    continue
                all_failed = False
                value = ch.apply_scale(raw)
                log.info("  %-30s → %10.4f %s", ch.name, value, ch.unit)
                batch.append({
                    "sensor_id": ch.sensor_id,
                    "value":     round(value, 6),
                    "unit":      ch.unit,
                })
            except Exception as e:
                log.error("Error reading channel %r: %s", ch.name, e)

        # Track consecutive full-poll failures → reconnect driver
        if self._channels and all_failed:
            self._consecutive_fails = getattr(self, "_consecutive_fails", 0) + 1
            if self._consecutive_fails >= self._FAIL_LIMIT:
                log.warning("Driver: %d consecutive poll failures — reconnecting", self._consecutive_fails)
                try:
                    self.driver.close()
                except Exception:
                    pass
                self._connect_driver_with_retry()
        else:
            self._consecutive_fails = 0

        return batch

    def _reload_channels(self) -> None:
        try:
            self._channels     = self.client.fetch_channels()
            self._last_reload  = time.monotonic()
        except Exception as e:
            log.error("Failed to reload channels: %s", e)
            if not self._channels:
                raise  # fatal if we have no channels at all

    def _maybe_reload(self) -> None:
        age = time.monotonic() - self._last_reload
        if age >= self._reload_interval:
            log.info("Reloading channel config (%.0fs since last load)", age)
            self._reload_channels()

    def _handle_command(self, cmd: dict[str, Any]) -> None:
        action = cmd.get("action", "")
        if action == "reload_config":
            self._reload_channels()
        elif action == "restart":
            log.warning("Restart command received — restarting process")
            self._shutdown()
            os.execv(sys.executable, [sys.executable] + sys.argv)
        elif action == "set_poll_interval":
            interval = cmd.get("interval")
            if interval:
                self._poll_override = int(interval)
                log.info("Poll interval changed to %ds", self._poll_override)
        else:
            self.driver.handle_command(cmd, self._channels)

    def _shutdown(self) -> None:
        log.info("Shutting down")
        try:
            self.driver.close()
        except Exception:
            pass
        try:
            self.client.disconnect()
        except Exception:
            pass

    # ── Class-level helpers ───────────────────────────────────────────────────

    @classmethod
    def from_env(cls, driver: ProtocolDriver | None = None) -> "IoT26Gateway":
        """
        Construct a gateway from environment variables::

            DEVICE_ID        (required)
            DEVICE_TOKEN     (required)
            IOT26_API        (default http://localhost:8443)
            MQTT_BROKER      (default localhost)
            MQTT_PORT        (default 1883)
            POLL_INTERVAL    (default: from API)
        """
        device_id    = os.environ["DEVICE_ID"]
        device_token = os.environ["DEVICE_TOKEN"]
        api_base     = os.environ.get("IOT26_API",     "http://localhost:8443")
        mqtt_broker  = os.environ.get("MQTT_BROKER",   "localhost")
        mqtt_port    = int(os.environ.get("MQTT_PORT", "1883"))
        poll         = os.environ.get("POLL_INTERVAL")

        if driver is None:
            driver = _auto_driver()

        return cls(
            device_id      = device_id,
            device_token   = device_token,
            driver         = driver,
            api_base       = api_base,
            mqtt_broker    = mqtt_broker,
            mqtt_port      = mqtt_port,
            poll_interval  = int(poll) if poll else None,
        )


def _auto_driver() -> ProtocolDriver:
    """
    Fallback: Modbus TCP driver using MODBUS_HOST / MODBUS_PORT env vars.
    Override by constructing IoT26Gateway with an explicit driver= argument.
    """
    from .protocols.modbus import ModbusTCPDriver
    host = os.environ.get("MODBUS_HOST", "127.0.0.1")
    port = int(os.environ.get("MODBUS_PORT", "502"))
    log.info("Auto-selected ModbusTCPDriver host=%s port=%d", host, port)
    return ModbusTCPDriver(host=host, port=port)


def _setup_signals(stop_fn) -> None:
    def _handler(sig, _frame):
        stop_fn()
    signal.signal(signal.SIGINT,  _handler)
    signal.signal(signal.SIGTERM, _handler)


def main() -> None:
    """CLI entry point: ``iot26-gateway`` script."""
    logging.basicConfig(
        level  = logging.INFO,
        format = "%(asctime)s %(levelname)-8s %(name)s %(message)s",
        datefmt= "%H:%M:%S",
    )
    IoT26Gateway.from_env().run()


if __name__ == "__main__":
    main()
