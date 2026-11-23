"""Single conservative publication policy for GTA VI Italia, effective 23 Nov 2026.

Goal: five to six useful X messages on a good day, 07:00-23:00 Italy/Germany.
Never fabricate a post just to reach the goal. One two-part thread uses TWO
message units; a Buffer reservation is not proof of delivery.

Truly urgent announcements have a small separate allowance only if both the
publisher and the topic pass an independent source test. No automatic replies
to third-party conversations, no new paid service.
"""
from __future__ import annotations
from datetime import datetime, timedelta, date, time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import re

ZONE = ZoneInfo("Europe/Rome")
START = date(2026, 11, 23)
DAILY_GOAL_MIN = 5
DAILY_GOAL_MAX = 6
ORDINARY_LIMIT_MESSAGES_24H = 6
HOUR_START = time(7, 0)
HOUR_END = time(23, 0)
ORDINARY_MIN_GAP = timedelta(minutes=120)
URGENT_LIMIT_24H = 2
URGENT_MIN_GAP = timedelta(minutes=30)
URGENT_RE = re.compile(
    r"\b(?:hotfix|patch|update|aggiornament[oi]|server(?:s)?\s+(?:down|offline)|"
    r"outage|interruzion[ei]|rinviat[oa]|postponed|delayed|"
    r"release\s+date|data\s+di\s+uscita|security\s+alert|"
    r"manutenzion[ei]\s+straordinar[ia]|emergency)\b", re.I)
TRUSTED_HOSTS = {
    "rockstargames.com", "support.rockstargames.com",
    "www.rockstargames.com", "blog.playstation.com",
    "www.playstation.com", "playstation.com",
}


def local(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware date/time required")
    return now.astimezone(ZONE)


def ordinary_hours(now: datetime) -> bool:
    clock = local(now).time().replace(tzinfo=None)
    return HOUR_START <= clock < HOUR_END


def verified_urgent(event: dict) -> bool:
    """Fail closed: official verified source AND meaningful urgent subject.

    A routine marketing post or a post by a community member is never breaking.
    This check does not pretend to prove that a page's contents were read; the
    separate official monitor owns original-source validation.
    """
    if not isinstance(event, dict) or event.get("trust") != "official":
        return False
    target = event.get("source_url", "")
    if not isinstance(target, str):
        return False
    try:
        uri = urlsplit(target)
        if (uri.scheme != "https" or uri.hostname not in TRUSTED_HOSTS
                or uri.username or uri.password or uri.port not in (None, 443)):
            return False
    except ValueError:
        return False
    headline = str(event.get("title") or event.get("headline") or "")
    if not headline or len(headline) > 300:
        return False
    return bool(URGENT_RE.search(headline))


def report(now: datetime) -> dict:
    return {
        "date": local(now).date().isoformat(),
        "timezone": "Europe/Rome",
        "ordinary_window": "07:00-23:00",
        "ordinary_goal_messages": [DAILY_GOAL_MIN, DAILY_GOAL_MAX],
        "ordinary_cap_rolling_24h": ORDINARY_LIMIT_MESSAGES_24H,
        "emergency_cap_rolling_24h": URGENT_LIMIT_24H,
        "filler_posts": False,
        "automatic_external_replies": False,
    }
