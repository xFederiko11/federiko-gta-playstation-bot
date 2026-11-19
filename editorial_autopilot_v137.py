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
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import xml.etree.ElementTree as ET
import requests
from editorial_language_it import italian_title, TranslationUnavailable
from editorial_director_v142 import priority, allowed as director_allowed

STATE = Path('.state/editorial-autopilot-v137.json')
CONFIG = Path('editorial-autopilot-v137-sources.json')
MAX_DOWNLOAD = 1_800_000
MAX_AGE_MIN = 720  # catch up on timely launch-day coverage, not only latest 3 hours
MAX_POSTS_DAY = 5  # 1 owned guide + up to 2 trophies + selective news; leave capacity for official monitor
MIN_SPACING_MIN = 45  # avoid back-to-back generic headline posts
RUN_LIMIT = 1
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
    if sum(1 for dt in stamped if dt.date() == now.date()) >= MAX_POSTS_DAY:
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
        if urlsplit(url).hostname != 'powerpyx.com':
            raise ValueError('PowerPyx spotlight uses non-PowerPyx URL')
        key = identity(url)
        sig = similarity_key(item['title'])
        if key in entries:
            continue
        if weight_x(item['text']) > 280:
            raise ValueError('PowerPyx post exceeds X character budget')
        if item['text'].count('\n\n') < 2 or 'PowerPyx' not in item['text']:
            raise ValueError('PowerPyx attribution or editorial layout missing')
        return {'key': key, 'sig': sig, 'url': url, 'title': item['title'],
                'text': item['text'], 'source': 'PowerPyx'}
    return None


def parse_feed(data: bytes, src: dict):
    if len(data) > MAX_DOWNLOAD:
        raise ValueError('Feed too large')
    root = ET.fromstring(data)
    rows = []
    if root.tag.lower().endswith('rss') or root.tag.lower() == 'rdf:rdf':
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
        u = urlsplit(src['feed'])
        if u.scheme != 'https' or u.hostname not in src['feed_domains'] or u.username or u.password:
            raise ValueError('Invalid feed domain')
    return settings['sources']

def read_feeds(sources: list[dict], *, session=None) -> tuple[list[dict], list[str]]:
    http = session or requests.Session()
    items = []
    errors = []
    for src in sources:
        if not src.get('enabled', True):
            continue
        try:
            response = http.get(src['feed'], timeout=(5, 12),
                                headers={'User-Agent': 'FederikoGTANewsCenter/1.0 (RSS reader)'},
                                stream=True, allow_redirects=True)
            try:
                response.raise_for_status()
                if response.url and urlsplit(response.url).hostname not in src['feed_domains']:
                    raise ValueError('Unexpected feed redirect')
                data = bytearray()
                for block in response.iter_content(65536):
                    data.extend(block)
                    if len(data) > MAX_DOWNLOAD:
                        raise ValueError('Excessive feed size')
            finally:
                response.close()
            found = list(parse_feed(bytes(data), src))
            items.extend(found)
            print(f"FEED_OK {src['name']}: qualifying={len(found)} bytes={len(data)}")
        except (requests.RequestException, ET.ParseError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"{src['name']}: {type(exc).__name__}")
            print(f"FEED_ERROR {src['name']}: {type(exc).__name__}")
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

def select(items: list[dict], state: dict, now: datetime, *, max_posts=RUN_LIMIT) -> list[dict]:
    if now.tzinfo is None:
        raise ValueError('UTC time required')
    now = now.astimezone(timezone.utc)
    existing = state['entries']
    sigs = state['signatures']
    entries_today = sum(1 for e in existing.values()
                        if e.get('reserved_utc', '')[:10] == now.date().isoformat())
    if entries_today >= MAX_POSTS_DAY:
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
        if len(out) >= min(max_posts, MAX_POSTS_DAY - entries_today):
            break
    return out

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

def reserve():
    run = os.getenv('GITHUB_RUN_ID')
    if not run:
        raise RuntimeError('GitHub Actions run ID required')
    state = load_state()
    items, errors = read_feeds(load_sources())
    now = datetime.now(timezone.utc)
    # Local reservation cooldown applies to ALL editorial types, including
    # quick tips, trophy posts and old PowerPyx spotlights. Never let a
    # second reserve in the same Actions run queue a different story.
    prior = [published(e.get('reserved_utc')) for e in state['entries'].values()
             if e.get('reserved_utc')]
    prior = [dt for dt in prior if dt is not None]
    local_hold = bool(prior and now - max(prior) < timedelta(minutes=MIN_SPACING_MIN))
    spotlight = None if local_hold else powerpyx_spotlight(state, now)
    ok, why = ((False, 'editorial_local_spacing') if local_hold else director_allowed(now))
    if not ok:
        print("DIRECTOR_HOLD", why)
        selected = []
    else:
        # Curated short tips publish as a genuine Buffer X thread: image and
        # actionable steps first, attribution/source link as its first reply.
        # Never extract instructions from arbitrary feed summaries.
        from quick_tips_v146 import candidate as quick_tip_candidate
        from gta6_special_campaign_v139 import probe_image
        quick_tip = quick_tip_candidate(state, now)
        if quick_tip and not probe_image(quick_tip["media_url"]):
            print("QUICK_TIP_HOLD_IMAGE_UNAVAILABLE", quick_tip["tip_id"])
            quick_tip = None
        # One factual, original guide-page excerpt daily provides ongoing
        # value from our existing site without resending headline-only news.
        # The exact canonical URL must return 200; unavailable pages stay on hold.
        owned_guide = None
        if not (spotlight or quick_tip):
            from site_evergreen_posts_v1 import candidate as owned_candidate
            owned_guide = owned_candidate(state, now)
        # Search-indexable Italian trophy pages must exist BEFORE linking them.
        # This is optional: unavailable Pages never blocks breaking news.
        trophy_item = None
        if not (spotlight or quick_tip or owned_guide):
            from trophy_posts_v142 import candidate, landing_live
            draft_trophy = candidate(state, now)
            if draft_trophy and landing_live():
                trophy_item = draft_trophy
        selected = ([quick_tip] if quick_tip else [spotlight] if spotlight
                    else [owned_guide] if owned_guide
                    else [trophy_item] if trophy_item else select(items, state, now))
    for item in selected:
        state['entries'][item['key']] = {
            'status': 'reserved', 'run_id': run, 'reserved_utc': now.isoformat(),
            'url': item['url'], 'source': item['source'], 'title': item['title'], 'text': item['text'],
            'media_url': item.get('media_url'), 'trophy_number': item.get('trophy_number'),
            'thread': item.get('thread'), 'tip_id': item.get('tip_id')
        }
        if item['sig']:
            state['signatures'][item['sig']] = item['key']
    if selected:
        state['run_history'].append({'run': run, 'at': now.isoformat(), 'feeds_relevant': len(items),
                                     'reserved': len(selected), 'errors': errors})
        state['run_history'] = state['run_history'][-75:]
        save_state(state)
    print(f"RESERVE count={len(selected)} relevant={len(items)} feed_errors={errors}")
    if not selected:
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
    client = BufferClient(expected_username='xFederiko11')
    client.verify_destination()
    for entry in mine:
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
                result = (client.publish(entry['text'], media_url=entry['media_url'])
                          if entry.get('media_url') else client.publish(entry['text']))
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
