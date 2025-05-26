from datetime import datetime
def log(msg): print(f"{datetime.now().strftime('%H:%M:%S')} 🧠 {msg}")

def float_to_q7_8(temp: float) -> tuple[int, int]:
    try:
        temp = float(temp)
        raw = int(temp * 256)
        return (raw >> 8) & 0xFF, raw & 0xFF
    except Exception as e:
        log(f"❌ float_to_q7_8 error: {e}")
        return 0, 0


def float_to_dynet_decimal(temp: float) -> tuple[int, int]:
    try:
        temp = float(temp)
        int_part = int(temp)
        decimal_part = int(round((temp - int_part) * 100))
        return int_part & 0xFF, decimal_part & 0xFF
    except Exception as e:
        log(f"❌ float_to_dynet_decimal error: {e}")
        return 0, 0


def build_area_setpoint_body(area: int, join: int, setpoint: float, device=0xBB, box=8) -> str:
    try:
        opcode = 0x56
        area_hi, area_lo = (area >> 8) & 0xFF, area & 0xFF
        box_hi, box_lo = (box >> 8) & 0xFF, box & 0xFF
        set_hi, set_lo = float_to_dynet_decimal(setpoint)

        body_bytes = [
            opcode, device,
            box_hi, box_lo,
            area_hi, area_lo,
            join,
            0x0D,
            set_hi, set_lo,
            0x00, 0x00
        ]

        return " ".join(f"{b:02X}" for b in body_bytes)

    except Exception as e:
        log(f"❌ build_area_setpoint_body error: {e}")
        return None


def build_area_temperature_body(area: int, join: int, temp: float, device=0xBB, box=8) -> str:
    try:
        opcode = 0x56
        area_hi, area_lo = (area >> 8) & 0xFF, area & 0xFF
        box_hi, box_lo = (box >> 8) & 0xFF, box & 0xFF
        temp_hi, temp_lo = float_to_dynet_decimal(temp)

        body_bytes = [
            opcode, device,
            box_hi, box_lo,
            area_hi, area_lo,
            join,
            0x0C,
            temp_hi, temp_lo,
            0x00, 0x00
        ]

        return " ".join(f"{b:02X}" for b in body_bytes)

    except Exception as e:
        log(f"❌ build_area_temperature_body error: {e}")
        return None


def build_area_preset_body(area: int, preset: int, device=1, box=1) -> str:
    try:
        opcode = 0x02
        area_hi, area_lo = (area >> 8) & 0xFF, area & 0xFF
        box_hi, box_lo = (box >> 8) & 0xFF, box & 0xFF

        body_bytes = [
            opcode, device,
            box_hi, box_lo,
            area_hi, area_lo,
            preset,
            0xFF
        ]

        return " ".join(f"{b:02X}" for b in body_bytes)

    except Exception as e:
        log(f"❌ build_area_preset_body error: {e}")
        return None


def percent_to_dynet_level(percent: int) -> int:
    try:
        if not isinstance(percent, (int, float)):
            raise ValueError("Level must be a number")
        percent = max(0, min(int(percent), 100))
        return int(percent / 100 * 254)
    except Exception as e:
        log(f"❌ percent_to_dynet_level error: {e}")
        return 0


def build_channel_level_body(area: int, channel: int, level: int,join: int, fade: int = 0, device=0xBB, box=8 ) -> str:
    try:
        opcode = 0x10
        area_hi, area_lo = (area >> 8) & 0xFF, area & 0xFF
        box_hi, box_lo = (box >> 8) & 0xFF, box & 0xFF
        channel_hi, channel_lo = (channel >> 8) & 0xFF, channel & 0xFF

        fade_hi = (fade >> 16) & 0xFF
        fade_mid = (fade >> 8) & 0xFF
        fade_lo = fade & 0xFF

        level = percent_to_dynet_level(level)

        body_bytes = [
            opcode, device,
            box_hi, box_lo,
            area_hi, area_lo,
            join,
            0x02,
            channel_hi, channel_lo,
            level,
            0x00,
            fade_hi, fade_mid, fade_lo,
            0x00
        ]

        return " ".join(f"{b:02X}" for b in body_bytes)

    except Exception as e:
        log(f"❌ build_channel_level_body error: {e}")
        return None
