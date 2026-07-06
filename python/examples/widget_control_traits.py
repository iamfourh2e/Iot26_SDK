"""
Widget Control Traits — Python SDK Example
==========================================

This example demonstrates how to publish sensor readings with `metadata_json`
to power the IoT26 Widget Builder's UI control components.

The Widget Builder supports the following UI components that derive their
displayed state from sensor readings published by your device:

  ┌─────────────────┬────────────────────────────────────────────────────┐
  │ UI Component    │ metadata_json field + values                       │
  ├─────────────────┼────────────────────────────────────────────────────┤
  │ Toggle (Relay)  │ {"mode": "on"} or {"mode": "off"}                  │
  │ AC Mode         │ {"mode": "cool"} or {"mode": "heat"} or {"mode": "off"} │
  │ Door / Motor    │ {"motor": "open"} or {"motor": "stop"} or {"motor": "close"} │
  │ Brightness      │ plain value (e.g. 80.0) — no metadata needed       │
  │ Display Text    │ {"display": "Hello World"}                         │
  └─────────────────┴────────────────────────────────────────────────────┘

The Widget reads `metadata_json` from the latest sensor reading and highlights
the matching button. The state also persists across page refreshes (fetched
from the database on reconnect).

Usage:
    pip install iot26-edge
    IOT26_DEVICE_ID=<uuid> IOT26_DEVICE_TOKEN=<token> python widget_control_traits.py

Environment variables:
    IOT26_DEVICE_ID     — Device UUID from IoT26 dashboard
    IOT26_DEVICE_TOKEN  — Device JWT token from IoT26 dashboard
    IOT26_BROKER        — MQTT broker host (default: localhost)
    IOT26_API_BASE      — REST API base URL (default: http://localhost:8443)
"""

import json
import logging
import os
import time
from iot26_edge.client import IoT26Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("widget_control_traits")

# ── Configuration ────────────────────────────────────────────────────────────

DEVICE_ID    = os.environ.get("IOT26_DEVICE_ID",    "your-device-uuid")
DEVICE_TOKEN = os.environ.get("IOT26_DEVICE_TOKEN", "your-device-token")
MQTT_BROKER  = os.environ.get("IOT26_BROKER",       "localhost")
API_BASE     = os.environ.get("IOT26_API_BASE",      "http://localhost:8443")

# ── Sensor IDs — replace with UUIDs from your IoT26 sensor config ───────────

SENSOR_RELAY      = "relay-sensor-uuid"     # Toggle widget (on/off)
SENSOR_AC_MODE    = "ac-mode-sensor-uuid"   # AC widget    (cool/heat/off)
SENSOR_DOOR_MOTOR = "door-motor-sensor-uuid"# Door widget  (open/stop/close)
SENSOR_BRIGHTNESS = "brightness-sensor-uuid"# Slider widget (0–100%)
SENSOR_DISPLAY    = "display-sensor-uuid"   # Display text widget


# ── Device state (simulated — replace with real hardware reads) ──────────────

state = {
    "relay":      "off",      # "on" | "off"
    "ac_mode":    "off",      # "cool" | "heat" | "off"
    "door_motor": "close",    # "open" | "stop" | "close"
    "brightness": 75.0,       # 0–100
    "display":    "Hello!",   # arbitrary string
}


def publish_all_states(client: IoT26Client) -> None:
    """Push the current device state to IoT26 so the widget reflects reality."""
    client.publish_batch([
        # Toggle/Relay: mode = "on" or "off"
        {
            "sensor_id": SENSOR_RELAY,
            "value":     1.0 if state["relay"] == "on" else 0.0,
            "unit":      "state",
            "metadata_json": json.dumps({"mode": state["relay"]}),
        },

        # AC Mode: mode = "cool" | "heat" | "off"
        {
            "sensor_id": SENSOR_AC_MODE,
            "value":     1.0,
            "unit":      "state",
            "metadata_json": json.dumps({"mode": state["ac_mode"]}),
        },

        # Door / Motor: motor = "open" | "stop" | "close"
        {
            "sensor_id": SENSOR_DOOR_MOTOR,
            "value":     1.0,
            "unit":      "state",
            "metadata_json": json.dumps({"motor": state["door_motor"]}),
        },

        # Brightness: plain numeric value — slider reads the value directly
        {
            "sensor_id": SENSOR_BRIGHTNESS,
            "value":     state["brightness"],
            "unit":      "%",
        },

        # Display text: display = "any text"
        {
            "sensor_id": SENSOR_DISPLAY,
            "value":     1.0,
            "unit":      "text",
            "metadata_json": json.dumps({"display": state["display"]}),
        },
    ])
    log.info("Pushed state → relay=%s, ac=%s, door=%s, brightness=%.0f",
             state["relay"], state["ac_mode"], state["door_motor"], state["brightness"])


def handle_command(cmd: dict) -> None:
    """
    Process downlink commands from the widget and publish uplink
    confirmation so the UI immediately reflects the new state.
    """
    action = cmd.get("action")
    custom = cmd.get("custom", {})
    log.info("⬇ Command received: action=%s  custom=%s", action, custom)

    if action != "custom":
        log.info("Ignoring non-custom action: %s", action)
        return

    # ── Relay toggle ─────────────────────────────────────────────────────────
    if "relay" in custom:
        state["relay"] = "on" if custom["relay"] else "off"
        log.info("Relay → %s", state["relay"])
        client.publish_batch([{
            "sensor_id": SENSOR_RELAY,
            "value":     1.0 if state["relay"] == "on" else 0.0,
            "unit":      "state",
            "metadata_json": json.dumps({"mode": state["relay"]}),
        }])

    # ── AC mode ──────────────────────────────────────────────────────────────
    if "ac_mode" in custom:
        new_mode = custom["ac_mode"]            # "cool" | "heat" | "off"
        if new_mode in ("cool", "heat", "off"):
            state["ac_mode"] = new_mode
            log.info("AC mode → %s", state["ac_mode"])
            client.publish_batch([{
                "sensor_id": SENSOR_AC_MODE,
                "value":     1.0,
                "unit":      "state",
                "metadata_json": json.dumps({"mode": state["ac_mode"]}),
            }])

    # ── Door / Motor ─────────────────────────────────────────────────────────
    if "motor" in custom:
        new_pos = custom["motor"]               # "open" | "stop" | "close"
        if new_pos in ("open", "stop", "close"):
            state["door_motor"] = new_pos
            log.info("Door motor → %s", state["door_motor"])
            client.publish_batch([{
                "sensor_id": SENSOR_DOOR_MOTOR,
                "value":     1.0,
                "unit":      "state",
                "metadata_json": json.dumps({"motor": state["door_motor"]}),
            }])

    # ── Brightness slider ─────────────────────────────────────────────────────
    if "brightness" in custom:
        state["brightness"] = float(custom["brightness"])
        log.info("Brightness → %.0f%%", state["brightness"])
        client.publish_batch([{
            "sensor_id": SENSOR_BRIGHTNESS,
            "value":     state["brightness"],
            "unit":      "%",
        }])

    # ── Display text ──────────────────────────────────────────────────────────
    if "display" in custom:
        state["display"] = str(custom["display"])
        log.info("Display → %r", state["display"])
        client.publish_batch([{
            "sensor_id": SENSOR_DISPLAY,
            "value":     1.0,
            "unit":      "text",
            "metadata_json": json.dumps({"display": state["display"]}),
        }])


# ── Main ─────────────────────────────────────────────────────────────────────

client = IoT26Client(
    device_id=DEVICE_ID,
    device_token=DEVICE_TOKEN,
    api_base=API_BASE,
    mqtt_broker=MQTT_BROKER,
    mqtt_port=1883,
)

client.on_command(handle_command)
client.connect_mqtt()

# Give the MQTT loop a moment to connect
time.sleep(1.5)

# Push initial state so the widget immediately shows correct button highlights
log.info("Publishing initial device state...")
publish_all_states(client)

try:
    log.info("Running — widget will reflect state in real time. Press Ctrl+C to stop.")
    while True:
        time.sleep(30)
        # Optionally re-publish heartbeat state every 30 s
        publish_all_states(client)

except KeyboardInterrupt:
    log.info("Shutting down...")
finally:
    client.disconnect()
