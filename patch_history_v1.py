"""Minimal factual patch evidence from a successful official monitor read.

Never fetches, publishes, translates, mirrors patch notes, or guesses versions.
The existing history database persists dated observations and source revisions.
"""
from datetime import datetime, timezone
from hashlib import sha256
import re

from bs4 import BeautifulSoup

OFFICIAL_ARTICLE = "https://support.rockstargames.com/articles/sN5pEdFYZdlvijKXd6xpJ/grand-theft-auto-vi-launch-updates-ps5-xbox-series-x-or-s"
TITLE = re.compile(r"^Grand Theft Auto VI Launch Updates\s*\(PS5\s*/\s*Xbox Series X\|S\)$", re.I)
DATE_HEADING = re.compile(r"^\[((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})\]\s*[-–—]\s*\S", re.I)
NOTE = re.compile(r"^(?:Fixed|Added|Improved|Resolved|Updated|Addressed|Removed|Adjusted|Enabled|Disabled|Optimized|Increased|Decreased|Reduced|Changed|Corrected|Made|Implemented)\b", re.I)
HELP = re.compile(r"^(?:Still need help\??|Submit a Request)$", re.I)


def normalize(value):
    return " ".join(value.split())


def parse_patch_records(raw, url, observed_at):
    """Return only dated, attributable metadata; fail closed on unknown format.

    The source is the exact known Rockstar article, not a search result or
    arbitrary page. A heading without recognized list entries is not evidence.
    """
    if url != OFFICIAL_ARTICLE or not isinstance(raw, str) or len(raw)>2_000_000:
        return []
    try:
        observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            return []
        observed = observed.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError):
        return []
    article = BeautifulSoup(raw, "html.parser").select_one("article:has([data-testid='page-title'])")
    if article is None:
        return []
    title = article.select_one("[data-testid='page-title']")
    if title is None or not TITLE.fullmatch(normalize(title.get_text(" ", strip=True))):
        return []
    for node in article.select("nav,aside,footer,script,style,noscript,[hidden],[aria-hidden='true']"):
        if node.parent is not None:
            node.decompose()
    dated = {}
    active = None
    for node in article.find_all(["h2","h3","h4","h5","h6","p","li"]):
        if node.name != "li" and node.find_parent("li"):
            continue
        if node.name == "li" and node.find_parent("li"):
            return []  # unknown nested list format; do not miscount
        text = normalize(node.get_text(" ", strip=True))
        if node.name != "li":
            if HELP.fullmatch(text):
                break
            match = DATE_HEADING.match(text)
            if match:
                try:
                    day = datetime.strptime(match.group(1), "%B %d, %Y").date()
                except ValueError:
                    return []
                if day > observed.date() or day.year < 2026:
                    return []
                active = day.isoformat()
                dated.setdefault(active, [])
            elif text.startswith("[") and re.match(r"^\[[A-Za-z]+\s+\d",text):
                return []  # changed heading syntax: require review
            continue
        if active is None:
            continue
        if node.parent.name not in ("ul","ol") or not NOTE.match(text):
            return []  # do not partially publish an unfamiliar dated section
        dated[active].append(text)
    if not dated or any(not entries or len(entries)>300 for entries in dated.values()):
        return []
    result = []
    for day, entries in sorted(dated.items()):
        result.append({
            "game":"GTA VI", "platform":"common", "region":"global",
            "event_type":"official_patch_notes_available", "metric_kind":"availability",
            "occurred_at":day, "date_precision":"date", "source_url":OFFICIAL_ARTICLE,
            "source_tier":"primary", "verification":"verified",
            "observed_at":observed.isoformat(timespec="seconds").replace("+00:00","Z"),
            "notes":"Data delle note Rockstar osservata dal monitor. Non prova numero di build, dimensione o test nel gioco.",
            "metadata":{"kind":"official_patch_note_metadata_v1", "platforms":["PS5","Xbox Series X|S"],
                        "entry_count":len(entries),
                        "content_sha256":sha256("\n".join(entries).encode("utf-8")).hexdigest()}
        })
    return result
