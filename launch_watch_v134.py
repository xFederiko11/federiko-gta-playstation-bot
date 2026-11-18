"""GTA VI official news watch v13.5 (compatible with v13.4 ledger through 14 Dec 2026).

Single-run official Rockstar alerts + time-specific, source-backed launch notices.
No media rehosting, press claims, leaks or post retries. Buffer createPost is
invoked only AFTER a GitHub commit reserves the candidate ID. See README.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from editorial_seo_v135 import compose_official_alert, finish, x_weight, category_from_title
from urllib.parse import urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

START = datetime(2026, 11, 18, 11, tzinfo=timezone.utc)
STOP = datetime(2026, 12, 15, 0, tzinfo=timezone.utc)
LOCAL = ZoneInfo('Europe/Berlin')
NEWSWIRE = 'https://www.rockstargames.com/newswire?tag=vi'
RELEASE_SOURCE = ('https://support.rockstargames.com/articles/29jV3Cv2cCgvwM1XgtMO5o/'
                  'grand-theft-auto-vi-regional-pre-load-and-release-times-on-playstation-5-and-xbox-series-x-or-s')
LEDGER = Path(__file__).resolve().parent / '.state' / 'launch-watch-v134.json'
RUN_ID = os.getenv('GITHUB_RUN_ID', 'local')
EXPECTED_X = 'xfederiko11'
CURRENT_NEWS_CUTOFF = datetime(2026, 11, 18, 0, tzinfo=timezone.utc).date()
TITLES_RE = re.compile(r'\b(?:grand theft auto|gta\s*(?:vi|6|online)|playstation\s*5)\b', re.I)
SUSPECT_RE = re.compile(r'(?i)\b(?:rumor|rumour|leak|leaked|alleged|unconfirmed)\b')
ARTICLE_RE = re.compile(r'^/newswire/article/[A-Za-z0-9]+/[A-Za-z0-9_-]+/?$')

# Only fixed, verifiable schedule facts. No claims about gameplay/servers/real-world access.
MILESTONES = (
    {'id': 'nz-local-release-times-20261118', 'start': '2026-11-18T11:05:00+00:00',
     'end': '2026-11-18T15:00:00+00:00',
     'text': '🚨 GTA VI | È scattato lo sblocco regionale previsto per la Nuova Zelanda: 19/11 ore 00:00 NZDT = 18/11 ore 12:00 in Italia. 🇳🇿\n🇮🇹 In Italia l’orario previsto resta la mezzanotte del 19/11. Attenzione agli spoiler!\n' + RELEASE_SOURCE},
    {'id': 'italy-launch-schedule-20261118', 'start': '2026-11-18T18:00:00+00:00',
     'end': '2026-11-18T21:00:00+00:00',
     'text': '🎮 GTA VI | Conto alla rovescia per l’Italia!\n⏰ Sblocco digitale previsto da Rockstar alle 00:00 del 19 novembre.\n💾 Precaricamento per i preordini digitali. Attenzione agli spoiler.\n' + RELEASE_SOURCE},
    {'id': 'italy-midnight-20261118', 'start': '2026-11-18T23:00:00+00:00',
     'end': '2026-11-18T23:45:00+00:00',
     'text': '🚨 GTA VI | È mezzanotte: 19 novembre in Italia! 🇮🇹\n⏰ È l’orario di sblocco digitale previsto da Rockstar per PS5 e Xbox Series X|S.\n⚠️ Disponibilità dei server e accesso individuale ancora da verificare.\n' + RELEASE_SOURCE},
)


def now_utc():
    return datetime.now(timezone.utc)


def in_window(now):
    return START <= now < STOP


def weight(text):
    return x_weight(text)


def ledger_load(path=LEDGER):
    if not path.exists():
        return {'schema': 1, 'posts': {}}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('posts'), dict):
        raise RuntimeError('invalid_persistent_ledger')
    return data


def ledger_save(data, path=LEDGER):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    temp.replace(path)


def safe_article_url(url):
    try:
        p = urlsplit(url)
        if (p.scheme != 'https' or p.hostname not in ('rockstargames.com', 'www.rockstargames.com')
                or p.username or p.password or p.port not in (None, 443) or not ARTICLE_RE.fullmatch(p.path)):
            return None
        return urlunsplit(('https', 'www.rockstargames.com', p.path.rstrip('/'), '', ''))
    except (TypeError, ValueError):
        return None


def parse_listing(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    root = soup.find('main') or soup.find(attrs={'role': 'main'}) or soup
    output, seen = [], set()
    for a in root.find_all('a', href=True):
        link = safe_article_url(urljoin(NEWSWIRE, a['href']))
        title = re.sub(r'\s+', ' ', a.get_text(' ', strip=True) or a.get('aria-label', '')).strip()
        if not link or link in seen or not 10 <= len(title) <= 220 or not TITLES_RE.search(title):
            continue
        seen.add(link)
        output.append((link, title))
        if len(output) == 15:
            break
    return output


def official_listing(fetcher=None):
    if fetcher:
        return parse_listing(fetcher(NEWSWIRE, 'listing'))
    import requests
    html = ''
    try:
        response = requests.get(NEWSWIRE, timeout=(4, 8),
                                headers={'Accept-Language': 'en-US,en;q=0.9'})
        response.raise_for_status()
        if len(response.content) < 2_000_000:
            html = response.text
    except requests.RequestException:
        pass
    listings = parse_listing(html)
    if not listings:
        from rockstar_render import fetch_rendered
        listings = parse_listing(fetch_rendered(NEWSWIRE, mode='listing'))
    if not listings:
        raise ValueError('newswire_no_article_links')
    return listings


def official_article_date(url, fetcher=None):
    """Return article date only if explicitly on the official page, otherwise hold."""
    from bs4 import BeautifulSoup
    from editorial_v13 import _published_date
    if fetcher:
        html = fetcher(url, 'article')
    else:
        import requests
        html = ''
        try:
            r = requests.get(url, timeout=(4, 7), headers={'Accept-Language': 'en-US,en;q=0.9'})
            r.raise_for_status()
            if len(r.content) < 1_300_000:
                html = r.text
        except requests.RequestException:
            pass
        s = BeautifulSoup(html, 'html.parser')
        if not s.find('h1') or not (s.find('main') or s.find('article')):
            from rockstar_render import fetch_rendered
            html = fetch_rendered(url, mode='article')
    s = BeautifulSoup(html, 'html.parser')
    main = s.find('main') or s.find('article') or s.find(attrs={'role': 'main'})
    return _published_date(s, main) if main else None


def already_in_archive(url, root=None):
    root = root or Path(__file__).resolve().parent
    # Existing v11/v12 archive is a secondary deduplication defence.
    for file in ('history-public.json', 'history-public.csv', 'history-ps-seed.json'):
        path = root / file
        if path.is_file() and url in path.read_text(encoding='utf-8', errors='replace'):
            return True
    return False


def select(now, ledger, *, listing=None, date_getter=None, root=None):
    """Select exactly one candidate: official breaking takes precedence over scheduled tips."""
    if not in_window(now):
        return [], ['outside_launch_window']
    notes = []
    # Time-critical New Zealand update is verified against Rockstar Support;
    # do not delay it behind a potentially slow Newswire/browser request.
    nz = MILESTONES[0]
    if (nz['id'] not in ledger['posts'] and
            datetime.fromisoformat(nz['start']) <= now < datetime.fromisoformat(nz['end'])):
        item = {'id': nz['id'], 'topic': 'launch-times', 'text': finish(nz['text'], category='vi'),
                'url': RELEASE_SOURCE, 'tier': 'OFFICIAL_ROCKSTAR_SCHEDULE'}
        return [item], ['official_regional_release_schedule']
    articles = []
    try:
        entries = listing if listing is not None else official_listing()
        for url, title in entries[:4]:
            canonical = safe_article_url(url)
            if not canonical or canonical in ledger['posts'] or already_in_archive(canonical, root=root):
                continue
            if SUSPECT_RE.search(title):
                notes.append('hold_risky_title')
                continue
            try:
                pub = (date_getter or official_article_date)(canonical)
            except Exception:
                notes.append('hold_article_date_unavailable')
                continue
            # Do not turn old material into "breaking news".
            if not pub or pub < CURRENT_NEWS_CUTOFF or pub > now.date() or (now.date() - pub).days > 1:
                continue
            # Exact official headline, with optional editorial headline truncation.
            # v13.5 adds searchable GTA VI / GTA 6 terms, source and relevant tags.
            copy = compose_official_alert(title, canonical)
            if not copy:
                notes.append('hold_unclassified_or_oversize_headline')
                continue
            articles.append({'id': 'official-' + hashlib.sha256(canonical.encode()).hexdigest()[:18],
                             'topic': 'rockstar-official', 'text': copy, 'url': canonical,
                             'published': pub.isoformat(), 'tier': 'OFFICIAL_ROCKSTAR'})
    except Exception:
        notes.append('newswire_unavailable_nonfatal')
    if articles:
        articles.sort(key=lambda p: p['published'], reverse=True)
        return articles[:1], notes
    for event in MILESTONES:
        if event['id'] in ledger['posts']:
            continue
        if datetime.fromisoformat(event['start']) <= now < datetime.fromisoformat(event['end']):
            if weight(event['text']) <= 280:
                return [{'id': event['id'], 'topic': 'launch-times', 'text': finish(event['text'], category='vi'),
                         'url': RELEASE_SOURCE, 'tier': 'OFFICIAL_ROCKSTAR_SCHEDULE'}], notes
    return [], notes


def daily_limit(ledger, now, max_posts=12):
    cutoff = (now - timedelta(hours=24)).timestamp()
    return sum(1 for v in ledger['posts'].values() if v.get('reserved_at', 0) >= cutoff) < max_posts


def reserve(now, candidate, ledger, *, path=LEDGER, run_id=RUN_ID):
    if candidate['id'] in ledger['posts'] or not daily_limit(ledger, now):
        return False
    ledger['posts'][candidate['id']] = {
        'status': 'reserved', 'run_id': str(run_id), 'reserved_at': now.timestamp(),
        'topic': candidate['topic'], 'text': candidate['text'], 'tier': candidate['tier'],
        'url': candidate['url'], 'sha256': hashlib.sha256(candidate['text'].encode()).hexdigest(),
    }
    ledger_save(ledger, path)
    return True


def deliver(ledger, *, path=LEDGER, run_id=RUN_ID, client_factory=None):
    """Called only AFTER the reservation has been committed and pushed upstream."""
    from buffer_publisher import BufferClient, BufferPending, BufferAPIError
    pending = [(key, v) for key, v in ledger['posts'].items()
               if v.get('status') == 'reserved' and v.get('run_id') == str(run_id)]
    if len(pending) != 1:
        print('DELIVERY_NOT_ATTEMPTED: no unique reservation for current run')
        return 0
    key, record = pending[0]
    client = client_factory() if client_factory else BufferClient(expected_username=EXPECTED_X)
    try:
        channel = client.verify_destination()
        if channel.get('isQueuePaused'):
            raise RuntimeError('channel_queue_paused')
        try:
            buf_id = client.publish(record['text'])
            record['status'] = 'accepted'
            record['buffer_post_id'] = buf_id
        except BufferPending as exc:
            record['status'] = 'accepted_pending'
            record['buffer_post_id'] = exc.post_id
    except (BufferAPIError, RuntimeError, ValueError):
        record['status'] = 'unknown_review_buffer'
        print('WARNING: Buffer request failed or unclear. Inspect Buffer before any manual retry.')
        ledger_save(ledger, path)
        return 1
    ledger_save(ledger, path)
    print(f'BUFFER_ACCEPTED id={record.get("buffer_post_id")} candidate={key}; check Sent on Buffer/X')
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=('preview', 'reserve', 'deliver'), default='preview')
    args = p.parse_args(argv)
    now = now_utc()
    ledger = ledger_load()
    if args.mode == 'deliver':
        return deliver(ledger)
    candidates, notes = select(now, ledger)
    print(f'V134 {args.mode}: now_utc={now.isoformat()}, candidates={len(candidates)}, notes={notes}')
    for item in candidates:
        print(f'CANDIDATE {item["id"]} {item["tier"]} {item["topic"]}\n{item["text"]}\n')
    if args.mode == 'reserve' and candidates:
        if os.getenv('LAUNCH_WATCH_V134_AUTOPUBLISH', '').lower() != 'true':
            print('FAIL_CLOSED: LAUNCH_WATCH_V134_AUTOPUBLISH is not true')
            return 2
        if not daily_limit(ledger, now):
            print('DAILY_LIMIT: no post')
            return 0
        print('RESERVED' if reserve(now, candidates[0], ledger) else 'ALREADY_RESERVED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
