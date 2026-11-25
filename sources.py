"""Collector indipendenti: X, feed, pagine pubbliche e snapshot tecnici."""

import hashlib
import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from official_media import image_from_official_html, youtube_thumbnail

LOG = logging.getLogger("gta6.sources")
AGENT = "GTAFanMonitor/2.0"
SCOPES = {"gta6": {"GTA VI"}, "gta": {"GTA VI", "GTA V", "GTA Online"},
          "rockstar": {"GTA VI", "GTA V", "GTA Online", "Rockstar"}}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def public_url(value):
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Le fonti web richiedono un URL HTTPS senza credenziali")
    return value


def canonical_url(value):
    parts = urlsplit(value)
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def load_config(path):
    data = json.loads(Path(path).read_text())
    if data.get("scope") not in SCOPES:
        raise ValueError("scope deve essere gta6, gta oppure rockstar")
    ids = set()
    for source in data["sources"]:
        if source["id"] in ids:
            raise ValueError("Identificativo fonte duplicato")
        ids.add(source["id"])
        if source.get("path"):
            source["path"] = str((Path(path).resolve().parent / source["path"]).resolve())
        if source["type"] not in {"x", "feed", "web_links", "page", "json", "manifest"}:
            raise ValueError("Tipo fonte non supportato")
        if source.get("trust") not in {"official", "community", "observation"}:
            raise ValueError("Ogni fonte richiede trust: official, community o observation")
        if source["type"] in {"json", "manifest"} and source["trust"] != "observation":
            raise ValueError("I confronti tecnici devono avere trust=observation")
        if source["type"] in {"json", "manifest"} and source.get("game") not in SCOPES[data["scope"]]:
            raise ValueError("Il gioco dello snapshot non rientra nella copertura scelta")
        if "url" in source:
            public_url(source["url"])
        if "public_url" in source:
            public_url(source["public_url"])
    return data


def init(db):
    db.executescript("""
      CREATE TABLE IF NOT EXISTS monitors (
        id TEXT PRIMARY KEY, state_json TEXT, last_success REAL, last_error TEXT,
        next_due REAL NOT NULL DEFAULT 0
      );
      CREATE TABLE IF NOT EXISTS content_seen (fingerprint TEXT PRIMARY KEY, post_key TEXT NOT NULL);
    """)


def text_from_html(raw, selector, exclude=None):
    soup = BeautifulSoup(raw, "html.parser")
    if exclude:
        for unwanted in soup.select(exclude):
            unwanted.decompose()
    nodes = soup.select(selector)
    if not nodes:
        raise ValueError("Selettore HTML assente: fonte da aggiornare")
    texts = []
    for node in nodes:
        for hidden in node.select("script,style,nav,footer,header,noscript"):
            hidden.decompose()
        texts.append(node.get_text(" ", strip=True))
    text = " ".join(" ".join(texts).split())
    if not text:
        raise ValueError("La fonte non contiene testo leggibile")
    return text


class SupportBrowserFailure(ValueError):
    """Safe diagnostic, without leaking website markup, URLs or credentials."""

    def __init__(self, phase, reason):
        self.phase = phase
        self.reason = reason
        super().__init__(f"Rockstar Support browser {phase}: {reason}")


def _browser_html(source, address, selector=None):
    """Render an official source; diagnose the phase without exposing secrets.

    A failed Chromium navigation, challenge, missing selector or empty article
    is never accepted as a successful source snapshot. The caller preserves
    the last good state and uses its existing backoff.
    """
    phase = "setup"
    is_support = source.get("id") in {"support-gta", "support-gta6"}
    try:
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(Path(__file__).with_name(".browsers")))
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            options = {"headless": True}
            proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
            if proxy:
                parts = urlsplit(proxy)
                options["proxy"] = {"server": f"{parts.scheme}://{parts.hostname}:{parts.port or 80}"}
                if parts.username:
                    from urllib.parse import unquote
                    options["proxy"].update(username=unquote(parts.username),
                                            password=unquote(parts.password or ""))
            phase = "launch"
            browser = playwright.chromium.launch(**options)
            try:
                phase = "page"
                page = browser.new_page(
                    user_agent=AGENT, locale="en-US",
                    extra_http_headers={"Accept-Language": "en-US,en;q=0.9"})
                phase = "navigation"
                page.goto(address, wait_until="domcontentloaded", timeout=30000)
                phase = "origin"
                if is_support and urlsplit(page.url).hostname != "support.rockstargames.com":
                    raise SupportBrowserFailure("origin", "left the approved host")
                selected = selector or source["selector"]
                phase = "selector"
                page.wait_for_selector(selected, state="attached", timeout=20000)
                phase = "content"
                page.wait_for_function(
                    "({selector,minimum}) => [...document.querySelectorAll(selector)].some(n => (n.innerText || '').trim().length >= minimum)",
                    arg={"selector": selected,
                         "minimum": 80 if selector else source.get("min_text_chars", 1)},
                    timeout=20000)
                phase = "html"
                return page.content()
            finally:
                browser.close()
    except Exception as error:
        if not is_support:
            raise
        # Do not print Playwright's exception message: it can contain a proxy
        # URL, auth data, or a third-party challenge's markup.
        if isinstance(error, SupportBrowserFailure):
            LOG.warning("Rockstar Support browser failed phase=%s reason=%s",
                        error.phase, error.reason)
            raise
        reason = type(error).__name__
        # Playwright often includes a long URL or a proxy address in the
        # navigation exception. Extract ONLY one allowlisted Chromium net::
        # constant; never log the raw exception message or an unknown code.
        if phase == "navigation":
            recognized = {
                "ERR_TUNNEL_CONNECTION_FAILED", "ERR_PROXY_CONNECTION_FAILED",
                "ERR_NAME_NOT_RESOLVED", "ERR_CONNECTION_REFUSED",
                "ERR_CONNECTION_RESET", "ERR_CONNECTION_CLOSED",
                "ERR_CONNECTION_TIMED_OUT", "ERR_TIMED_OUT",
                "ERR_CERT_AUTHORITY_INVALID", "ERR_CERT_COMMON_NAME_INVALID",
                "ERR_BLOCKED_BY_CLIENT", "ERR_NETWORK_CHANGED",
                "ERR_ADDRESS_UNREACHABLE", "ERR_HTTP_RESPONSE_CODE_FAILURE",
            }
            match = re.search(r"net::(ERR_[A-Z0-9_]+)", str(error))
            if match and match.group(1) in recognized:
                reason += "_" + match.group(1)
        LOG.warning("Rockstar Support browser failed phase=%s reason=%s", phase, reason)
        raise SupportBrowserFailure(phase, reason) from None


def get_html(source, url=None, selector=None):
    address = public_url(url or source["url"])
    if source.get("render_js"):
        return _browser_html(source, address, selector)
    headers = {"User-Agent": AGENT, "Accept-Language": "en-US,en;q=0.9"}
    # Rockstar Support can time out from Actions' HTTP client even while
    # Newswire/YouTube are healthy. Two *bounded* HTTP reads are followed by
    # one Chromium read of the same official URL, only for explicitly opted-in
    # Support. No third-party caches, bypass hosts, credentials or paid APIs.
    support = source.get("id") in {"support-gta", "support-gta6"}
    fallback = (support and source.get("browser_fallback_on_timeout") is True
                and urlsplit(address).hostname == "support.rockstargames.com")
    selected = selector or source.get("selector")
    for attempt in range(2 if support else 1):
        try:
            response = requests.get(
                address, headers=headers, timeout=(5, 12) if support else 30)
            response.raise_for_status()
            if fallback and selected and not BeautifulSoup(response.text, "html.parser").select(selected):
                # An HTML shell with no official link/article is not a valid
                # source snapshot; render JavaScript rather than clearing it.
                LOG.warning("Rockstar Support HTTP returned no matching content; trying Chromium")
                return _browser_html(source, address, selector)
            return response.text
        except requests.exceptions.Timeout:
            if not support:
                raise
            if attempt == 0:
                time.sleep(1)
                continue
            if fallback:
                LOG.warning("Rockstar Support HTTP timeout; retrying in Chromium")
                return _browser_html(source, address, selector)
            raise


def event(source, identifier, text, url="", **extra):
    return {"id": str(identifier), "key": f"{source['id']}:{identifier}",
            "text": text, "source_name": source["name"], "trust": source["trust"],
            "source_url": url, "urls": [url] if url else [],
            **({"official_channel_id": source["official_channel_id"]} if source.get("official_channel_id") else {}), **extra}


def collect_x(source, previous, client):
    if client is None:
        raise ValueError("X richiede credenziali API utente")
    user_id = previous.get("user_id") or client.get(
        "/users/by/username/" + source["username"])["data"]["id"]
    posts = client.timeline(user_id, previous.get("cursor"), baseline=not previous)
    events = []
    for post in posts:
        if not post["repost"]:
            value = event(source, post["key"], post["text"],
                          f"https://x.com/{source['username']}/status/{post['id']}")
            value["urls"] = post["urls"]
            value["images"] = post.get("images", [])
            # Mantiene le chiavi della prima versione per la migrazione del database.
            if source["username"].casefold() == "rockstargames":
                value["key"] = post["key"]
            events.append(value)
    ids = [post["id"] for post in posts]
    if previous.get("cursor"):
        ids.append(previous["cursor"])
    return events, {"user_id": user_id, "cursor": max(ids, key=int) if ids else None}


def collect_feed(source):
    response = requests.get(source["url"], headers={"User-Agent": AGENT, 'Accept-Language':'en-US,en;q=0.9'}, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    entries = root.findall(".//item") + root.findall("{http://www.w3.org/2005/Atom}entry")
    if root.tag not in {"rss", "{http://www.w3.org/2005/Atom}feed", "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF"}:
        raise ValueError("La risposta non è un feed RSS/Atom")
    events = []
    for entry in entries:
        def value(name):
            return (entry.findtext(name) or entry.findtext("{http://www.w3.org/2005/Atom}" + name) or "").strip()
        link = value("link")
        if not link:
            links = entry.findall("{http://www.w3.org/2005/Atom}link")
            link = next((x.get("href", "") for x in links if x.get("rel", "alternate") == "alternate"), "")
        public_url(link)
        title, body = value("title"), value("description") or value("summary") or value("content")
        media = entry.find("{http://search.yahoo.com/mrss/}group/{http://search.yahoo.com/mrss/}description")
        if media is not None and media.text:
            body = media.text
        text = BeautifulSoup(title + "\n" + body, "html.parser").get_text(" ", strip=True)
        identifier = value("guid") or value("id") or link
        image_url = youtube_thumbnail(link, source.get("official_channel_id"))
        extra = {"official_image_url": image_url} if image_url else {}
        events.append(event(source, digest(identifier + "\n" + text), text, link, identity=identifier, **extra))
    return events


SUPPORT_ARTICLE_INDEX = "https://support.rockstargames.com/articles"
SUPPORT_ARTICLE_HOST = "support.rockstargames.com"


def support_index_links(html, previous=None):
    """Read only official GTA VI update links from the general knowledge base.

    Match the exact game and patch topics, not account help, GTA V or VI
    substring collisions. Normalize tracking variants and the stable article ID.
    """
    previous = previous or {}
    known = {}
    for url in previous:
        try:
            u = urlsplit(url)
            match = re.fullmatch(r"/articles/([A-Za-z0-9_-]+)/[^/]+/?", u.path)
            if u.scheme == "https" and u.netloc == SUPPORT_ARTICLE_HOST and match:
                known[match.group(1)] = url
        except ValueError:
            continue
    found = {}
    for node in BeautifulSoup(html, "html.parser").select("a[href]"):
        try:
            u = urlsplit(urljoin(SUPPORT_ARTICLE_INDEX, node.get("href", "")))
        except ValueError:
            continue
        if u.scheme != "https" or u.netloc != SUPPORT_ARTICLE_HOST:
            continue
        match = re.fullmatch(r"/articles/([A-Za-z0-9_-]+)/([A-Za-z0-9_-]+)/?", u.path)
        if not match:
            continue
        title = node.get_text(" ", strip=True)
        if not title:
            continue
        subject = match.group(2).replace("-", " ") + " " + title
        if not re.search(r"\b(?:grand theft auto vi|gta\s*(?:vi|6))\b", subject, re.I):
            continue
        if not re.search(r"\b(?:launch updates?|patch notes?|title updates?)\b", subject, re.I):
            continue
        ident = match.group(1)
        url = known.get(ident, "https://" + SUPPORT_ARTICLE_HOST + u.path.rstrip("/"))
        found.setdefault(ident, (url, title))
    return dict(found.values())


def read_support_article_index(source, previous=None):
    """One bounded public HTTP request, with existing Chromium renderer only
    for an HTTP 200 shell. No alternate host, private API, proxy changes, or
    vendor-access bypass. Empty or unrelated content is never a success.
    """
    address = SUPPORT_ARTICLE_INDEX
    headers = {"User-Agent": AGENT, "Accept-Language": "en-US,en;q=0.9"}
    with requests.get(address, headers=headers, timeout=(5, 10),
                      allow_redirects=False, stream=True) as response:
        response.raise_for_status()
        if response.status_code != 200 or response.url != address:
            raise ValueError("Rockstar Support index unavailable")
        body = bytearray()
        for chunk in response.iter_content(chunk_size=16384):
            body.extend(chunk)
            if len(body) > 1_500_000:
                raise ValueError("Rockstar Support index too large")
    links = support_index_links(bytes(body), previous)
    if not links:
        # Same existing browser restrictions as support-gta6. The general
        # index may be a JavaScript shell, but a shell is not a valid listing.
        html = _browser_html(source, address)
        links = support_index_links(html, previous)
    if not links:
        raise ValueError("Rockstar Support index: no official GTA VI patch links")
    return links


def listing_links(source, html):
    selected = BeautifulSoup(html, "html.parser").select(source["selector"])
    if not selected:
        raise ValueError("Nessun link trovato: JavaScript o struttura della fonte da verificare")
    links = {}
    for node in selected:
        url = canonical_url(urljoin(source["url"], node.get("href", "")))
        if urlsplit(url).netloc != urlsplit(source["url"]).netloc:
            continue
        title = node.get_text(" ", strip=True)
        include_pattern = source.get("include_link_pattern")
        if include_pattern and not re.search(include_pattern, url + " " + title, re.I):
            continue
        links[url] = title
    if not links:
        raise ValueError("Nessun articolo valido trovato")
    return links


def collect_links(source, previous):
    using_index = False
    try:
        links = listing_links(source, get_html(source))
    except (requests.RequestException, ValueError):
        if (source.get("id") != "support-gta6"
                or source.get("url") != "https://support.rockstargames.com/VI"
                or source.get("trust") != "official"
                or source.get("article_index_fallback") is not True):
            raise
        links = read_support_article_index(source, previous.get("links", {}))
        using_index = True
        LOG.info("Rockstar Support GTA VI: official article-index fallback, %d patch links", len(links))
    # First use of the broader index is a baseline for newly discovered URLs,
    # not breaking news. Existing watched URLs may still produce revisions.
    seed_index = using_index and not previous.get("article_index_baseline")
    events = []
    patch_records = []
    article_hashes = dict(previous.get("article_hashes", {}))
    article_sequences = dict(previous.get("article_sequences", {}))
    for url, title in links.items():
        is_new = bool(previous) and url not in previous.get("links", {})
        watch = bool(source.get("watch_existing_pattern") and re.search(source["watch_existing_pattern"], url, re.I))
        if is_new or watch:
            raw = get_html(source, url, source.get("article_selector", "main"))
            # Reuse the already successful official article read; no extra HTTP.
            if source.get("id") == "support-gta6" and source.get("trust") == "official":
                from patch_history_v1 import OFFICIAL_ARTICLE, parse_patch_records
                if url == OFFICIAL_ARTICLE:
                    from history import utc_now
                    patch_records = parse_patch_records(raw, url, utc_now())
                    LOG.info("PATCH_EVIDENCE_%s dates=%d", "OBSERVED" if patch_records else "UNCONFIRMED", len(patch_records))
            body = text_from_html(raw, source.get("article_selector", "main"), source.get("article_exclude_selector"))
            heading = BeautifulSoup(raw, "html.parser").select_one("h1,[data-testid='page-title']")
            headline = heading.get_text(" ", strip=True) if heading else title
            image_url = image_from_official_html(raw, url)
            image_meta = {"official_image_url": image_url} if image_url else {}
            if is_new and not seed_index:
                events.append(event(source, digest(url), headline + "\n" + body, url, headline=headline, **image_meta))
            elif watch and url in article_hashes and article_hashes[url] != digest(body):
                sequence = article_sequences.get(url, 0) + 1
                article_sequences[url] = sequence
                events.append(event(source, digest(url) + ":revision:" + str(sequence) + ":" + digest(body),
                                    headline + "\n" + body, url, headline=headline, change_context="patch note aggiornata", **image_meta))
            if watch:
                article_hashes[url] = digest(body)
    # Mantiene i link usciti dalla prima pagina per non ripubblicarli se ricompaiono.
    state = {"links": {**previous.get("links", {}), **links}}
    if patch_records:
        state["patch_history_records"] = patch_records
    if using_index or previous.get("article_index_baseline"):
        state["article_index_baseline"] = True
    if source.get("watch_existing_pattern"):
        state.update(article_hashes=article_hashes, article_sequences=article_sequences)
    return events, state


def pointer(data, path):
    for part in path.strip("/").split("/") if path else []:
        name = part.replace("~1", "/").replace("~0", "~")
        data = data[int(name)] if isinstance(data, list) else data[name]
    return data


def changes(old, new):
    return [{"field": key, "before": old.get(key), "after": new.get(key),
             "change": "added" if key not in old else "removed" if key not in new else "changed"}
            for key in sorted(set(old) | set(new)) if old.get(key) != new.get(key) or (key in old) != (key in new)]


def snapshot_event(source, previous, current):
    if not previous or previous["snapshot"] == current:
        return []
    delta = changes(previous["snapshot"], current)
    text = json.dumps({"game": source["game"], "platform": source.get("platform", ""), "changes": delta}, ensure_ascii=False)
    return [event(source, str(previous.get("sequence", 0) + 1) + ":" + digest(current), text,
                  source.get("public_url", source.get("url", "")), game=source["game"],
                  platform=source.get("platform", ""), observation=delta)]


def collect(source, previous, client):
    kind = source["type"]
    if kind == "x":
        return collect_x(source, previous, client)
    if kind == "feed":
        events = collect_feed(source)
        seen = previous.get("seen", {})
        new = [item for item in events if item["key"] not in seen]
        return new, {"seen": {**seen, **{item["key"]: True for item in events}}}
    if kind == "web_links":
        return collect_links(source, previous)
    if kind == "page":
        text = text_from_html(get_html(source), source["selector"])
        signature = digest(text)
        sequence = previous.get("sequence", 0) + int(bool(previous) and previous.get("hash") != signature)
        events = [] if not previous or previous.get("hash") == signature else [
            event(source, f"{sequence}:{signature}", text, source["url"], change_context="pagina modificata")]
        return events, {"hash": signature, "sequence": sequence}
    if kind == "manifest":
        data = json.loads(Path(source["path"]).read_text())
        if data.get("game") != source["game"] or data.get("platform") != source["platform"]:
            raise ValueError("Gioco/piattaforma del manifest non corrispondono alla fonte")
        current = data["files"]
        if not isinstance(current, dict):
            raise ValueError("files deve essere un oggetto JSON")
    else:
        response = requests.get(source["url"], headers={"User-Agent": AGENT, 'Accept-Language':'en-US,en;q=0.9'}, timeout=30)
        response.raise_for_status()
        data = response.json()
        # Confronta solo i campi scelti, mai timestamp o token di sessione estranei.
        current = {label: pointer(data, path) for label, path in source["fields"].items()}
    sequence = previous.get("sequence", 0) + int(bool(previous) and previous.get("snapshot") != current)
    return snapshot_event(source, previous, current), {"snapshot": current, "sequence": sequence}


def old_rockstar_state(db, source):
    if source["type"] != "x" or source["username"].casefold() != "rockstargames":
        return {}
    old = dict(db.execute("SELECT key,value FROM meta WHERE key IN ('initialized','source_id','cursor')").fetchall())
    if old.get("initialized"):
        return {"user_id": old.get("source_id"), "cursor": old.get("cursor")}
    return {}


def poll(db, config, client=None, force=False):
    """Ogni fonte ha cursore, errore e backoff separati. Ritorna gli errori."""
    init(db)
    errors = 0
    for source in config["sources"]:
        if not source.get("enabled", True):
            continue
        row = db.execute("SELECT * FROM monitors WHERE id=?", (source["id"],)).fetchone()
        now = time.time()
        if row and row["next_due"] > now and not force:
            continue
        previous = json.loads(row["state_json"]) if row and row["state_json"] else old_rockstar_state(db, source)
        interval = max(60, int(source.get("interval", os.getenv("POLL_SECONDS", "300"))))
        try:
            events, current = collect(source, previous, client)
            # Persist only fresh, parsed primary evidence in the existing ledger.
            # A failed source scan never invents a new observation timestamp.
            patch_records = current.pop("patch_history_records", [])
            if patch_records:
                from history import import_history
                import_history(db, patch_records)
            with db:
                if previous:
                    for item in events:
                        # Solo duplicati testuali esatti; non elimina nuove osservazioni sullo stesso URL.
                        fingerprint = digest({"text": " ".join(item["text"].split()),
                                              "urls": sorted(item.get("urls", [])),
                                              "transition": item["key"] if "observation" in item or "change_context" in item else None})
                        duplicate = db.execute("SELECT 1 FROM content_seen WHERE fingerprint=?", (fingerprint,)).fetchone()
                        if not duplicate:
                            db.execute("INSERT OR IGNORE INTO posts(key,source_id,source_json) VALUES (?,?,?)",
                                       (item["key"], item["id"], json.dumps(item, ensure_ascii=False)))
                            db.execute("INSERT OR IGNORE INTO content_seen VALUES (?,?)", (fingerprint, item["key"]))
                db.execute("INSERT OR REPLACE INTO monitors VALUES (?,?,?,?,?)",
                           (source["id"], json.dumps(current, ensure_ascii=False), now, None, now + interval))
            LOG.info("Fonte %s: %s", source["id"], "baseline salvata" if not previous else f"{len(events)} segnali raccolti")
        except Exception as error:
            # Una fonte non deve bloccare tutte le altre; niente valori di token nei log.
            errors += 1
            delay = max(interval, getattr(error, "retry_after", 0))
            if isinstance(error, requests.HTTPError) and error.response is not None and error.response.status_code == 429:
                try:
                    delay = max(delay, float(error.response.headers.get("Retry-After", 900)))
                except ValueError:
                    delay = max(delay, 900)
            with db:
                description = str(error) if isinstance(error, ValueError) else type(error).__name__
                db.execute("INSERT OR REPLACE INTO monitors VALUES (?,?,?,?,?)",
                           (source["id"], json.dumps(previous) if previous else None,
                            row["last_success"] if row else None, description, now + delay))
            LOG.error("Fonte %s non aggiornata (%s)", source["id"], type(error).__name__)
    return errors


def scan(root, output, game, platform):
    """Crea un manifest leggendo file locali: non scarica o modifica i file di gioco."""
    root, output = Path(root).resolve(), Path(output).resolve()
    if not root.is_dir():
        raise ValueError("La cartella da confrontare non esiste")
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file() or path.resolve() in {output, output.with_name(output.name + ".tmp")}:
            continue
        before = path.stat()
        sha256, md5 = hashlib.sha256(), hashlib.md5(usedforsecurity=False)
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                sha256.update(block)
                md5.update(block)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("File cambiato durante la scansione: ripetere a download completato")
        files[path.relative_to(root).as_posix()] = {"bytes": after.st_size,
                                                  "sha256": sha256.hexdigest(), "md5": md5.hexdigest()}
    document = {"game": game, "platform": platform, "files": files}
    temp = output.with_name(output.name + ".tmp")
    temp.write_text(json.dumps(document, ensure_ascii=False, indent=2))
    temp.replace(output)
    return len(files)
