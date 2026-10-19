import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
import foxesscloud.openapi as f

def main():
    api_key = os.getenv("FOX_API_KEY")
    device_sn = os.getenv("FOX_DEVICE_SN", "60HD103058XM117")

    if not api_key:
        print("ERROR: FOX_API_KEY secret is missing")
        sys.exit(1)

    f.api_key = api_key
    f.device_sn = device_sn

    now = datetime.now(ZoneInfo("Australia/Sydney"))
    hour = now.hour
    minute = now.minute

    print(f"=== Fox ESS Scheduler Control ===")
    print(f"Sydney time : {now.strftime('%Y-%m-%d %H:%M %Z')}")
    print(f"Inverter SN : {device_sn}")

    # Manual force from workflow dispatch or cron trigger
    if len(sys.argv) > 1:
        action = sys.argv[1].lower()
        print(f"Manual action: {action}")
    else:
        # Automatic fallback based on current Sydney time
        # 10:00 AM – 9:00 PM → ON
        # 9:00 PM – 10:00 AM → OFF
        if hour >= 10 and hour < 21:
            action = "on"
        else:
            action = "off"

    print(f"Action      : {action}")

    try:
        schedule = f.get_schedule()
        print(f"Current enable: {schedule.get('enable') if schedule else 'unknown'}")
    except Exception as e:
        print(f"Warning: {e}")

    # 1. OFF / SELF-USE MODE
    if action in ["off", "false", "0"]:
        print("→ Switching to Self-use (disabling Mode Scheduler)...")
        result = f.set_schedule(enable=0)
        print(f"Result: {result}")

    # 2. ON / GRID CHARGE MODE
    elif action in ["on", "true", "1"]:
        print("→ Enabling Mode Scheduler...")
        schedule = f.get_schedule()
        periods = schedule.get('periods') if schedule else None

        if periods:
            result = f.set_schedule(periods=periods, enable=1)
        else:
            period = f.set_period(0, 24, "SelfUse", min_soc=10)
            result = f.set_schedule(periods=[period], enable=1)

        print(f"Result: {result}")

    # 3. ADVANCED MIDDAY SMART CHECK (Weather & Battery Evaluation)
    elif action == "smart-check":
        print("→ Running Midday Weather & Battery Smart Check...")
        
        # Fetch current battery SOC
        try:
            device_detail = f.get_device_detail()
            soc = float(device_detail.get('soc', 50) if isinstance(device_detail, dict) else getattr(device_detail, 'soc', 50))
        except Exception as e:
            print(f"Warning: Could not fetch battery SOC ({e}). Defaulting to 50%.")
            soc = 50.0

        battery_capacity_kwh = 42.91
        kwh_needed = (100.0 - soc) / 100.0 * battery_capacity_kwh
        print(f"Current Battery SOC : {soc}%")
        print(f"Energy needed to 100%: {kwh_needed:.2f} kWh")

        # Fetch free solar radiation forecast for Sydney (-33.8688, 151.2093) via Open-Meteo
        lat, lon = -33.8688, 151.2093
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=shortwave_radiation&timezone=Australia%2FSydney"
        
        try:
            res = requests.get(weather_url).json()
            hourly_rad = res['hourly']['shortwave_radiation']
            times = res['hourly']['time']

            now_hour = now.hour
            estimated_remaining_solar_kwh = 0.0
            
            for t_str, rad in zip(times, hourly_rad):
                t_hour = datetime.fromisoformat(t_str).hour
                # Calculate generation from current hour until 5:00 PM (17:00) for your 6.6kW array
                if now_hour <= t_hour < 17:
                    estimated_remaining_solar_kwh += (rad / 1000.0) * 6.6 * 0.75

            print(f"Estimated Afternoon Solar: {estimated_remaining_solar_kwh:.2f} kWh")

            # Decision rule: If afternoon sun is enough to finish charging, stop grid charge early!
            if estimated_remaining_solar_kwh >= kwh_needed:
                print("→ Solar forecast is sufficient! Switching to Self-use early to save grid power.")
                result = f.set_schedule(enable=0)
                print(f"Result: {result}")
            else:
                print("→ Cloudy skies or low solar forecast. Maintaining grid charge to ensure full battery.")

        except Exception as e:
            print(f"Error fetching weather forecast: {e}. Skipping smart switch.")

    print("Done.")

if __name__ == "__main__":
    main()
