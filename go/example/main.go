// IoT26 Go SDK — Dynamic Config & Button Example
//
// This example fetches the dynamic configuration from the IoT26 REST API,
// looks for a sensor named "button", and publishes simulated button clicks.
//
// Usage:
//
//	export IOT26_DEVICE_ID=your-device-uuid
//	export IOT26_DEVICE_TOKEN=eyJhbGci...
//
//	go run ./example_button
package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	iot26client "github.com/iamfourh2e/IOT2026/sdk/go/iot26client"
)

type APIConfigResponse struct {
	PollIntervalSeconds int `json:"poll_interval_seconds"`
	Sensors             []struct {
		SensorID     string `json:"sensor_id"`
		Name         string `json:"name"`
		ChannelProps struct {
			Pin int `json:"pin"`
		} `json:"channel_props"`
	} `json:"sensors"`
}

func main() {
	deviceID := os.Getenv("IOT26_DEVICE_ID")
	deviceToken := os.Getenv("IOT26_DEVICE_TOKEN")

	if deviceID == "" || deviceToken == "" {
		log.Fatal("IOT26_DEVICE_ID and IOT26_DEVICE_TOKEN must be set")
	}

	// 1. Fetch Configuration via REST API
	log.Println("Fetching dynamic configuration...")
	req, err := http.NewRequest("GET", "https://<iot26_url>/v1/devices/"+deviceID+"/config", nil)
	if err != nil {
		log.Fatal(err)
	}
	req.Header.Set("Authorization", "Bearer "+deviceToken)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		log.Fatal("Failed to fetch config:", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		log.Fatalf("API returned status %d", resp.StatusCode)
	}

	var config APIConfigResponse
	if err := json.NewDecoder(resp.Body).Decode(&config); err != nil {
		log.Fatal("Failed to parse config:", err)
	}

	// 2. Parse Button Sensor configuration
	var buttonSensorID string
	for _, s := range config.Sensors {
		if strings.Contains(strings.ToLower(s.Name), "button") {
			buttonSensorID = s.SensorID
			log.Printf("Found button sensor! ID: %s, Assigned GPIO Pin: %d", s.SensorID, s.ChannelProps.Pin)
		}
	}

	if buttonSensorID == "" {
		log.Println("Warning: No sensor named 'button' found in configuration.")
		// Fallback for testing
		buttonSensorID = "fallback-button-id" 
	}

	// 3. Connect MQTT Client
	client, err := iot26client.New(iot26client.Config{
		DeviceID:    deviceID,
		DeviceToken: deviceToken,
		Broker:      "tls://<iot26_url>:8883",
	})
	if err != nil {
		log.Fatal(err)
	}
	defer client.Disconnect()

	// 4. Handle Downlink Commands (Mirroring C++ Example)
	client.OnCommand(func(cmd iot26client.Command) {
		log.Printf("Received command from dashboard: %s", cmd.Action)

		switch cmd.Action {
		case "reload_config":
			log.Println("-> Reloading configuration...")
			// TODO: trigger a re-fetch of the config
		case "write_register":
			log.Println("-> Modbus Write requested")
		case "read_register":
			log.Println("-> Modbus Read requested")
		case "trigger_ota":
			log.Println("-> Trigger OTA Update")
		case "custom":
			// Parse the raw JSON payload to extract 'custom' fields
			var payload struct {
				Custom map[string]interface{} `json:"custom"`
			}
			if err := json.Unmarshal(cmd.Raw, &payload); err == nil {
				custom := payload.Custom
				if v, ok := custom["valve"]; ok {
					log.Printf("-> Toggle Switch/Valve: %v\n", v)
				}
				if v, ok := custom["dimmer"]; ok {
					log.Printf("-> Dimmer Level: %v%%\n", v)
				}
				if v, ok := custom["color"]; ok {
					log.Printf("-> Set RGB Color: %v\n", v)
				}
				if v, ok := custom["lock"]; ok {
					log.Printf("-> Electronic Lock: %v\n", v)
				}
				if v, ok := custom["ir_blaster"]; ok {
					log.Printf("-> Blast IR Code: %v\n", v)
				}
				if ptz, ok := custom["ptz"].(map[string]interface{}); ok {
					log.Printf("-> PTZ Camera Move to X:%v, Y:%v\n", ptz["pan"], ptz["tilt"])
				}
				if v, ok := custom["display"]; ok {
					log.Printf("-> LCD Display Text: %v\n", v)
				}
				if cal, ok := custom["calibrate"].(map[string]interface{}); ok {
					log.Printf("-> Sensor Calibration [%v]: %v\n", cal["type"], cal["value"])
				}
			}
		}
	})

	// 5. Simulate Button Polling Loop
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	pollInterval := time.Duration(config.PollIntervalSeconds) * time.Second
	if pollInterval == 0 {
		pollInterval = 5 * time.Second
	}

	log.Printf("Configuration applied. Polling every %s", pollInterval)

	ticker := time.NewTicker(pollInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Println("Shutting down...")
			return
		case <-ticker.C:
			// Simulate a button press (In a real Go app on a Pi, you'd use a GPIO library here)
			log.Println("[HARDWARE] Button pressed! Publishing telemetry...")
			client.PublishReadings([]iot26client.Reading{
				{SensorID: buttonSensorID, Value: 1.0, Unit: "click"},
			})
		}
	}
}
