"""Protocol driver base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..client import DeviceChannel


class ProtocolDriver(ABC):
    """
    Abstract base for a protocol driver.

    Each subclass handles one protocol family (Modbus, I²C, SPI, …).
    ``read(channel)`` returns the **raw** value; scaling is applied by the gateway.
    """

    @abstractmethod
    def connect(self) -> None:
        """Open the hardware connection."""

    @abstractmethod
    def read(self, channel: DeviceChannel) -> float | None:
        """
        Read one channel.

        Returns the raw (unscaled) value, or None on error.
        The gateway applies scale_factor + offset after this call.
        """

    def close(self) -> None:
        """Optional: release hardware resources."""

    def handle_command(self, cmd: dict[str, Any], channels: list[DeviceChannel]) -> None:
        """Optional: handle a downlink command from the server."""
