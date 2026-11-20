"""Read-only GTA VI specialist/community research digest.

Only public RSS/Atom feeds with configured, pinned hostnames are fetched.
Independent press and community sources create *research leads*, never Buffer
posts, GitHub state changes or claims of official Rockstar confirmation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import requests

from editorial_autopilot_v137 import canonical, published, clean, TOPIC_RE

REGISTRY = Path("community-research-sources-v1.json")
MAX_DOWNLOAD = 1_800_000
WINDOW_HOURS = 96
REDDIT_TOPIC = re.compile(
    r'\b(?:money|cash|glitch|vehicle|garage|car|location|map|collectible|mission|'
    r'trophy|platinum|secret|trick|tips|PS5|100\s*%)\b', re.I)
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


def parse_research_feed(raw: bytes, source: dict):
    """Parse RSS and YouTube Atom without the auto-publisher's rumor filter.

    Unconfirmed or leaked titles are retained strictly as labeled research.
    No article bodies are parsed, copied, summarized or published.
    """
    if len(raw) > MAX_DOWNLOAD:
        raise ValueError("Excessive feed size")
    root = ET.fromstring(raw)
    rows = []
    if root.tag.lower().endswith("rss") or root.tag.lower().endswith("rdf"):
        for node in root.findall(".//item"):
            rows.append((node.findtext("title"), node.findtext("link"),
                         node.findtext("pubDate") or
                         node.findtext("{http://purl.org/dc/elements/1.1/}date")))
    else:
        ns = "{http://www.w3.org/2005/Atom}"
        for node in root.findall(f".//{ns}entry"):
            alternate = next((x.get("href") for x in node.findall(ns + "link")
                              if x.get("rel") in (None, "alternate") and x.get("href")), "")
            rows.append((node.findtext(ns + "title"), alternate,
                         node.findtext(ns + "published") or node.findtext(ns + "updated")))
    for title, link, stamp in rows:
        title = clean(title or "")
        reddit_actionable=(source.get("name")=="Reddit r/GTA6"
                           and REDDIT_TOPIC.search(title))
        if not title or not (TOPIC_RE.search(title) or reddit_actionable):
            continue
        dt = published(stamp or "")
        if dt is None:
            continue
        try:
            link = canonical(link or "")
        except (ValueError, TypeError):
            continue
        parsed_url=urlsplit(link)
        if parsed_url.hostname not in set(source["domains"]):
            continue
        if source.get("name")=="Reddit r/GTA6" and not (
                parsed_url.path.startswith("/r/GTA6/comments/")
                or parsed_url.path.startswith("/r/gta6/comments/")):
            continue
        yield {"source": source["name"], "title": title, "url": link,
               "published": dt.isoformat()}


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
    for item in parse_research_feed(bytes(raw), source):
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
