# DTX-AI Hardware Demo Node (ESP32)

Everything that gets flashed to the ESP32 lives in this folder. The node
reads a **DS18B20** temperature probe and a **BMP280** barometric pressure
sensor and serves the readings as JSON over the local WiFi network. The
backend bridge (`scripts/hw_demo_bridge.py`) polls this API and feeds the
dashboard exactly like the dataset replay demo does.

## Bill of materials

| Part | Notes |
| --- | --- |
| ESP32-WROOM-32 dev board ("ESP32 DevKit") | classic 38/30-pin board |
| DS18B20 temperature sensor | 3 pins: `+`, `-`, `OUT` |
| BMP280 pressure module | 6 pins: `VCC`, `GND`, `SCL`, `SDA`, `CSB`, `SDO` |
| 4.7 kΩ resistor | DS18B20 data pull-up |
| Breadboard + jumper wires | |

## Wiring

```
ESP32-WROOM-32              DS18B20            BMP280
--------------              -------            ------
3V3  ──────────┬─────────── +
               ├─[4.7 kΩ]─┐
GPIO 4 ────────┴──────────┴ OUT
GND  ─────────────────────── -

3V3  ─────────────────────────────────────────  VCC
3V3  ─────────────────────────────────────────  CSB   (high = I2C mode)
GND  ─────────────────────────────────────────  GND
GND  ─────────────────────────────────────────  SDO   (low = I2C addr 0x76)
GPIO 22 ──────────────────────────────────────  SCL
GPIO 21 ──────────────────────────────────────  SDA
```

The full diagram with explanations is in `docs/hardware_demo.md`.

## Build & flash

```bash
cd HW
cp include/wifi_config.example.h include/wifi_config.h
# edit include/wifi_config.h with your WiFi SSID/password

pio run -t upload        # build + flash (auto-detects serial port)
pio device monitor       # watch boot log, note the IP address
```

## API

Once on WiFi the node is reachable at its DHCP IP (printed on the serial
monitor) and via mDNS at `http://dtx-esp32.local`.

| Endpoint | Response |
| --- | --- |
| `GET /` | plain-text banner |
| `GET /health` | `{"status":"ok","uptime_ms":…,"wifi_rssi_dbm":…,"ds18b20_ok":…,"bmp280_ok":…}` |
| `GET /reading` | `{"temperature_c":…,"pressure_pa":…,"bmp280_temperature_c":…,"sequence":…,"sampled_at_ms":…}` |

`temperature_c` comes from the DS18B20; `pressure_pa` is the BMP280
absolute pressure in pascal. Either field is `null` when the sensor is
missing or faulted, so the bridge can degrade gracefully.

## Using it in the demo

```bash
# on the machine running the DTX-AI backend:
python scripts/hw_demo_bridge.py --esp32-url http://dtx-esp32.local
```

or pick **IRL demo** on the dashboard's validation page — the backend then
starts/stops the bridge for you.
