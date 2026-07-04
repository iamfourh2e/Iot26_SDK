"""
1-Wire driver via Linux kernel sysfs interface.

Works with DS18B20 and any w1_therm sensor. Requires:
  /boot/config.txt:  dtoverlay=w1-gpio
  modprobe w1_gpio w1_therm

channel_props keys:
  one_wire_rom  str   ROM code, e.g. '28-0000083b3a8d'
  scale_factor  float Applied by gateway (default 1.0 → raw millidegrees → °C with offset)

Device-level connection_props:
  bus_path  str   Base path for 1-Wire devices (default /sys/bus/w1/devices)

Note: The Linux kernel already returns temperature in millidegrees Celsius.
Set scale_factor = 0.001 in channel_props to get °C, or 1.0 to get raw millidegrees.
"""

from __future__ import annotations

import logging
import pathlib
import time

from .base import ProtocolDriver
from ..client import DeviceChannel

log = logging.getLogger(__name__)

_DEFAULT_BUS = "/sys/bus/w1/devices"
_TEMP_FILE   = "temperature"
_MAX_RETRIES = 3


class OneWireDriver(ProtocolDriver):
    """
    1-Wire driver using Linux kernel w1_therm sysfs.

    Args:
        bus_path: Directory containing ROM-code subdirectories.
                  Default: /sys/bus/w1/devices
    """

    def __init__(self, bus_path: str = _DEFAULT_BUS) -> None:
        self._bus_path = pathlib.Path(bus_path)

    def connect(self) -> None:
        if not self._bus_path.exists():
            log.warning(
                "1-Wire bus path %s not found — "
                "check dtoverlay=w1-gpio in /boot/config.txt",
                self._bus_path,
            )
        else:
            devices = list(self._bus_path.glob("28-*"))
            log.info("1-Wire bus ready: %d device(s) found", len(devices))
            for d in devices:
                log.info("  %s", d.name)

    def read(self, channel: DeviceChannel) -> float | None:
        """
        Returns raw millidegrees Celsius from the kernel.
        Set scale_factor = 0.001 in channel_props to convert to °C.
        """
        rom = channel.props.get("one_wire_rom", "")
        if not rom:
            log.error("Channel %r has no one_wire_rom in channel_props", channel.name)
            return None

        sensor_path = self._bus_path / rom / _TEMP_FILE

        for attempt in range(_MAX_RETRIES):
            try:
                raw = sensor_path.read_text(encoding="utf-8").strip()
                return float(raw)
            except FileNotFoundError:
                log.error("1-Wire sensor %r not found at %s", rom, sensor_path)
                return None
            except OSError as e:
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(0.1)
                    continue
                log.error("1-Wire read error %r: %s", channel.name, e)
                return None
        return None

    def list_devices(self) -> list[str]:
        """List all attached 1-Wire ROM codes (any family, not just DS18B20)."""
        return [d.name for d in self._bus_path.iterdir() if d.is_dir() and d.name != "w1_bus_master1"]
