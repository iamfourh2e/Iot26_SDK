// Package iot26client provides a Go client for publishing sensor readings
// to the IoT26 platform and receiving downlink commands over MQTT.
//
// Wire protocol:
//   - Publish  → devices/{device_id}/ingest   (QoS 1)
//   - Subscribe← devices/{device_id}/commands (QoS 1)
//
// Basic usage:
//
//	client, err := iot26client.New(iot26client.Config{
//	    DeviceID:    "your-device-uuid",
//	    DeviceToken: "eyJhbGci...",
//	    Broker:      "tcp://your-broker.com:1883",
//	})
//	if err != nil {
//	    log.Fatal(err)
//	}
//	defer client.Disconnect()
//
//	client.OnCommand(func(cmd iot26client.Command) {
//	    fmt.Println("action:", cmd.Action)
//	})
//
//	err = client.PublishReadings([]iot26client.Reading{
//	    {SensorID: "sensor-uuid", Value: 23.5, Unit: "°C"},
//	})
package iot26client

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"log/slog"
	"sync"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

// ── Public types ──────────────────────────────────────────────────────────────

// Reading is a single sensor measurement to publish.
type Reading struct {
	SensorID string  `json:"sensor_id"`
	Value    float64 `json:"value"`
	Unit     string  `json:"unit"`
}

// Command is a downlink message received from IoT26.
type Command struct {
	Action string          `json:"action"`
	Raw    json.RawMessage `json:"-"` // full JSON for action-specific fields
}

// CommandHandler is called each time a command arrives.
type CommandHandler func(cmd Command)

// Config holds the connection parameters for the client.
type Config struct {
	// DeviceID is the UUID of the device in IoT26.
	DeviceID string

	// DeviceToken is the device JWT / API token from IoT26.
	DeviceToken string

	// Broker is the MQTT broker URL, e.g.:
	//   "tcp://localhost:1883"        plain MQTT
	//   "ssl://your-broker.com:8883"  MQTTS
	//   "ws://localhost:9001"         WebSocket
	Broker string

	// TLSConfig is optional — set for custom CA or client certificates.
	// Leave nil to use the system root CAs (needed for "ssl://" Broker URLs).
	TLSConfig *tls.Config

	// ConnectTimeout is how long to wait for the initial MQTT handshake.
	// Default: 10 seconds.
	ConnectTimeout time.Duration

	// PublishTimeout is how long to wait for a publish acknowledgement (QoS 1).
	// Default: 5 seconds.
	PublishTimeout time.Duration

	// Logger is an optional structured logger. Defaults to slog.Default().
	Logger *slog.Logger
}

// ── Client ────────────────────────────────────────────────────────────────────

// Client is a thread-safe IoT26 MQTT client.
type Client struct {
	cfg     Config
	log     *slog.Logger
	mqttc   mqtt.Client
	handler CommandHandler
	mu      sync.RWMutex

	ingestTopic  string
	commandTopic string
}

// New creates and connects a new Client.
// Returns an error if the initial connection to the broker fails.
func New(cfg Config) (*Client, error) {
	if cfg.DeviceID == "" || cfg.DeviceToken == "" || cfg.Broker == "" {
		return nil, fmt.Errorf("iot26client: DeviceID, DeviceToken, and Broker are required")
	}
	if cfg.ConnectTimeout == 0 {
		cfg.ConnectTimeout = 10 * time.Second
	}
	if cfg.PublishTimeout == 0 {
		cfg.PublishTimeout = 5 * time.Second
	}

	log := cfg.Logger
	if log == nil {
		log = slog.Default()
	}

	c := &Client{
		cfg:          cfg,
		log:          log,
		ingestTopic:  fmt.Sprintf("devices/%s/ingest", cfg.DeviceID),
		commandTopic: fmt.Sprintf("devices/%s/commands", cfg.DeviceID),
	}

	if err := c.connect(); err != nil {
		return nil, err
	}
	return c, nil
}

// OnCommand registers a handler called when a downlink command arrives.
// Replaces any previously registered handler. Safe to call from any goroutine.
func (c *Client) OnCommand(h CommandHandler) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.handler = h
}

// PublishReadings publishes a batch of sensor readings.
// Blocks until the broker acknowledges the message (QoS 1) or the publish
// timeout is exceeded.
func (c *Client) PublishReadings(readings []Reading) error {
	if len(readings) == 0 {
		return nil
	}

	payload := struct {
		Token    string    `json:"token"`
		Readings []Reading `json:"readings"`
	}{
		Token:    c.cfg.DeviceToken,
		Readings: readings,
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("iot26client: marshal readings: %w", err)
	}

	token := c.mqttc.Publish(c.ingestTopic, 1 /*QoS*/, false, data)
	if ok := token.WaitTimeout(c.cfg.PublishTimeout); !ok {
		return fmt.Errorf("iot26client: publish timeout after %s", c.cfg.PublishTimeout)
	}
	if err := token.Error(); err != nil {
		return fmt.Errorf("iot26client: publish: %w", err)
	}

	c.log.Info("published readings", "count", len(readings), "topic", c.ingestTopic)
	return nil
}

// Disconnect cleanly closes the MQTT connection.
// The quiesce period is 250 ms.
func (c *Client) Disconnect() {
	c.mqttc.Disconnect(250)
	c.log.Info("disconnected from broker")
}

// RunForever blocks, publishing readings on the given interval.
// readings is called each tick to obtain the current batch.
// Stops when ctx is cancelled.
func (c *Client) RunForever(ctx context.Context, interval time.Duration, readings func() []Reading) error {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	c.log.Info("starting publish loop", "interval", interval)
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
			batch := readings()
			if err := c.PublishReadings(batch); err != nil {
				c.log.Error("publish failed", "error", err)
			}
		}
	}
}

// ── Internal ──────────────────────────────────────────────────────────────────

func (c *Client) connect() error {
	clientID := fmt.Sprintf("iot26-go-%s", safePrefix(c.cfg.DeviceID, 8))

	opts := mqtt.NewClientOptions().
		AddBroker(c.cfg.Broker).
		SetClientID(clientID).
		SetKeepAlive(60 * time.Second).
		SetAutoReconnect(true).
		SetMaxReconnectInterval(60 * time.Second).
		SetOnConnectHandler(c.onConnect).
		SetConnectionLostHandler(c.onConnectionLost)

	if c.cfg.TLSConfig != nil {
		opts.SetTLSConfig(c.cfg.TLSConfig)
	}

	c.mqttc = mqtt.NewClient(opts)
	token := c.mqttc.Connect()
	if ok := token.WaitTimeout(c.cfg.ConnectTimeout); !ok {
		return fmt.Errorf("iot26client: connect timeout after %s", c.cfg.ConnectTimeout)
	}
	return token.Error()
}

func (c *Client) onConnect(client mqtt.Client) {
	c.log.Info("MQTT connected", "broker", c.cfg.Broker)
	// Re-subscribe on every connect (handles reconnects)
	token := client.Subscribe(c.commandTopic, 1, c.onMessage)
	token.Wait()
	if err := token.Error(); err != nil {
		c.log.Error("subscribe failed", "topic", c.commandTopic, "error", err)
	} else {
		c.log.Info("subscribed to commands", "topic", c.commandTopic)
	}
}

func (c *Client) onConnectionLost(_ mqtt.Client, err error) {
	c.log.Warn("MQTT connection lost — will auto-reconnect", "error", err)
}

func (c *Client) onMessage(_ mqtt.Client, msg mqtt.Message) {
	c.mu.RLock()
	h := c.handler
	c.mu.RUnlock()

	if h == nil {
		return
	}

	var raw map[string]json.RawMessage
	if err := json.Unmarshal(msg.Payload(), &raw); err != nil {
		c.log.Error("command parse error", "error", err)
		return
	}

	var action string
	if a, ok := raw["action"]; ok {
		_ = json.Unmarshal(a, &action)
	}

	cmd := Command{
		Action: action,
		Raw:    msg.Payload(),
	}
	c.log.Info("command received", "action", action)
	h(cmd)
}

func safePrefix(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}
