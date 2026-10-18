import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
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

    # Manual force from the Run workflow button
    if len(sys.argv) > 1:
        action = sys.argv[1].lower()
        print(f"Manual action: {action}")
    else:
        # Automatic based on current Sydney time
        # 9:45 AM – 9:00 PM → ON
        # 9:00 PM – 9:45 AM → OFF
        if (hour > 9 or (hour == 9 and minute >= 45)) and hour < 21:
            action = "on"
        else:
            action = "off"

    print(f"Action      : {action}")

    try:
        schedule = f.get_schedule()
        print(f"Current enable: {schedule.get('enable') if schedule else 'unknown'}")
    except Exception as e:
        print(f"Warning: {e}")

    if action in ["off", "false", "0"]:
        print("→ Switching to Self-use (disabling Mode Scheduler)...")
        result = f.set_schedule(enable=0)
        print(f"Result: {result}")

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

    print("Done.")

if __name__ == "__main__":
    main()
