"""
Modbus TCP + RTU driver.

Supports:
  - FC01 Read Coils
  - FC02 Read Discrete Inputs
  - FC03 Read Holding Registers
  - FC04 Read Input Registers
  - FC06 Write Single Register  (via handle_command)
  - FC10 Write Multiple Registers (via handle_command)

channel_props keys:
  slave_addr      int    Modbus slave / unit ID (RTU) or unit on TCP
  register_address int   0-indexed register number
  register_type   str    'holding' | 'input' | 'coil' | 'discrete'  (overrides function_code)
  function_code   int    1 | 2 | 3 | 4
  register_count  int    1 (16-bit) or 2 (32-bit float/int)
  data_type       str    'int16' | 'uint16' | 'int32' | 'uint32' | 'float32' | 'bool'
  word_order      str    'AB' | 'BA' | 'ABCD' | 'CDAB' | 'DCBA' | 'BADC'
"""

from __future__ import annotations

import logging
import struct
from typing import Any

from .base import ProtocolDriver
from ..client import DeviceChannel

log = logging.getLogger(__name__)

# Register type → function code default
_FC_MAP = {"holding": 3, "input": 4, "coil": 1, "discrete": 2}

# Word orders for 32-bit decoding (Big-Endian vs Little-Endian word arrangement)
_WORD_ORDERS = {
    "AB":   ">H",    # 16-bit big-endian
    "BA":   "<H",    # 16-bit little-endian
    "ABCD": ">I",    # 32-bit big-endian
    "CDAB": None,    # 32-bit mid-big (swap words then big)
    "DCBA": "<I",    # 32-bit little-endian
    "BADC": None,    # 32-bit mid-little (swap words then little)
}


class ModbusTCPDriver(ProtocolDriver):
    """
    Modbus TCP driver.

    Args:
        host:    IP address or hostname of the Modbus TCP device / gateway
        port:    TCP port (default 502; simulator uses 5020)
        timeout: Socket timeout in seconds
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 502, timeout: float = 3.0) -> None:
        try:
            from pymodbus.client import ModbusTcpClient
        except ImportError:
            raise ImportError("Install pymodbus: pip install 'iot26-edge[modbus]'")
        self._cls    = ModbusTcpClient
        self._host   = host
        self._port   = port
        self._timeout = timeout
        self._client = None

    def connect(self) -> None:
        self._client = self._cls(host=self._host, port=self._port, timeout=self._timeout)
        self._client.connect()
        log.info("Modbus TCP connected → %s:%d", self._host, self._port)

    def read(self, channel: DeviceChannel) -> float | None:
        return _read_register(self._client, channel)

    def handle_command(self, cmd: dict[str, Any], _channels) -> None:
        _handle_write(self._client, cmd)

    def close(self) -> None:
        if self._client:
            self._client.close()


class ModbusRTUDriver(ProtocolDriver):
    """
    Modbus RTU (serial) driver.

    Args:
        port:     Serial port, e.g. '/dev/ttyUSB0' or '/dev/ttyAMA0'
        baudrate: Baud rate (match slave DIP switch)
        parity:   'N' | 'E' | 'O'
        stopbits: 1 or 2
        timeout:  Read timeout in seconds
    """

    def __init__(
        self,
        port:     str   = "/dev/ttyUSB0",
        baudrate: int   = 9600,
        parity:   str   = "N",
        stopbits: int   = 1,
        timeout:  float = 1.0,
    ) -> None:
        try:
            from pymodbus.client import ModbusSerialClient
        except ImportError:
            raise ImportError("Install pymodbus: pip install 'iot26-edge[modbus]'")
        self._cls      = ModbusSerialClient
        self._port     = port
        self._baudrate = baudrate
        self._parity   = parity
        self._stopbits = stopbits
        self._timeout  = timeout
        self._client   = None

    def connect(self) -> None:
        self._client = self._cls(
            port=self._port, baudrate=self._baudrate, parity=self._parity,
            stopbits=self._stopbits, bytesize=8, timeout=self._timeout,
        )
        self._client.connect()
        log.info("Modbus RTU connected → %s @ %d baud", self._port, self._baudrate)

    def read(self, channel: DeviceChannel) -> float | None:
        return _read_register(self._client, channel)

    def handle_command(self, cmd: dict[str, Any], _channels) -> None:
        _handle_write(self._client, cmd)

    def close(self) -> None:
        if self._client:
            self._client.close()


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _read_register(client, channel: DeviceChannel) -> float | None:
    """Read registers from either TCP or RTU client and decode to float."""
    cp      = channel.props
    slave   = int(cp.get("slave_addr", 1))
    reg     = int(cp.get("register_address", cp.get("register", 0)))
    count   = int(cp.get("register_count", 1))
    fc      = int(cp.get("function_code",
                         _FC_MAP.get(cp.get("register_type", "input"), 4)))
    dtype   = cp.get("data_type", "int16")
    word_ord= cp.get("word_order", "AB")

    try:
        if fc == 3:
            result = client.read_holding_registers(reg, count, slave=slave)
        elif fc == 4:
            result = client.read_input_registers(reg, count, slave=slave)
        elif fc == 1:
            result = client.read_coils(reg, count, slave=slave)
        elif fc == 2:
            result = client.read_discrete_inputs(reg, count, slave=slave)
        else:
            log.warning("Unsupported function_code %d on channel %r", fc, channel.name)
            return None

        if result.isError():
            log.error("Modbus error on %r: %s", channel.name, result)
            return None

        if fc in (1, 2):
            return float(result.bits[0])

        return _decode(result.registers, dtype, word_ord)

    except Exception as e:
        log.error("Modbus read error on %r: %s", channel.name, e)
        return None


def _decode(registers: list[int], dtype: str, word_order: str) -> float | None:
    """Decode register(s) into a Python float."""
    try:
        if len(registers) == 1:
            raw = registers[0]
            if dtype in ("int16",):
                return float(raw if raw <= 32767 else raw - 65536)
            return float(raw)  # uint16, bool

        if len(registers) >= 2:
            # 32-bit decode
            hi, lo = registers[0], registers[1]
            wo = word_order.upper()
            if wo == "ABCD":
                b = struct.pack(">HH", hi, lo)
            elif wo == "CDAB":
                b = struct.pack(">HH", lo, hi)
            elif wo == "BADC":
                b = struct.pack("<HH", hi, lo)
            elif wo == "DCBA":
                b = struct.pack("<HH", lo, hi)
            else:
                b = struct.pack(">HH", hi, lo)

            if dtype == "float32":
                return float(struct.unpack(">f", b)[0])
            elif dtype == "int32":
                return float(struct.unpack(">i", b)[0])
            elif dtype == "uint32":
                return float(struct.unpack(">I", b)[0])

        return None
    except Exception as e:
        log.error("Decode error dtype=%s order=%s: %s", dtype, word_order, e)
        return None


def _handle_write(client, cmd: dict[str, Any]) -> None:
    """Handle write_register / write_registers downlink commands."""
    action = cmd.get("action")
    if action == "write_register":
        slave = int(cmd.get("slave", 1))
        reg   = int(cmd.get("register", 0))
        value = int(cmd.get("value", 0))
        result = client.write_register(reg, value, slave=slave)
        if result.isError():
            log.error("write_register failed: %s", result)
        else:
            log.info("write_register OK slave=%d reg=%d val=%d", slave, reg, value)
    elif action == "write_registers":
        slave  = int(cmd.get("slave", 1))
        reg    = int(cmd.get("register", 0))
        values = cmd.get("values", [])
        result = client.write_registers(reg, values, slave=slave)
        if result.isError():
            log.error("write_registers failed: %s", result)
        else:
            log.info("write_registers OK slave=%d reg=%d count=%d", slave, reg, len(values))
