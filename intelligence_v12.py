"""V12 Multi-Source Intelligence: opt-in, read-only, auditable RSS research.

IMPORTANT: This module NEVER calls Buffer or X; it only records candidates in
an existing encrypted SQLite database. No press/rumor content is auto-published.
The official v11 publication pipeline remains the sole automatic publisher.

RSS feed headlines are treated as publisher claims, not corroborated facts.
Article images are NOT downloaded, rehosted, or posted (rights unverified).
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
import hashlib
import json
import logging
from pathlib import Path
import re
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit, urljoin
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import requests

LOG = logging.getLogger('gta.intelligence.v12')
MAX_FEED_BYTES = 1_500_000
MAX_ITEMS_PER_FEED = 45
DEFAULT_POLL_SECONDS = 600
MAX_NEW_ITEM_AGE_SECONDS = 72 * 3600
MAX_DISPLAY = 8
HEADERS = {'User-Agent': 'Federiko-GTA-NewsCenter/12 (editorial RSS research; source links only)',
           'Accept': 'application/rss+xml,application/atom+xml,application/xml,text/xml,*/*;q=0.5'}

# Source-to-domain binding is code-controlled, not supplied solely by a JSON feed.
ALLOWLIST = {
    'ps-blog': ('blog.playstation.com',),
    'ign': ('ign.com',),
    'vgc': ('videogameschronicle.com',),
    'eurogamer': ('eurogamer.net',),
    'pushsquare': ('pushsquare.com',),
    'multiplayer': ('multiplayer.it',),
    'everyeye': ('everyeye.it',),
    'digital-foundry': ('youtube.com',),
    'powerpyx': ('powerpyx.com',),
}
DF_CHANNEL_ID = 'UC9PBzalIcEQCsiIkq36PyUA'

GTA_RE = re.compile(r'\b(?:gta[ -]?(?:vi|6)|grand\s+theft\s+auto[ -]?(?:vi|6))\b', re.I)
PS5_RE = re.compile(r'\b(?:ps5(?:\s*pro)?|playstation\s*5(?:\s*pro)?)\b', re.I)
GTA_ONLINE_RE = re.compile(r'(?:\b(?:gta[ -]?(?:online|v|5)|grand\s+theft\s+auto\s+(?:online|v|5))\b|\bgta\+)', re.I)
WEEKLY_RE = re.compile(r'\b(?:weekly|week|settimanale|event\s+week|bonus|bonuses|sconti|discounts?|'
                       r'ricompense|rewards?|double|triple|quadruple|2x|3x|4x|'
                       r'prize\s+ride|podium|vehicle|veicolo|heist|mission|farm|payout|'
                       r'earnings|patch|title\s+update|aggiornamento)\b|\bgta\$|\bgta\+', re.I)

PS5_TECH_RE = re.compile(r'\b(?:firmware|system\s+software|system\s+update|aggiornamento\s+(?:di\s+)?sistema|'
                         r'aggiornamento\s+ps5|console\s+update|pssr|frame\s*rate|prestazioni|performance|'
                         r'ray[ -]?tracing|security\s+patch|correzioni\s+di\s+sicurezza|hardware)\b', re.I)
RISK_RE = re.compile(r'\b(?:leak(?:ed|s)?|rumou?rs?|indiscrezion[ei]|trapelat[oaie]|spoiler|'
                     r'presunt[oaie]|unverified|non\s+confermat[oaie]|allegedly|speculat(?:ion|ive)|'
                     r'theory|teoria|hack|mod\s+menu|ban\s+wave)\b', re.I)
GUIDE_RE = re.compile(r'\b(?:guida|guide|walkthrough|trofe[io]|troph(?:y|ies)|platino|platinum|'
                      r'strateg(?:y|ie)|consigl(?:io|i)|tips|trick|glitch|exploit|duplicat)\w*\b', re.I)
TOPIC_EQUIVALENTS = {
    'trailer': 'trailer', 'annuncio': 'announce', 'announced': 'announce', 'announcement': 'announce',
    'lancio': 'launch', 'launch': 'launch', 'uscita': 'release', 'release': 'release',
    'rinvio': 'delay', 'delayed': 'delay', 'delay': 'delay',
    'trofei': 'trophy', 'trofeo': 'trophy', 'trophies': 'trophy', 'trophy': 'trophy',
    'platino': 'platinum', 'platinum': 'platinum', 'patch': 'patch',
    'aggiornamento': 'update', 'update': 'update',
    'prestazioni': 'performance', 'performance': 'performance',
    'sicurezza': 'security', 'security': 'security',
    'radio': 'radio', 'musica': 'music', 'music': 'music',
    'recensione': 'review', 'review': 'review', 'gameplay': 'gameplay',
}
STOP_WORDS = {'the','and','for','with','from','that','this','are','our','new','a','an','in','on','at','of','to','is',
              'il','la','lo','gli','una','uno','con','per','del','della','dello','delle','e','di','da','dei','su',
              'gta','vi','6','ps5','pro','playstation','grand','theft','auto','news','notizie', 'oggi', 'today'}


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith('.' + domain)


def safe_url(url: str, domains: tuple[str, ...]) -> str | None:
    """Canonicalize a publisher URL and reject foreign/unsafe domains and ports."""
    try:
        parts = urlsplit(str(url).strip())
        host = (parts.hostname or '').lower()
        if (parts.scheme != 'https' or not host or parts.username or parts.password or
                parts.port not in (None, 443) or not any(_host_matches(host, d) for d in domains)):
            return None
        params = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False)
                  if not (k.lower().startswith('utm_') or k.lower() in {'fbclid', 'gclid', 'ref', 'mc_cid', 'mc_eid'})]
        path = parts.path.rstrip('/') or '/'
        return urlunsplit(('https', host, path, urlencode(params), ''))
    except ValueError:
        return None


def load_config(path: str | Path) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    if payload.get('schema_version') != 12 or not isinstance(payload.get('feeds'), list):
        raise ValueError('Configurazione v12 non valida')
    result, seen = [], set()
    for item in payload['feeds']:
        if not isinstance(item, dict) or item.get('id') not in ALLOWLIST or item['id'] in seen:
            raise ValueError('Fonte v12 sconosciuta o duplicata')
        sid = item['id']
        seen.add(sid)
        domains = ALLOWLIST[sid]
        if not safe_url(item.get('url', ''), domains):
            raise ValueError('Feed non HTTPS o dominio diverso dalla fonte registrata')
        if sid == 'digital-foundry':
            parsed = urlsplit(item['url'])
            query = dict(parse_qsl(parsed.query))
            if parsed.path != '/feeds/videos.xml' or query != {'channel_id': DF_CHANNEL_ID}:
                raise ValueError('Digital Foundry YouTube channel ID mismatch')
        if item.get('tier') not in ('official', 'press') or (sid == 'ps-blog') != (item.get('tier') == 'official'):
            raise ValueError('Livello attendibilita non valido')
        if item.get('language') not in ('it', 'en'):
            raise ValueError('Lingua del feed non valida')
        if not isinstance(item.get('enabled'), bool):
            raise ValueError('enabled deve essere un booleano')
        item = dict(item)
        item['interval'] = max(300, min(int(item.get('interval', DEFAULT_POLL_SECONDS)), 86400))
        result.append(item)
    return result


def clean_text(raw: str, limit: int = 300) -> str:
    text = BeautifulSoup(unescape(str(raw or '')), 'html.parser').get_text(' ', strip=True)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:limit].rstrip()


def xml_text(node, tags):
    for tag in tags:
        found = node.find(tag)
        if found is not None:
            text = ''.join(found.itertext()).strip()
            if text:
                return text
    return ''


def _published(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (ValueError, TypeError, IndexError):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def parse_feed(xml: bytes, source: dict) -> list[dict]:
    if not isinstance(xml, bytes) or len(xml) > MAX_FEED_BYTES or b'<!DOCTYPE' in xml.upper():
        raise ValueError('RSS troppo grande o contiene DTD')
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError('RSS/XML non leggibile') from exc
    atom = root.tag.rsplit('}', 1)[-1] == 'feed'
    if atom:
        nodes = root.findall('{http://www.w3.org/2005/Atom}entry')
    else:
        nodes = root.findall('.//item')
    if not nodes:
        raise ValueError('Feed senza item o entry')
    result = []
    for item in nodes[:MAX_ITEMS_PER_FEED]:
        if atom:
            ns = '{http://www.w3.org/2005/Atom}'
            title = xml_text(item, [ns+'title'])
            summary = xml_text(item, [ns+'summary', ns+'content'])
            link = next((el.get('href') for el in item.findall(ns+'link')
                         if el.get('rel', 'alternate') == 'alternate' and el.get('href')), '')
            timestamp = xml_text(item, [ns+'published', ns+'updated'])
        else:
            title = xml_text(item, ['title'])
            summary = xml_text(item, ['description', '{http://purl.org/rss/1.0/modules/content/}encoded'])
            link = xml_text(item, ['link'])
            timestamp = xml_text(item, ['pubDate', '{http://purl.org/dc/elements/1.1/}date'])
        title = clean_text(title, 230)
        summary = clean_text(summary, 400)
        url = safe_url(link, ALLOWLIST[source['id']])
        if not title or not url:
            continue
        if source['id'] == 'digital-foundry':
            vid_channel = xml_text(item, ['{http://www.youtube.com/xml/schemas/2015}channelId'])
            if vid_channel != DF_CHANNEL_ID:
                # Do not attribute videos from another channel to Digital Foundry.
                continue
        result.append({'url': url, 'title': title, 'summary': summary,
                       'published_at': _published(timestamp), 'language': source['language'],
                       'source_id': source['id'], 'source_name': source['name'], 'tier': source['tier']})
    return result


def relevance(headline: str, summary: str = '') -> str | None:
    text = ' '.join([headline, summary])
    if GTA_RE.search(text):
        return 'GTA VI'
    if GTA_ONLINE_RE.search(text):
        # The monitor is PS5-first: PC-only mod menus and outdated legacy
        # console posts must not enter the editorial queue.
        if re.search(r'\b(?:PC[ -]?only|PS4[ -]?only|solo\s+(?:pc|ps4))\b', text, re.I):
            return None
        if WEEKLY_RE.search(text):
            return 'GTA Online / bonus e aggiornamenti'
        if re.search(r'(?:\b(?:gta[ -]?online|grand\s+theft\s+auto\s+online)\b|\bgta\+)',text,re.I):
            return 'GTA Online / approfondimenti'
        return None
    if PS5_RE.search(text) and PS5_TECH_RE.search(text):
        if re.search(r'\b(?:only|soltanto|esclusiva(?:mente)?\s+ps4|ps4\s+only)\b', headline, re.I):
            return None
        return 'PS5 / PS5 Pro'
    return None


def risk_for(item: dict) -> str:
    text = item['title'] + ' ' + item['summary']
    if RISK_RE.search(text):
        return 'hold_rumor_or_spoiler'
    if GUIDE_RE.search(text):
        return 'review_guide'
    return 'review_news'


def topic_signature(item: dict) -> str:
    title = item['title'].casefold()
    tokens = re.findall(r'\w+', title)
    tags = sorted({TOPIC_EQUIVALENTS[t] for t in tokens if t in TOPIC_EQUIVALENTS})
    # Broad affinity label, never proof two sources independently verified a claim.
    return (relevance(item['title'], item['summary']) or 'other').lower().replace(' ', '-') + ':' + ('+'.join(tags) or 'general')


def init_tables(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS intel_v12_sources (
        id TEXT PRIMARY KEY, state_json TEXT NOT NULL, next_due REAL NOT NULL,
        last_success REAL, last_error TEXT
    );
    CREATE TABLE IF NOT EXISTS intel_v12_articles (
        id TEXT PRIMARY KEY, source_id TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL, summary TEXT NOT NULL, published_at TEXT,
        seen_at REAL NOT NULL, topic TEXT NOT NULL, topic_signature TEXT NOT NULL,
        language TEXT NOT NULL, tier TEXT NOT NULL, risk TEXT NOT NULL,
        review_status TEXT NOT NULL, media_rights TEXT NOT NULL DEFAULT 'unverified'
    );
    ''')


def request_feed(source: dict, *, session=None) -> bytes:
    client = session or requests
    address = source['url']
    response = None
    # At most two same-publisher redirects; never follow a third-party host.
    for _ in range(3):
        response = client.get(address, headers=HEADERS, timeout=(4, 7), allow_redirects=False)
        if response.status_code not in (301, 302, 303, 307, 308):
            break
        target = urljoin(address, response.headers.get('Location', ''))
        canonical = safe_url(target, ALLOWLIST[source['id']])
        if not canonical:
            raise ValueError('RSS redirect fuori dal dominio verificato')
        address = canonical
    else:
        raise ValueError('Troppi redirect RSS')
    response.raise_for_status()
    if response.status_code != 200 or not safe_url(getattr(response, 'url', address), ALLOWLIST[source['id']]):
        raise ValueError('RSS non disponibile su URL verificato')
    data = response.content
    if not isinstance(data, bytes) or len(data) > MAX_FEED_BYTES:
        raise ValueError('RSS oltre il limite di dimensione')
    return data


def poll(db, config_path, *, fetcher=None, now=None, max_seconds=48) -> dict:
    """Poll each feed into encrypted DB state. No remote write, no Buffer/X API.

    A new feed is baseline-only, not an old-news backfill. Subsequent unseen
    items are staged for human review. Feed titles are not verified facts.
    """
    now = float(now if now is not None else time.time())
    started = time.monotonic()
    init_tables(db)
    feeds = load_config(config_path)
    counts = {'checked': 0, 'baseline': 0, 'new': 0, 'held': 0, 'errors': 0, 'skipped': 0}
    for source in feeds:
        if not source['enabled']:
            counts['skipped'] += 1
            continue
        row = db.execute('SELECT * FROM intel_v12_sources WHERE id=?', (source['id'],)).fetchone()
        if row and row['next_due'] > now:
            continue
        if time.monotonic() - started >= max_seconds:
            counts['skipped'] += 1
            continue
        previous = json.loads(row['state_json']) if row else None
        first_success = row is None or row['last_success'] is None
        interval = source['interval']
        try:
            data = fetcher(source) if fetcher else request_feed(source)
            items = parse_feed(data, source)
            seen = set(previous.get('seen', [])) if previous else set()
            all_ids = list(seen)
            with db:
                for item in items:
                    label = relevance(item['title'], item['summary'])
                    if not label:
                        continue
                    stamp = item['published_at']
                    aid = hashlib.sha256(item['url'].encode('utf-8')).hexdigest()
                    if aid in seen:
                        continue
                    all_ids.append(aid)
                    if db.execute('SELECT 1 FROM intel_v12_articles WHERE id=?', (aid,)).fetchone():
                        continue
                    # First successful fetch NEVER creates a publishable backlog.
                    baseline = first_success
                    fresh = (stamp is not None and -3600 <= now-stamp.timestamp() <= MAX_NEW_ITEM_AGE_SECONDS)
                    risk = risk_for(item)
                    review_status = ('baseline' if baseline else
                                     'hold' if not fresh or risk.startswith('hold') else 'review')
                    db.execute('''INSERT OR IGNORE INTO intel_v12_articles
                        (id,source_id,url,title,summary,published_at,seen_at,topic,topic_signature,
                         language,tier,risk,review_status,media_rights)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (aid, source['id'], item['url'], item['title'], item['summary'],
                         stamp.isoformat() if stamp else None, now, label,
                         topic_signature(item), item['language'], item['tier'], risk,
                         review_status, 'unverified'))
                    counts['baseline' if baseline else 'new'] += 1
                    if review_status == 'hold':
                        counts['held'] += 1
                # Store a bounded fingerprint window; article URLs persist in the table.
                rolling = list(dict.fromkeys(all_ids))[-600:]
                db.execute('''INSERT OR REPLACE INTO intel_v12_sources
                    (id,state_json,next_due,last_success,last_error) VALUES (?,?,?,?,?)''',
                    (source['id'], json.dumps({'seen': rolling}), now+interval, now, None))
            counts['checked'] += 1
        except (requests.RequestException, ValueError, ET.ParseError) as error:
            counts['errors'] += 1
            # Preserve previous cursor, short backoff for failures, no noisy retry.
            with db:
                db.execute('''INSERT OR REPLACE INTO intel_v12_sources
                    (id,state_json,next_due,last_success,last_error) VALUES (?,?,?,?,?)''',
                    (source['id'], json.dumps(previous or {'seen': []}), now + max(interval, 900),
                     row['last_success'] if row else None, type(error).__name__))
            LOG.warning('v12 source %s not updated (%s)', source['id'], type(error).__name__)
    return counts


def review_queue(db, limit=MAX_DISPLAY) -> list[dict]:
    init_tables(db)
    rows = db.execute('''SELECT source_id,url,title,published_at,topic,topic_signature,
                         tier,language,risk,review_status,media_rights
                         FROM intel_v12_articles WHERE review_status IN ('review','hold')
                         ORDER BY seen_at DESC,id LIMIT ?''', (max(0, min(int(limit), 100)),)).fetchall()
    return [dict(row) for row in rows]


def report(db, max_display=5, output_path=None) -> None:
    pending = review_queue(db, max_display)
    print(f'INTELLIGENCE V12 — {len(pending)} research candidates shown; zero Buffer/X posts')
    for item in pending[:5]:
        print(f"{item['review_status'].upper()} [{item['language'].upper()}] "
              f"{item['source_id']}: {item['title'][:115]} | {item['url']}")
    print('Publisher headlines are unverified claims; media rights unverified; NO auto-post.')
    if output_path:
        # The report contains only excerpts of headlines and links, not articles,
        # full RSS descriptions, private tokens or Buffer post data.
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {'schema_version': 12,
                   'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                   'publication': 'NONE — sources are read-only',
                   'note': 'Publisher headlines are editorial leads, NOT independent verification.',
                   'candidates': [{**item, 'title': item['title'][:150]} for item in pending]}
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
