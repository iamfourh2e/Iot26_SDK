import time
import logging
from iot26_edge.client import IoT26Client

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sensor_uplink")

def main():
    # Initialize the Python IoT26 Client
    client = IoT26Client(
        device_id="your-device-uuid",
        device_token="your-device-token",
        mqtt_broker="localhost",
        mqtt_port=1883
    )

    # Listen for downlink commands from the widget
    def on_command(cmd: dict):
        log.info(f"Received command: {cmd.get('action')}")
        
        if cmd.get("action") == "custom":
            log.info("Processing custom action command...")
            
            # Publish an uplink telemetry point back to sync the UI!
            log.info("Publishing uplink to update the widget UI...")
            client.publish_readings([
                {"sensor_id": "valve-sensor-uuid", "value": 1.0, "unit": "state"}
            ])

    client.on_command = on_command

    client.connect()
    client.loop_start()

    # Periodically publish telemetry
    try:
        while True:
            log.info("Publishing routine telemetry...")
            client.publish_readings([
                {"sensor_id": "temp-sensor-uuid", "value": 24.5, "unit": "C"},
                {"sensor_id": "hum-sensor-uuid", "value": 60.0, "unit": "%"}
            ])
            time.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
