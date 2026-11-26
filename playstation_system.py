"""Legge le versioni di sistema pubblicate da Sony, senza scaricare firmware."""

from datetime import datetime, timezone
import re
import logging
import time
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
import requests
from official_media import image_from_official_html

URLS = {platform: f"https://www.playstation.com/it-it/support/hardware/{platform.lower()}/system-software-info/"
        for platform in ("PS5", "PS4")}


def _sony_url(value):
    parsed = urlsplit(value)
    return (parsed.scheme == "https" and not parsed.username and not parsed.password
            and (parsed.hostname == "playstation.com" or (parsed.hostname or "").endswith(".playstation.com")))


def parse_system_page(raw, platform, *, source_url=None, observed_at=None):
    if platform not in URLS:
        raise ValueError("Il monitor software supporta PS5 e PS4")
    address = source_url or URLS[platform]
    if not _sony_url(address):
        raise ValueError("Il software di sistema richiede una fonte ufficiale PlayStation")
    image_url = image_from_official_html(raw, address)
    soup = BeautifulSoup(raw, "html.parser")
    for hidden in soup.select("script,style,nav,header,footer"):
        hidden.decompose()
    current, found_previous = [], False
    for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "span", "button"]):
        text = " ".join(node.get_text(" ", strip=True).split())
        if re.search(r"Aggiornamenti precedenti.*software|Previous system software updates|Previous updates", text, re.I):
            found_previous = True
            break
        if node.name.startswith("h"):
            match = re.fullmatch(r"(?:Versione|Version)\s*:?\s*(\d[\d.\-]*)", text, re.I)
            if match:
                current.append((match.group(1), node))
    if not found_previous or len(current) != 1:
        raise ValueError("Versione corrente Sony non identificabile senza ambiguità")
    version, heading = current[0]
    pattern = r"\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}" if platform == "PS5" else r"\d{1,2}\.\d{2}"
    if not re.fullmatch(pattern, version):
        raise ValueError("Formato versione Sony da verificare")
    notes = [" ".join(node.get_text(" ", strip=True).split()) for node in heading.parent.select("ul li")]
    stamp = observed_at or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {"event_key": f"sony-system:{platform}:{version}", "game": "PlayStation", "category": "SISTEMA",
            "data_kind": "system_software", "platforms": [platform], "version": version,
            "version_namespace": platform + "_SYSTEM_SOFTWARE", "region": None,
            "title": "Aggiornamento di sistema disponibile", "facts": [
                {"label": "Versione ufficiale", "value": version},
                {"label": "Novità indicate da Sony", "value": notes[0] if notes else None},
                {"label": "Data di rilascio", "value": None}],
            "source_url": address, "source_name": "PlayStation Support", "trust": "official",
            "observed_at": stamp, "release_at": None, "official_notes": notes,
            **({"official_image_url": image_url} if image_url else {})}


def _fetch_system_page(platform, timeout):
    """Single bounded HTML read; never download firmware."""
    if platform not in URLS:
        raise ValueError("Il monitor software supporta PS5 e PS4")
    with requests.get(URLS[platform], headers={"User-Agent": "GTA-PlayStation-Monitor/4.0", "Accept": "text/html"},
                      timeout=timeout, stream=True) as response:
        response.raise_for_status()
        if not _sony_url(response.url) or "text/html" not in response.headers.get("Content-Type", "").lower():
            raise ValueError("Sony non ha restituito la pagina HTML attesa; nessun firmware viene scaricato")
        raw = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            raw.extend(chunk)
            if len(raw) > 2_000_000:
                raise ValueError("Pagina Sony oltre il limite dei metadati")
        return parse_system_page(bytes(raw), platform, source_url=response.url)


LOG = logging.getLogger("gta6.playstation")
TRANSIENT_HTTP = {408, 500, 502, 503, 504}


def fetch_system_update(platform, timeout=25):
    """One retry of the same official URL on transient network/server errors."""
    for attempt in range(2):
        try:
            return _fetch_system_page(platform, timeout)
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            status = response.status_code if isinstance(exc, requests.HTTPError) and response is not None else None
            if isinstance(status, int) and 100 <= status <= 599:
                reason = "HTTP_" + str(status)
            else:
                reason = type(exc).__name__
            transient = (status in TRANSIENT_HTTP if isinstance(exc, requests.HTTPError)
                         else isinstance(exc, (requests.Timeout, requests.ConnectionError))
                         and not isinstance(exc, (requests.exceptions.SSLError, requests.exceptions.ProxyError)))
            LOG.warning("SONY_SOURCE_ERROR platform=%s reason=%s attempt=%d",
                        platform, reason, attempt + 1)
            # Do not retry access denial, rate limits, redirects to non-HTML,
            # parse failures, certificate/proxy errors, or unknown status.
            if attempt or not transient:
                raise
            time.sleep(1)
