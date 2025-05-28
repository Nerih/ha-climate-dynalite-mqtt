# HA Climate → Dynalite Bridge

🚀 A lightweight Python async service that syncs Home Assistant MQTT climate topics with a Dynalite lighting system (via Dynet1/Dynet2) in both directions.

## Features

- 🔄 **Bidirectional sync** between Home Assistant Climate and Dynalite HVAC channels
- 🧠 Intelligent state caching to reduce redundant network chatter
- 🧾 Response tracking via UUID with auto-expiry logging
- 📡 MQTT message handling for both climate state and Dynalite set commands
- 🪛 Designed for containerized deployment (Docker)

---

## Topics Handled

| Direction | Topic                                         | Description                                    |
|----------|-----------------------------------------------|------------------------------------------------|
| ⬅ HA → Dynalite | `homeassistant/climate/+/state`              | Receives climate updates from HA               |
| ⬅ HA → Dynalite | `${MQTT_DYNALITE_PREFIX}/set`              | Sends structured Dynet commands to Dynalite    |
| ➡ Dynalite → HA | `${MQTT_DYNALITE_PREFIX}/set/res/#`        | Receives feedback from Dynalite bridge         |
| ⬅ Status Watch | `${MQTT_DYNALITE_WILL}` / `${MQTT_CLIMATE_WILL}` | Waits for dependent bridges to report online  |

---

## Dynalite Channel Mapping

| Channel | Purpose        | Value Mapping                           |
|---------|----------------|------------------------------------------|
| 101     | On/Off         | `0=off`, `1=auto`                        |
| 102     | HVAC Mode      | `0=cool`, `1=heat`, `2=fan`, `3=dry`, `4=auto` |
| 103     | Fan Speed      | `0=low`, `1=med`, `2=high`, `3=top`, `4=auto` |
| 105     | Error Status   | `0=OK`, `1=Error`                        |

---

## Requirements

- Python 3.8+
- MQTT broker (e.g., Mosquitto)
- Dynalite bridge (supporting Dynet1/2)
- Home Assistant with `mqtt` climate entities

---

## Environment Configuration

These are the required environment variables:

```env
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_USERNAME=your_mqtt_user
MQTT_PASSWORD=your_mqtt_password

MQTT_CLIMATE_STATE=homeassistant/climate/+/state
MQTT_CLIMATE_PREFIX=homeassistant/climate
MQTT_DYNALITE_PREFIX=dynalite

MQTT_BRIDGE_WILL=bridges/climate_dynalite
MQTT_CLIMATE_WILL=bridges/climate/status
MQTT_DYNALITE_WILL=bridges/dynalite/status

TEMP_PRECISION=1
OUT_JOIN=254
IN_JOIN=255
MQTT_DEBUG=False
Running in Docker
Here's a minimal Dockerfile:

dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
To build and run:

bash
docker build -t climate-dynalite-bridge .
docker run -e MQTT_HOST=192.168.1.100 ... climate-dynalite-bridge
Health & Logging
Logs are printed to STDOUT using emojis and timestamps for easy Docker log access.

Unacknowledged Dynalite response IDs are expired after 15s and logged for audit.

Development
The core entrypoint is:

python
if __name__ == "__main__":
    asyncio.run(main())
Use main.py to launch the service either inside Docker or locally.

Acknowledgements
This bridge is tailored for use with Philips Dynalite systems and custom Dynet decoding logic. It relies on external helpers like build_area_setpoint_body() and MQTTPublisher to abstract Dynet packet creation and MQTT comms.

License
MIT — use at your own risk.