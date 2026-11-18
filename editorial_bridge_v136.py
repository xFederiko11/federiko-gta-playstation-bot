"""GTA VI Launch Editorial Bridge v13.6 - one-time, fact-checked posts.

Run once via dedicated GitHub workflow. Never republishes a reserved ID.
The script deliberately DOES NOT scrape, rehost images or invent claims.
Sources independently reviewed 18-Nov-2026; links always retained.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

STATE = Path('.state/editorial-bridge-v136.json')
# Preview is possible before release. A stale one-time package must not silently
# post yesterday's news after the launch moment passes.
EXPIRY_UTC = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
POSTS = [
    {
        'slug': 'vgc-review-20261118',
        'source': 'https://www.videogameschronicle.com/review/grand-theft-auto-6/',
        'text': '📰 GTA VI (GTA 6) | Prime recensioni: VGC assegna 5/5 e premia il mondo aperto e la storia di Jason e Lucia. È il giudizio della testata, non una dichiarazione Rockstar. #GTAVI #GTA6',
    },
    {
        'slug': 'ps5pro-pushsquare-review-20261118',
        'source': 'https://www.pushsquare.com/reviews/ps5/grand-theft-auto-6',
        'text': '🎮 GTA VI (GTA 6) su PS5 Pro: nella prova di Push Square il gioco gira a 30 fps, senza opzione 60 fps. Recensione: 10/10. Dati riferiti alla versione testata dalla redazione. #GTAVI #PS5Pro',
    },
    {
        'slug': 'vgc-criminal-profile-20261118',
        'source': 'https://www.videogameschronicle.com/review/grand-theft-auto-6/',
        'text': '🧠 GTA VI (GTA 6) | Dettaglio nerd senza spoiler: VGC descrive un Criminal Profile che cambia in base alle azioni nel mondo aperto. Secondo la recensione, il livello «Irredeemable» è permanente. #GTAVI #GTA6',
    },
    {
        'slug': 'vgc-metascore-20261118',
        'source': 'https://www.videogameschronicle.com/news/grand-theft-auto-6-is-currently-the-highest-scoring-video-game-of-all-time-according-to-metacritic/',
        'text': '📊 GTA VI (GTA 6) | Alle 12:22 italiane del 18 novembre VGC riportava 99 su Metacritic: un risultato da record, ma il valore può cambiare con nuove recensioni. #GTAVI #GTA6',
    },
    {
        'slug': 'gta-online-weekly-stunt-challenge-20261118',
        'source': 'https://gta.guide/article/contact-missions-bonus-week',
        'text': '💰 GTA Online | Ultime ore per la sfida settimanale: vinci 2 Gare Stunt per ottenere 100.000 GTA$ e 10.000 RP, secondo il tracker GTA Guide. Controlla la scadenza nell’interfaccia di gioco. #GTAOnline',
    },
]


def _weight_x(txt):
    # Conservative X approximation (23-character URLs, 2 for supplementary emoji).
    fragments = re.split(r'(https?://\S+)', txt)
    total = 0
    for part in fragments:
        if re.match(r'^https?://', part):
            total += 23
        else:
            total += sum(2 if ord(c) > 0xFFFF else 1 for c in part)
    return total


def _uid(item):
    return hashlib.sha256(('editorial-bridge-20261118:' + item['slug']).encode()).hexdigest()[:20]


def _validate(item):
    url = urlsplit(item['source'])
    allowed = {'www.videogameschronicle.com', 'www.pushsquare.com', 'gta.guide'}
    if url.scheme != 'https' or url.hostname not in allowed:
        raise ValueError('Unapproved source hostname')
    full = item['text'].strip() + '\nFonte: ' + item['source']
    if _weight_x(full) > 280:
        raise ValueError('X weighted text exceeds 280 chars: ' + item['slug'])
    if len(re.findall(r'(?<!\w)#[A-Za-z0-9_]+',full))>2:
        raise ValueError('More than two hashtags')
    return full


def _load():
    if not STATE.exists():
        return {'version': 'v13.6', 'entries': {}}
    d=json.loads(STATE.read_text(encoding='utf-8'))
    if d.get('version')!='v13.6' or not isinstance(d.get('entries'),dict):
        raise ValueError('Ledger schema mismatch; refuse publishing')
    return d


def _save(data):
    STATE.parent.mkdir(parents=True,exist_ok=True)
    tmp=STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    tmp.replace(STATE)


def preview():
    state=_load()
    for item in POSTS:
        full=_validate(item)
        status=state['entries'].get(_uid(item),{}).get('status','new')
        print(f"{item['slug']}: status={status}; weighted={_weight_x(full)}; {full}")
    print('PREVIEW ONLY - 0 Buffer API calls; 0 writes')


def reserve():
    if datetime.now(timezone.utc)>=EXPIRY_UTC:
        print('EXPIRED: this curated launch burst is no longer timely; no posts')
        return
    data=_load()
    run=os.getenv('GITHUB_RUN_ID')
    if not run:
        raise RuntimeError('Only a GitHub Actions workflow may reserve posts')
    created=0
    for item in POSTS:
        _validate(item)
        key=_uid(item)
        if key not in data['entries']:
            data['entries'][key]={
                'slug':item['slug'], 'status':'reserved',
                'run_id':str(run), 'source':item['source'],
                'reserved_utc':datetime.now(timezone.utc).isoformat(),
            }
            created+=1
    if created:
        _save(data)
    print('RESERVED',created,'new posts. Existing ledger items never retried')


def deliver():
    from buffer_publisher import BufferAPIError, BufferPending, BufferClient
    run=str(os.getenv('GITHUB_RUN_ID',''))
    if not run:
        raise RuntimeError('Only a GitHub Actions workflow may deliver')
    state=_load()
    mine=[(item,_uid(item)) for item in POSTS if state['entries'].get(_uid(item),{}).get('run_id')==run
          and state['entries'].get(_uid(item),{}).get('status')=='reserved']
    if not mine:
        print('NO SEND: no new reservations for this run')
        return
    client=BufferClient(expected_username='xFederiko11')
    client.verify_destination()
    for index,(item,key) in enumerate(mine):
        # Per-post pre-call journal is durable only on runner. The repo already has
        # 'reserved', which prevents any subsequent run from attempting it again.
        entry=state['entries'][key]
        if entry['status']!='reserved':
            continue
        entry['status']='attempted'
        entry['attempted_utc']=datetime.now(timezone.utc).isoformat()
        _save(state)
        try:
            result=client.publish(_validate(item))
        except BufferPending as e:
            entry['status']='accepted_pending'
            entry['buffer_id']=e.post_id
            print('BUFFER_PENDING',item['slug'],e.post_id)
        except BufferAPIError as e:
            entry['status']='uncertain' if e.outcome_unknown else 'rejected'
            entry['buffer_id']=e.post_id
            print('BUFFER_ISSUE',item['slug'],entry['status'],str(e))
        else:
            entry['status']='sent'
            entry['buffer_id']=result
            print('BUFFER_SENT',item['slug'],result)
        finally:
            entry['completed_utc']=datetime.now(timezone.utc).isoformat()
            _save(state)
        # A curated burst, not a wall of five instant posts.
        if index<len(mine)-1:
            time.sleep(55)


def preflight():
    from buffer_publisher import BufferClient
    client=BufferClient(expected_username='xFederiko11')
    channel=client.verify_destination()
    print('PREFLIGHT OK: X destination verified; no posts created')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['preview','preflight','reserve','deliver'],required=True)
    args=parser.parse_args()
    {'preview':preview,'preflight':preflight,'reserve':reserve,'deliver':deliver}[args.mode]()


if __name__=='__main__':
    main()
