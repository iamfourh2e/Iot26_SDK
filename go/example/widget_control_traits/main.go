// Package main — Widget Control Traits Example (IoT26 Go SDK)
//
// This example shows how to publish sensor readings with metadata_json
// to power the IoT26 Widget Builder's UI control components.
//
// Widget UI Component → metadata_json field + values:
//
//	Toggle (Relay)  → {"mode": "on"} | {"mode": "off"}
//	AC Mode         → {"mode": "cool"} | {"mode": "heat"} | {"mode": "off"}
//	Door / Motor    → {"motor": "open"} | {"motor": "stop"} | {"motor": "close"}
//	Brightness      → plain numeric value (no metadata needed)
//	Display Text    → {"display": "Hello World"}
//
// The Widget reads metadata_json from the latest sensor reading and highlights
// the matching button. State persists across refreshes via the database snapshot.
//
// Usage:
//
//	IOT26_DEVICE_ID=<uuid> IOT26_DEVICE_TOKEN=<token> go run main.go
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/iamfourh2e/IOT2026/sdk/go/iot26client"
)

// ── Sensor IDs — replace with UUIDs from your IoT26 sensor config ────────────

const (
	sensorRelay      = "relay-sensor-uuid"      // Toggle widget (on/off)
	sensorACMode     = "ac-mode-sensor-uuid"    // AC widget    (cool/heat/off)
	sensorDoorMotor  = "door-motor-sensor-uuid" // Door widget  (open/stop/close)
	sensorBrightness = "brightness-sensor-uuid" // Slider widget (0–100%)
	sensorDisplay    = "display-sensor-uuid"    // Display text widget
)

// ── Device state (simulated — replace with real hardware reads) ───────────────

type DeviceState struct {
	Relay      string  // "on" | "off"
	ACMode     string  // "cool" | "heat" | "off"
	DoorMotor  string  // "open" | "stop" | "close"
	Brightness float64 // 0–100
	DisplayMsg string
}

var state = DeviceState{
	Relay:      "off",
	ACMode:     "off",
	DoorMotor:  "close",
	Brightness: 75,
	DisplayMsg: "Hello!",
}

// mustJSON is a helper to inline JSON metadata in readings.
func mustJSON(v any) string {
	b, _ := json.Marshal(v)
	return string(b)
}

// ── Reading builders ──────────────────────────────────────────────────────────

func relayReading() iot26client.Reading {
	val := 0.0
	if state.Relay == "on" {
		val = 1.0
	}
	return iot26client.Reading{
		SensorID:     sensorRelay,
		Value:        val,
		Unit:         "state",
		MetadataJSON: mustJSON(map[string]string{"mode": state.Relay}),
	}
}

func acReading() iot26client.Reading {
	return iot26client.Reading{
		SensorID:     sensorACMode,
		Value:        1.0,
		Unit:         "state",
		MetadataJSON: mustJSON(map[string]string{"mode": state.ACMode}),
	}
}

func doorReading() iot26client.Reading {
	return iot26client.Reading{
		SensorID:     sensorDoorMotor,
		Value:        1.0,
		Unit:         "state",
		MetadataJSON: mustJSON(map[string]string{"motor": state.DoorMotor}),
	}
}

func brightnessReading() iot26client.Reading {
	// Slider reads the plain numeric value — no metadata needed
	return iot26client.Reading{
		SensorID: sensorBrightness,
		Value:    state.Brightness,
		Unit:     "%",
	}
}

func displayReading() iot26client.Reading {
	return iot26client.Reading{
		SensorID:     sensorDisplay,
		Value:        1.0,
		Unit:         "text",
		MetadataJSON: mustJSON(map[string]string{"display": state.DisplayMsg}),
	}
}

// publishAll pushes the full device state so the widget reflects reality.
func publishAll(client *iot26client.Client) {
	err := client.PublishReadings([]iot26client.Reading{
		relayReading(),
		acReading(),
		doorReading(),
		brightnessReading(),
		displayReading(),
	})
	if err != nil {
		log.Printf("⚠ publishAll error: %v", err)
	} else {
		log.Printf("↑ State pushed  relay=%s ac=%s door=%s brightness=%.0f display=%q",
			state.Relay, state.ACMode, state.DoorMotor, state.Brightness, state.DisplayMsg)
	}
}

// ── Command handler ───────────────────────────────────────────────────────────

func handleCommand(client *iot26client.Client) iot26client.CommandHandler {
	return func(cmd iot26client.Command) {
		log.Printf("↓ Command received: action=%s", cmd.Action)

		if cmd.Action != "custom" {
			log.Printf("  Ignoring non-custom action: %s", cmd.Action)
			return
		}

		// Decode the nested "custom" payload
		var body struct {
			Custom map[string]json.RawMessage `json:"custom"`
		}
		if err := json.Unmarshal(cmd.Raw, &body); err != nil || body.Custom == nil {
			log.Printf("  Could not decode custom payload: %v", err)
			return
		}
		c := body.Custom

		changed := false

		// ── Relay ────────────────────────────────────────────────────────────
		if raw, ok := c["relay"]; ok {
			var on bool
			if err := json.Unmarshal(raw, &on); err == nil {
				if on {
					state.Relay = "on"
				} else {
					state.Relay = "off"
				}
				log.Printf("  Relay → %s", state.Relay)
				_ = client.PublishReadings([]iot26client.Reading{relayReading()})
				changed = true
			}
		}

		// ── AC Mode ──────────────────────────────────────────────────────────
		if raw, ok := c["ac_mode"]; ok {
			var mode string
			if err := json.Unmarshal(raw, &mode); err == nil {
				switch mode {
				case "cool", "heat", "off":
					state.ACMode = mode
					log.Printf("  AC mode → %s", state.ACMode)
					_ = client.PublishReadings([]iot26client.Reading{acReading()})
					changed = true
				default:
					log.Printf("  Unknown AC mode: %q", mode)
				}
			}
		}

		// ── Door / Motor ──────────────────────────────────────────────────────
		if raw, ok := c["motor"]; ok {
			var pos string
			if err := json.Unmarshal(raw, &pos); err == nil {
				switch pos {
				case "open", "stop", "close":
					state.DoorMotor = pos
					log.Printf("  Door motor → %s", state.DoorMotor)
					_ = client.PublishReadings([]iot26client.Reading{doorReading()})
					changed = true
				default:
					log.Printf("  Unknown motor position: %q", pos)
				}
			}
		}

		// ── Brightness ────────────────────────────────────────────────────────
		if raw, ok := c["brightness"]; ok {
			var val float64
			if err := json.Unmarshal(raw, &val); err == nil {
				state.Brightness = val
				log.Printf("  Brightness → %.0f%%", state.Brightness)
				_ = client.PublishReadings([]iot26client.Reading{brightnessReading()})
				changed = true
			}
		}

		// ── Display text ──────────────────────────────────────────────────────
		if raw, ok := c["display"]; ok {
			var text string
			if err := json.Unmarshal(raw, &text); err == nil {
				state.DisplayMsg = text
				log.Printf("  Display → %q", state.DisplayMsg)
				_ = client.PublishReadings([]iot26client.Reading{displayReading()})
				changed = true
			}
		}

		if !changed {
			log.Println("  No recognized custom fields in command")
		}
	}
}

// ── Main ──────────────────────────────────────────────────────────────────────

func main() {
	deviceID := os.Getenv("IOT26_DEVICE_ID")
	if deviceID == "" {
		deviceID = "your-device-uuid"
	}
	deviceToken := os.Getenv("IOT26_DEVICE_TOKEN")
	if deviceToken == "" {
		deviceToken = "your-device-token"
	}
	broker := os.Getenv("IOT26_BROKER")
	if broker == "" {
		broker = "tcp://localhost:1883"
	}

	client, err := iot26client.New(iot26client.Config{
		DeviceID:    deviceID,
		DeviceToken: deviceToken,
		Broker:      broker,
	})
	if err != nil {
		log.Fatal("Failed to create IoT26 client:", err)
	}
	defer client.Disconnect()

	// Register command handler
	client.OnCommand(handleCommand(client))

	// Publish initial state so the widget immediately shows correct buttons
	fmt.Println("Publishing initial device state...")
	publishAll(client)

	fmt.Println("Running — widget reflects state in real time. Press Ctrl+C to stop.")
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		// Re-publish heartbeat state every 30 s
		publishAll(client)
	}
}
