"""Read-only public Rockstar Support reachability diagnosis for GitHub Actions.

No database, state, Buffer, X, authenticated endpoints or new services.  The
monitor is authoritative; a successful one-off probe is NOT a confirmed news
event and must never update any persistent cursor.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit
import json
import requests
import re

from bs4 import BeautifulSoup
from sources import SupportBrowserFailure, get_html, read_support_article_index

OFFICIAL_SOURCES = {
    "support-gta6": "https://support.rockstargames.com/VI",
    "support-gta": "https://support.rockstargames.com/gta-online",
}


def probe(config_file=Path("sources.free.json"), *, fetcher=None, report=print):
    fetcher = fetcher or get_html
    settings = json.loads(Path(config_file).read_text(encoding="utf-8"))
    ids = {source.get("id"): source for source in settings.get("sources", [])}
    outcome = {}
    for source_id, official_url in OFFICIAL_SOURCES.items():
        source = ids.get(source_id)
        if (not isinstance(source, dict) or source.get("url") != official_url
                or source.get("selector") != "a[href*='/articles/']"
                or source.get("browser_fallback_on_timeout") is not True):
            outcome[source_id] = "unsafe_configuration"
            report("SUPPORT_PROBE_DIAG source="+source_id+
                   " status=unavailable phase=config reason=invalid_official_source")
            continue
        try:
            html = fetcher(source)
            if not isinstance(html, str):
                raise ValueError("Unusable official response")
            doc = BeautifulSoup(html, "html.parser")
            links = [
                anchor for anchor in doc.select(source["selector"])
                if anchor.get_text(" ", strip=True) and
                (
                    (anchor.get("href") or "").startswith("/articles/")
                    or urlsplit(anchor.get("href") or "").hostname
                    == "support.rockstargames.com"
                )
            ]
            if not links:
                outcome[source_id] = "empty_listing"
                report("SUPPORT_PROBE_DIAG source="+source_id+
                       " status=unavailable phase=content reason=no_article_links")
            else:
                outcome[source_id] = "listing_present"
                # Only report the count of authentic, visible official links.
                # Do not publish article titles, IDs, or URLs as news.
                report("SUPPORT_PROBE_DIAG source="+source_id+
                       " status=listing_present links="+str(len(links))+
                       " note=not_a_news_scan")
        except SupportBrowserFailure as exc:
            outcome[source_id] = "browser_"+exc.phase
            report("SUPPORT_PROBE_DIAG source="+source_id+
                   " status=unavailable phase="+exc.phase+" reason="+exc.reason)
        except Exception as exc:
            outcome[source_id] = "source_"+type(exc).__name__
            # No exception messages/stack traces: they can leak host paths,
            # proxies or details of a vendor challenge.
            report("SUPPORT_PROBE_DIAG source="+source_id+
                   " status=unavailable phase=source reason="+type(exc).__name__)
    return outcome


# Exact official article surfaced by public search. This is a reachability
# diagnostic, NOT a new source in the production monitor or a fresh event.
PATCH_ARTICLE = "https://support.rockstargames.com/articles/sN5pEdFYZdlvijKXd6xpJ/grand-theft-auto-vi-launch-updates-ps5-xbox-series-x-or-s"
MAX_ARTICLE_BYTES = 1_500_000


def probe_direct_article(*, fetcher=None, report=print):
    fetcher = fetcher or requests.get
    outcome = "unconfirmed"
    try:
        with fetcher(PATCH_ARTICLE,
                     headers={"Accept": "text/html", "Accept-Language": "en-US,en;q=0.9",
                              "User-Agent": "GTA6Italia-SupportDiagnostic/1.0"},
                     timeout=(5, 10), allow_redirects=False, stream=True) as response:
            if response.status_code != 200 or response.url != PATCH_ARTICLE:
                outcome = "redirect_or_http_unavailable"
            else:
                body = bytearray()
                for chunk in response.iter_content(chunk_size=16384):
                    body.extend(chunk)
                    if len(body) > MAX_ARTICLE_BYTES:
                        break
                if len(body) > MAX_ARTICLE_BYTES:
                    outcome = "response_too_large"
                else:
                    doc = BeautifulSoup(bytes(body), "html.parser")
                    heading = doc.select_one("[data-testid='page-title'], article h1, main h1")
                    region = doc.select_one("article, main")
                    heading_text = heading.get_text(" ", strip=True) if heading else ""
                    # Never count generic HTML shell, access challenge, or a
                    # mere mention of the game as an authentic patch article.
                    text = region.get_text(" ", strip=True) if region else ""
                    if (re.search(r"grand theft auto vi launch updates", heading_text, re.I)
                            and re.search(r"November\s+23,\s+2026", text, re.I)
                            and re.search(r"\bFixed\b", text, re.I)):
                        outcome = "known_patch_article_present"
                    else:
                        outcome = "article_content_unconfirmed"
    except Exception as exc:
        # Only exception class, no potentially sensitive response/URL.
        outcome = "source_" + type(exc).__name__
    report("SUPPORT_DIRECT_ARTICLE_DIAG status="+outcome+" note=not_a_news_scan")
    return outcome


def probe_general_index(*, fetcher=None, report=print):
    """Exercise the exact fallback in production code without state or posting."""
    fetcher = fetcher or read_support_article_index
    source = next(x for x in json.loads(Path("sources.free.json").read_text(encoding="utf-8"))["sources"]
                  if x.get("id") == "support-gta6")
    try:
        links = fetcher(source)
        if not links:
            outcome = "no_patch_links"
        else:
            outcome = "patch_links_present"
        report("SUPPORT_GENERAL_INDEX_DIAG status="+outcome+" links="+str(len(links))+" note=not_a_news_scan")
    except Exception as exc:
        outcome = "source_"+type(exc).__name__
        report("SUPPORT_GENERAL_INDEX_DIAG status="+outcome+" note=not_a_news_scan")
    return outcome


if __name__ == "__main__":
    # Diagnostics are informational. A failed public vendor site must never
    # block CI or trigger a publication; the monitor will retain its last state.
    probe()
    probe_direct_article()
