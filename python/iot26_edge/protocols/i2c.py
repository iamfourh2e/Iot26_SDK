"""
I²C driver via smbus2.

Supports any I²C sensor by sending configurable command bytes and reading
N bytes back. Handles read_delay_ms for sensors that need settle time (BME280).

channel_props keys:
  i2c_command       str  Hex bytes to write as command, e.g. 'F3 00'  (optional)
  i2c_read_len      int  Number of bytes to read back
  i2c_byte_offset   int  Start byte for MSB (default 0)
  i2c_read_delay_ms int  Wait this many ms between write and read (default 0)
  scale_factor      float  Applied by gateway after raw decode
  offset            float  Applied by gateway after raw decode

Device-level connection_props:
  bus               str  I²C bus path, e.g. '/dev/i2c-1'
  device_address    str  I²C address, hex or int, e.g. '0x76' or '118'
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .base import ProtocolDriver
from ..client import DeviceChannel

log = logging.getLogger(__name__)


class I2CDriver(ProtocolDriver):
    """
    Generic I²C driver.

    Args:
        bus:            I²C bus path or number (e.g. '/dev/i2c-1' or 1)
        device_address: Default device address (hex string or int).
                        Can be overridden per-channel via connection_props.
    """

    def __init__(self, bus: str | int = 1, device_address: int | str = 0x76) -> None:
        try:
            import smbus2 as smbus2_mod
            self._smbus2 = smbus2_mod
        except ImportError:
            raise ImportError("Install smbus2: pip install 'iot26-edge[i2c]'")
        self._bus_id  = int(bus) if str(bus).isdigit() else self._parse_bus_number(str(bus))
        self._addr    = self._parse_addr(device_address)
        self._bus     = None

    def connect(self) -> None:
        self._bus = self._smbus2.SMBus(self._bus_id)
        log.info("I²C bus %d opened (default addr=0x%02X)", self._bus_id, self._addr)

    def read(self, channel: DeviceChannel) -> float | None:
        cp   = channel.props
        addr = self._parse_addr(cp.get("i2c_address", cp.get("device_address", self._addr)))
        cmd_hex   = cp.get("i2c_command", "")
        read_len  = int(cp.get("i2c_read_len", 1))
        byte_off  = int(cp.get("i2c_byte_offset", 0))
        delay_ms  = int(cp.get("i2c_read_delay_ms", 0))

        try:
            # Write command bytes if specified
            if cmd_hex.strip():
                cmd = bytes.fromhex(cmd_hex.replace(" ", ""))
                self._bus.write_i2c_block_data(addr, cmd[0], list(cmd[1:]) if len(cmd) > 1 else [])

            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

            # Read back
            data = self._bus.read_i2c_block_data(addr, byte_off, read_len)

            # Decode: treat bytes[0] as MSB for multi-byte reads
            raw = 0
            for b in data:
                raw = (raw << 8) | b

            return float(raw)

        except Exception as e:
            log.error("I²C read error on %r addr=0x%02X: %s", channel.name, addr, e)
            return None

    def close(self) -> None:
        if self._bus:
            self._bus.close()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_addr(val: Any) -> int:
        if isinstance(val, int):
            return val
        s = str(val).strip().lower()
        return int(s, 16) if s.startswith("0x") else int(s)

    @staticmethod
    def _parse_bus_number(path: str) -> int:
        # '/dev/i2c-1' → 1
        try:
            return int(path.split("-")[-1])
        except ValueError:
            return 1
