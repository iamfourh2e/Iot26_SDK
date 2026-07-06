package main

import (
	"fmt"
	"log"
	"time"

	"github.com/iamfourh2e/IOT2026/sdk/go/iot26client"
)

func main() {
	// Initialize the IoT26 Go SDK Client
	client, err := iot26client.New(iot26client.Config{
		DeviceID:    "your-device-uuid",
		DeviceToken: "your-device-token",
		Broker:      "tcp://localhost:1883",
	})
	if err != nil {
		log.Fatal(err)
	}
	defer client.Disconnect()

	// Listen for downlink commands (like from Widget Builder)
	client.OnCommand(func(cmd iot26client.Command) {
		fmt.Printf("Received command action: %s\n", cmd.Action)

		if cmd.Action == "custom" {
			// Example: if command toggles a valve, publish the new state!
			fmt.Println("Processing custom command...")

			// Publish uplink to update dashboard widget state
			err = client.PublishReadings([]iot26client.Reading{
				{SensorID: "valve-sensor-uuid", Value: 1.0, Unit: "state"},
			})
			if err != nil {
				log.Printf("Failed to publish uplink: %v", err)
			} else {
				log.Println("Published uplink state successfully!")
			}
		}
	})

	// Simulate periodic telemetry uplinks
	for {
		log.Println("Publishing routine sensor telemetry...")
		err = client.PublishReadings([]iot26client.Reading{
			{SensorID: "temp-sensor-uuid", Value: 24.5, Unit: "C"},
			{SensorID: "hum-sensor-uuid", Value: 60.0, Unit: "%"},
		})
		if err != nil {
			log.Printf("Publish error: %v", err)
		}
		time.Sleep(10 * time.Second)
	}
}
