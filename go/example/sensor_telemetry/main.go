// Package main — Normal Sensor Telemetry Example (IoT26 Go SDK)
//
// Shows how to publish continuous numeric sensor readings (flow, temperature,
// humidity, pressure, water level, power, energy, CO₂, soil moisture, pH)
// to IoT26. These are "display-only" sensors shown as charts, gauges, and
// value tiles on the dashboard. No metadata_json is needed.
//
// Common sensor types:
//
//	Flow rate     L/min  — water/gas flow meters
//	Temperature   °C     — DS18B20, NTC, thermocouples
//	Humidity      %RH    — DHT22, SHT31
//	Pressure      Pa     — BMP280, MPX5500
//	Water level   mm     — ultrasonic, float switch
//	Power         W      — CT clamp, PZEM-004T
//	Energy        kWh    — cumulative energy meter
//	CO₂ / gas     ppm    — MQ-135, SCD40
//	Soil moisture %      — capacitive soil sensor
//	pH            pH     — analog pH probe
//
// Usage:
//
//	IOT26_DEVICE_ID=<uuid> IOT26_DEVICE_TOKEN=<token> go run main.go
package main

import (
	"log"
	"math"
	"math/rand/v2"
	"os"
	"time"

	"github.com/iamfourh2e/IOT2026/sdk/go/iot26client"
)

// ── Sensor IDs — replace with UUIDs from your IoT26 sensor config ────────────

const (
	sensorFlowRate   = "flow-rate-sensor-uuid"     // L/min — water/gas flow meter
	sensorTemp       = "temperature-sensor-uuid"   // °C    — ambient temperature
	sensorHumidity   = "humidity-sensor-uuid"      // %RH   — relative humidity
	sensorPressure   = "pressure-sensor-uuid"      // Pa    — atmospheric/pipe pressure
	sensorWaterLevel = "water-level-sensor-uuid"   // mm    — tank water level
	sensorPower      = "power-sensor-uuid"         // W     — real-time power draw
	sensorEnergy     = "energy-sensor-uuid"        // kWh   — cumulative energy
	sensorCO2        = "co2-sensor-uuid"           // ppm   — CO₂ concentration
	sensorSoil       = "soil-moisture-sensor-uuid" // %     — soil moisture
	sensorPH         = "ph-sensor-uuid"            // pH    — water pH
)

const pollInterval = 5 * time.Second

// ── Simulated hardware reads (replace with real sensor driver calls) ──────────

var tick float64

func readFlowRate() float64   { return round(12.5+rand.NormFloat64()*0.3, 2) }
func readTemperature() float64 { return round(25.0+3.0*math.Sin(tick/60.0), 2) }
func readHumidity() float64   { return round(60.0+rand.NormFloat64()*1.5, 1) }
func readPressure() float64   { return round(101325+rand.NormFloat64()*50, 0) }
func readWaterLevel() float64 { return round(750+rand.NormFloat64()*5, 1) }
func readPower() float64      { return round(250.0+rand.NormFloat64()*10, 1) }
func readCO2() float64        { return round(450+rand.NormFloat64()*20, 0) }
func readSoilMoisture() float64 { return round(45.0+rand.NormFloat64()*2, 1) }
func readPH() float64         { return round(7.2+rand.NormFloat64()*0.05, 2) }

func incrementEnergy(prev float64, power float64) float64 {
	deltaKWh := power / 1000.0 * (float64(pollInterval) / float64(time.Hour))
	return round(prev+deltaKWh, 4)
}

func round(v float64, decimals int) float64 {
	p := math.Pow10(decimals)
	return math.Round(v*p) / p
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

	log.Printf("Publishing sensor telemetry every %s. Ctrl+C to stop.", pollInterval)

	totalEnergyKWh := 1234.5 // starting cumulative energy value
	ticker := time.NewTicker(pollInterval)
	defer ticker.Stop()

	for range ticker.C {
		tick += pollInterval.Seconds()

		flow   := readFlowRate()
		temp   := readTemperature()
		hum    := readHumidity()
		pres   := readPressure()
		level  := readWaterLevel()
		power  := readPower()
		energy := incrementEnergy(totalEnergyKWh, power)
		co2    := readCO2()
		soil   := readSoilMoisture()
		ph     := readPH()

		totalEnergyKWh = energy

		// ── Publish all readings in one batch ──────────────────────────────
		// No MetadataJSON needed for pure numeric sensors.
		// The dashboard displays them as charts, gauges, or value tiles.
		err = client.PublishReadings([]iot26client.Reading{
			{SensorID: sensorFlowRate,   Value: flow,   Unit: "L/min"},
			{SensorID: sensorTemp,       Value: temp,   Unit: "°C"},
			{SensorID: sensorHumidity,   Value: hum,    Unit: "%RH"},
			{SensorID: sensorPressure,   Value: pres,   Unit: "Pa"},
			{SensorID: sensorWaterLevel, Value: level,  Unit: "mm"},
			{SensorID: sensorPower,      Value: power,  Unit: "W"},
			{SensorID: sensorEnergy,     Value: energy, Unit: "kWh"},
			{SensorID: sensorCO2,        Value: co2,    Unit: "ppm"},
			{SensorID: sensorSoil,       Value: soil,   Unit: "%"},
			{SensorID: sensorPH,         Value: ph,     Unit: "pH"},
		})
		if err != nil {
			log.Printf("Publish error: %v", err)
			continue
		}

		log.Printf(
			"flow=%.1f L/min  temp=%.1f°C  hum=%.0f%%  level=%.0fmm  "+
				"power=%.0fW  energy=%.3fkWh  CO₂=%.0fppm  soil=%.0f%%  pH=%.2f",
			flow, temp, hum, level, power, energy, co2, soil, ph,
		)
	}
}
