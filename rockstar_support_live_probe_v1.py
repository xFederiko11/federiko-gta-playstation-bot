"""Read-only public Rockstar Support reachability diagnosis for GitHub Actions.

No database, state, Buffer, X, authenticated endpoints or new services.  The
monitor is authoritative; a successful one-off probe is NOT a confirmed news
event and must never update any persistent cursor.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit
import json

from bs4 import BeautifulSoup
from sources import SupportBrowserFailure, get_html

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


if __name__ == "__main__":
    # Diagnostics are informational. A failed public vendor site must never
    # block CI or trigger a publication; the monitor will retain its last state.
    probe()
