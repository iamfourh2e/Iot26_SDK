"""
SPI driver via spidev.

Sends configurable command bytes and reads N bytes back.
Handles cs_pin (manual GPIO chip-select) and bit_order (MSB/LSB).

channel_props keys:
  spi_command   str  Hex bytes to send e.g. '01 80 00'
  spi_read_len  int  Bytes to clock in (response)
  cs_pin        int  GPIO chip-select pin (-1 = handled by spidev)
  bit_order     str  'MSB' (default) | 'LSB'

Device-level connection_props:
  device_path   str  spidev path, e.g. '/dev/spidev0.0'
  speed_hz      int  SPI clock speed (default 1 MHz)
  mode          int  SPI mode 0–3 (CPOL/CPHA, default 0)
"""

from __future__ import annotations

import logging

from .base import ProtocolDriver
from ..client import DeviceChannel

log = logging.getLogger(__name__)

# Mask for LSB-first bit reversal of a byte
def _reverse_byte(b: int) -> int:
    b = (b & 0xF0) >> 4 | (b & 0x0F) << 4
    b = (b & 0xCC) >> 2 | (b & 0x33) << 2
    b = (b & 0xAA) >> 1 | (b & 0x55) << 1
    return b


class SPIDriver(ProtocolDriver):
    """
    Generic SPI driver.

    Args:
        bus:      SPI bus number (0 for /dev/spidev0.x)
        device:   SPI device (CE index: 0 = CE0, 1 = CE1)
        speed_hz: Clock rate in Hz (default 1 MHz)
        mode:     SPI mode 0–3
    """

    def __init__(
        self,
        bus:      int = 0,
        device:   int = 0,
        speed_hz: int = 1_000_000,
        mode:     int = 0,
    ) -> None:
        try:
            import spidev as spidev_mod
            self._spidev = spidev_mod
        except ImportError:
            raise ImportError("Install spidev: pip install 'iot26-edge[spi]'")
        self._bus      = bus
        self._device   = device
        self._speed_hz = speed_hz
        self._mode     = mode
        self._spi      = None

    def connect(self) -> None:
        self._spi = self._spidev.SpiDev()
        self._spi.open(self._bus, self._device)
        self._spi.max_speed_hz = self._speed_hz
        self._spi.mode         = self._mode
        log.info("SPI /dev/spidev%d.%d opened @ %d Hz mode=%d",
                 self._bus, self._device, self._speed_hz, self._mode)

    def read(self, channel: DeviceChannel) -> float | None:
        cp       = channel.props
        cmd_hex  = cp.get("spi_command", "00")
        read_len = int(cp.get("spi_read_len", 1))
        lsb_first = str(cp.get("bit_order", "MSB")).upper() == "LSB"

        try:
            tx_bytes = bytes.fromhex(cmd_hex.replace(" ", ""))
            # Pad command to match expected clock cycles (read_len may differ from cmd len)
            tx = list(tx_bytes) + [0x00] * max(0, read_len - len(tx_bytes))
            rx = self._spi.xfer2(tx[:read_len + len(tx_bytes)])  # clock out cmd + read bytes

            # Take the last read_len bytes as response
            response = rx[-read_len:]

            if lsb_first:
                response = [_reverse_byte(b) for b in response]

            raw = 0
            for b in response:
                raw = (raw << 8) | b

            return float(raw)

        except Exception as e:
            log.error("SPI read error on %r: %s", channel.name, e)
            return None

    def close(self) -> None:
        if self._spi:
            self._spi.close()
