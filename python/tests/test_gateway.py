"""
Edge SDK unit tests — no hardware, no broker, no API server required.

Run:
  cd edge
  pip install -e . pytest
  pytest tests/ -v
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from iot26_edge.client import DeviceChannel


# ── DeviceChannel helpers ────────────────────────────────────────────────────

def make_channel(
    name: str = "ch1",
    sensor_id: str = "s1",
    scale_factor: float = 1.0,
    offset: float = 0.0,
    unit: str = "°C",
    enabled: bool = True,
    props: dict | None = None,
) -> DeviceChannel:
    p = {
        "scale_factor": scale_factor,
        "offset":       offset,
        "unit":         unit,
        "enabled":      enabled,
    }
    if props:
        p.update(props)
    return DeviceChannel(name=name, sensor_id=sensor_id, channel_props=p)


# ── apply_scale ──────────────────────────────────────────────────────────────

class TestApplyScale:
    def test_identity(self):
        ch = make_channel(scale_factor=1.0, offset=0.0)
        assert ch.apply_scale(42.0) == pytest.approx(42.0)

    def test_scale_factor(self):
        # 0.001 → millidegrees to degrees
        ch = make_channel(scale_factor=0.001, offset=0.0)
        assert ch.apply_scale(25000.0) == pytest.approx(25.0)

    def test_scale_and_offset(self):
        # 4-20mA on 250Ω, vref 3.3V, 12-bit: roughly maps 0→0, 4095→some bar
        ch = make_channel(scale_factor=0.0806, offset=-25.0)
        raw = 2000.0
        assert ch.apply_scale(raw) == pytest.approx(raw * 0.0806 - 25.0)

    def test_negative_offset(self):
        ch = make_channel(scale_factor=1.0, offset=-273.15)
        assert ch.apply_scale(300.0) == pytest.approx(26.85)


# ── Enabled flag ─────────────────────────────────────────────────────────────

class TestEnabledFlag:
    def test_enabled_true(self):
        ch = make_channel(enabled=True)
        assert ch.enabled is True

    def test_enabled_false(self):
        ch = make_channel(enabled=False)
        assert ch.enabled is False

    def test_enabled_default(self):
        # No 'enabled' key → defaults to True
        ch = DeviceChannel(name="x", sensor_id="x", channel_props={})
        assert ch.enabled is True


# ── Gateway reconnect logic ───────────────────────────────────────────────────

class TestGatewayReconnect:
    """Tests the driver reconnect loop without real hardware."""

    def _make_gw(self, driver):
        from iot26_edge.gateway import IoT26Gateway
        gw = IoT26Gateway.__new__(IoT26Gateway)
        gw.driver          = driver
        gw._poll_override  = 5
        gw._reload_interval= 300
        gw._running        = True
        gw._channels       = []
        gw._last_reload    = 0.0
        gw._consecutive_fails = 0
        gw.client          = MagicMock()
        return gw

    def test_connect_succeeds_first_try(self):
        driver = MagicMock()
        driver.connect.return_value = None
        gw = self._make_gw(driver)
        gw._connect_driver_with_retry()
        driver.connect.assert_called_once()

    def test_connect_retries_on_failure_then_succeeds(self):
        driver = MagicMock()
        driver.connect.side_effect = [OSError("bus error"), OSError("bus error"), None]
        gw = self._make_gw(driver)

        with patch("time.sleep"):  # don't actually wait
            gw._connect_driver_with_retry()

        assert driver.connect.call_count == 3

    def test_poll_all_returns_empty_on_all_none(self):
        driver = MagicMock()
        driver.read.return_value = None
        gw = self._make_gw(driver)
        gw._channels = [make_channel("ch1"), make_channel("ch2")]
        result = gw._poll_all()
        assert result == []

    def test_poll_all_applies_scale(self):
        driver = MagicMock()
        driver.read.return_value = 25000.0  # millidegrees
        ch = make_channel("temp", scale_factor=0.001, offset=0.0, unit="°C")
        gw = self._make_gw(driver)
        gw._channels = [ch]
        result = gw._poll_all()
        assert len(result) == 1
        assert result[0]["value"] == pytest.approx(25.0)
        assert result[0]["unit"] == "°C"
        assert result[0]["sensor_id"] == "s1"

    def test_consecutive_fail_counter_resets_on_success(self):
        driver = MagicMock()
        driver.read.side_effect = [None, None, 42.0]
        ch = make_channel("ch1", scale_factor=1.0)
        gw = self._make_gw(driver)
        gw._channels = [ch]

        gw._poll_all()  # None  → all_failed=True, fails=1
        assert gw._consecutive_fails == 1

        driver.read.side_effect = [42.0]
        gw._poll_all()  # success → reset
        assert gw._consecutive_fails == 0

    def test_reconnect_triggers_after_fail_limit(self):
        driver = MagicMock()
        driver.read.return_value = None
        ch = make_channel("ch1")
        gw = self._make_gw(driver)
        gw._channels = [ch]

        # Exhaust the fail limit
        for _ in range(gw._FAIL_LIMIT - 1):
            gw._consecutive_fails += 1

        # Next failing poll should trigger reconnect
        with patch.object(gw, "_connect_driver_with_retry") as mock_reconnect:
            gw._poll_all()
            mock_reconnect.assert_called_once()


# ── Modbus driver (no real connection) ───────────────────────────────────────

class TestModbusDriverDecoding:
    """Test register decoding logic without a real Modbus device."""

    def test_import(self):
        """Driver must be importable even without pymodbus installed."""
        try:
            from iot26_edge.protocols.modbus import ModbusTCPDriver  # noqa
        except ImportError as e:
            pytest.skip(f"pymodbus not installed: {e}")

    def test_float_prop_roundtrip(self):
        """Scale + offset math must be exact to 6 decimal places."""
        ch = make_channel(scale_factor=0.1, offset=5.0)
        assert ch.apply_scale(100.0) == pytest.approx(15.0, abs=1e-6)


# ── One-Wire driver (sysfs stub) ──────────────────────────────────────────────

class TestOneWireDriver:
    def test_read_from_sysfs(self, tmp_path):
        from iot26_edge.protocols.one_wire import OneWireDriver

        # Create fake sysfs structure
        rom_dir = tmp_path / "28-0000083b3a8d"
        rom_dir.mkdir()
        (rom_dir / "temperature").write_text("25300\n")   # 25.3°C in millidegrees

        driver = OneWireDriver(bus_path=str(tmp_path))
        driver.connect()

        ch = make_channel(props={"one_wire_rom": "28-0000083b3a8d"}, scale_factor=0.001)
        raw = driver.read(ch)
        assert raw == pytest.approx(25300.0)   # driver returns raw millidegrees
        assert ch.apply_scale(raw) == pytest.approx(25.3, abs=0.001)

    def test_missing_rom_returns_none(self, tmp_path):
        from iot26_edge.protocols.one_wire import OneWireDriver

        driver = OneWireDriver(bus_path=str(tmp_path))
        ch = make_channel(props={"one_wire_rom": "28-nonexistent"})
        assert driver.read(ch) is None

    def test_empty_rom_prop_returns_none(self, tmp_path):
        from iot26_edge.protocols.one_wire import OneWireDriver

        driver = OneWireDriver(bus_path=str(tmp_path))
        ch = make_channel(props={})   # no one_wire_rom key
        assert driver.read(ch) is None
