// Package iot26client_test provides unit tests for the IoT26 Go client.
package iot26client_test

import (
	"encoding/json"
	"sync"
	"testing"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
	iot26client "github.com/iamfourh2e/IOT2026/sdk/go/iot26client"
)

// mockBroker spins up an in-memory mqtt.Client stub for testing without a
// real broker. For full integration tests, point at a local mosquitto instance.

// ─── Unit-level tests (no broker needed) ────────────────────────────────────

func TestReadingMarshalling(t *testing.T) {
	readings := []iot26client.Reading{
		{SensorID: "sensor-001", Value: 23.5, Unit: "°C"},
		{SensorID: "sensor-002", Value: 60.0, Unit: "%RH"},
	}

	data, err := json.Marshal(readings)
	if err != nil {
		t.Fatalf("marshal failed: %v", err)
	}

	var back []iot26client.Reading
	if err := json.Unmarshal(data, &back); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}

	if len(back) != 2 {
		t.Fatalf("expected 2 readings, got %d", len(back))
	}
	if back[0].SensorID != "sensor-001" {
		t.Errorf("unexpected sensor_id: %q", back[0].SensorID)
	}
	if back[1].Value != 60.0 {
		t.Errorf("unexpected value: %v", back[1].Value)
	}
}

func TestCommandParsing(t *testing.T) {
	payload := []byte(`{"action":"set_poll_interval","interval":30}`)

	var raw map[string]json.RawMessage
	if err := json.Unmarshal(payload, &raw); err != nil {
		t.Fatalf("unmarshal raw: %v", err)
	}

	var action string
	if err := json.Unmarshal(raw["action"], &action); err != nil {
		t.Fatalf("unmarshal action: %v", err)
	}
	if action != "set_poll_interval" {
		t.Errorf("unexpected action: %q", action)
	}
}

// ─── Integration test (requires real MQTT broker) ───────────────────────────
// Run with: IOT26_TEST_BROKER=tcp://localhost:1883 go test ./... -tags integration

func TestPublishAndReceive(t *testing.T) {
	t.Skip("integration test — set IOT26_TEST_BROKER and remove t.Skip() to run")

	const broker = "tcp://localhost:1883"
	deviceID := "test-device-1234"
	token := "test-token"

	// Set up a listener on the ingest topic using a raw paho client
	var wg sync.WaitGroup
	wg.Add(1)
	var received []byte

	opts := mqtt.NewClientOptions().AddBroker(broker).SetClientID("iot26-test-listener")
	listener := mqtt.NewClient(opts)
	if tok := listener.Connect(); !tok.WaitTimeout(5 * time.Second) {
		t.Fatal("listener connect timeout")
	}
	listener.Subscribe("devices/"+deviceID+"/ingest", 1, func(_ mqtt.Client, msg mqtt.Message) {
		received = msg.Payload()
		wg.Done()
	})
	defer listener.Disconnect(100)

	// Create IoT26 client and publish
	client, err := iot26client.New(iot26client.Config{
		DeviceID:    deviceID,
		DeviceToken: token,
		Broker:      broker,
	})
	if err != nil {
		t.Fatalf("client connect: %v", err)
	}
	defer client.Disconnect()

	err = client.PublishReadings([]iot26client.Reading{
		{SensorID: "s1", Value: 42.0, Unit: "°C"},
	})
	if err != nil {
		t.Fatalf("publish: %v", err)
	}

	done := make(chan struct{})
	go func() { wg.Wait(); close(done) }()

	select {
	case <-done:
	case <-time.After(5 * time.Second):
		t.Fatal("timed out waiting for message")
	}

	var payload struct {
		Token    string              `json:"token"`
		Readings []iot26client.Reading `json:"readings"`
	}
	if err := json.Unmarshal(received, &payload); err != nil {
		t.Fatalf("payload parse: %v", err)
	}
	if payload.Token != token {
		t.Errorf("token mismatch: got %q", payload.Token)
	}
	if len(payload.Readings) != 1 || payload.Readings[0].Value != 42.0 {
		t.Errorf("unexpected readings: %+v", payload.Readings)
	}
}
