"""GTA VI News Center v13.7: cautious RSS editorial autopilot.

Publishes attributed headlines and source links only, not unverified article claims.
Reservations are committed to GitHub before Buffer is invoked.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
from html import unescape
import json
import os
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import xml.etree.ElementTree as ET
import requests
from editorial_language_it import italian_title, TranslationUnavailable
from editorial_director_v142 import priority, allowed as director_allowed
from launch_cadence_v1 import (active as launch_active, in_hours as launch_in_hours,
    count_local_day as launch_day_count, TARGET_MAX as LAUNCH_DAILY_CAP)
from editorial_double_threads_v1 import double as launch_double
from quality_publish_policy_v1 import ordinary_hours, local as publishing_local, START as QUALITY_START

STATE = Path('.state/editorial-autopilot-v137.json')
CONFIG = Path('editorial-autopilot-v137-sources.json')
MAX_DOWNLOAD = 1_800_000
MAX_AGE_MIN = 720  # catch up on timely launch-day coverage, not only latest 3 hours
MAX_POSTS_DAY = 6  # original posts, not tweet/reply units; global director still guards all workflows
MIN_SPACING_MIN = 45  # avoid back-to-back generic headline posts
RUN_LIMIT = 1
MAX_MEDIA_CANDIDATES = 8  # inspect backups, but reserve no more than one post per run
BRIDGE_URLS = {
    'https://www.videogameschronicle.com/review/grand-theft-auto-6/',
    'https://www.pushsquare.com/reviews/ps5/grand-theft-auto-6',
    'https://www.videogameschronicle.com/news/grand-theft-auto-6-is-currently-the-highest-scoring-video-game-of-all-time-according-to-metacritic/',
    'https://gta.guide/article/contact-missions-bonus-week',
}
TOPIC_RE = re.compile(r'\b(?:gta[\s\-]*(?:vi|6|online)|grand\s+theft\s+auto\s*(?:vi|6|online)|gta\+|vice\s+city|jason\s+(?:duval|and\s+lucia)|lucia\s+caminos)\b', re.I)
REJECT_RE = re.compile(r'\b(?:rumou?r(?:s|ed)?|leak(?:ed|s)?|datamine(?:d)?|unconfirmed|alleged|supposedly|insider|speculat(?:ion|e|es)|prediction|predicts|theory|theories|could|might|maybe|may\s+be|possibly|what\s+if|spoilers?|spoilerosi|indiscrezion[ei]|fuga\s+di\s+notizie|trapelat[oi]|ipotetic[oi]|svelat[oi]\s+da\s+un\s+insider|non\s+confermato|screenshot\s+rubat[oi]|mod\s+menu|hack(?:ed|s|ing)?|pirat[ae]|torrent|giveaway|gift\s+card|sponsored|#ad|offerta\s+amazon|black\s+friday)\b', re.I)
CLICK_RE = re.compile(r'(?:you\s+won.t\s+believe|sconvolgente|incredibile\s+segreto|nessuno\s+te\s+lo\s+dice|shock|gioc[a-z]*\s+gratis|buy\s+now|preorder\s+now)', re.I)
STRIP_TAGS = re.compile(r'<[^>]*>')
# Episodic walkthrough uploads remain available via the independent research
# feed and website, but raw "mission 8 chapter 1" titles are a weak X format.
# Concrete how-to, trophy and calibration video titles remain eligible.
GENERIC_VIDEO_EPISODE = re.compile(
    r'\b(?:mission(?:e)?\s*(?:n\.?|no\.?|number|#)?\s*\d+|'
    r'chapter\s*\d+|capitolo\s*\d+|episode\s*\d+|episodio\s*\d+|'
    r'(?:full|complete)\s+(?:walkthrough|playthrough)|'
    r'(?:walkthrough|gameplay)\s*(?:part|ep\.?|#)\s*\d+)\b', re.I)
VIDEO_HELPFUL = re.compile(
    r'\b(?:how\s+to|come\s+fare|guide\s+to|tutorial|'
    r'troph(?:y|ies)|trofeo|platinum|platino|'
    r'collectibles?|collezionabil[ie]|all\s+locations?|'
    r'gold\s+medals?|medagli[ae]\s+oro|'
    r'hdr|oled|glitch|duplication|'
    r'tips?\s+(?:and|&)\s+tricks?|fast\s+travel|'
    r'100\s*%|settings|impostazioni)\b', re.I)


def x_quality_gate(item: dict) -> tuple[bool, str]:
    """Filter headline-only X posts; do not certify unseen video content.

    The research issue and website retain original source leads even if the
    public X autopublisher skips a low-value episodic title.
    """
    if item.get("source") != "GTA Series Videos":
        return True, "editorial_source"
    title = clean(item.get("title", ""))
    if GENERIC_VIDEO_EPISODE.search(title) and not VIDEO_HELPFUL.search(title):
        return False, "episode_only"
    if not VIDEO_HELPFUL.search(title):
        return False, "no_actionable_topic"
    return True, "actionable_independent_video"


def clean(s: str) -> str:
    return re.sub(r'\s+', ' ', unescape(STRIP_TAGS.sub(' ', str(s)))).strip()

def canonical(url: str) -> str:
    u = urlsplit(str(url))
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.port not in (None, 443):
        raise ValueError('Untrusted article URL')
    host = u.hostname.lower().removeprefix('www.')
    path = re.sub('/+', '/', u.path).rstrip('/') or '/'
    params = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
              if k.lower() not in {'fbclid', 'gclid', 'mc_cid', 'mc_eid', 'ref', 'source'}
              and not k.lower().startswith('utm_')]
    return urlunsplit(('https', host, path, urlencode(params), ''))

def identity(url: str) -> str:
    return hashlib.sha256(canonical(url).encode()).hexdigest()[:24]

def similarity_key(title: str) -> str:
    title = unicodedata.normalize('NFKD', clean(title)).encode('ascii', 'ignore').decode().lower()
    title = re.sub(r'\b(?:gta|grand|theft|auto|vi|6|online|playstation|ps5|pro|review|recensione|news|video)\b', ' ', title)
    title = re.sub(r'[^a-z0-9 ]+', ' ', title)
    return ' '.join(w for w in title.split() if len(w) > 2)[:180]

def same_story(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    x = set(a.split())
    y = set(b.split())
    return len(x & y) >= 5 and len(x & y) / max(1, min(len(x), len(y))) >= 0.80

def published(s: str) -> datetime | None:
    if not s:
        return None
    try:
        dt = parsedate_to_datetime(s)
    except (TypeError, ValueError, IndexError):
        try:
            dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)

def weight_x(text: str) -> int:
    parts = re.split(r'(https?://\S+)', text)
    return sum(23 if p.startswith('https://') else sum(2 if ord(ch) > 0xFFFF else 1 for ch in p)
               for p in parts)

def topic(title: str) -> str | None:
    s = clean(title)
    if not (TOPIC_RE.search(s) or re.search(r'\bgta\+(?!\w)', s, re.I)):
        return None
    if REJECT_RE.search(s) or CLICK_RE.search(s) or priority(s) < 0:
        return None
    return 'GTAOnline' if re.search(
        r'(?:\b(?:gta\s*online|grand theft auto online)\b|\bgta\+(?!\w))', s, re.I
    ) else 'GTAVI'

def post_text(item: dict) -> str:
    """Italian-only headline; title, source, URL and hashtags as separate blocks."""
    category = topic(item['title'])
    if not category:
        raise ValueError('Topic or safety filter rejected')
    headline = italian_title(item['title'], item.get('language', 'en'))
    src = item['source']
    if src == 'PowerPyx':
        lead = '🏆 GTA VI | Guida PowerPyx'
    elif src == 'GTA Series Videos':
        lead = '🎥 GTA VI | Video community (non ufficiale)'
    elif re.search('review|recension', item['title'], re.I):
        lead = '📝 GTA VI | Recensione'
    elif re.search('guide|guida|trophy|trofeo|achiev|soluzion', item['title'], re.I):
        lead = '🧭 GTA VI | Guida' if category == 'GTAVI' else '🧭 GTA Online | Guida'
    elif category == 'GTAOnline':
        lead = '💰 GTA Online | Aggiornamento'
    else:
        lead = '📰 GTA VI | Novità'

    hashtags = '#GTAOnline' if category == 'GTAOnline' else '#GTAVI #GTA6'
    # The original URL is never shortened or lost; X weighs it as a link.
    suffix = f'\n\n🔗 Fonte: {src}\n{item["url"]}\n\n{hashtags}'
    prefix = lead + '\n\n'
    budget = 280 - weight_x(prefix + suffix)
    if budget < 35:
        raise ValueError('URL leaves too little space for Italian headline')
    truncated = headline
    while truncated and weight_x(truncated) > budget:
        truncated = truncated[:-1]
    if truncated != headline:
        truncated = truncated.rstrip(' -–:,') + '…'
        while truncated and weight_x(prefix + truncated + suffix) > 280:
            truncated = truncated[:-2] + '…'
    if len(truncated) < 12:
        raise ValueError('Headline too short after formatting')
    post = prefix + truncated + suffix
    if weight_x(post) > 280 or headline == item['title'] and item.get('language', 'en') == 'en':
        raise TranslationUnavailable('Italian text not available: no English fallback')
    return post

# Hand-curated, source-attributed launch guides. Facts come from PowerPyx
# pages dated 2026-11-18. The date range is an editorial publication window,
# NOT an invented precise time when PowerPyx published the guides.
POWERPYX_SPOTLIGHTS = [
    {
        'title': 'GTA VI: quattro luoghi per fare soldi subito',
        'url': 'https://insider-gaming.com/gta-6-early-game-locations-make-money/',
        'text': (
            '💰 GTA VI | SOLDI SUBITO\n\n'
            'Quattro luoghi da esplorare nel Capitolo 1 per trovare denaro e oggetti utili. '
            '⚠️ Posizioni con spoiler nella guida.\n\n'
            '🔗 Fonte: Insider Gaming\n'
            'https://insider-gaming.com/gta-6-early-game-locations-make-money/\n\n'
            '#GTA6 #GTAVI'
        ),
    },
    {
        'title': 'GTA VI: roadmap del platino PowerPyx',
        'url': 'https://www.powerpyx.com/gta-6-grand-theft-auto-vi-trophy-guide-roadmap/',
        'text': (
            '🏆 GTA VI | PLATINO: guida PowerPyx\n\n'
            '⏳ Circa 200 ore e 55 trofei offline, secondo PowerPyx.\n'
            '⚠️ Una meditazione del Capitolo 1 potrebbe essere mancabile!\n\n'
            '🔗 Guida completa:\n'
            'https://www.powerpyx.com/gta-6-grand-theft-auto-vi-trophy-guide-roadmap/\n\n'
            '#GTAVI #Platino'
        ),
    },
    {
        'title': 'GTA VI: 70 sfide su 80 per il completamento',
        'url': 'https://www.powerpyx.com/gta-6-all-challenges-guide/',
        'text': (
            '🎯 GTA VI | Sfide e 100%\n\n'
            '💡 Secondo PowerPyx bastano 70 sfide su 80 per la checklist del 100%. '
            'Puoi saltarne 10!\n\n'
            '📋 Guida alle sfide:\n'
            'https://www.powerpyx.com/gta-6-all-challenges-guide/\n\n'
            '#GTAVI #GTA6'
        ),
    },
    {
        'title': 'GTA VI: missioni, incarichi opzionali e salvataggi',
        'url': 'https://www.powerpyx.com/gta-6-full-walkthrough-all-missions/',
        'text': (
            '🗺️ GTA VI | Missioni e salvataggi\n\n'
            '⚠️ PowerPyx segnala missioni opzionali a tempo e assenza di replay '
            'delle missioni.\n'
            '💾 Meglio conservare salvataggi manuali!\n\n'
            '🔗 Guida alle missioni:\n'
            'https://www.powerpyx.com/gta-6-full-walkthrough-all-missions/\n\n'
            '#GTAVI #GTA6'
        ),
    },
    {
        'title': 'GTA VI: database di veicoli e collezionabili',
        'url': 'https://www.powerpyx.com/gta-6-collectible-guide-progress-database/',
        'text': (
            '🚗 GTA VI | Collezionabili e veicoli\n\n'
            '🔎 PowerPyx raccoglie veicoli, animali, armi e collezionabili '
            'nel database di gioco.\n'
            '💡 Per il 100% non serve trovare proprio tutto!\n\n'
            '🔗 Database e guida:\n'
            'https://www.powerpyx.com/gta-6-collectible-guide-progress-database/\n\n'
            '#GTAVI #GTA6'
        ),
    },
]


def editorial_day_slots(existing: dict, now: datetime) -> tuple[int,int]:
    """Local editorial slots; launch recovery has a separate five-post budget.

    Old launch posts remain permanently deduplicated, but do not stop all
    editorial coverage during the one-off global director recovery.
    """
    from editorial_director_v142 import RECOVERY_START, RECOVERY_END
    clock=now.astimezone(timezone.utc)
    if launch_active(clock):
        return launch_day_count(existing,clock),LAUNCH_DAILY_CAP
    if RECOVERY_START<=clock<RECOVERY_END:
        recent=[published(e.get('reserved_utc')) for e in existing.values()
                if e.get('reserved_utc')]
        return sum(stamp is not None and RECOVERY_START<=stamp<=clock for stamp in recent),5
    today=publishing_local(now).date()
    return sum(1 for e in existing.values()
               if (stamp := published(e.get('reserved_utc'))) is not None
               and publishing_local(stamp).date()==today),MAX_POSTS_DAY


def powerpyx_spotlight(state: dict, now: datetime) -> dict | None:
    """One original Italian guide spotlight, spaced across launch days.

    Uses the SAME ledger and URL identity as RSS news so a guide never posts
    twice even when the PowerPyx RSS also contains that guide.
    """
    now = now.astimezone(timezone.utc)
    if not (datetime(2026, 11, 18, tzinfo=timezone.utc)
            <= now < datetime(2026, 11, 24, tzinfo=timezone.utc)):
        return None
    entries = state['entries']
    stamped = [published(e.get('reserved_utc')) for e in entries.values()
               if e.get('reserved_utc')]
    stamped = [dt for dt in stamped if dt is not None]
    taken,limit=editorial_day_slots(entries,now)
    if taken>=limit:
        return None
    if stamped and now - max(stamped) < timedelta(minutes=MIN_SPACING_MIN):
        return None
    older = [published(e.get('reserved_utc')) for e in entries.values()
             if e.get('source') == 'PowerPyx' and e.get('reserved_utc')]
    older = [dt for dt in older if dt is not None]
    if older and now - max(older) < timedelta(minutes=120):
        return None
    for item in POWERPYX_SPOTLIGHTS:
        url = canonical(item['url'])
        host = urlsplit(url).hostname
        if host not in ('powerpyx.com', 'insider-gaming.com'):
            raise ValueError('Curated spotlight uses unapproved source')
        key = identity(url)
        sig = similarity_key(item['title'])
        if key in entries:
            continue
        if weight_x(item['text']) > 280:
            raise ValueError('PowerPyx post exceeds X character budget')
        source = 'Insider Gaming' if host == 'insider-gaming.com' else 'PowerPyx'
        if item['text'].count('\n\n') < 2 or source not in item['text']:
            raise ValueError('Curated source attribution or editorial layout missing')
        return {'key': key, 'sig': sig, 'url': url, 'title': item['title'],
                'text': item['text'], 'source': source}
    return None


FEED_ACCEPT = 'application/rss+xml, application/atom+xml, application/xml, text/xml'
ATOM_ROOT = '{http://www.w3.org/2005/Atom}feed'


def feed_payload_kind(data):
    """Bounded, sanitized shape diagnostics; never expose response text."""
    prefix = data[:4096].lstrip(b'\xef\xbb\xbf \t\r\n')
    if not prefix:
        return 'empty'
    prefix = re.sub(rb'^<\?xml[^>]*>\s*', b'', prefix, count=1)
    if re.match(rb'<(?:rss|feed)(?:\s|>)', prefix):
        return 'rss_or_atom'
    if re.match(rb'(?:<!doctype\s+html\b|<html(?:\s|>)|<head(?:\s|>)|<body(?:\s|>))',
                prefix, flags=re.I):
        return 'html'
    return 'other'


def validate_feed_root(root):
    """Only supported public RSS/Atom envelopes count as a successful read."""
    if root.tag == 'rss' and root.find('channel') is not None:
        return 'rss'
    if root.tag == ATOM_ROOT:
        return 'atom'
    raise ValueError('Unexpected RSS/Atom root or missing RSS channel')


def validate_feed_url(value, domains):
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or parsed.hostname not in domains or
            parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError('Unexpected feed URL or redirect')


def parse_feed(data: bytes, src: dict):
    if len(data) > MAX_DOWNLOAD:
        raise ValueError('Feed too large')
    root = ET.fromstring(data)
    rows = []
    kind = validate_feed_root(root)
    if kind == 'rss':
        for node in root.findall('.//item'):
            title = node.findtext('title') or ''
            url = node.findtext('link') or ''
            stamp = node.findtext('pubDate') or node.findtext('{http://purl.org/dc/elements/1.1/}date')
            rows.append((title, url, stamp))
    else:
        atom = '{http://www.w3.org/2005/Atom}'
        for node in root.findall(f'.//{atom}entry'):
            title = node.findtext(atom + 'title') or ''
            links = node.findall(atom + 'link')
            link = next((n.get('href', '') for n in links if n.get('rel', 'alternate') == 'alternate'), '')
            if not link:
                link = next((n.get('href', '') for n in links
                             if not n.get('rel') or n.get('rel') == 'alternate'), '')
            stamp = node.findtext(atom + 'published') or node.findtext(atom + 'updated')
            rows.append((title, link, stamp))
    for title, url, stamp in rows:
        if not topic(title) or not published(stamp):
            continue
        try:
            canon = canonical(url)
        except (ValueError, TypeError):
            continue
        if urlsplit(canon).hostname not in src['domains']:
            continue
        yield {'source': src['name'], 'title': clean(title), 'url': canon,
               'published': published(stamp).isoformat(), 'language': src.get('language', '')}

def load_sources(path: Path = CONFIG) -> list[dict]:
    settings = json.loads(path.read_text('utf-8'))
    if settings.get('schema') != 'v13.7' or not isinstance(settings.get('sources'), list):
        raise ValueError('Unsupported sources schema')
    for src in settings['sources']:
        validate_feed_url(src['feed'], src['feed_domains'])
    return settings['sources']

def _read_feed_once(http, src):
    validate_feed_url(src['feed'], src['feed_domains'])
    response = http.get(src['feed'], timeout=(5, 12),
                        headers={'User-Agent': 'FederikoGTANewsCenter/1.0 (RSS reader)',
                                 'Accept': FEED_ACCEPT},
                        stream=True, allow_redirects=True)
    try:
        response.raise_for_status()
        if response.url:
            validate_feed_url(response.url, src['feed_domains'])
        data = bytearray()
        for block in response.iter_content(65536):
            data.extend(block)
            if len(data) > MAX_DOWNLOAD:
                raise ValueError('Excessive feed size')
    finally:
        response.close()
    return bytes(data)


def _looks_like_feed(data):
    return feed_payload_kind(data) == 'rss_or_atom'


def read_feeds(sources: list[dict], *, session=None) -> tuple[list[dict], list[str]]:
    http = session or requests.Session()
    items = []
    errors = []
    for src in sources:
        if not src.get('enabled', True):
            continue
        data = None
        try:
            data = _read_feed_once(http, src)
            try:
                found = list(parse_feed(data, src))
            except ET.ParseError:
                if src['name'] != 'PowerPyx' or not _looks_like_feed(data):
                    raise
                print('FEED_RETRY PowerPyx: malformed RSS/Atom; one retry')
                time.sleep(1)
                data = _read_feed_once(http, src)
                found = list(parse_feed(data, src))
            items.extend(found)
            print(f"FEED_OK {src['name']}: qualifying={len(found)} bytes={len(data)}")
        except (requests.RequestException, ET.ParseError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"{src['name']}: {type(exc).__name__}")
            print(f"FEED_ERROR {src['name']}: {type(exc).__name__}")
            if data is not None and isinstance(exc, (ET.ParseError, ValueError)):
                print(f"FEED_RESPONSE_KIND {src['name']}: {feed_payload_kind(data)} bytes={len(data)}")
    return items, errors

def load_state(path: Path | None = None) -> dict:
    path = path or STATE
    if not path.exists():
        return {'schema': 'v13.7', 'entries': {}, 'signatures': {}, 'run_history': []}
    state = json.loads(path.read_text('utf-8'))
    if state.get('schema') != 'v13.7' or not isinstance(state.get('entries'), dict) or not isinstance(state.get('signatures'), dict):
        raise ValueError('Refuse unknown ledger schema')
    return state

def save_state(state: dict, path: Path | None = None):
    path = path or STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    temp.replace(path)

def select(items: list[dict], state: dict, now: datetime, *, max_posts=RUN_LIMIT,
           candidate_pool=False) -> list[dict]:
    if now.tzinfo is None:
        raise ValueError('UTC time required')
    now = now.astimezone(timezone.utc)
    existing = state['entries']
    sigs = state['signatures']
    entries_today,day_limit=editorial_day_slots(existing,now)
    if entries_today >= day_limit:
        return []
    latest = max((published(e['reserved_utc']) for e in existing.values()
                  if e.get('reserved_utc')), default=None)
    if latest and (now - latest) < timedelta(minutes=MIN_SPACING_MIN):
        return []
    out, keys, new_sigs = [], set(), []
    old_sigs = list(sigs)
    # Surface important PS5, platinum and primary-source news before parodies.
    for item in sorted(items, key=lambda x: (priority(x['title'], x.get('source','')), x['published']), reverse=True):
        stamp = published(item['published'])
        if stamp is None or stamp > now + timedelta(minutes=3) or now - stamp > timedelta(minutes=MAX_AGE_MIN):
            continue
        if canonical(item['url']) in {canonical(u) for u in BRIDGE_URLS}:
            continue
        key = identity(item['url'])
        sig = similarity_key(item['title'])
        if key in existing or key in keys or (sig and any(same_story(sig, other) for other in old_sigs + new_sigs)):
            continue
        if not topic(item['title']):
            continue
        passes, reason = x_quality_gate(item)
        if not passes:
            print("EDITORIAL_SKIP_LOW_VALUE", item.get("source", ""), reason)
            continue
        try:
            item = {**item, 'text': post_text(item), 'key': key, 'sig': sig}
        except ValueError:
            continue
        out.append(item)
        keys.add(key)
        new_sigs.append(sig)
        # An image fallback inspects candidates, not post slots. The director
        # still permits at most one ordinary reservation and enforces the
        # global rolling 24-hour caps after the media gate.
        cap = max_posts if candidate_pool else min(max_posts, day_limit - entries_today)
        if len(out) >= cap:
            break
    return out


def selection_diagnostics(items: list[dict], state: dict, now: datetime) -> dict:
    """Read-only funnel: explain zero reservations without bypassing safety gates.

    Counts are aggregate only; no feed headlines, user handles or API data.
    This diagnostic must not mutate the deduplication state.
    """
    clock = now.astimezone(timezone.utc)
    seen = state['entries']
    signatures = list(state['signatures'])
    counts = {'feed_items': len(items), 'fresh': 0, 'not_reserved': 0,
              'on_topic': 0, 'quality_eligible': 0}
    for item in items:
        stamp = published(item.get('published'))
        if (stamp is None or stamp > clock + timedelta(minutes=3)
                or clock - stamp > timedelta(minutes=MAX_AGE_MIN)):
            continue
        counts['fresh'] += 1
        try:
            url = canonical(item['url'])
            if url in BRIDGE_URLS:
                continue
            key = identity(item['url'])
            signature = similarity_key(item['title'])
        except (KeyError, ValueError, TypeError):
            continue
        if (key in seen or
                (signature and any(same_story(signature, previous) for previous in signatures))):
            continue
        counts['not_reserved'] += 1
        if not topic(item['title']):
            continue
        counts['on_topic'] += 1
        if not x_quality_gate(item)[0]:
            continue
        counts['quality_eligible'] += 1
    return counts


def preview():
    items, errors = read_feeds(load_sources())
    state = load_state()
    now = datetime.now(timezone.utc)
    spotlight = powerpyx_spotlight(state, now)
    selected = [spotlight] if spotlight else select(items, state, now, max_posts=5)
    print("TROPHY_SERIES configured=55, photo-posts wait for live GitHub Pages")
    from quick_tips_v146 import candidate as quick_tip_candidate
    tip_preview=quick_tip_candidate(state,now)
    print("QUICK_TIPS preview=",tip_preview["tip_id"] if tip_preview else "none",
          "format=two-post-thread; attribution in reply")
    print('FEEDS total_relevant=', len(items), 'errors=', errors, 'selected=', len(selected))
    for item in selected:
        print('PREVIEW', item['source'], item['published'], item['url'])
        print(item['text'])
    print('PREVIEW ONLY: no Buffer calls, no Git writes')

def media_thread_preflight(item:dict) -> bool:
    """Match Buffer photo-thread checks BEFORE reserving or marking attempted.

    A first-party social card is attached *after* launch_double(), so even
    a media-less 280-character thread can become ineligible for a photo.
    Fail closed rather than dropping a photo or mutating Buffer on a bad post.
    """
    from editorial_seo_v135 import x_weight
    thread=item.get('thread')
    if thread is None:
        text=item.get('text')
        if not isinstance(text,str) or not text.strip():
            return False
        return x_weight(text)<=(235 if item.get('media_url') else 280)
    if not isinstance(thread,list) or len(thread)!=2:
        return False
    if any(not isinstance(part,str) or not part.strip() or x_weight(part)>280 for part in thread):
        return False
    return not (item.get('media_url') and x_weight(thread[0])>235)


def quick_tip_media_available(item: dict) -> bool:
    """Probe the exact image that the final media gate would attach to Buffer.

    Once our canonical Italian guide is live, prepare() chooses its dedicated
    first-party article card instead of the optional Rockstar hotlink.
    Validate that same card here. If no owned guide is live, validate the
    official image as before; both paths fail closed on missing bytes.
    """
    from social_media_gate_v2 import cover_for, probe_image
    selected = cover_for(item.get('url')) or item.get('media_url')
    return probe_image(selected)


def reserve():
    run = os.getenv('GITHUB_RUN_ID')
    if not run:
        raise RuntimeError('GitHub Actions run ID required')
    state = load_state()
    items, errors = read_feeds(load_sources())
    now = datetime.now(timezone.utc)
    from game_photo_policy_v1 import active as photo_policy_active, prepare_photo, scan_kind
    photo_required = photo_policy_active(now)
    if launch_active(now) and not launch_in_hours(now):
        print('LAUNCH_HOLD outside 08:00-21:00 Europe/Rome; no reservation')
        return
    # Local reservation cooldown applies to ALL editorial types, including
    # quick tips, trophy posts and old PowerPyx spotlights. Never let a
    # second reserve in the same Actions run queue a different story.
    prior = [published(e.get('reserved_utc')) for e in state['entries'].values()
             if e.get('reserved_utc')]
    prior = [dt for dt in prior if dt is not None]
    local_hold = bool(prior and now - max(prior) < timedelta(minutes=MIN_SPACING_MIN))
    spotlight = None if local_hold else powerpyx_spotlight(state, now)
    ok, why = ((False, 'editorial_local_spacing') if local_hold else
               director_allowed(now,kind='launch_thread' if launch_active(now) else None))
    if ok and editorial_day_slots(state['entries'],now)[0]>=editorial_day_slots(state['entries'],now)[1]:
        ok, why = False, 'editorial_daily_capacity'
    if not ok:
        print("DIRECTOR_HOLD", why)
        selected = []
    else:
        # Curated short tips publish as a genuine Buffer X thread: image and
        # actionable steps first, attribution/source link as its first reply.
        # Never extract instructions from arbitrary feed summaries.
        from quick_tips_v146 import candidate as quick_tip_candidate
        quick_tip = quick_tip_candidate(state, now)
        if quick_tip and photo_required and not prepare_photo(quick_tip):
            print('QUICK_TIP_HOLD_NO_REVIEWED_GAME_PHOTO')
            quick_tip = None
        if quick_tip and not quick_tip_media_available(quick_tip):
            print("QUICK_TIP_HOLD_IMAGE_UNAVAILABLE", quick_tip["tip_id"])
            quick_tip = None
        # One factual, original guide-page excerpt daily provides ongoing
        # value from our existing site without resending headline-only news.
        # The exact canonical URL must return 200; unavailable pages stay on hold.
        # One *original question on our own X account* can replace a normal
        # post during the launch, never append an extra publication. It is
        # paired with a relevant, publicly verified Italian guide in reply.
        # Growth questions are original posts on our X account only.
        # Readers use X/YouTube; GitHub Issues never trigger a social post.
        growth_question = None
        if launch_active(now):
            from growth_conversion_v1 import candidate as growth_candidate
            growth_question = growth_candidate(state, now)
            if growth_question and photo_required and not prepare_photo(growth_question):
                print('GROWTH_HOLD_NO_REVIEWED_GAME_PHOTO')
                growth_question = None
        owned_guide = None
        if not (quick_tip or growth_question):
            from site_evergreen_posts_v1 import candidate as owned_candidate
            owned_guide = (owned_candidate(state, now, photo_checker=scan_kind, include_feed=True)
                           if photo_required else owned_candidate(state, now))
        # Search-indexable Italian trophy pages must exist BEFORE linking them.
        # This is optional: unavailable Pages never blocks breaking news.
        trophy_item = None
        if not (quick_tip or growth_question or owned_guide):
            from trophy_posts_v142 import candidate, landing_live
            draft_trophy = candidate(state, now)
            if draft_trophy and landing_live():
                trophy_item = draft_trophy
        # Prefer original site articles with their own unique preview over
        # source spotlights without a verifiable media asset.
        preferred = (growth_question or quick_tip or owned_guide or trophy_item or spotlight)
        selected = [preferred] if preferred else []
        # Reviewed owned-article rotation is one ordinary candidate, not an
        # extra slot or a bypass of the global director. Existing fresh tips
        # and first publications keep their original preference.
        if not launch_active(now):
            from site_article_rotation_v1 import candidate as rotation_candidate
            try:
                rotation=rotation_candidate(state,now,live_checker=lambda url: bool(scan_kind(url))) if photo_required else rotation_candidate(state,now)
            except (OSError,ValueError,TypeError,KeyError) as exc:
                print("ARTICLE_ROTATION_HOLD",type(exc).__name__)
                rotation=None
            if rotation and rotation["key"] not in {x["key"] for x in selected}:
                selected.append(rotation)
        # A reused or unavailable image must not waste the entire scanning cycle:
        # inspect fresh, individually deduplicated backup stories instead.
        # Every backup MUST pass the same media and factual title gates.
        backup = select(items, state, now, max_posts=MAX_MEDIA_CANDIDATES,
                        candidate_pool=True)
        selected.extend(item for item in backup
                        if item['key'] not in {x['key'] for x in selected})
        from social_media_gate_v2 import prepare as prepare_media
        converted=[]
        source_link_fallback=None
        for item in selected:
            if source_link_fallback is None:
                from per_item_media_policy_v1 import source_link_candidate
                source_link_fallback=source_link_candidate(item)
            try:
                ready=launch_double(item) if launch_active(now) and not photo_required else item
                if photo_required:
                    if not scan_kind(ready.get('url')):
                        print('MEDIA_HOLD_NO_REVIEWED_GAME_PHOTO',str(item.get('source','unknown')))
                        continue
                    ready = prepare_photo(ready)
                    if ready is None:
                        print('MEDIA_HOLD_PHOTO_COPY_OVER_BUDGET')
                        continue
                    image_backed=(prepare_media(ready,state,now=now) if "rotation_variant" in ready
                                  else prepare_media(ready,state))
                    if image_backed is None:
                        print('MEDIA_HOLD_MISSING_OR_REUSED',str(item.get('source','unknown')),
                              str(item.get('url',''))[:100])
                        continue
                    from game_photo_policy_v1 import probe_cover_digest
                    if not probe_cover_digest(image_backed['media_url'], image_backed.get('cover_sha256')):
                        print('MEDIA_HOLD_GAME_PHOTO_DIGEST_MISMATCH_OR_UNAVAILABLE')
                        continue
                    image_backed['media_mode']='approved_photo'
                else:
                    image_backed=(prepare_media(ready,state,now=now) if "rotation_variant" in ready
                                  else prepare_media(ready,state))
                    if image_backed is None:
                        print('MEDIA_HOLD_MISSING_OR_REUSED',str(item.get('source','unknown')),
                              str(item.get('url',''))[:100])
                        continue
                    image_backed['media_mode']='verified_image'
                if not media_thread_preflight(image_backed):
                    print('MEDIA_HOLD_COPY_OVER_BUDGET',str(item.get('source','unknown')),
                          str(item.get('url',''))[:100])
                    continue
                converted.append(image_backed)
                break  # one editorial reservation, never a batch
            except (KeyError,ValueError,TypeError) as exc:
                print('THREAD_HOLD_UNVERIFIED',item.get('source','unknown'),type(exc).__name__)
        # Photos are reviewed per exact article and destination. If this
        # candidate pool has none, use one pre-registered official video link;
        # it stays on its publisher platform and is never attached as an image.
        if not converted and source_link_fallback and media_thread_preflight(source_link_fallback):
            converted.append(source_link_fallback)
            print('MEDIA_FALLBACK_SOURCE_LINK_ONLY: verified article link, no image attachment')
        if not converted:
            from per_item_media_policy_v1 import launch_video_candidate
            fallback=launch_video_candidate(state,now,launch=launch_active(now))
            if fallback and media_thread_preflight(fallback):
                converted.append(fallback)
                print('MEDIA_FALLBACK_OFFICIAL_VIDEO_LINK: exact source, no image attachment')
        # The item must carry an individually approved photo or exact official video link.
        selected=converted[:1] if launch_active(now) else converted[:RUN_LIMIT]
        if selected and publishing_local(now).date()>=QUALITY_START:
            # The director counts a parent post and separately checks X message units.
            msg=selected[0].get("thread")
            units=len(msg) if isinstance(msg,list) and len(msg)>1 else 1
            permitted,reason=director_allowed(now,kind="ordinary",units=units)
            if not permitted:
                print("DIRECTOR_HOLD_AFTER_FORMAT",reason,"X_messages",units)
                selected=[]
    for item in selected:
        state['entries'][item['key']] = {
            'status': 'reserved', 'run_id': run, 'reserved_utc': now.isoformat(),
            'url': item['url'], 'source': item['source'], 'title': item['title'], 'text': item['text'],
            'media_url': item.get('media_url'), 'media_mode': item.get('media_mode'),
            'trophy_number': item.get('trophy_number'),
            'thread': item.get('thread'), 'tip_id': item.get('tip_id')
        }
        if item.get('photo_kind'):
            state['entries'][item['key']]['photo_kind'] = item['photo_kind']
            state['entries'][item['key']]['cover_sha256'] = item.get('cover_sha256')
        if item.get('feed_summary'):
            for field in ('feed_summary','feed_kind','feed_digest'):
                state['entries'][item['key']][field]=item[field]
        if "rotation_variant" in item:
            for field in ("key","rotation_variant","rotation_revision","rotation_reason"):
                state['entries'][item['key']][field]=item[field]
        if item['sig']:
            state['signatures'][item['sig']] = item['key']
    if selected:
        state['run_history'].append({'run': run, 'at': now.isoformat(), 'feeds_relevant': len(items),
                                     'reserved': len(selected), 'errors': errors})
        state['run_history'] = state['run_history'][-75:]
        save_state(state)
    print(f"RESERVE count={len(selected)} relevant={len(items)} feed_errors={errors}")
    if not selected:
        print('EDITORIAL_SELECTION_FUNNEL', json.dumps(selection_diagnostics(items, state, now), sort_keys=True))
        print('NO POST: freshness, safety, duplicate, daily or spacing rules')

def preflight():
    from buffer_publisher import BufferClient
    client = BufferClient(expected_username='xFederiko11')
    client.verify_destination()
    print('PREFLIGHT: expected X account verified; no posts created')

def deliver():
    from buffer_publisher import BufferClient, BufferAPIError, BufferPending
    run = os.getenv('GITHUB_RUN_ID')
    if not run:
        raise RuntimeError('GitHub Actions run ID required')
    state = load_state()
    mine = [entry for entry in state['entries'].values()
            if entry.get('status') == 'reserved' and entry.get('run_id') == run]
    if not mine:
        print('DELIVERY_NOT_ATTEMPTED: no unique reservation')
        return
    if len(mine) > RUN_LIMIT:
        raise RuntimeError('Too many reservations')
    # The Buffer reservation is durable. A delayed job may cross the quiet
    # hours; do not deliver it after 23:00 or before 07:00.
    if publishing_local(datetime.now(timezone.utc)).date()>=QUALITY_START and not ordinary_hours(datetime.now(timezone.utc)):
        print('BUFFER_HOLD_OUTSIDE_07_23: retained, no Buffer mutation')
        return
    client = BufferClient(expected_username='xFederiko11')
    client.verify_destination()
    from social_media_gate_v2 import probe_image
    for entry in mine:
        clock=datetime.now(timezone.utc)
        from site_article_rotation_v1 import SOURCE as ROTATION_SOURCE, delivery_authorized
        if entry.get("source")==ROTATION_SOURCE and not delivery_authorized(entry,state,clock):
            entry["status"]="held_rotation_recheck"
            save_state(state)
            print("BUFFER_ROTATION_HOLD",str(entry.get("url",""))[:100])
            continue
        # Revalidate the item-specific media mode before any Buffer mutation.
        from game_photo_policy_v1 import active as photo_policy_active, verify_delivery
        media_mode=entry.get('media_mode')
        if media_mode == 'official_video_link':
            from per_item_media_policy_v1 import verify_link_only_entry
            if not verify_link_only_entry(entry):
                entry['status']='held_invalid_official_link'
                save_state(state)
                print('BUFFER_OFFICIAL_LINK_HOLD: source or link changed')
                continue
        elif photo_policy_active(clock):
            if media_mode != 'approved_photo' or not verify_delivery(entry):
                entry['status']='held_missing_reviewed_game_photo'
                save_state(state)
                print('BUFFER_GAME_PHOTO_HOLD: no matching reviewed photo for this item')
                continue
        elif (media_mode != 'verified_image' or not entry.get('media_url')
              or not probe_image(entry['media_url'])):
            entry['status']='held_missing_verified_image'
            save_state(state)
            print('BUFFER_IMAGE_HOLD',str(entry.get('url',''))[:100])
            continue
        if launch_active(clock) and (not launch_in_hours(clock) or
                                     not isinstance(entry.get('thread'),list) or
                                     len(entry['thread'])!=2):
            entry['status']='held_launch_format_or_window'
            save_state(state)
            print('LAUNCH_DELIVERY_HOLD: outside hours or not exactly two messages')
            continue
        # A second preflight catches old reserved jobs and code changes.
        # Check before marking attempted: Buffer has NOT been mutated yet.
        if not media_thread_preflight(entry):
            entry['status']='held_invalid_photo_text_budget'
            save_state(state)
            print('BUFFER_COPY_PRECHECK_HOLD',str(entry.get('url',''))[:100])
            continue
        # No retry after attempted mutation: avoid duplicate Buffer posts.
        entry['status'] = 'attempted'
        entry['attempted_utc'] = datetime.now(timezone.utc).isoformat()
        save_state(state)
        try:
            if entry.get('thread'):
                # An atomic Buffer thread, not two unrelated scheduled posts.
                # One createPost mutation with both items; no retries on timeout.
                result = client.publish_thread(entry['thread'], media_url=entry['media_url'])
            else:
                result = client.publish(entry['text'], media_url=entry['media_url'])
        except BufferPending as exc:
            entry['status'] = 'accepted_pending'
            entry['buffer_id'] = exc.post_id
            print('BUFFER_PENDING', exc.post_id)
        except BufferAPIError as exc:
            entry['status'] = 'uncertain' if exc.outcome_unknown else 'rejected'
            entry['buffer_id'] = exc.post_id
            print('BUFFER_ERROR', entry['status'], type(exc).__name__)
        else:
            entry['status'] = 'sent'
            entry['buffer_id'] = result
            print('BUFFER_SENT', result)
        finally:
            entry['completed_utc'] = datetime.now(timezone.utc).isoformat()
            save_state(state)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['preview', 'preflight', 'reserve', 'deliver'], required=True)
    args = parser.parse_args()
    {'preview': preview, 'preflight': preflight, 'reserve': reserve, 'deliver': deliver}[args.mode]()

if __name__ == '__main__':
    main()
