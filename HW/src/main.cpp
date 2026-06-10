// DTX-AI hardware demo node.
//
// ESP32-WROOM-32 reading a DS18B20 (1-Wire temperature) and a BMP280
// (I2C pressure), exposed as a tiny JSON HTTP API on the local WiFi so
// scripts/hw_demo_bridge.py can stream readings into the DTX-AI backend.
//
// Wiring (see docs/hardware_demo.md for the full diagram):
//   DS18B20  +      -> 3V3
//   DS18B20  -      -> GND
//   DS18B20  OUT    -> GPIO 4   (with a 4.7 kΩ pull-up resistor to 3V3)
//   BMP280   VCC    -> 3V3
//   BMP280   GND    -> GND
//   BMP280   SCL    -> GPIO 22  (I2C clock)
//   BMP280   SDA    -> GPIO 21  (I2C data)
//   BMP280   CSB    -> 3V3     (selects I2C mode)
//   BMP280   SDO    -> GND     (I2C address 0x76)
//
// Endpoints:
//   GET /         -> plain-text identity banner
//   GET /health   -> {"status":"ok","uptime_ms":...,"wifi_rssi_dbm":...}
//   GET /reading  -> latest sensor sample (see handleReading)

#include <Arduino.h>
#include <ArduinoJson.h>
#include <DallasTemperature.h>
#include <ESPmDNS.h>
#include <OneWire.h>
#include <WebServer.h>
#include <WiFi.h>
#include <Wire.h>

#include <Adafruit_BMP280.h>

#include "wifi_config.h"

constexpr uint8_t ONE_WIRE_PIN = 4;     // DS18B20 data (needs 4.7k pull-up)
constexpr uint8_t BMP_I2C_ADDR = 0x76;  // SDO -> GND
constexpr uint32_t SAMPLE_PERIOD_MS = 500;
constexpr char MDNS_HOSTNAME[] = "dtx-esp32";

OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature ds18b20(&oneWire);
Adafruit_BMP280 bmp280;  // I2C on default Wire (SDA 21 / SCL 22)
WebServer server(80);

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
bool bmp280_present = false;
uint32_t lastSampleMs = 0;

void takeSample() {
  Sample s;
  s.sequence = latest.sequence + 1;
  s.sampled_at_ms = millis();

  ds18b20.requestTemperatures();
  const float tempC = ds18b20.getTempCByIndex(0);
  if (tempC > DEVICE_DISCONNECTED_C + 1.0f) {
    s.ds18b20_temperature_c = tempC;
    s.ds18b20_ok = true;
  }

  if (bmp280_present) {
    const float pressurePa = bmp280.readPressure();  // already in Pa
    const float bmpTempC = bmp280.readTemperature();
    if (!isnan(pressurePa) && pressurePa > 30000.0f && pressurePa < 120000.0f) {
      s.bmp280_pressure_pa = pressurePa;
      s.bmp280_temperature_c = bmpTempC;
      s.bmp280_ok = true;
    }
  }

  latest = s;
}

void handleRoot() {
  server.send(200, "text/plain",
              "DTX-AI hardware demo node (ESP32-WROOM-32 + DS18B20 + BMP280)\n"
              "GET /health  -> node status\n"
              "GET /reading -> latest sensor sample as JSON\n");
}

void handleHealth() {
  JsonDocument doc;
  doc["status"] = "ok";
  doc["uptime_ms"] = millis();
  doc["wifi_rssi_dbm"] = WiFi.RSSI();
  doc["ip"] = WiFi.localIP().toString();
  doc["ds18b20_ok"] = latest.ds18b20_ok;
  doc["bmp280_ok"] = latest.bmp280_ok;
  String body;
  serializeJson(doc, body);
  server.send(200, "application/json", body);
}

void handleReading() {
  JsonDocument doc;
  // Field names deliberately match what scripts/hw_demo_bridge.py expects.
  if (latest.ds18b20_ok) {
    doc["temperature_c"] = latest.ds18b20_temperature_c;
  } else {
    doc["temperature_c"] = nullptr;
  }
  if (latest.bmp280_ok) {
    doc["pressure_pa"] = latest.bmp280_pressure_pa;
    doc["bmp280_temperature_c"] = latest.bmp280_temperature_c;
  } else {
    doc["pressure_pa"] = nullptr;
    doc["bmp280_temperature_c"] = nullptr;
  }
  doc["sequence"] = latest.sequence;
  doc["sampled_at_ms"] = latest.sampled_at_ms;
  doc["ds18b20_ok"] = latest.ds18b20_ok;
  doc["bmp280_ok"] = latest.bmp280_ok;
  String body;
  serializeJson(doc, body);
  server.send(200, "application/json", body);
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
#if DTX_USE_STATIC_IP
  IPAddress ip(DTX_STATIC_IP), gw(DTX_GATEWAY), sn(DTX_SUBNET);
  WiFi.config(ip, gw, sn);
#endif
  WiFi.begin(DTX_WIFI_SSID, DTX_WIFI_PASSWORD);
  Serial.printf("Connecting to WiFi '%s'", DTX_WIFI_SSID);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\nConnected. IP: %s\n", WiFi.localIP().toString().c_str());
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\nDTX-AI hardware demo node booting...");

  ds18b20.begin();
  Serial.printf("DS18B20 devices found: %d\n", ds18b20.getDeviceCount());

  Wire.begin();  // SDA 21, SCL 22
  bmp280_present = bmp280.begin(BMP_I2C_ADDR);
  if (!bmp280_present) {
    // Some clone boards strap SDO high -> address 0x77.
    bmp280_present = bmp280.begin(0x77);
  }
  Serial.printf("BMP280 present: %s\n", bmp280_present ? "yes" : "NO");
  if (bmp280_present) {
    bmp280.setSampling(Adafruit_BMP280::MODE_NORMAL,
                       Adafruit_BMP280::SAMPLING_X2,   // temperature
                       Adafruit_BMP280::SAMPLING_X16,  // pressure
                       Adafruit_BMP280::FILTER_X16,
                       Adafruit_BMP280::STANDBY_MS_125);
  }

  connectWifi();

  if (MDNS.begin(MDNS_HOSTNAME)) {
    MDNS.addService("http", "tcp", 80);
    Serial.printf("mDNS: http://%s.local\n", MDNS_HOSTNAME);
  }

  server.on("/", handleRoot);
  server.on("/health", handleHealth);
  server.on("/reading", handleReading);
  server.begin();
  Serial.println("HTTP server listening on port 80.");

  takeSample();
}

void loop() {
  server.handleClient();
  const uint32_t now = millis();
  if (now - lastSampleMs >= SAMPLE_PERIOD_MS) {
    lastSampleMs = now;
    takeSample();
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi lost — reconnecting...");
    connectWifi();
  }
}
