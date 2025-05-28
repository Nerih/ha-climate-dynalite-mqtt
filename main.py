import asyncio
import json
from datetime import datetime
from config import (
    MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD,
    MQTT_CLIMATE_STATE, MQTT_DYNALITE_PREFIX, MQTT_BRIDGE_WILL,
    OUT_JOIN, IN_JOIN, TEMP_PRECISION, MQTT_CLIMATE_PREFIX, MQTT_DEBUG
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
            client.subscribe(MQTT_DYNALITE_PREFIX)
            log(f"📡 Subscribed to {MQTT_DYNALITE_PREFIX}")
        except Exception as e:
            log(f"❌ Failed to subscribe: {e}")
    else:
        log(f"❌ Connection failed with code {rc}")


def handle_climate_message(topic: str, state):
    try:
        log(f"🔄 Handling Climate message")

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

        if new_state == prev_state:
            log("✅ No change in climate state — skipping publish")
            return


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
        log(f"❌ Failed handling Climate message: {e}")



def handle_dynalite_message(topic: str, dynalite):
    try:
        log(f"🔄 Handling Dynalite message {dynalite.get("description", "")}")
        #do not process FE joins and/or where the device/box=bb 08
        #this avoids loop backs when issuing commands
        
        description = str(dynalite.get("description", "").lower())
        template = dynalite.get("template", "")
        type = dynalite.get("type")
        fields = dynalite.get("fields")
  
        if "join fe" in description:
            log(f"⛔ Skipping due to Join FE → {description}")
            return

        if "set temperature set point to" in description:
            if type =="dynet1":
                #got dynet 1, we know field format is Area, Join, Setpoint
                if not len(fields) == 3:
                    log(f"⛔ Field length for Dynet1 Setpoint is more than 3 → {dynalite}")
                    return   
                area = fields[0]
                join = fields[1]
                setpoint = fields[2]
            elif type =="dynet2":
                if not len(fields) == 5:
                    log(f"⛔ Field length for Dynet2 Setpoint is more than 5 → {dynalite}")
                    return
                #got dynet 2, we know field format is more complicated :)
                area = fields[2]
                join = fields[3]
                setpoint = fields[4]
            if area not in last_state:
                log(f"⚠️ Area {area} not in cache (not a command for climate related area) — skipping publish")
                return
            topic_out = f"homeassistant/climate/coolmaster_L1_{area}/set/temperature"
            mqtt_client.publish(topic_out, setpoint)
            log(f"✅ Setpoint {setpoint} -> {area} ")
            return

        #handle all other commands    
        elif "recall level" in description:
            if type == "dynet1":
                if not len(fields) == 5:
                    log(f"⛔ Field length for Dynet1 Recall Level must be 4 → {dynalite}")
                    return
                #field len is 5
                area = fields[0]
                join = fields[1]
                channel = fields[2]
                level = int(fields[3].strip('%'))
            elif type == "dynet2":
                if not len(fields) == 7:
                    log(f"⛔ Field length for Dynet2 Recall Level must be 6 → {dynalite} FIELD{len(fields)}")
                    return
                #field len is 7
                area = fields[2]
                join = fields[3]
                channel = fields[4]
                level = int(fields[5].strip('%'))
            else:   
                log(f"⛔ Unknown type → {dynalite}")
                return
            
            if area not in last_state:
                log(f"⚠️ Area {area} not in cache (not a command for climate related area) — skipping publish")
                return
            
            if channel not in [101, 102, 103]:
                log(f"⚠️ Channel {channel} is not HVAC command (101,102,103) — skipping")
                return
            
            log(f"recall level for area{area} channel{channel} level{level} join{join}")

            #update on/off
            if channel == 101:
                mode = "off" if level == 0 else "auto"
                topic_out = f"homeassistant/climate/coolmaster_L1_{area}/set/mode"
                mqtt_client.publish(topic_out, mode)
                log(f"✅ HVAC mode {mode} -> {area} ")
                return
            #update mode
            elif channel == 102:
                hvac_modes = ["cool", "heat", "fan", "dry", "auto"]
                if 0 <= level < len(hvac_modes):
                    mode = hvac_modes[level]
                    topic_out = f"homeassistant/climate/coolmaster_L1_{area}/set/mode"
                    mqtt_client.publish(topic_out, mode)
                    log(f"✅ HVAC mode {mode} -> {area} ")
                return
            #update fan
            elif channel ==103:
                fan_modes = ["low", "med", "high", "top", "auto"]
                if 0 <= level < len(fan_modes):
                    mode = fan_modes[level]
                    topic_out = f"homeassistant/climate/coolmaster_L1_{area}/set/fan_mode"
                    mqtt_client.publish(topic_out, mode)
                    log(f"✅ Fan mode {mode} -> {area} ")
                return


        log("✅ Skipped Dynalite Message")
    except Exception as e:
        log(f"❌ Failed handling Dynalite message: {e}")


# MQTT Message handler
def handle_mqtt_command(topic, payload):
    try:
        #log(f"📥 Received on {topic}: {payload}")

        # Parse JSON
        try:
            parsed = json.loads(payload)
        except Exception as e:
            log(f"❌ Invalid JSON: {e}")
            return

        

        #if topic is on Climate prefix
        if topic.startswith(MQTT_CLIMATE_PREFIX):
            handle_climate_message(topic, parsed)
            return
          #if topic is on Dynalite Bus
        elif topic.startswith(MQTT_DYNALITE_PREFIX):
            handle_dynalite_message(topic, parsed)
            return
        
              
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
        will_topic=f"{MQTT_BRIDGE_WILL}/status",
        mqtt_debug=MQTT_DEBUG
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
