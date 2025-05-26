import asyncio
import json
from datetime import datetime
from config import (
    MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD,
    MQTT_CLIMATE_STATE, MQTT_DYNALITE_PREFIX, MQTT_BRIDGE_WILL,
    OUT_JOIN, IN_JOIN, TEMP_PRECISION
)
from helpers.dynet_mqtt import (
    build_area_temperature_body, build_area_preset_body,
    build_channel_level_body, build_area_setpoint_body
)
from mqtt.publisher import MQTTPublisher

mqtt_client = None  # Global instance
last_state = {}     # State cache per area

# Logger
def log(msg: str):
    print(f"{datetime.now().strftime('%H:%M:%S')} 🧠 {msg}")

# MQTT Connect handler
def handle_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        #log("✅ Connected to MQTT broker.")
        try:
            client.subscribe(MQTT_CLIMATE_STATE)
            log(f"📡 Subscribed to {MQTT_CLIMATE_STATE}")
        except Exception as e:
            log(f"❌ Failed to subscribe: {e}")
    else:
        log(f"❌ Connection failed with code {rc}")

# MQTT Message handler
def handle_mqtt_command(topic, payload):
    try:
        log(f"📥 Received on {topic}: {payload}")

        # Parse JSON
        try:
            state = json.loads(payload)
        except Exception as e:
            log(f"❌ Invalid JSON: {e}")
            return

        # Extract area from topic
        try:
            device_id = topic.split("/")[-2]
            area_code = int(device_id.split("_")[-1])
            log(f"🏷️  Area Code: {area_code}")
        except Exception as e:
            log(f"❌ Failed to extract area from topic: {e}")
            return

        # Extract state
        try:
            setpoint     = state.get("temperature")
            current_temp = round(state.get("current_temperature", 0), TEMP_PRECISION)
            hvac_mode    = state.get("hvac_mode")
            fan_mode     = state.get("fan_mode")
            status       = state.get("status")

            missing = [k for k, v in {
                "temperature": setpoint,
                "current_temperature": current_temp,
                "hvac_mode": hvac_mode,
                "fan_mode": fan_mode,
                "status": status
            }.items() if v is None]

            if missing:
                raise ValueError(f"Missing keys: {', '.join(missing)}")

        except Exception as e:
            log(f"❌ Failed to extract valid state: {e}")
            return

        # Log new state
        log(f"🌡️ Parsed State → Setpoint: {setpoint}, Temp: {current_temp}, Mode: {hvac_mode}, Fan: {fan_mode}, Status: {status}")

        new_state = {
            "setpoint": setpoint,
            "current_temp": current_temp,
            "hvac_mode": hvac_mode,
            "fan_mode": fan_mode,
            "status": status
        }
        prev_state = last_state.get(area_code, {})

        # Compare and publish only if changed

        if new_state["setpoint"] != prev_state.get("setpoint"):
            log("📡 Setpoint changed")
            try:
                setpoint_hex = build_area_setpoint_body(area=area_code, join=OUT_JOIN, setpoint=setpoint)
                log(f"📤 Dynalite Setpoint Hex → {setpoint_hex}")
                mqtt_client.publish("dynalite/set", {"type": "dynet2", "hex_string": setpoint_hex})
            except Exception as e:
                log(f"❌ Failed to publish setpoint: {e}")

        if new_state["current_temp"] != prev_state.get("current_temp"):
            log("📡 Current Temp changed")
            try:
                temp_hex = build_area_temperature_body(area=area_code, join=OUT_JOIN, temp=current_temp)
                log(f"📤 Dynalite Temp Hex → {temp_hex}")
                mqtt_client.publish("dynalite/set", {"type": "dynet2", "hex_string": temp_hex})
            except Exception as e:
                log(f"❌ Failed to publish temperature: {e}")

        if new_state["hvac_mode"] != prev_state.get("hvac_mode"):
            log("📡 HVAC Mode changed")
            try:
                on_off = 0 if hvac_mode.lower() == "off" else 1
                onoff_hex = build_channel_level_body(area=area_code, join=OUT_JOIN, channel=101, level=on_off)
                log(f"📤 Dynalite On/Off Hex → {onoff_hex}")
                mqtt_client.publish("dynalite/set", {"type": "dynet2", "hex_string": onoff_hex})

                hvac_map = {"cool": 0, "heat": 1, "fan": 2, "dry": 3, "auto": 4}
                hvac_num = hvac_map.get(hvac_mode.lower())
                if hvac_num is not None:
                    hvac_hex = build_channel_level_body(area=area_code, join=OUT_JOIN, channel=102, level=hvac_num)
                    log(f"📤 Dynalite HVAC Mode Hex → {hvac_hex}")
                    mqtt_client.publish("dynalite/set", {"type": "dynet2", "hex_string": hvac_hex})
                else:
                    log(f"⚠️ Unknown HVAC mode: {hvac_mode}")
            except Exception as e:
                log(f"❌ Failed to publish HVAC mode: {e}")

        if new_state["fan_mode"] != prev_state.get("fan_mode"):
            log("📡 Fan Mode changed")
            try:
                fan_map = {"low": 0, "med": 1, "high": 2, "top": 3, "auto": 4}
                fan_num = fan_map.get(fan_mode.lower())
                if fan_num is not None:
                    fan_hex = build_channel_level_body(area=area_code, join=OUT_JOIN, channel=103, level=fan_num)
                    log(f"📤 Dynalite Fan Mode Hex → {fan_hex}")
                    mqtt_client.publish("dynalite/set", {"type": "dynet2", "hex_string": fan_hex})
                else:
                    log(f"⚠️ Unknown Fan mode: {fan_mode}")
            except Exception as e:
                log(f"❌ Failed to publish Fan mode: {e}")

        if new_state["status"] != prev_state.get("status"):
            log("📡 Status changed")
            try:
                error_no = 0 if status.lower() == "ok" else 1
                status_hex = build_channel_level_body(area=area_code, join=OUT_JOIN, channel=105, level=error_no)
                log(f"📤 Dynalite Error Status Hex → {status_hex}")
                mqtt_client.publish("dynalite/set", {"type": "dynet2", "hex_string": status_hex})
            except Exception as e:
                log(f"❌ Failed to publish error status: {e}")


        # Cache updated state
        last_state[area_code] = new_state

    except Exception as e:
        log(f"❌ Handler crashed: {e}")

# Async main
async def main():
    global mqtt_client
    log("🚀 Starting HA Climate → Dynalite Bridge")

    mqtt_client = MQTTPublisher(
        mqtt_username=MQTT_USERNAME,
        mqtt_password=MQTT_PASSWORD,
        mqtt_host=MQTT_HOST,
        mqtt_port=MQTT_PORT,
        will_topic=f"{MQTT_BRIDGE_WILL}/status"
    )

    mqtt_client.on_message = handle_mqtt_command
    mqtt_client.on_connect = handle_mqtt_connect

    try:
        while True:
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        log("⏹ Cancelled by asyncio")

    except KeyboardInterrupt:
        log("🛑 Stopped by user")

    except Exception as e:
        log(f"❌ Fatal error: {e}")

    finally:
        log("🔍 Shutting down...")

# Entrypoint
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        log(f"❌ Startup failed: {e}")
