"""
Analog (ADC) driver via MCP3208 over SPI.

Reads raw 12-bit samples from an MCP3208 8-channel ADC.
Designed to work with 4–20 mA sensors, potentiometers, NTC thermistors, etc.

channel_props keys:
  adc_channel   int    ADC input channel 0–7
  sample_count  int    Number of raw samples to average (default 1)

Device-level connection_props:
  device_path   str    spidev path (parsed: /dev/spidev0.0 → bus=0, dev=0)
  resolution    int    ADC bit resolution (default 12 for MCP3208)
  vref          float  Reference voltage in V (default 3.3)
  speed_hz      int    SPI speed (default 1 MHz)
"""

from __future__ import annotations

import logging

from .base import ProtocolDriver
from ..client import DeviceChannel

log = logging.getLogger(__name__)


class AnalogDriver(ProtocolDriver):
    """
    MCP3208 / generic SPI ADC driver.

    The ``read()`` method returns the **raw ADC count** (0 – 2^resolution-1).
    Apply ``scale_factor + offset`` in channel_props to convert to engineering units.

    Example for 4–20 mA on 250Ω shunt (0–1V at 3.3V VRef, 12-bit):
        final_bar = raw × (3.3/4096) × (100/4.0) − 25.0
        → scale_factor ≈ 0.0806, offset ≈ −25.0

    Args:
        bus:      SPI bus (0 for /dev/spidev0.x)
        device:   SPI device CE index
        speed_hz: SPI clock rate
        vref:     ADC reference voltage (default 3.3)
        bits:     ADC resolution in bits (default 12 for MCP3208)
    """

    def __init__(
        self,
        bus:      int   = 0,
        device:   int   = 0,
        speed_hz: int   = 1_000_000,
        vref:     float = 3.3,
        bits:     int   = 12,
    ) -> None:
        try:
            import spidev as spidev_mod
            self._spidev = spidev_mod
        except ImportError:
            raise ImportError("Install spidev: pip install 'iot26-edge[spi]'")
        self._bus      = bus
        self._device   = device
        self._speed_hz = speed_hz
        self._vref     = vref
        self._bits     = bits
        self._max      = (1 << bits) - 1
        self._spi      = None

    def connect(self) -> None:
        self._spi = self._spidev.SpiDev()
        self._spi.open(self._bus, self._device)
        self._spi.max_speed_hz = self._speed_hz
        self._spi.mode         = 0
        log.info("ADC SPI /dev/spidev%d.%d @ %d Hz vref=%.1fV bits=%d",
                 self._bus, self._device, self._speed_hz, self._vref, self._bits)

    def read(self, channel: DeviceChannel) -> float | None:
        """Return raw ADC count (not scaled). Gateway applies scale_factor + offset."""
        cp      = channel.props
        ch      = int(cp.get("adc_channel", 0))
        samples = int(cp.get("sample_count", 1))

        try:
            total = sum(self._read_raw(ch) for _ in range(samples))
            return float(total / samples)
        except Exception as e:
            log.error("ADC read error channel=%d: %s", ch, e)
            return None

    def _read_raw(self, channel: int) -> int:
        """MCP3208 single-ended read, returns 12-bit integer."""
        # MCP3208 SPI protocol: 3 bytes
        # Start bit | SGL/DIFF | D2 | D1 | D0
        cmd = [
            0x06 | (channel >> 2),      # start + SGL + D2
            (channel & 0x03) << 6,      # D1 D0 + don't-care
            0x00,                       # clock 8 more bits for result
        ]
        resp = self._spi.xfer2(cmd)
        return ((resp[1] & 0x0F) << 8) | resp[2]

    def voltage(self, raw: float) -> float:
        """Convert raw count to voltage."""
        return raw / self._max * self._vref

    def close(self) -> None:
        if self._spi:
            self._spi.close()
