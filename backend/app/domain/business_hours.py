from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

def parse_time(time_str: str) -> tuple[int, int]:
    """Parses time like '9:00 AM' into (hour, minute)"""
    time_str = time_str.strip().upper()
    parts = time_str.split()
    if len(parts) != 2:
        return 0, 0
    time_part, ampm = parts
    hour_str, min_str = time_part.split(":")
    hour = int(hour_str)
    minute = int(min_str)

    if ampm == "PM" and hour < 12:
        hour += 12
    if ampm == "AM" and hour == 12:
        hour = 0
    return hour, minute

def is_within_business_hours(starts_at: datetime, ends_at: datetime, business_hours: dict[str, Any], timezone: str) -> bool:
    """
    Checks if a slot is strictly within the specified business hours.
    Empty or unconfigured business_hours returns True (backward compatibility).
    """
    if not business_hours:
        return True

    try:
        tz = ZoneInfo(timezone)
    except Exception:
        tz = ZoneInfo("America/Los_Angeles")

    local_start = starts_at.astimezone(tz)
    local_end = ends_at.astimezone(tz)

    # If the slot crosses midnight in local time, it's outside business hours.
    if local_start.date() != local_end.date():
        return False

    day_name = local_start.strftime("%A")
    hours_str = business_hours.get(day_name)

    if not hours_str or not isinstance(hours_str, str):
        return False

    if "-" not in hours_str:
        return False

    start_str, end_str = hours_str.split("-")
    start_h, start_m = parse_time(start_str)
    end_h, end_m = parse_time(end_str)

    # Compare minutes since midnight
    slot_start_mins = local_start.hour * 60 + local_start.minute
    slot_end_mins = local_end.hour * 60 + local_end.minute

    biz_start_mins = start_h * 60 + start_m
    biz_end_mins = end_h * 60 + end_m

    return slot_start_mins >= biz_start_mins and slot_end_mins <= biz_end_mins
