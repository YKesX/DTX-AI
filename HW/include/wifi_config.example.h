#pragma once

// Copy to wifi_config.h and use a 2.4 GHz WiFi network.
// wifi_config.h is gitignored; keep actual credentials there.
#define DTX_WIFI_SSID     "YOUR_WIFI_SSID"
#define DTX_WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

#define DTX_USE_STATIC_IP 0
#define DTX_STATIC_IP     192, 168, 1, 80
#define DTX_GATEWAY       192, 168, 1, 1
#define DTX_SUBNET        255, 255, 255, 0
