"""Read-only GTA VI specialist/community research digest.

Only public RSS/Atom feeds with configured, pinned hostnames are fetched.
Independent press and community sources create *research leads*, never Buffer
posts, GitHub state changes or claims of official Rockstar confirmation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import requests

from editorial_autopilot_v137 import canonical, parse_feed, published

REGISTRY = Path("community-research-sources-v1.json")
MAX_DOWNLOAD = 1_800_000
WINDOW_HOURS = 96
VALID_TIERS = {
    "official", "specialist", "specialist_video", "community",
    "community_wiki", "database", "community_news", "dataminer", "journalist",
}
VALID_MODES = {"read_only_feed", "manual_review", "existing_official_monitor"}


def hostname(url: str) -> str:
    split = urlsplit(url)
    if split.scheme != "https" or not split.hostname or split.username or split.password:
        raise ValueError("Non-HTTPS or credential-bearing research source URL")
    if split.port not in (None, 443):
        raise ValueError("Nonstandard port on research source URL")
    return split.hostname.lower()


def validate(registry: dict) -> list[dict]:
    if registry.get("schema_version") != 1 or not isinstance(registry.get("sources"), list):
        raise ValueError("Unrecognized research registry")
    sources = registry["sources"]
    if not sources or len({x["name"] for x in sources}) != len(sources):
        raise ValueError("Missing or duplicate research sources")
    for source in sources:
        if source.get("tier") not in VALID_TIERS:
            raise ValueError("Unrecognized source tier")
        if source.get("collection") not in VALID_MODES:
            raise ValueError("Unrecognized source collection mode")
        hostname(source["url"])
        if source["collection"] != "read_only_feed":
            if source.get("feed"):
                raise ValueError("Manual source must not have a fetchable feed")
            continue
        feed_host = hostname(source["feed"])
        feed_hosts = set(source["feed_domains"])
        article_hosts = set(source["domains"])
        if (feed_host not in feed_hosts or not article_hosts or
                any(not value or value.startswith(".") or "/" in value for value in feed_hosts | article_hosts)):
            raise ValueError("Invalid allowlisted feed or article domains")
    if registry.get("policy", {}).get("auto_publish") is not False:
        raise ValueError("Research sources must never automatically publish")
    return sources


def load_registry(path: Path = REGISTRY) -> dict:
    registry = json.loads(path.read_text(encoding="utf-8"))
    validate(registry)
    return registry


def fetch_candidates(source: dict, *, session, now: datetime) -> list[dict]:
    """Fetch one pinned public feed and retain attribution and age."""
    response = session.get(
        source["feed"], timeout=(5, 12), stream=True, allow_redirects=True,
        headers={"User-Agent": "Federiko-GTA-VI-Research/1.0 (public RSS only)"},
    )
    try:
        response.raise_for_status()
        if response.url and hostname(response.url) not in set(source["feed_domains"]):
            raise ValueError("Unexpected feed redirect")
        raw = bytearray()
        for chunk in response.iter_content(65536):
            raw.extend(chunk)
            if len(raw) > MAX_DOWNLOAD:
                raise ValueError("Excessive feed size")
    finally:
        response.close()
    candidates = []
    feed_src = {k: source[k] for k in ("name", "domains", "language")}
    for item in parse_feed(bytes(raw), feed_src):
        when = published(item["published"])
        if when is None or when > now + timedelta(minutes=5) or now - when > timedelta(hours=WINDOW_HOURS):
            continue
        candidates.append({
            "source": source["name"],
            "tier": source["tier"],
            "published_utc": when.isoformat(),
            "title": item["title"],
            "url": canonical(item["url"]),
            "content_type": "video" if source["tier"] == "specialist_video" else "article",
            "status": "RICERCA: da verificare prima di un articolo o post",
            "official_rockstar": False,
        })
    return candidates


def collect(registry: dict, *, session=None, now: datetime | None = None) -> dict:
    sources = validate(registry)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("A timezone-aware clock is required")
    now = now.astimezone(timezone.utc)
    http = session or requests.Session()
    research, checked, errors = [], [], []
    for src in sources:
        if src["collection"] != "read_only_feed":
            continue
        try:
            found = fetch_candidates(src, session=http, now=now)
            checked.append({"source": src["name"], "status": "ok", "relevant": len(found)})
            research.extend(found)
        except (requests.RequestException, ValueError, ET.ParseError, KeyError, TypeError) as exc:
            errors.append({"source": src["name"], "error": type(exc).__name__})
            checked.append({"source": src["name"], "status": "unavailable", "relevant": 0})
    # No speculative auto-publication and no double-counting multiple-source reprints.
    seen, distinct = set(), []
    for entry in sorted(research, key=lambda x: x["published_utc"], reverse=True):
        if entry["url"] in seen:
            continue
        seen.add(entry["url"])
        distinct.append(entry)
    return {
        "schema": "gta6-research-digest-v1",
        "generated_utc": now.isoformat(),
        "window_hours": WINDOW_HOURS,
        "sources_checked": checked,
        "errors": errors,
        "manual_sources": [
            {"name": s["name"], "tier": s["tier"], "url": s["url"]}
            for s in sources if s["collection"] == "manual_review"
        ],
        "candidates": distinct[:50],
        "publication": "read_only__no_buffer_post__no_articles_auto_created",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("validate", "preview"), required=True)
    parser.add_argument("--output", type=Path, default=Path("research-digest.json"))
    args = parser.parse_args()
    registry = load_registry()
    if args.mode == "validate":
        print("RESEARCH_SOURCES_VALID", len(registry["sources"]))
        return
    result = collect(registry)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("RESEARCH_DIGEST", "candidates=" + str(len(result["candidates"])),
          "errors=" + str(len(result["errors"])), "read_only=true")
    for item in result["candidates"][:15]:
        print("RESEARCH_LEAD", item["source"], item["published_utc"], item["url"])
    print("RESEARCH_NO_POST: all candidates require editorial verification")


if __name__ == "__main__":
    main()
