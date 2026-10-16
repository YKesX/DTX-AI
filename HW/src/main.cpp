// DTX-AI hardware demo node: externally powered DS18B20 + I2C BMP280.
// DS18B20: + -> 3V3, - -> GND, yellow DATA -> GPIO 4.
// Place a 4.7 kOhm resistor BETWEEN GPIO 4/DATA and 3V3 (not a jumper).
// BMP280: VCC/CSB -> 3V3, GND/SDO -> GND, SDA -> 21, SCL -> 22.
// The BMP280 does not support the DS18B20's 1-Wire protocol.

#include <Arduino.h>
#include <ArduinoJson.h>
#include <DallasTemperature.h>
#include <ESPmDNS.h>
#include <OneWire.h>
#include <WebServer.h>
#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_BMP280.h>
#include <math.h>

#include "wifi_config.h"

constexpr uint8_t ONE_WIRE_PIN = 4;
constexpr uint8_t I2C_SDA_PIN = 21;
constexpr uint8_t I2C_SCL_PIN = 22;
constexpr uint32_t SAMPLE_PERIOD_MS = 1000;
constexpr uint32_t CONVERSION_MS = 750;  // DS18B20 maximum at 12-bit resolution
constexpr uint32_t SENSOR_RETRY_MS = 5000;
constexpr uint32_t WIFI_RETRY_MS = 15000;
constexpr uint32_t STALE_AFTER_MS = 3000;
constexpr char FIRMWARE_RELEASE[] = "v3.0 Final";
constexpr char MDNS_HOSTNAME[] = "dtx-esp32";

OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature ds18b20(&oneWire);
Adafruit_BMP280 bmp280;
WebServer server(80);
DeviceAddress temperatureAddress;

struct Sample {
  float ds18b20_temperature_c = NAN;
  float bmp280_pressure_pa = NAN;
  float bmp280_temperature_c = NAN;
  uint32_t sequence = 0;
  uint32_t sampled_at_ms = 0;
  bool ds18b20_ok = false;
  bool bmp280_ok = false;
};

Sample latest;
bool ds18b20_present = false;
bool bmp280_present = false;
bool conversionPending = false;
bool conversionRequested = false;
bool wifiWasConnected = false;
bool mdnsStarted = false;
uint8_t bmpAddress = 0;
uint32_t conversionStartedMs = 0;
uint32_t lastSampleStartMs = 0;
uint32_t lastSensorRetryMs = 0;
uint32_t lastWifiAttemptMs = 0;

bool i2cResponds(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
}

void discoverSensors() {
  if (!ds18b20_present) {
    ds18b20.setOneWire(&oneWire);  // reset cached parasite-power state before rescanning
    ds18b20.begin();
    ds18b20.setAutoSaveScratchPad(false);  // no EEPROM writes on each recovery
    ds18b20.setWaitForConversion(false);
    ds18b20_present = ds18b20.getAddress(temperatureAddress, 0) &&
                      temperatureAddress[0] == 0x28 &&
                      !ds18b20.isParasitePowerMode();
    if (ds18b20_present) {
      ds18b20_present = ds18b20.setResolution(temperatureAddress, 12);
    }
    Serial.printf("DS18B20: %s\n", ds18b20_present ? "ready" :
                  "not ready; check +/GND/yellow DATA and 4.7k pull-up (external power required)");
  }
  if (!bmp280_present) {
    for (uint8_t address : {uint8_t(0x76), uint8_t(0x77)}) {
      if (i2cResponds(address) && bmp280.begin(address)) {
        bmpAddress = address;
        bmp280_present = true;
        bmp280.setSampling(Adafruit_BMP280::MODE_NORMAL,
                           Adafruit_BMP280::SAMPLING_X2,
                           Adafruit_BMP280::SAMPLING_X16,
                           Adafruit_BMP280::FILTER_X16,
                           Adafruit_BMP280::STANDBY_MS_125);
        Serial.printf("BMP280: ready at 0x%02X\n", address);
        break;
      }
    }
    if (!bmp280_present) {
      Serial.println("BMP280: not found at 0x76/0x77; check SDA=21, SCL=22, CSB=3V3, SDO=GND");
    }
  }
}

void startSample() {
  conversionRequested = ds18b20_present &&
                        ds18b20.requestTemperaturesByAddress(temperatureAddress).result;
  // Record the time AFTER issuing Convert T. No blocking conversion delay.
  conversionStartedMs = millis();
  lastSampleStartMs = conversionStartedMs;
  conversionPending = true;
}

void finishSample() {
  Sample s;
  s.sequence = latest.sequence + 1;
  if (conversionRequested && ds18b20.isConversionComplete()) {
    // DallasTemperature checks scratchpad CRC and returns -127 on disconnect.
    const float tempC = ds18b20.getTempC(temperatureAddress);
    if (isfinite(tempC) && tempC >= -55.0f && tempC <= 125.0f) {
      s.ds18b20_temperature_c = tempC;
      s.ds18b20_ok = true;
    }
  }
  if (!s.ds18b20_ok) ds18b20_present = false;

  if (bmp280_present && i2cResponds(bmpAddress)) {
    const float pressurePa = bmp280.readPressure();
    const float bmpTempC = bmp280.readTemperature();
    if (i2cResponds(bmpAddress) && isfinite(pressurePa) &&
        pressurePa >= 30000.0f && pressurePa <= 110000.0f &&
        isfinite(bmpTempC) && bmpTempC >= -40.0f && bmpTempC <= 85.0f) {
      s.bmp280_pressure_pa = pressurePa;
      s.bmp280_temperature_c = bmpTempC;
      s.bmp280_ok = true;
    }
  }
  if (!s.bmp280_ok) bmp280_present = false;
  s.sampled_at_ms = millis();
  latest = s;
  conversionPending = false;
}

bool sampleFresh() {
  return latest.sequence != 0 && millis() - latest.sampled_at_ms <= STALE_AFTER_MS;
}

void addSampleStatus(JsonDocument& doc) {
  const bool fresh = sampleFresh();
  doc["ds18b20_ok"] = fresh && latest.ds18b20_ok;
  doc["bmp280_ok"] = fresh && latest.bmp280_ok;
  if (latest.sequence != 0) doc["sample_age_ms"] = millis() - latest.sampled_at_ms;
  else doc["sample_age_ms"] = nullptr;
}

void handleRoot() {
  server.send(200, "text/plain",
              "DTX-AI v3.0 Final hardware node (ESP32 + DS18B20 + BMP280)\n"
              "GET /health -> node and sensor status\n"
              "GET /reading -> latest sensor sample\n");
}

void handleHealth() {
  JsonDocument doc;
  doc["status"] = latest.sequence == 0 ? "warming_up" :
                  !sampleFresh() ? "stale" :
                  latest.ds18b20_ok && latest.bmp280_ok ? "ok" : "degraded";
  doc["release"] = FIRMWARE_RELEASE;
  doc["firmware_version"] = "3.0.0";
  doc["uptime_ms"] = millis();
  doc["wifi_rssi_dbm"] = WiFi.RSSI();
  doc["ip"] = WiFi.localIP().toString();
  addSampleStatus(doc);
  String body;
  serializeJson(doc, body);
  server.send(200, "application/json", body);
}

void handleReading() {
  JsonDocument doc;
  const bool fresh = sampleFresh();
  // Names and units match scripts/hw_demo_bridge.py. Invalid data stays null.
  if (fresh && latest.ds18b20_ok) doc["temperature_c"] = latest.ds18b20_temperature_c;
  else doc["temperature_c"] = nullptr;
  if (fresh && latest.bmp280_ok) {
    doc["pressure_pa"] = latest.bmp280_pressure_pa;
    doc["bmp280_temperature_c"] = latest.bmp280_temperature_c;
  } else {
    doc["pressure_pa"] = nullptr;
    doc["bmp280_temperature_c"] = nullptr;
  }
  doc["sequence"] = latest.sequence;
  doc["sampled_at_ms"] = latest.sampled_at_ms;
  addSampleStatus(doc);
  String body;
  serializeJson(doc, body);
  server.send(200, "application/json", body);
}

void serviceWifi() {
  const bool connected = WiFi.status() == WL_CONNECTED;
  if (connected && !wifiWasConnected) {
    Serial.printf("WiFi connected. IP: %s\n", WiFi.localIP().toString().c_str());
    if (mdnsStarted) MDNS.end();
    mdnsStarted = MDNS.begin(MDNS_HOSTNAME);
    if (mdnsStarted) {
      MDNS.addService("http", "tcp", 80);
      Serial.printf("mDNS: http://%s.local\n", MDNS_HOSTNAME);
    }
  }
  if (!connected && wifiWasConnected) {
    Serial.println("WiFi lost; sampling continues while reconnecting.");
    if (mdnsStarted) MDNS.end();
    mdnsStarted = false;
  }
  wifiWasConnected = connected;
  if (!connected && millis() - lastWifiAttemptMs >= WIFI_RETRY_MS) {
    lastWifiAttemptMs = millis();
    Serial.println("Retrying WiFi; check SSID/password and a 2.4 GHz network.");
    WiFi.reconnect();
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\nDTX-AI v3.0 Final hardware node booting...");
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.setTimeOut(50);  // bound failed I2C transactions
  discoverSensors();
  lastSensorRetryMs = millis();

  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
#if DTX_USE_STATIC_IP
  IPAddress ip(DTX_STATIC_IP), gw(DTX_GATEWAY), sn(DTX_SUBNET);
  if (!WiFi.config(ip, gw, sn)) Serial.println("Static IP configuration failed.");
#endif
  WiFi.begin(DTX_WIFI_SSID, DTX_WIFI_PASSWORD);
  lastWifiAttemptMs = millis();
  Serial.println("Connecting to WiFi in background...");

  server.on("/", HTTP_GET, handleRoot);
  server.on("/health", HTTP_GET, handleHealth);
  server.on("/reading", HTTP_GET, handleReading);
  server.begin();
  startSample();
}

void loop() {
  server.handleClient();
  serviceWifi();
  const uint32_t now = millis();
  if (conversionPending && now - conversionStartedMs >= CONVERSION_MS) finishSample();
  if (!conversionPending) {
    if ((!ds18b20_present || !bmp280_present) && now - lastSensorRetryMs >= SENSOR_RETRY_MS) {
      lastSensorRetryMs = now;
      discoverSensors();
    }
    if (now - lastSampleStartMs >= SAMPLE_PERIOD_MS) startSample();
  }
  delay(1);  // yield to the ESP32 network/RTOS tasks
}
