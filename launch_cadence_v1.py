"""First fortnight of GTA VI: a *quality-gated* editorial goal, not a spam target.

Calendar dates are inclusive and checked in the Italian/German CET timezone.
Each eligible editorial item is one atomic two-message X thread.
Do not fabricate or recycle content to fill unused slots.
"""
from __future__ import annotations
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Europe/Rome")
START = date(2026, 11, 19)
LAST = date(2026, 12, 2)
HOUR_START = time(8, 0)
HOUR_END = time(21, 0)
TARGET_MIN = 10
TARGET = 12
TARGET_MAX = 16
MAX_BUFFER_X_MESSAGES_24H = 48  # 50-unverified limit, leave two spare.
MIN_PACING = timedelta(minutes=45)
THREAD_LENGTH = 2


def local(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return now.astimezone(ZONE)


def active(now: datetime) -> bool:
    return START <= local(now).date() <= LAST


def in_hours(now: datetime) -> bool:
    t = local(now).time().replace(tzinfo=None)
    return HOUR_START <= t < HOUR_END


def launch_eligible(now: datetime) -> bool:
    return active(now) and in_hours(now)


def parse_timestamp(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def count_local_day(entries: dict, now: datetime) -> int:
    day = local(now).date()
    return sum(1 for e in entries.values()
               if isinstance(e,dict) and e.get('status') != 'rejected'
               and (dt := parse_timestamp(e.get('reserved_utc') or e.get('reserved_at'))) is not None
               and local(dt).date() == day)


def message_units(entry: dict) -> int:
    thread = entry.get('thread')
    return len(thread) if isinstance(thread, list) and len(thread) >= 2 else 1


def campaign_status(now: datetime, sent_threads: int = 0) -> dict:
    clock = local(now)
    return {
        'active': active(now), 'timezone': 'Europe/Rome', 'date': str(clock.date()),
        'window': '08:00-21:00', 'thread_messages': THREAD_LENGTH,
        'target_min': TARGET_MIN, 'target': TARGET, 'cap': TARGET_MAX,
        'confirmed_this_day': sent_threads,
        'missing_to_minimum': max(0, TARGET_MIN-sent_threads),
        'mode': 'quality_gated_no_filler',
        'last_day': str(LAST),
    }
