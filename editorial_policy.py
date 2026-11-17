"""Pubblica solo fonti ufficiali e contenuti comuni/PlayStation."""

import re
from urllib.parse import urlsplit, parse_qs

ROCKSTAR_YOUTUBE_CHANNEL = "UC6VcWc1rAoWdBCM0JxrRQ3A"


def official_url(url):
    try:
        parts = urlsplit(str(url))
        host = (parts.hostname or "").casefold()
        return parts.scheme == "https" and not parts.username and not parts.password and any(
            host == domain or host.endswith("." + domain) for domain in ("rockstargames.com", "playstation.com"))
    except ValueError:
        return False


def approved_source(source):
    if source.get("trust") != "official":
        return False
    if official_url(source.get("url", "")):
        return True
    parts = urlsplit(source.get("url", ""))
    return (source.get("type") == "feed" and parts.scheme == "https" and parts.hostname in {"youtube.com", "www.youtube.com"}
            and parts.path == "/feeds/videos.xml" and parse_qs(parts.query).get("channel_id") == [ROCKSTAR_YOUTUBE_CHANNEL]
            and source.get("official_channel_id") == ROCKSTAR_YOUTUBE_CHANNEL)


def allowed_platforms(platforms):
    if not platforms:
        # Un annuncio generale non assegna dati a una console inventata.
        return True
    if isinstance(platforms, str):
        platforms = [platforms]
    names = [str(value).strip().casefold() for value in platforms]
    return any(name.startswith(("ps5", "ps4", "playstation")) or name in {"common", "comune", "all", "tutte"} for name in names)


def event_allowed(event, policy):
    if policy.get("official_only"):
        def proof(url):
            parts = urlsplit(url)
            return official_url(url) or (parts.scheme == "https" and parts.hostname in {"youtube.com", "www.youtube.com"}
                                          and event.get("official_channel_id") == ROCKSTAR_YOUTUBE_CHANNEL)
        if event.get("trust") != "official" or not proof(event.get("source_url", "")):
            return False
        if any(not proof(source["url"]) for source in event.get("sources", []) if source.get("url")):
            return False
    if policy.get("playstation_and_common_only"):
        if not allowed_platforms(event.get("platforms", [])):
            return False
        headline = str(event.get("title", ""))
        if re.search(r"\b(?:PC|Xbox)(?:[- ]only|\s+exclusive)\b|\bsolo\s+(?:PC|Xbox)\b", headline, re.I):
            return False
    return True


def history_record_allowed(record, policy):
    if policy.get("official_only"):
        if record.get("source_tier") != "primary" or record.get("verification") != "verified" or not official_url(record.get("source_url", "")):
            return False
    if policy.get("playstation_and_common_only") and not allowed_platforms([record.get("platform", "")]):
        return False
    return True
