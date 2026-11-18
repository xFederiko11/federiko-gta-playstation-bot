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

STATE = Path('.state/editorial-autopilot-v137.json')
CONFIG = Path('editorial-autopilot-v137-sources.json')
MAX_DOWNLOAD = 1_800_000
MAX_AGE_MIN = 720  # catch up on timely launch-day coverage, not only latest 3 hours
MAX_POSTS_DAY = 16
MIN_SPACING_MIN = 12
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
    if REJECT_RE.search(s) or CLICK_RE.search(s):
        return None
    return 'GTAOnline' if re.search(
        r'(?:\b(?:gta\s*online|grand theft auto online)\b|\bgta\+(?!\w))', s, re.I
    ) else 'GTAVI'

def post_text(item: dict) -> str:
    category = topic(item['title'])
    if not category:
        raise ValueError('Topic or safety filter rejected')
    title = item['title']
    src = item['source']
    if re.search('review|recension', title, re.I):
        lead = f'📝 GTA VI | Recensione di {src}: '
    elif re.search('guide|guida|trophy|trofeo|achiev|soluzion', title, re.I):
        lead = f'🧭 {"GTA Online" if category=="GTAOnline" else "GTA VI"} | Guida di {src}: '
    elif category == 'GTAOnline':
        lead = f'💰 GTA Online | {src} segnala: '
    else:
        lead = f'📰 GTA VI | {src} pubblica: '
    suffix = '\n#GTAOnline' if category == 'GTAOnline' else '\n#GTAVI #GTA6'
    url = item['url']
    source_line = '\nFonte: ' + url
    budget = 280 - weight_x(lead + suffix + source_line)
    if budget < 35:
        raise ValueError('Article URL leaves too little content')
    headline = clean(title)
    while headline and weight_x(headline) > budget:
        headline = headline[:-1]
    if headline != clean(title):
        headline = headline.rstrip(' -–:,') + '…'
        while headline and weight_x(lead + headline + suffix + source_line) > 280:
            headline = headline[:-2] + '…'
    result = lead + headline + suffix + source_line
    assert weight_x(result) <= 280
    return result

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
               'published': published(stamp).isoformat()}

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
    for item in sorted(items, key=lambda x: x['published'], reverse=True):
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
    selected = select(items, load_state(), datetime.now(timezone.utc), max_posts=5)
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
    selected = select(items, state, now)
    for item in selected:
        state['entries'][item['key']] = {
            'status': 'reserved', 'run_id': run, 'reserved_utc': now.isoformat(),
            'url': item['url'], 'source': item['source'], 'title': item['title'], 'text': item['text']
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
            result = client.publish(entry['text'])
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
