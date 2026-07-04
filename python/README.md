# iot26-edge

Python SDK for connecting hardware sensors to IoT26 via any protocol.

## Install

```bash
cd edge

# Core only (no hardware deps)
uv sync

# With specific protocol support
uv sync --extra modbus    # Modbus TCP + RTU
uv sync --extra i2c       # I²C via smbus2
uv sync --extra spi       # SPI + Analog via spidev
uv sync --extra all       # Everything
```

## Quick start

```python
from iot26_edge import IoT26Gateway
from iot26_edge.protocols import ModbusTCPDriver

gw = IoT26Gateway(
    device_id    = "your-device-uuid",
    device_token = "eyJhbGci...",
    api_base     = "http://your-server:8443",
    mqtt_broker  = "your-server",
    driver       = ModbusTCPDriver(host="192.168.1.100", port=502),
)
gw.run()
```

Or from environment variables:

```bash
export DEVICE_ID=your-device-uuid
export DEVICE_TOKEN=eyJhbGci...
export IOT26_API=http://your-server:8443
export MQTT_BROKER=your-server
export MODBUS_HOST=192.168.1.100
export MODBUS_PORT=502

iot26-gateway    # CLI entry point
# or:
uv run examples/run_modbus_tcp.py
```

## Protocol drivers

| Driver | Class | Install extra |
|--------|-------|---------------|
| Modbus TCP | `ModbusTCPDriver(host, port)` | `modbus` |
| Modbus RTU | `ModbusRTUDriver(port, baudrate)` | `modbus` |
| I²C | `I2CDriver(bus, device_address)` | `i2c` |
| SPI | `SPIDriver(bus, device)` | `spi` |
| Analog ADC | `AnalogDriver(bus, device)` | `spi` |
| 1-Wire | `OneWireDriver(bus_path)` | *(kernel driver)* |
| MQTT Direct | `MQTTDirectDriver(broker)` | *(paho, already a core dep)* |

All drivers implement the same interface:

```python
driver.connect()               # open hardware
value = driver.read(channel)   # returns raw float, or None on error
driver.close()                 # release hardware
driver.handle_command(cmd, channels)   # handle downlink from server
```

## How channels are decoded

The gateway fetches channel config from `GET /v1/devices/{id}` and parses
`channel_props` for each sensor. After `driver.read()` returns the raw value,
the gateway applies:

```
final = raw × scale_factor + offset
```

All `scale_factor`, `offset`, `unit`, `alarm_high`, `alarm_low`, `deadband`,
`sample_count`, and `enabled` fields are read from IoT26 — no hardcoding in firmware.

## Downlink commands

The gateway subscribes to `devices/{device_id}/commands` and handles:

| Action | Effect |
|--------|--------|
| `reload_config` | Re-fetches channel config from API |
| `restart` | `os.execv` — replaces process |
| `set_poll_interval` | Changes poll speed live |
| `write_register` | Forwarded to Modbus driver (FC06) |
| `write_registers` | Forwarded to Modbus driver (FC10) |

## Examples

```
examples/
├── run_modbus_tcp.py   Modbus TCP (incl. local simulator)
├── run_modbus_rtu.py   Modbus RTU / RS-485 serial
├── run_i2c.py          I²C (BME280 / any sensor)
├── run_one_wire.py     1-Wire DS18B20 probes
└── run_mqtt_direct.py  MQTT Direct (ESP32 nodes)
```

## Writing a custom driver

```python
from iot26_edge.protocols.base import ProtocolDriver
from iot26_edge.client import DeviceChannel

class MyDriver(ProtocolDriver):
    def connect(self):
        # open your hardware
        pass

    def read(self, channel: DeviceChannel) -> float | None:
        # read the sensor, return raw unscaled value
        cp = channel.props
        return 42.0   # replace with real read

gw = IoT26Gateway(..., driver=MyDriver())
gw.run()
```
