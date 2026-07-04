'use strict';

/**
 * @file index.js
 * @description IoT26 Node.js client library.
 *
 * Publishes sensor readings to IoT26 and receives downlink commands over MQTT.
 *
 * Wire protocol:
 *   Publish  → devices/{device_id}/ingest   QoS 1
 *   Subscribe← devices/{device_id}/commands QoS 1
 *
 * Payload format (publish):
 *   { "token": "<device_token>", "readings": [ { "sensor_id", "value", "unit" }, ... ] }
 *
 * @example
 * const { IoT26Client } = require('iot26-client');
 *
 * const client = new IoT26Client({
 *   deviceId:    'your-device-uuid',
 *   deviceToken: 'eyJhbGci...',
 *   broker:      'mqtt://localhost:1883',
 * });
 *
 * await client.connect();
 * client.onCommand((cmd) => console.log('command:', cmd.action));
 * await client.publishReadings([
 *   { sensorId: 'sensor-uuid', value: 23.5, unit: '°C' },
 * ]);
 */

const mqtt = require('mqtt');
const EventEmitter = require('events');

// ── Constants ─────────────────────────────────────────────────────────────────

const DEFAULT_CONNECT_TIMEOUT = 10_000; // ms
const DEFAULT_PUBLISH_TIMEOUT = 5_000;  // ms
const QOS = 1;

// ── IoT26Client ───────────────────────────────────────────────────────────────

/**
 * @typedef {Object} Reading
 * @property {string} sensorId  - Sensor UUID matching IoT26 configuration
 * @property {number} value     - Scaled engineering value
 * @property {string} unit      - Unit string, e.g. '°C', '%RH', 'Pa'
 */

/**
 * @typedef {Object} Command
 * @property {string} action  - Command action, e.g. 'reload_config', 'restart'
 * @property {Object} raw     - Full parsed command object
 */

/**
 * @typedef {Object} IoT26ClientOptions
 * @property {string}  deviceId           - Device UUID from IoT26 dashboard
 * @property {string}  deviceToken        - Device JWT / API token
 * @property {string}  broker             - MQTT broker URL (mqtt://, mqtts://, ws://, wss://)
 * @property {Object}  [tlsOptions]       - Node.js tls.connect options for mqtts:// connections
 * @property {number}  [connectTimeout]   - ms to wait for connect (default: 10000)
 * @property {number}  [publishTimeout]   - ms to wait for QoS-1 puback (default: 5000)
 * @property {boolean} [debug]            - Enable debug logging to console
 */

class IoT26Client extends EventEmitter {
  /**
   * @param {IoT26ClientOptions} options
   */
  constructor(options) {
    super();

    const { deviceId, deviceToken, broker, tlsOptions, connectTimeout, publishTimeout, debug } = options;

    if (!deviceId || !deviceToken || !broker) {
      throw new Error('IoT26Client: deviceId, deviceToken, and broker are required');
    }

    this._deviceId      = deviceId;
    this._deviceToken   = deviceToken;
    this._broker        = broker;
    this._tlsOptions    = tlsOptions || null;
    this._connectTimeout = connectTimeout || DEFAULT_CONNECT_TIMEOUT;
    this._publishTimeout = publishTimeout || DEFAULT_PUBLISH_TIMEOUT;
    this._debug          = !!debug;

    this._ingestTopic  = `devices/${deviceId}/ingest`;
    this._commandTopic = `devices/${deviceId}/commands`;
    this._client       = null;
    this._commandHandler = null;
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  /**
   * Connect to the MQTT broker.
   * @returns {Promise<void>} Resolves when connected and subscribed.
   */
  connect() {
    return new Promise((resolve, reject) => {
      const clientId = `iot26-node-${this._deviceId.slice(0, 8)}-${Date.now()}`;

      const mqttOpts = {
        clientId,
        keepalive: 60,
        reconnectPeriod: 5_000,
        connectTimeout: this._connectTimeout,
        ...(this._tlsOptions ? { ...this._tlsOptions } : {}),
      };

      this._log(`Connecting to ${this._broker} as ${clientId}`);
      this._client = mqtt.connect(this._broker, mqttOpts);

      const timeout = setTimeout(() => {
        reject(new Error(`IoT26Client: connect timeout after ${this._connectTimeout}ms`));
      }, this._connectTimeout);

      this._client.once('connect', () => {
        clearTimeout(timeout);
        this._log(`Connected. Subscribing to ${this._commandTopic}`);
        this._client.subscribe(this._commandTopic, { qos: QOS }, (err) => {
          if (err) {
            reject(new Error(`IoT26Client: subscribe failed — ${err.message}`));
          } else {
            resolve();
          }
        });
      });

      this._client.once('error', (err) => {
        clearTimeout(timeout);
        reject(err);
      });

      this._client.on('reconnect', () => {
        this._log('Reconnecting…');
        this.emit('reconnect');
      });

      this._client.on('offline', () => {
        this._log('Client offline');
        this.emit('offline');
      });

      this._client.on('message', (topic, payload) => {
        this._handleMessage(topic, payload);
      });
    });
  }

  /**
   * Publish a batch of sensor readings.
   *
   * @param {Reading[]} readings
   * @returns {Promise<void>} Resolves when the broker acknowledges the publish.
   */
  publishReadings(readings) {
    if (!Array.isArray(readings) || readings.length === 0) {
      return Promise.resolve();
    }
    if (!this._client?.connected) {
      return Promise.reject(new Error('IoT26Client: not connected'));
    }

    const payload = JSON.stringify({
      token:    this._deviceToken,
      readings: readings.map((r) => ({
        sensor_id: r.sensorId,
        value:     r.value,
        unit:      r.unit,
      })),
    });

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new Error(`IoT26Client: publish timeout after ${this._publishTimeout}ms`));
      }, this._publishTimeout);

      this._client.publish(this._ingestTopic, payload, { qos: QOS }, (err) => {
        clearTimeout(timer);
        if (err) {
          reject(err);
        } else {
          this._log(`Published ${readings.length} reading(s) → ${this._ingestTopic}`);
          resolve();
        }
      });
    });
  }

  /**
   * Register a callback for downlink commands.
   * Replaces any previously registered handler.
   *
   * @param {function(Command): void} handler
   */
  onCommand(handler) {
    this._commandHandler = handler;
  }

  /**
   * Start a publish loop, calling readingsFn on each tick.
   *
   * @param {function(): Reading[]} readingsFn  - Function returning current readings
   * @param {number} intervalMs                 - Publish interval in milliseconds
   * @returns {{ stop: function(): void }}       - Object with a stop() method
   */
  startPublishLoop(readingsFn, intervalMs = 10_000) {
    const timer = setInterval(async () => {
      try {
        const readings = readingsFn();
        await this.publishReadings(readings);
      } catch (err) {
        this._log(`Publish error: ${err.message}`);
        this.emit('error', err);
      }
    }, intervalMs);

    return {
      stop: () => clearInterval(timer),
    };
  }

  /**
   * Disconnect from the broker.
   * @returns {Promise<void>}
   */
  disconnect() {
    return new Promise((resolve) => {
      if (!this._client) return resolve();
      this._client.end(false, {}, resolve);
    });
  }

  /** @returns {boolean} True if currently connected */
  get connected() {
    return !!this._client?.connected;
  }

  // ── Internal ────────────────────────────────────────────────────────────────

  _handleMessage(topic, payloadBuffer) {
    if (topic !== this._commandTopic) return;
    let cmd;
    try {
      cmd = JSON.parse(payloadBuffer.toString());
    } catch (err) {
      this._log(`Command parse error: ${err.message}`);
      return;
    }
    this._log(`Command received: action=${cmd.action}`);
    this.emit('command', { action: cmd.action, raw: cmd });
    if (this._commandHandler) {
      this._commandHandler({ action: cmd.action, raw: cmd });
    }
  }

  _log(msg) {
    if (this._debug) {
      console.log(`[IoT26] ${msg}`);
    }
  }
}

module.exports = { IoT26Client };
