"""Federiko GTA News Center v13: verifiable Rockstar weekly briefing engine.

Strict safety boundary:
- Official Rockstar Newswire only, no user-supplied target URLs or X scraping.
- News listing first contact establishes a no-backfill baseline.
- A new post requires directly stated, in-period benefits with concrete dates.
- Press, leaks, screenshots, native retweets and datamining never auto-post here.
- Buffer is invoked only with *both* V13 and global opt-ins, in RUN mode.
- Delivery state is checkpointed BEFORE the irreversible API call. No blind retries.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
import hashlib
import json
import re
import time
import logging

from bs4 import BeautifulSoup
import requests

LOG = logging.getLogger('gta.editorial_v13')
OFFICIAL_NEWSWIRE = 'https://www.rockstargames.com/newswire?tag=702'
RELEVANT = re.compile(r'\b(?:gta\s*online|gta\+|heist|bonus|reward|discount|cash|weekly|missions?|vehicle|sale)\b', re.I)
RISK = re.compile(r'\b(?:rumou?r\w*|leak\w*|datamin\w*|unconfirmed|alleged|speculat\w*|may\s+be|might|spoiler)\b', re.I)
MONTHS = {name: i for i, name in enumerate(('January','February','March','April','May','June','July',
                                             'August','September','October','November','December'),1)}
MONTH_PAT = '|'.join(MONTHS)
BENEFIT_ACTIVITIES = {
    'Contact Missions': 'Missioni Contatto',
    'Freemode Challenges': 'Sfide in modalità libera',
    'Stunt Race Series': 'Serie Gare Stunt',
    'Import/Export Sell Missions': 'Vendite Import/Export',
    'Vehicle Cargo Sell Missions': 'Vendite Carichi veicoli',
    'Community Series': 'Serie Community',
    'Sumo (Remix)': 'Sumo (Remix)',
    'KnoWay Out': 'KnoWay Out',
    'Special Cargo Sourcing': 'Rifornimento Carichi speciali',
    'Motor Wars': 'Motor Wars',
}
BENEFIT_ORDER = tuple(sorted(BENEFIT_ACTIVITIES, key=len, reverse=True))
MAX_ARTICLE_BYTES = 1_250_000
MAX_NEW_ARTICLES = 2
MAX_ARTICLE_AGE_DAYS = 3
DEFAULT_INTERVAL = 900
MAX_REQUEST_SECONDS = 18
DISCOUNT_ITEMS = {
    'Grotti Veleno GT': 'Grotti Veleno GT',
    'High-End Apartment': 'Appartamenti di lusso',
    'Casino Penthouse': 'Attico del Casinò',
    'Facility': 'Base operativa',
    'Vehicle Warehouses': 'Magazzini veicoli',
    'Special Cargo Warehouses': 'Magazzini Carichi speciali',
}
FREE_ITEMS = {
    'Grotti Itali RSX': 'Grotti Itali RSX',
    'Sod Off Painting': 'Quadro Sod Off',
    'Pop Art Revere Collar': 'Maglia Pop Art Revere Collar',
    'Pegassi Oppressor': 'Pegassi Oppressor',
}


_SAFE_ERROR = re.compile(r'[a-z][a-z0-9_]{2,70}\Z')
_LEGACY_ERROR_TYPES = frozenset({'ValueError','HTTPError','ReadTimeout','ConnectTimeout',
    'Timeout','ConnectionError','ProxyError','SSLError','KeyError'})


def _error_code(error: Exception) -> str:
    """Safe reason codes only: no URL query strings, tokens or response text."""
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
    """One safe source record, even when no article was parsed successfully."""
    init(db)
    rows = db.execute("SELECT id,last_success,next_due,last_error FROM editorial_v13_sources ORDER BY id").fetchall()
    return [{'id': r['id'], 'status': 'error' if r['last_error'] else
             'ok' if r['last_success'] is not None else 'never_succeeded',
             'last_error': r['last_error'], 'last_success_utc':
             datetime.fromtimestamp(r['last_success'],timezone.utc).isoformat() if r['last_success'] is not None else None,
             'next_retry_utc': datetime.fromtimestamp(r['next_due'],timezone.utc).isoformat()}
            for r in rows]


def _https_rockstar(url: str, *, article=False) -> str | None:
    try:
        parts = urlsplit(url)
        if (parts.scheme != 'https' or parts.username or parts.password or parts.port not in (None,443)
                or (parts.hostname or '').lower() not in ('rockstargames.com','www.rockstargames.com')):
            return None
        if article and not re.fullmatch(r'/newswire/article/[a-zA-Z0-9]+/[^/?#]+', parts.path.rstrip('/')):
            return None
        return urlunsplit(('https','www.rockstargames.com',parts.path.rstrip('/') or '/', '', ''))
    except (ValueError, TypeError):
        return None


def _text(node, maximum=500):
    raw = node.get_text(' ',strip=True) if hasattr(node, 'get_text') else str(node or '')
    return re.sub(r'\s+', ' ', raw).strip()[:maximum]


def _article_links(html: str):
    soup = BeautifulSoup(html,'html.parser')
    container = soup.find('main') or soup.find(attrs={'role':'main'})
    if container is None:
        raise ValueError('newswire_listing_missing_main')
    links=[]
    for a in container.find_all('a',href=True):
        url = _https_rockstar(urljoin(OFFICIAL_NEWSWIRE,a['href']),article=True)
        title = _text(a,180)
        if not url or not title or not RELEVANT.search(title):
            continue
        if url not in {x['url'] for x in links}:
            links.append({'url':url,'title':title})
    if not links:
        raise ValueError('no_valid_rockstar_article_links')
    return links[:40]


def _fetch(url: str, *, session=None) -> str:
    url = _https_rockstar(url, article=bool('/article/' in url))
    if not url:
        raise ValueError('url_not_official_rockstar')
    client = session or requests
    response = client.get(url, headers={'User-Agent':'FederikoGTA-NewsCenter/13 (public first-party editorial monitoring)',
                                        'Accept-Language':'en-US,en;q=0.9', 'Accept':'text/html'},
                          timeout=(4,6),allow_redirects=False)
    if response.status_code in (301,302,303,307,308):
        redirect = _https_rockstar(urljoin(url,response.headers.get('Location','')),
                                   article='/article/' in url)
        if not redirect:
            raise ValueError('external_or_unsafe_redirect')
        response = client.get(redirect,headers={'Accept-Language':'en-US,en;q=0.9'},
                              timeout=(4,6),allow_redirects=False)
    response.raise_for_status()
    if response.status_code!=200 or not _https_rockstar(response.url,article='/article/' in url):
        raise ValueError('bad_official_response')
    if 'html' not in response.headers.get('Content-Type','text/html').lower():
        raise ValueError('unexpected_content_type')
    if len(response.content)>MAX_ARTICLE_BYTES:
        raise ValueError('article_exceeds_size_limit')
    return response.text


def _date_from_label(label: str, year: int) -> date | None:
    m = re.search(rf'\b({MONTH_PAT})\s+(\d{{1,2}})(?:,?\s+(20\d{{2}}))?\b', label, re.I)
    if not m:
        return None
    try:
        month = next(i for n,i in MONTHS.items() if n.lower()==m.group(1).lower())
        return date(int(m.group(3) or year),month,int(m.group(2)))
    except ValueError:
        return None


def _published_date(soup, main) -> date | None:
    for node in soup.find_all('meta'):
        if node.get('property') == 'article:published_time' or node.get('name') in ('date','pubdate'):
            val=node.get('content','')
            try: return date.fromisoformat(val[:10])
            except ValueError: pass
    for node in main.find_all('time',attrs={'datetime':True}):
        try: return date.fromisoformat(node['datetime'][:10])
        except ValueError: pass
    for script in soup.find_all('script',attrs={'type':'application/ld+json'}):
        raw=script.string or ''
        if len(raw)>64000: continue
        try: payload=json.loads(raw)
        except ValueError: continue
        objects=payload if isinstance(payload,list) else [payload]
        for obj in objects:
            if isinstance(obj,dict) and any(k in str(obj.get('@type','')) for k in ('NewsArticle','BlogPosting','Article')):
                published=obj.get('datePublished')
                if isinstance(published,str):
                    try: return date.fromisoformat(published[:10])
                    except ValueError: pass
    # Rockstar renders the publication date in the article header. Consider
    # ONLY text before the first article paragraph; never infer from bonus dates.
    prior=[]
    for node in main.find_all(['p','h1','h2','h3','time','span'],recursive=True):
        if node.name=='p': break
        s = _text(node,75)
        if len(s)<70: prior.append(s)
    for s in prior:
        m = re.search(rf'\b({MONTH_PAT})\s+(\d{{1,2}}),\s*(20\d{{2}})\b',s,re.I)
        if m:
            return _date_from_label(m.group(0),int(m.group(3)))
    return None


def _range_dates(text: str, year: int, reference:date) -> tuple[date|None,date|None]:
    """Only explicit periods; never project a timeless reward into the future."""
    # 'from November 12 through December 2'
    p = re.search(rf'\bfrom\s+({MONTH_PAT})\s+(\d{{1,2}})\s+(?:through|until|to|[-–])\s+({MONTH_PAT})\s+(\d{{1,2}})',text,re.I)
    if p:
        start=_date_from_label(p.group(1)+' '+p.group(2),year)
        end=_date_from_label(p.group(3)+' '+p.group(4),year)
        if start and end and end<start:
            try: end=end.replace(year=end.year+1)
            except ValueError: return None,None
        return start,end
    # 'from November 5–11'
    p = re.search(rf'\bfrom\s+({MONTH_PAT})\s+(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})',text,re.I)
    if p:
        start=_date_from_label(p.group(1)+' '+p.group(2),year)
        end=_date_from_label(p.group(1)+' '+p.group(3),year)
        if start and end and end>=start: return start,end
    # 'through December 9' does not prove start; earliest eligible at article publication.
    p = re.search(rf'\b(?:through|until)\s+({MONTH_PAT})\s+(\d{{1,2}})',text,re.I)
    if p:
        end=_date_from_label(p.group(1)+' '+p.group(2),year)
        if end and end<reference and end.month < reference.month:
            try: end=end.replace(year=end.year+1)
            except ValueError: return None,None
        return None,end
    return None,None


def _evidence_paragraphs(main) -> list[tuple[str,str]]:
    result=[]; heading=''
    for node in main.descendants:
        if getattr(node,'name',None) in ('h1','h2','h3'):
            heading=_text(node,220)
        if getattr(node,'name',None) in ('p','li') and not node.find(['p','li']):
            content=_text(node,1800)
            if len(content)>30: result.append((heading,content))
    return result[:150]


def _conservative_bonus_facts(heading:str, body:str, published:date, now:date) -> list[dict]:
    """Known subjects only; do not mix multipliers/audience from adjacent clauses."""
    if RISK.search(heading+' '+body): return []
    # Two distinct deadlines in one paragraph => manual verification; never
    # transfer an unrelated benefit's validity window to another activity.
    all_dates=set(re.findall(rf'(?:through|until)\s+(?:{MONTH_PAT})\s+\d{{1,2}}',body,re.I))
    if len({x.lower() for x in all_dates})>1: return []
    start,end=_range_dates(heading+' '+body,published.year,published)
    if not end or end<now or (end-published).days>60:
        return []
    out=[]
    clauses=re.split(r'[.!?;]|,\s+and\s+',body)
    for activity in BENEFIT_ORDER:
        h=heading.casefold(); act=activity.casefold()
        if act not in h and act not in body.casefold(): continue
        multiplier=None; special=False
        match_clause=next((c for c in clauses if act in c.casefold()),'')
        header=re.search(r'\b([234])\s*[xX]\s+GTA\$\s+(?:and\s+RP\s+)?on\s+',heading,re.I)
        # An old heading is not evidence for a different activity that appears
        # in the following paragraph. Match the activity within that headline.
        if header and act in h:
            if not match_clause and any(x.casefold() in body.casefold() for x in BENEFIT_ORDER if x!=activity):
                continue
            multiplier=int(header.group(1))
            matched_text=heading+' '+match_clause
        else:
            matched_text=match_clause
            if not matched_text: continue
            number=re.search(r'\b([234])\s*[xX]\s+GTA\$',matched_text,re.I)
            if number: multiplier=int(number.group(1))
            else:
                # 'Double rewards' without explicit cash may refer only to RP.
                cash='gta$' in (heading+' '+matched_text).casefold()
                if cash and re.search(r'\b(?:double|doubled)\s+rewards',matched_text,re.I): multiplier=2
                elif cash and re.search(r'\b(?:triple|tripled)\s+rewards',matched_text,re.I): multiplier=3
                elif cash and re.search(r'\b(?:quadruple|quadrupled)\s+rewards',matched_text,re.I): multiplier=4
        if multiplier is None: continue
        # A shared clause with different multipliers for multiple activities is
        # ambiguous unless the activities were separated into individual clauses.
        # Do not attribute the first number to every activity in the sentence.
        other_activities=[name for name in BENEFIT_ORDER if name != activity and name.casefold() in match_clause.casefold()]
        distinct_multipliers=set(re.findall(r'\b([234])\s*[xX]\s+GTA\$',match_clause,re.I))
        if other_activities and len(distinct_multipliers)>1:
            continue
        # One-time/first-completion restrictions cannot be silently omitted.
        if re.search(r'\b(?:first\s+(?:weekly\s+)?completion|first-time|once\s+per\s+week|select\s+missions)\b',matched_text,re.I):
            continue
        # 'Stacking to 4X for GTA+' is a separate additional benefit; do not
        # label Freemode/Stunt as subscriber-only because Contact Missions
        # elsewhere in the paragraph mentions GTA+.
        special=bool(re.search(r'\bstacking\s+to\s+4X\s+for\s+GTA\+\s+Members',matched_text,re.I))
        audience='GTA+' if not special and re.search(
            r'\b(?:only\s+for|to|for)\s+GTA\+\s+Members\b|\bGTA\+\s+Members\s+only\b',matched_text,re.I) else 'all'
        reward_rp = bool(re.search(r'GTA\$\s+and\s+RP',matched_text,re.I))
        evidence=(heading+' | '+matched_text)[:340]
        out.append({'kind':'bonus','subject':activity,'display':BENEFIT_ACTIVITIES[activity],
                    'multiplier':multiplier,'rp':reward_rp,'audience':audience,'start':start.isoformat() if start else None,
                    'end':end.isoformat(),'evidence':evidence,'approval':'official_direct'})
        if special and multiplier==2:
            out.append({'kind':'bonus','subject':activity,'display':BENEFIT_ACTIVITIES[activity],
                        'multiplier':4,'rp':reward_rp,'audience':'GTA+', 'start':start.isoformat() if start else None,
                        'end':end.isoformat(),'evidence':evidence,'approval':'official_direct'})
    return out


def _conservative_offers(heading:str, body:str, published:date, now:date) -> list[dict]:
    """Only exact named assets with a numeric discount or explicit free claim window."""
    if RISK.search(heading+' '+body): return []
    start,end=_range_dates(heading+' '+body,published.year,published)
    if not end or end<now or (end-published).days>60:
        return []
    facts=[]
    for item,label in DISCOUNT_ITEMS.items():
        match=re.search(re.escape(item),body,re.I)
        if not match: continue
        # Discount must be attributable in the same sentence or list segment,
        # not taken from an unrelated 75% armor offer elsewhere on the page.
        clause=next((x for x in re.split(r'[.!?]',body) if item.casefold() in x.casefold()),'')
        discount=re.search(r'\b([1-9][0-9]?)\s*%\s+off\b',clause,re.I)
        # Do not assign one unrelated percent to every item in a mixed
        # discount sentence. A single shared rate is acceptable if nearby.
        all_rates={int(v) for v in re.findall(r'\b([1-9][0-9]?)\s*%\s+off\b',clause,re.I)}
        near=bool(discount and abs(discount.start()-clause.casefold().find(item.casefold()))<=80)
        if discount and len(clause)<410 and len(all_rates)==1 and near:
            facts.append({'kind':'discount','subject':item,'display':label,'percent':int(discount.group(1)),
                          'audience':'GTA+' if re.search(r'GTA\+\s+Members',clause,re.I) else 'all',
                          'start':start.isoformat() if start else None,'end':end.isoformat(),
                          'evidence':(heading+' | '+clause)[:340],'approval':'official_direct'})
    for item,label in FREE_ITEMS.items():
        clause=next((x for x in re.split(r'[.!?]',body) if item.casefold() in x.casefold()),'')
        if not clause: continue
        if re.search(r'\bfree\s+to\s+claim\b',clause,re.I) and re.search(r'\bGTA\+\s+Members\b',clause,re.I):
            facts.append({'kind':'free','subject':item,'display':label,
                          'audience':'GTA+','start':start.isoformat() if start else None,
                          'end':end.isoformat(),'evidence':(heading+' | '+clause)[:340],
                          'approval':'official_direct'})
    return facts


def parse_article(html:str, url:str, *, today:date|None=None) -> dict:
    url=_https_rockstar(url,article=True)
    if not url: raise ValueError('non_rockstar_article')
    today=today or datetime.now(timezone.utc).date()
    soup=BeautifulSoup(html,'html.parser')
    main=soup.find('main') or soup.find('article') or soup.find(attrs={'role':'main'})
    if main is None: raise ValueError('article_missing_main')
    header=main.find('h1')
    title=_text(header,200) if header else ''
    if not title: raise ValueError('article_missing_title')
    published=_published_date(soup,main)
    sections=_evidence_paragraphs(main)
    if len(sections)==0: raise ValueError('article_missing_body')
    facts=[]
    if published:
        for heading,paragraph in sections:
            facts+=_conservative_bonus_facts(heading,paragraph,published,today)
            facts+=_conservative_offers(heading,paragraph,published,today)
    unique={}
    for item in facts:
        k=(item['kind'],item['subject'],item['audience'],item.get('multiplier',item.get('percent')),item['end'])
        unique[k]=item
    facts=list(unique.values())
    facts.sort(key=lambda i:(i['end'],i['subject'],i['audience']))
    text = ' '.join(x[1] for x in sections[:40])[:3000]
    if published is None: reason='no_verifiable_publication_date'
    elif published>today+timedelta(days=1): reason='publication_date_future'
    elif RISK.search(title): reason='risky_article_headline'
    elif not facts: reason='no_explicit_current_bonus_with_expiration'
    else: reason='official_facts_extracted'
    return {'url':url,'title':title,'published_on':published.isoformat() if published else None,
            'facts':facts,'review_reason':reason,'is_current':bool(published and published<=today and
                       (today-published).days<=MAX_ARTICLE_AGE_DAYS),
            'source_tier':'OFFICIAL_ROCKSTAR','language':'en','auto_image':'none_link_preview_only',
            'source_excerpt':text[:280]}


def _x_weight(text: str) -> int:
    from presentation import _post_weight
    return _post_weight(text)


def build_post(article:dict) -> str|None:
    """Original Italian micro-digest: no translation of unverified free text."""
    if article.get('review_reason')!='official_facts_extracted' or not article.get('is_current'):
        return None
    facts=[f for f in article['facts'] if f['kind'] in ('bonus','discount','free') and f['end']]
    if not facts: return None
    lines=[]
    # Prioritize broad-access benefits; max 2 concise facts per post.
    ordered=sorted(facts,key=lambda f:(f['audience']!='all', f['kind']!='bonus',-f.get('multiplier',1),f['subject']))
    for f in ordered:
        until=date.fromisoformat(f['end']).strftime('%d/%m')
        period=(f"dal {date.fromisoformat(f['start']).strftime('%d/%m')} al {until}" if f.get('start')
                else f'fino al {until}')
        audience=' (GTA+)' if f['audience']=='GTA+' else ''
        if f['kind']=='bonus':
            money='GTA$ e RP' if f.get('rp') else 'GTA$'
            sentence=f"✅ {f['display']}: {f['multiplier']}× {money}{audience} {period}"
        elif f['kind']=='discount':
            sentence=f"🏷️ {f['display']}: -{f['percent']}%{audience} {period}"
        else:
            sentence=f"🎁 {f['display']}: gratis{audience} {period}"
        if sentence not in lines: lines.append(sentence)
        if len(lines)>=2: break
    if not lines: return None
    # Preserve the original link: X generates its own preview if supported.
    prefix='🎮 GTA ONLINE | BONUS ROCKSTAR\n'
    suffix=f"\n🔗 Fonte ufficiale: {article['url']}\n#GTAOnline"
    text=prefix+'\n'.join(lines)+suffix
    if _x_weight(text)>280:
        text=prefix+lines[0]+suffix
    if _x_weight(text)>280:
        return None
    return text


def init(db):
    db.executescript('''
      CREATE TABLE IF NOT EXISTS editorial_v13_sources (
          id TEXT PRIMARY KEY, seen_urls_json TEXT NOT NULL, next_due REAL NOT NULL,
          last_success REAL, last_error TEXT);
      CREATE TABLE IF NOT EXISTS editorial_v13_articles (
          url TEXT PRIMARY KEY, title TEXT NOT NULL, detected_at REAL NOT NULL,
          published_on TEXT, status TEXT NOT NULL, data_json TEXT NOT NULL,
          post_text TEXT, buffer_id TEXT, attempted_at REAL, last_error TEXT, retry_at REAL NOT NULL DEFAULT 0);
    ''')


def _exists_in_existing_publisher(db, url:str) -> bool:
    # Research is allowed, but do not independently broadcast the same URL
    # already tracked by the official publisher. Avoid SQL LIKE injection.
    needle=urlsplit(url).path.split('/')[3]  # article slug-id
    if len(needle)<7: return True
    for table, column in (('publish_jobs','event_json'),('posts','source_json')):
        try:
            row=db.execute(f'SELECT 1 FROM {table} WHERE {column} LIKE ? LIMIT 1',('%'+needle+'%',)).fetchone()
            if row: return True
        except Exception:
            # Fail closed when v11 ledger cannot be inspected.
            return True
    return False


def _fact_key(fact:dict) -> tuple:
    # One benefit for one period, independent of the Rockstar article URL.
    return (fact.get('kind'),fact.get('subject'),fact.get('audience'),fact.get('start'),
            fact.get('end'),fact.get('multiplier'),fact.get('percent'))


def _remove_reported_facts(db, article:dict) -> dict:
    # A later Rockstar story can repeat a bonus from an earlier bulletin.
    # Previously sent (or ambiguous-delivery) facts are not eligible again.
    prior=set()
    for row in db.execute("SELECT data_json FROM editorial_v13_articles WHERE status IN "
                          "('sent','accepted','sending','uncertain','review_delivery')"):
        try: previous=json.loads(row['data_json'])
        except (ValueError,TypeError): continue
        for fact in previous.get('facts',[]):
            prior.add(_fact_key(fact))
    fresh=[fact for fact in article.get('facts',[]) if _fact_key(fact) not in prior]
    if not fresh and article.get('facts'):
        article['review_reason']='already_announced_facts'
    article['facts']=fresh
    return article


def research(db,*, listing_html=None, article_fetcher=None, now=None, min_interval=DEFAULT_INTERVAL) -> dict:
    """First contact baselines links and previews; later only new links become candidates."""
    init(db)
    now=float(time.time() if now is None else now)
    today=datetime.fromtimestamp(now,timezone.utc).date()
    old=db.execute("SELECT * FROM editorial_v13_sources WHERE id='rockstar-online-us'").fetchone()
    totals={'checked':0,'baseline':0,'new':0,'eligible':0,'errors':0,'skipped':0}
    if old and old['next_due']>now and old['last_error'] not in _LEGACY_ERROR_TYPES:
        totals['skipped']=1; return totals
    try:
        links=_article_links(listing_html if listing_html is not None else _fetch(OFFICIAL_NEWSWIRE))
        seen=set(json.loads(old['seen_urls_json'])) if old else set()
        initial=old is None or (not seen and old['last_success'] is None)
        novel=[x for x in links if x['url'] not in seen]
        # The first baseline stores all 40 IDs to avoid backfilling the archive,
        # but previews up to two useful current official articles in the report.
        to_examine=novel[:MAX_NEW_ARTICLES]
        for lead in to_examine:
            if old and _exists_in_existing_publisher(db,lead['url']):
                state='review_duplicate_with_v11'; data={'url':lead['url'],'facts':[], 'review_reason':state}
            else:
                try:
                    page=article_fetcher(lead['url']) if article_fetcher else _fetch(lead['url'])
                    data=parse_article(page,lead['url'],today=today)
                    if not initial and data.get('facts'):
                        data=_remove_reported_facts(db,data)
                    state=('baseline_review' if initial else
                           'ready' if data['is_current'] and build_post(data) else 'review')
                except (ValueError,requests.RequestException) as error:
                    state='review_fetch_error'
                    data={'url':lead['url'],'facts':[],'review_reason':_error_code(error)}
                    totals['errors']+=1
                    LOG.warning('V13 article source failure: reason=%s', _error_code(error))
            post_text=build_post(data)
            with db:
                db.execute('''INSERT INTO editorial_v13_articles
                  (url,title,detected_at,published_on,status,data_json,post_text,last_error)
                  VALUES(?,?,?,?,?,?,?,?)
                  ON CONFLICT(url) DO UPDATE SET
                    published_on=excluded.published_on, status=excluded.status,
                    data_json=excluded.data_json, post_text=excluded.post_text,
                    last_error=excluded.last_error
                  WHERE editorial_v13_articles.status='review_fetch_error' ''',
                  (lead['url'],lead['title'],now,data.get('published_on'),state,
                   json.dumps(data,ensure_ascii=False),post_text,
                   data.get('review_reason') if state.startswith('review') else None))
            totals['new']+=int(not initial)
            totals['eligible']+=int(state=='ready')
        with db:
            db.execute('''INSERT OR REPLACE INTO editorial_v13_sources
              (id,seen_urls_json,next_due,last_success,last_error) VALUES(?,?,?,?,?)''',
              ('rockstar-online-us',json.dumps(sorted(seen|{x['url'] for x in (links if initial else to_examine)
               if initial or db.execute('SELECT status FROM editorial_v13_articles WHERE url=?',(x['url'],)).fetchone()[0]!='review_fetch_error'})),
               now+max(300,min_interval),now,None))
        totals['baseline' if initial else 'checked']=1
    except (ValueError,requests.RequestException,KeyError) as error:
        totals['errors']+=1
        LOG.warning('V13 Rockstar Newswire listing failed: reason=%s', _error_code(error))
        with db:
            db.execute('''INSERT OR REPLACE INTO editorial_v13_sources
              (id,seen_urls_json,next_due,last_success,last_error) VALUES(?,?,?,?,?)''',
              ('rockstar-online-us',old['seen_urls_json'] if old else '[]',now+1800,
               old['last_success'] if old else None,_error_code(error)))
    return totals


def report(db,path: str|Path, limit=25) -> dict:
    init(db)
    records=[]
    for r in db.execute('''SELECT url,title,published_on,status,data_json,post_text,last_error
                           FROM editorial_v13_articles ORDER BY detected_at DESC LIMIT ?''',(limit,)):
        evidence=json.loads(r['data_json'])
        records.append({'url':r['url'],'title':r['title'],'published_on':r['published_on'],
                        'status':r['status'],'post_preview_it':r['post_text'],
                        'last_error':r['last_error'],'facts':evidence.get('facts',[]),
                        'review_reason':evidence.get('review_reason')})
    payload={'schema_version':'13.0','generated_at':datetime.now(timezone.utc).isoformat(),
             'scope':'ONLY_OFFICIAL_ROCKSTAR_BONUS_WITH_EXPLICIT_EXPIRATION',
             'notes':['First run baselines current articles: no retroactive publication',
                      'Press and community never automatically published',
                      'Link preview determined by X; no external media copied'],
             'records':records,'source_health':source_health(db),
             'diagnostics_version':'13.1'}
    dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return payload


def deliver_ready(db,*,client,checkpoint,now=None,max_per_day=2,earliest_since_seconds=900) -> dict:
    """Strict idempotency: no automatic retry on ambiguous createPost outcomes."""
    from buffer_publisher import BufferAPIError, BufferPending, BufferDeliveryFailed
    init(db)
    now=float(time.time() if now is None else now)
    result={'sent':0,'accepted':0,'review':0,'deferred':0}
    # Resolve Buffer-accepted IDs WITHOUT a second createPost. A pending or
    # uncertain request is never blindly retried.
    for pending in db.execute("SELECT url,buffer_id,attempted_at FROM editorial_v13_articles WHERE status='accepted' AND buffer_id IS NOT NULL LIMIT 2"):
        if now - float(pending['attempted_at'] or now) < 300: continue
        try:
            delivery=client.delivery_status(pending['buffer_id'])
            state='sent' if delivery.status=='sent' else 'review_delivery' if delivery.status=='error' else 'accepted'
            if state != 'accepted':
                with db: db.execute("UPDATE editorial_v13_articles SET status=? WHERE url=?",(state,pending['url']))
                checkpoint()
                result['sent' if state=='sent' else 'review']+=1
        except BufferAPIError:
            result['deferred']+=1
    existing=db.execute('''SELECT COUNT(*) FROM editorial_v13_articles WHERE
          attempted_at>? AND status IN ('sending','sent','accepted','uncertain','review_delivery')''',
          (now-86400,)).fetchone()[0]
    if existing>=max_per_day: result['deferred']+=1; return result
    # Do not compete with the official breaking news publisher.
    try:
        last=db.execute("SELECT MAX(attempted_at) FROM publish_jobs").fetchone()[0]
        if last and now-float(last)<earliest_since_seconds:
            result['deferred']+=1; return result
    except Exception:
        result['deferred']+=1; return result
    rows=db.execute("SELECT * FROM editorial_v13_articles WHERE status='ready' ORDER BY detected_at LIMIT 1").fetchall()
    for r in rows:
        data=json.loads(r['data_json'])
        pub=data.get('published_on')
        if (not pub or not data.get('is_current') or not build_post(data) or
              (datetime.fromtimestamp(now,timezone.utc).date()-date.fromisoformat(pub)).days>MAX_ARTICLE_AGE_DAYS):
            with db:
                db.execute("UPDATE editorial_v13_articles SET status='review',last_error='stale_or_missing_verified_facts' WHERE url=?",(r['url'],))
            result['review']+=1; continue
        if _exists_in_existing_publisher(db,r['url']):
            with db:
                db.execute("UPDATE editorial_v13_articles SET status='review',last_error='duplicate_with_official_monitor' WHERE url=?",(r['url'],))
            result['review']+=1; continue
        # Read-only destination check first. Invalid auth/quota must not mark an
        # unattempted item as 'sending' or consume its unique deduplication key.
        if getattr(client,'destination',None) is None:
            client.verify_destination()
        with db:
            db.execute("UPDATE editorial_v13_articles SET status='sending',attempted_at=? WHERE url=?",(now,r['url']))
        checkpoint() # Must be durable before calling Buffer; failure aborts publication.
        try:
            message=r['post_text']
            if not message or _x_weight(message)>280:
                raise ValueError('invalid_x_post_text')
            post_id=client.publish(message)
            with db:
                db.execute("UPDATE editorial_v13_articles SET status='sent',buffer_id=? WHERE url=?",(str(post_id),r['url']))
            checkpoint()
            result['sent']+=1
        except BufferPending as error:
            with db:
                db.execute("UPDATE editorial_v13_articles SET status='accepted',buffer_id=? WHERE url=?",(error.post_id,r['url']))
            checkpoint(); result['accepted']+=1
        except (BufferAPIError,ValueError) as error:
            with db:
                db.execute("UPDATE editorial_v13_articles SET status=?,last_error=? WHERE url=?",
                           ('uncertain' if getattr(error,'outcome_unknown',False) else 'review_delivery',
                            type(error).__name__,r['url']))
            checkpoint();result['review']+=1
    return result
