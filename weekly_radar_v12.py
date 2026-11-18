"""Source-first GTA Online / GTA VI / PS5 radar. Research only, NEVER posts.

Observes official Rockstar EN pages before third-party editorial sites.
Stable link and page fingerprints are persisted in the encrypted SQLite DB.
No scraping of X or login-protected media. No claims from unverified reposts.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
import time
import logging
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode
from bs4 import BeautifulSoup
import requests

LOG = logging.getLogger('gta.weekly_radar')
MAX_BODY = 1_500_000
MAX_LINKS = 100
MAX_REPORT = 60

# Fixed first-party and editorial discovery pages. No config supplied SSRF URLs.
TARGETS = (
    {'id':'rsg-online-us', 'name':'Rockstar Newswire - GTA Online (US)',
     'url':'https://www.rockstargames.com/newswire?tag=702', 'host':'rockstargames.com',
     'tier':'official', 'kind':'links', 'interval':300, 'language':'en'},
    {'id':'rsg-gta-online', 'name':'Rockstar GTA Online (US)',
     'url':'https://www.rockstargames.com/gta-online', 'host':'rockstargames.com',
     'tier':'official', 'kind':'snapshot', 'interval':600, 'language':'en'},
    {'id':'rsg-vi-media', 'name':'Rockstar GTA VI Screenshot Gallery (US)',
     'url':'https://www.rockstargames.com/VI/media/screenshots', 'host':'rockstargames.com',
     'tier':'official', 'kind':'snapshot', 'interval':900, 'language':'en'},
    {'id':'rsg-vi-video', 'name':'Rockstar GTA VI Official Videos (US)',
     'url':'https://www.rockstargames.com/VI/media/videos', 'host':'rockstargames.com',
     'tier':'official', 'kind':'snapshot', 'interval':900, 'language':'en'},
    {'id':'rsg-gtav-patch', 'name':'Rockstar Support GTA V Title Update (PS5)',
     'url':'https://support.rockstargames.com/articles/4vRqEDvjUs9h7nqRUgc8YO/gtav-title-update-1-73-notes-ps5-ps4-xbox-series-x-or-s-xbox-one-pc-enhanced-legacy',
     'host':'rockstargames.com', 'tier':'official', 'kind':'snapshot', 'interval':900, 'language':'en'},
    {'id':'gtabase-weekly', 'name':'GTABase - Weekly Bonuses and Discounts',
     'url':'https://www.gtabase.com/gta-online/weekly-update-bonuses-discounts',
     'host':'gtabase.com', 'tier':'press', 'kind':'snapshot', 'interval':600, 'language':'en'},
    {'id':'rockstarintel', 'name':'RockstarINTEL - Early Event Research',
     'url':'https://rockstarintel.com/', 'host':'rockstarintel.com',
     'tier':'press', 'kind':'links', 'interval':600, 'language':'en'},
)

WEEKLY = re.compile(r'\b(?:gta\s*(?:online|plus|\+)|grand theft auto\s+online|'
                    r'bonus(?:es)?|discounts?|sconti|ricompense|weekly|'
                    r'cash|payout|prize ride|podium|vinewood car club|'
                    r'2x|3x|4x|double|triple|quadruple|heist|'
                    r'kortz|vehicle|title update|patch|new screenshots|gta\s*(?:vi|6))\b|\bgta\+|\bgta\$', re.I)
RISK = re.compile(r'\b(?:leak(?:ed|s)?|rumou?rs?|speculat(?:ion|ive)|'
                  r'not confirmed|unconfirmed|alleged|datamin(?:e|ed|ing)|'
                  r'leaked copies|spoiler|supposedly|presunt[oaie]|'
                  r'indiscrezion[ei]|rumor|anticipazion[ei])\b', re.I)
GTA6 = re.compile(r'\b(?:gta\s*(?:vi|6)|grand theft auto\s*(?:vi|6))\b', re.I)
TECH = re.compile(r'\b(?:patch|title update|file\s+update|build|version|firmware|'
                  r'aggiornamento|hotfix|md5|hash|manifest|depot|update)\b', re.I)


_SAFE_ERROR = re.compile(r'[a-z][a-z0-9_]{2,70}\Z')
_LEGACY_ERROR_TYPES = frozenset({'ValueError','HTTPError','ReadTimeout','ConnectTimeout',
    'Timeout','ConnectionError','ProxyError','SSLError','KeyError'})


def _error_code(error: Exception) -> str:
    """Categorize public-source failures without logging response text or tokens."""
    if isinstance(error, requests.exceptions.HTTPError):
        status = getattr(getattr(error, 'response', None), 'status_code', None)
        return 'http_'+str(status) if type(status) is int and 100 <= status <= 599 else 'http_error'
    if isinstance(error, requests.exceptions.ReadTimeout):
        return 'read_timeout'
    if isinstance(error, requests.exceptions.ConnectTimeout):
        return 'connect_timeout'
    if isinstance(error, requests.exceptions.Timeout):
        return 'timeout'
    if isinstance(error, requests.exceptions.SSLError):
        return 'ssl_error'
    if isinstance(error, requests.exceptions.ConnectionError):
        return 'connection_error'
    if isinstance(error, ValueError):
        reason = error.args[0] if error.args else ''
        return reason if isinstance(reason, str) and _SAFE_ERROR.fullmatch(reason) else 'invalid_response'
    return 'source_error'


def source_health(db) -> list[dict]:
    init(db)
    rows = db.execute("SELECT id,last_success,next_due,last_error FROM weekly_radar_v12_sources ORDER BY id").fetchall()
    return [{'id':r['id'], 'status':'error' if r['last_error'] else
             'ok' if r['last_success'] is not None else 'never_succeeded',
             'last_error':r['last_error'], 'last_success_utc':
             datetime.fromtimestamp(r['last_success'],timezone.utc).isoformat() if r['last_success'] is not None else None,
             'next_retry_utc':datetime.fromtimestamp(r['next_due'],timezone.utc).isoformat()}
            for r in rows]


def _valid(url: str, host: str) -> bool:
    try:
        p = urlsplit(url)
        return bool(p.scheme == 'https' and p.hostname and not p.username and not p.password
                    and p.port in (None, 443)
                    and (p.hostname.lower() == host or p.hostname.lower().endswith('.'+host)))
    except ValueError:
        return False


def _url(url: str, host: str) -> str | None:
    if not _valid(url, host):
        return None
    p = urlsplit(url)
    params = [(k,v) for k,v in parse_qsl(p.query,keep_blank_values=False)
              if not k.lower().startswith('utm_') and k.lower() not in ('ref','fbclid','gclid')]
    return urlunsplit(('https',p.netloc.lower(),p.path.rstrip('/') or '/',urlencode(params),''))


def fetch(target: dict, session=None) -> str:
    client = session or requests
    address = target['url']
    for _ in range(3):
        response = client.get(address, headers={'User-Agent':'FederikoNewsCenter/12.1 (public pages research)', 'Accept-Language':'en-US,en;q=0.9'},
                              allow_redirects=False,timeout=(4,7))
        if response.status_code in (301,302,303,307,308):
            address = _url(urljoin(address,response.headers.get('Location','')),target['host'])
            if not address: raise ValueError('redirect_outside_publisher')
        else: break
    else: raise ValueError('too_many_redirects')
    response.raise_for_status()
    if response.status_code != 200 or not _valid(getattr(response,'url',address),target['host']):
        raise ValueError('invalid_response_url')
    body = response.content
    if len(body) > MAX_BODY: raise ValueError('page_too_large')
    return response.text


def _compact(text: str, limit=500) -> str:
    return re.sub(r'\s+',' ',text or '').strip()[:limit].rstrip()


def parse_html(page: str, target: dict) -> dict:
    """Extract article links or stable announcement text, not whole pages/ads/comments."""
    soup = BeautifulSoup(page,'html.parser')
    for tag in soup.select('script,style,noscript,nav,footer,aside,form,iframe'):
        tag.decompose()
    main = soup.find('main') or soup.find('article') or soup.find(attrs={'role':'main'})
    if main is None: raise ValueError('missing_main_container')
    for tag in main.select('aside,footer,nav,[class*=comment], [id*=comment]'):
        tag.decompose()
    title = _compact((soup.find('h1') or soup.find('title') or main).get_text(' ',strip=True),180)
    links=[]
    for a in main.select('a[href]'):
        href = _url(urljoin(target['url'],a.get('href','')),target['host'])
        if not href: continue
        if target['id'] == 'rsg-online-us' and '/newswire/article/' not in urlsplit(href).path:
            continue
        label = _compact(a.get_text(' ',strip=True),175)
        if not label or not WEEKLY.search(label+' '+href): continue
        links.append({'url':href,'title':label})
    links = list({row['url']:row for row in links}.values())[:MAX_LINKS]
    if target['kind']=='links' and not links: raise ValueError('no_relevant_links')
    text = _compact(main.get_text(' ',strip=True),6500)
    if target['kind']=='snapshot' and len(text)<90: raise ValueError('no_meaningful_page_text')
    # Preserve only meaningful excerpts in a private research ledger, not article copies.
    markers = [ _compact(h.get_text(' ',strip=True),145) for h in main.select('h1,h2,h3')
                if WEEKLY.search(h.get_text(' ',strip=True)) ][:40]
    if not markers and target['kind']=='snapshot':
        markers = [_compact(text,250)]
    return {'title':title,'links':links,'markers':markers,'signature':hashlib.sha256(
       json.dumps({'links':links,'markers':markers},sort_keys=True,ensure_ascii=False).encode()).hexdigest()}


def _category(headline: str, target: dict) -> str:
    if target['id'] in ('rsg-vi-media',): return 'GTA VI screenshot'
    if target['id'] in ('rsg-vi-video',): return 'GTA VI video'
    if target['id']=='rsg-gtav-patch' or TECH.search(headline): return 'Aggiornamento tecnico (da verificare)'
    if GTA6.search(headline): return 'GTA VI'
    return 'GTA Online bonus/sconti'


def init(db):
    db.executescript('''
      CREATE TABLE IF NOT EXISTS weekly_radar_v12_sources (
        id TEXT PRIMARY KEY, signature TEXT NOT NULL, link_ids_json TEXT NOT NULL,
        next_due REAL NOT NULL,last_success REAL,last_error TEXT);
      CREATE TABLE IF NOT EXISTS weekly_radar_v12_candidates (
        id TEXT PRIMARY KEY, source_id TEXT NOT NULL, url TEXT NOT NULL,
        title TEXT NOT NULL,category TEXT NOT NULL,trust TEXT NOT NULL,
        observed_at REAL NOT NULL,status TEXT NOT NULL,rights TEXT NOT NULL,
        note TEXT NOT NULL);
    ''')


def poll(db,*,fetcher=None,now=None,max_seconds=28) -> dict:
    """Research-only polling. No Buffer mutation; no false NZ / pre-release claims."""
    init(db)
    now=float(time.time() if now is None else now)
    started=time.monotonic()
    totals={'checked':0,'baseline':0,'candidates':0,'errors':0,'deferred':0}
    for target in TARGETS:
        row=db.execute('SELECT * FROM weekly_radar_v12_sources WHERE id=?',(target['id'],)).fetchone()
        successful_before = row is not None and row['last_success'] is not None
        if row and row['next_due']>now and row['last_error'] not in _LEGACY_ERROR_TYPES: continue
        if time.monotonic()-started>max_seconds:
            totals['deferred']+=1
            continue
        try:
            data = fetcher(target) if fetcher else fetch(target)
            parsed=parse_html(data,target)
            current={hashlib.sha256(link['url'].encode()).hexdigest() for link in parsed['links']}
            previous=set(json.loads(row['link_ids_json'])) if row else set()
            old_signature = row['signature'] if row else None
            fresh_links=[e for e in parsed['links'] if hashlib.sha256(e['url'].encode()).hexdigest() not in previous]
            changed = successful_before and old_signature != parsed['signature']
            with db:
                if successful_before and target['kind']=='links':
                    for e in fresh_links:
                        # Never auto-publish site summaries, even when on Rockstar's domain.
                        status='hold' if RISK.search(e['title']) else 'review'
                        db.execute('''INSERT OR IGNORE INTO weekly_radar_v12_candidates
                           (id,source_id,url,title,category,trust,observed_at,status,rights,note)
                           VALUES(?,?,?,?,?,?,?,?,?,?)''',
                           (hashlib.sha256(e['url'].encode()).hexdigest(),target['id'],e['url'],e['title'],
                            _category(e['title'],target),target['tier'],now,status,'not_cleared',
                            'Link nuovo; verificare contenuti, piattaforma e periodo prima di postare'))
                        totals['candidates']+=1
                elif row and changed and target['kind']=='snapshot':
                    name = _compact('; '.join(parsed['markers'][:3]) or parsed['title'],220)
                    ident = hashlib.sha256((target['id']+parsed['signature']).encode()).hexdigest()
                    status='hold' if RISK.search(name) else 'review'
                    db.execute('''INSERT OR IGNORE INTO weekly_radar_v12_candidates
                           (id,source_id,url,title,category,trust,observed_at,status,rights,note)
                           VALUES(?,?,?,?,?,?,?,?,?,?)''',
                           (ident,target['id'],target['url'],name,_category(name,target),target['tier'],now,
                            status,'not_cleared',
                            'Pagina cambiata: non equivale a patch o nuovo evento finche non verificato'))
                    totals['candidates']+=1
                db.execute('''INSERT OR REPLACE INTO weekly_radar_v12_sources
                    (id,signature,link_ids_json,next_due,last_success,last_error)
                    VALUES(?,?,?,?,?,?)''',(target['id'],parsed['signature'],json.dumps(sorted(current)),
                                            now+target['interval'],now,None))
            totals['baseline' if not successful_before else 'checked']+=1
        except (ValueError,requests.RequestException,KeyError) as exc:
            totals['errors']+=1
            LOG.warning('WEEKLY RADAR source=%s failed reason=%s', target['id'], _error_code(exc))
            with db:
                db.execute('''INSERT OR REPLACE INTO weekly_radar_v12_sources
                    (id,signature,link_ids_json,next_due,last_success,last_error)
                    VALUES(?,?,?,?,?,?)''',(target['id'],row['signature'] if row else '',
                        row['link_ids_json'] if row else '[]',now+max(900,target['interval']),
                        row['last_success'] if row else None,_error_code(exc)))
    return totals


def review(db,limit=MAX_REPORT):
    init(db)
    return [dict(row) for row in db.execute('''SELECT source_id,url,title,category,trust,
             observed_at,status,rights,note FROM weekly_radar_v12_candidates
             ORDER BY observed_at DESC,source_id LIMIT ?''',(min(max(int(limit),0),200),)).fetchall()]


def report(db, output_path, limit=MAX_REPORT):
    rows=review(db,limit)
    payload={'schema_version':'12.1','generated_at':datetime.now(timezone.utc).isoformat(),
             'mode':'RESEARCH_ONLY','automatic_posts':0,
             'labels':{'official':'Rockstar official source; content still requires fact-check',
                       'press':'Research lead; not an official announcement'},
             'rights':'Third-party pictures must not be downloaded/published without permission',
             'candidates':rows,'source_health':source_health(db),
             'diagnostics_version':'13.1'}
    output=Path(output_path); output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'WEEKLY RADAR v12.1: {len(rows)} review/hold leads, 0 automated posts')


def payout_rank(records):
    """Never guess profitability: rank only verified GTA$ AND typical minutes."""
    valid=[]
    for obj in records:
        if obj.get('verification')!='official_or_two_independent_confirmations': continue
        amount, duration=obj.get('net_gta_dollars'),obj.get('median_minutes')
        if type(amount) not in (float,int) or type(duration) not in (float,int): continue
        if amount<0 or duration<=0: continue
        valid.append({**obj,'gta_dollars_per_minute':round(amount/duration,2)})
    return sorted(valid,key=lambda item:-item['gta_dollars_per_minute'])
