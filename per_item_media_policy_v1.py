"""Per-item X media policy: reviewed photos or exact official links only.

A link to Rockstar's official YouTube video is a platform link, not a grant to
download, re-host, crop, attach, or embed its thumbnail. This module never
authorizes an image attachment. Its one-time launch candidate is deliberately
small, source-labeled, deduplicated, and may only be sent as an X link post.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit
import re

# Exact destinations reviewed against the source publisher on 2026-11-27.
# The official video remains on YouTube; its link preview belongs to the platform.
OFFICIAL_LINKS = {
    "https://www.youtube.com/watch?v=T95WGWkx7P0": {
        "kind": "official_video_link",
        "publisher": "Rockstar Games",
        "evidence_url": "https://www.rockstargames.com/newswire/article/39akk424a9oo53/grand-theft-auto-vi-now-available",
        "published": "2026-11-19",
        "scope": "x_link_only",
        "image_attachment_allowed": False,
    },
    "https://www.rockstargames.com/newswire/article/39akk424a9oo53/grand-theft-auto-vi-now-available": {
        "kind": "official_source_link",
        "publisher": "Rockstar Games",
        "evidence_url": "https://www.rockstargames.com/newswire/article/39akk424a9oo53/grand-theft-auto-vi-now-available",
        "published": "2026-11-19",
        "scope": "x_link_only",
        "image_attachment_allowed": False,
    },
}

VIDEO_URL = "https://www.youtube.com/watch?v=T95WGWkx7P0"
SOURCE_URL = "https://www.rockstargames.com/newswire/article/39akk424a9oo53/grand-theft-auto-vi-now-available"
VIDEO_KEY = "official-video-link:gta-vi-now-available-2026"


def approved_link_url(value: str) -> bool:
    """Accept only an exact reviewed official video or source URL."""
    if not isinstance(value, str) or value not in OFFICIAL_LINKS:
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.fragment):
        return False
    if parsed.hostname == "www.youtube.com":
        query = parse_qs(parsed.query, keep_blank_values=True)
        return (parsed.path == "/watch" and set(query) == {"v"}
                and query["v"] == ["T95WGWkx7P0"])
    if parsed.hostname == "www.rockstargames.com":
        return (parsed.path == "/newswire/article/39akk424a9oo53/grand-theft-auto-vi-now-available"
                and parsed.query == "")
    return False



SOURCE_LINK_DOMAINS = {
    "PowerPyx": {"powerpyx.com", "www.powerpyx.com"},
    "VGC": {"videogameschronicle.com", "www.videogameschronicle.com"},
    "Push Square": {"pushsquare.com", "www.pushsquare.com"},
    "IGN": {"ign.com", "www.ign.com"},
    "GameSpot": {"gamespot.com", "www.gamespot.com"},
    "Everyeye": {"everyeye.it", "www.everyeye.it"},
    "Multiplayer.it": {"multiplayer.it", "www.multiplayer.it"},
}


def source_link_message_valid(message: dict, *, source: str | None = None,
                              expected_url: str | None = None) -> bool:
    """Validate a source link for review; this is not permission to publish it."""
    if not isinstance(message, dict) or message.get("assets") not in (None, []):
        return False
    text = message.get("text")
    if not isinstance(text, str) or not text.strip():
        return False
    links = [u.rstrip(".,);]") for u in re.findall(r"https://[^\s<>]+", text)]
    if len(links) != 1 or (expected_url is not None and links[0] != expected_url):
        return False
    try:
        parsed = urlsplit(links[0])
        if (parsed.scheme != "https" or parsed.username or parsed.password
                or parsed.port not in (None, 443) or parsed.fragment):
            return False
    except ValueError:
        return False
    for publisher, domains in SOURCE_LINK_DOMAINS.items():
        if source is not None and publisher != source:
            continue
        if f"Fonte: {publisher}" in text and parsed.hostname in domains:
            return True
    return False


def source_link_message_allowed(message: dict, *, source: str | None = None,
                                expected_url: str | None = None) -> bool:
    """Ordinary RSS links without a reviewed image must stay in editorial review.

    Enforce the photo requirement at both reservation and Buffer mutation. A
    valid publisher link is not a substitute for a relevant approved image.
    The separate exact, one-time official video policy is unchanged.
    """
    return False


def source_link_candidate(item: dict) -> dict | None:
    """Do not reserve a source-only RSS item under the current photo policy."""
    if not isinstance(item, dict) or not source_link_message_allowed(
            {"text": item.get("text"), "assets": []},
            source=item.get("source"), expected_url=item.get("url")):
        return None
    result = dict(item)
    result.update(media_url=None, media_mode="source_link_only")
    result.pop("photo_kind", None)
    result.pop("cover_sha256", None)
    return result


def verify_source_link_entry(entry: dict) -> bool:
    """Reject legacy source-only reservations under the current photo policy."""
    return (isinstance(entry, dict) and entry.get("media_mode") == "source_link_only"
            and not entry.get("media_url") and not entry.get("photo_kind")
            and not entry.get("cover_sha256")
            and source_link_message_allowed(
                {"text": entry.get("text"), "assets": []},
                source=entry.get("source"), expected_url=entry.get("url")))

VIDEO_TEXT = ("🎮 GTA VI è disponibile su PS5 e Xbox Series X|S.\n\n"
               "Video ufficiale Rockstar Games:\n" + VIDEO_URL)
SOURCE_TEXT = ("La pagina Rockstar raccoglie il video, gli screenshot e la mappa stampabile "
               "di Leonida.\n\nFonte: Rockstar Games\n" + SOURCE_URL)


def link_only_message_allowed(message: dict, *, allow_thread: bool = True) -> bool:
    """Allow only exact reviewed copy; a source URL cannot license extra claims."""
    if not isinstance(message, dict) or message.get("assets") not in (None, []):
        return False
    text = message.get("text")
    allowed = {VIDEO_TEXT}
    if allow_thread:
        allowed.add(SOURCE_TEXT)
    if text not in allowed:
        return False
    links = [u.rstrip(".,);]") for u in re.findall(r"https://[^\s<>]+", text)]
    return len(links) == 1 and approved_link_url(links[0])


def link_only_thread_allowed(messages) -> bool:
    """Only the one reviewed video/source pair may be sent as a link-only thread."""
    return isinstance(messages, (list, tuple)) and list(messages) == [VIDEO_TEXT, SOURCE_TEXT]

def verify_link_only_entry(entry: dict) -> bool:
    """Revalidate the exact one-time reservation immediately before delivery."""
    if (not isinstance(entry, dict) or entry.get("media_mode") != "official_video_link"
            or entry.get("media_url") or entry.get("photo_kind") or entry.get("cover_sha256")
            or entry.get("url") != VIDEO_URL
            or entry.get("official_video_url") != VIDEO_URL
            or entry.get("source") != "Rockstar Games"):
        return False
    thread = entry.get("thread")
    if thread is None:
        return entry.get("text") == VIDEO_TEXT
    return link_only_thread_allowed(thread) and entry.get("text") == VIDEO_TEXT

def launch_video_candidate(state: dict, now: datetime, *, launch: bool = False) -> dict | None:
    """One factual, one-time link post; never attach or scrape an image."""
    if now.tzinfo is None:
        raise ValueError("UTC publication time required")
    entries = state.get("entries")
    if not isinstance(entries, dict) or VIDEO_KEY in entries:
        return None
    if any(row.get("url") == VIDEO_URL or row.get("official_video_url") == VIDEO_URL
           for row in entries.values() if isinstance(row, dict)):
        return None

    first = ("🎮 GTA VI è disponibile su PS5 e Xbox Series X|S.\n\n"
             "Video ufficiale Rockstar Games:\n" + VIDEO_URL)
    thread = None
    text = first
    if launch:
        second = ("La pagina Rockstar raccoglie il video, gli screenshot e la mappa stampabile "
                  "di Leonida.\n\nFonte: Rockstar Games\n" + SOURCE_URL)
        thread = [first, second]
    from editorial_seo_v135 import x_weight
    if x_weight(first) > 280 or (thread and x_weight(thread[1]) > 280):
        return None
    return {
        "key": VIDEO_KEY,
        "sig": "gta vi disponibilita video ufficiale rockstar 2026",
        "title": "GTA VI è disponibile su PS5 e Xbox Series X|S",
        "url": VIDEO_URL,
        "official_video_url": VIDEO_URL,
        "source": "Rockstar Games",
        "published": now.astimezone(timezone.utc).isoformat(),
        "text": text,
        "thread": thread,
        "media_url": None,
        "media_mode": "official_video_link",
    }
