# DTX-AI Hardware Demo Node (ESP32)

Release: **v3.0 Final** (package version `3.0.0`).

Everything that gets flashed to the ESP32 lives in this folder. The node
reads a **DS18B20** temperature probe and a **BMP280** barometric pressure
sensor and serves the readings as JSON over the local WiFi network. The
backend bridge (`scripts/hw_demo_bridge.py`) polls this API and feeds the
dashboard exactly like the dataset replay demo does.

## Bill of materials

| Part | Notes |
| --- | --- |
| ESP32-WROOM-32 dev board ("ESP32 DevKit") | classic 38/30-pin board |
| DS18B20 temperature sensor | 3 leads: `+`, `-`, yellow `DATA` (also called `OUT`/`DQ`) |
| BMP280 pressure module | 6 pins: `VCC`, `GND`, `SCL`, `SDA`, `CSB`, `SDO` |
| 4.7 kΩ resistor | DS18B20 data pull-up |
| Breadboard + jumper wires | |

## Wiring

The **DS18B20** uses 1-Wire: its yellow lead is data, in addition to
separate power and ground. The **BMP280** uses I²C here, with separate
SDA and SCL lines; it is not a 1-Wire sensor.

| Sensor lead | ESP32 connection |
| --- | --- |
| DS18B20 `+` | 3V3 |
| DS18B20 `-` | GND |
| DS18B20 yellow `DATA` / `OUT` | GPIO 4 |
| 4.7 kΩ resistor | between yellow DATA / GPIO 4 and 3V3 |
| BMP280 `VCC` and `CSB` | 3V3 |
| BMP280 `GND` and `SDO` | GND (address `0x76`) |
| BMP280 `SDA` | GPIO 21 |
| BMP280 `SCL` | GPIO 22 |

```
3V3 -------------------------- DS18B20 +
3V3 ----[4.7 kΩ]----+---------- DS18B20 yellow DATA
                   |
GPIO 4 ------------+
GND -------------------------- DS18B20 -
```

The resistor is the connection between data and 3V3; do not replace it
with a direct wire. This firmware expects external power on `+`, not
parasite power. All sensors share the ESP32 ground. Follow the probe's
labels/vendor pinout if its wire colors differ.

The full diagram with explanations is in `docs/hardware_demo.md`.

## Build & flash

```bash
cd HW
test -f include/wifi_config.h || cp include/wifi_config.example.h include/wifi_config.h
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
missing, faulted, or stale. The firmware samples once per second and waits
750 ms for a 12-bit DS18B20 conversion without blocking HTTP handling.
`sampled_at_ms` is the completed sample time; `sample_age_ms` reports its age.
`/health` reports `warming_up`, `ok`, `degraded`, or `stale` based on the sensors.
Failed sensors are probed again every five seconds, and WiFi connection attempts
run in the background. Use a 2.4 GHz WiFi network.

The bridge skips events when neither sensor has valid fresh data. When one
sensor fails, its channels use nominal synthesized values and are identified
as synthesized in event metadata. A sensor missing at startup gets a baseline
from its first valid reading on recovery; keep it unstimulated at that point.

The firmware has been compiled for `esp32dev`; verifying actual readings,
disconnect/reconnect recovery, and power/wiring still requires the board.
A repeated 85 °C reading at room temperature can indicate a DS18B20 power
reset. A real 85 °C measurement is valid and is not automatically discarded.

References: [DS18B20 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ds18b20.pdf),
[BMP280 datasheet](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp280-ds001.pdf).

## Using it in the demo

```bash
# on the machine running the DTX-AI backend:
python scripts/hw_demo_bridge.py --esp32-url http://dtx-esp32.local
```

or pick **IRL demo** on the dashboard's validation page — the backend then
starts/stops the bridge for you.
