"""One-shot, opt-in launch-day editorial pulse for @xFederiko11.

All claims were verified against the linked sources on 2026-11-18.
No live scraping, no historical backfill, no automatic media copying.
Run with --mode preview to see output; --mode publish to create up to four Buffer posts.
Persistent repository ledger prevents repeats across runs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

VERSION = '13.3'
LOCAL = ZoneInfo('Europe/Berlin')
ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / '.state' / 'launch-pulse-v133.json'
EXPECTED_HANDLE = 'xfederiko11'
WINDOW_START = datetime(2026, 11, 18, 0, 0, tzinfo=LOCAL)
WINDOW_END = datetime(2026, 11, 19, 0, 0, tzinfo=LOCAL)
NZ_UNLOCK_UTC = datetime(2026, 11, 18, 11, 0, tzinfo=timezone.utc)

# A unique source URL and topic per slot; no repeated media assets. Link preview is
# rendered by X, not guaranteed by Buffer. No license to reupload press images.
POSTS = (
    {
        'id': 'nz-early-unlock-20261118',
        'text': ('🚨 GTA VI | Si avvicina il primo sblocco!\n'
                 'Secondo gli orari del PlayStation Store, in Nuova Zelanda è previsto alle 12:00 italiane (00:00 del 19/11 ad Auckland).\n'
                 '⚠️ È un orario regionale: cambiare fuso non garantisce accesso.\n'
                 'https://www.gadgets360.com/games/news/gta-6-global-release-timings-midnight-local-time-playstation-store-rockstar-games-12017494'),
        'valid_before': NZ_UNLOCK_UTC,
        'topic': 'nz-store-time',
        'tier': 'STORE_LISTING_REPORTED',
    },
    {
        'id': 'gtaonline-current-bonuses-20261118',
        'text': ('💰 GTA ONLINE | Bonus confermati Rockstar\n'
                 '✅ Sfide in modalità libera: 4× GTA$ e RP\n'
                 '✅ Serie Gare Stunt: 3× GTA$ e RP\n'
                 '✅ Missioni Contatto: 2× (4× per GTA+)\n'
                 '📅 Rockstar indica bonus fino al 2 dicembre.\n'
                 'https://www.rockstargames.com/newswire/article/4k17a844oakk5o/take-down-the-kortz-center-and-more-high-value-targets-in-this-week-s'),
        'valid_before': datetime(2026, 12, 2, 23, 0, tzinfo=timezone.utc),
        'topic': 'gtaonline-boosts',
        'tier': 'OFFICIAL_ROCKSTAR',
    },
    {
        'id': 'gtaplus-itali-rsx-20261118',
        'text': ('🚗 GTA+ | Auto gratuita da non perdere\n'
                 'La Grotti Itali RSX si può riscattare gratis al Vinewood Car Club fino al 9 dicembre.\n'
                 'Requisito: abbonamento GTA+ attivo. Non è un regalo per tutti i giocatori.\n'
                 '🔗 Fonte Rockstar: https://www.rockstargames.com/newswire/article/178a115o743442/gta-members-can-now-claim-a-free-grotti-itali-rsx'),
        'valid_before': datetime(2026, 12, 9, 22, 0, tzinfo=timezone.utc),
        'topic': 'itali-rsx',
        'tier': 'OFFICIAL_ROCKSTAR',
    },
    {
        'id': 'ps5pro-gtavi-technical-20261118',
        'text': ('🎮 GTA VI | PS5 vs PS5 Pro: cosa cambia?\n'
                 'Rockstar indica 30 fps come obiettivo e, sulla PS5 Pro, PSSR e ombre ray tracing dedicate.\n'
                 '⚠️ Nessuna promessa ufficiale di 60 fps al lancio.\n'
                 '🔗 Dettagli: https://www.rockstargames.com/newswire/article/89834o94713o21/pre-load-grand-theft-auto-vi-now'),
        'valid_before': datetime(2026, 11, 20, 0, 0, tzinfo=timezone.utc),
        'topic': 'ps5-pro-tech',
        'tier': 'OFFICIAL_ROCKSTAR',
    },
)


def weighted_length(value):
    """Conservative approximation: URLs count as 23 on X, but reject longer copy."""
    import re
    return len(re.sub(r'https?://\S+', 'x'*23, value))


def load_ledger(path=LEDGER):
    if not path.exists():
        return {'version': VERSION, 'posts': {}}
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('posts'),dict):
        raise ValueError('ledger_invalid')
    return data


def save_ledger(data, path=LEDGER):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    temp.replace(path)


def eligible(now, ledger):
    when=now.astimezone(LOCAL)
    if not WINDOW_START <= when < WINDOW_END:
        raise ValueError('launch_pulse_window_closed')
    remaining=[]
    for p in POSTS:
        if now >= p['valid_before'] or p['id'] in ledger['posts']:
            continue
        if weighted_length(p['text'])>280:
            raise ValueError('copy_over_280:'+p['id'])
        remaining.append(p)
    return remaining[:4]


def dispatch(client, items, now, ledger, *,save=save_ledger):
    """Use Buffer official GraphQL. Checkpoint *before* a remote mutation.

    On an ambiguous outcome retain `unknown` in ledger. A second execution
    must never blindly retry. Operator should inspect the Buffer dashboard.
    """
    from buffer_publisher import CREATE_MUTATION, BufferAPIError
    channel=client.verify_destination()
    if (channel.get('service')!='twitter' or channel.get('isQueuePaused') or
        channel.get('isDisconnected') or channel.get('isLocked')):
        raise RuntimeError('buffer_channel_not_ready')
    result=[]
    for i,p in enumerate(items):
        # Different topics separated by at least 25 minutes, not 4 identical posts.
        due=now+timedelta(minutes=25*i)
        mode='shareNow' if i==0 else 'customScheduled'
        payload={
            'text':p['text'], 'channelId':client.channel_id,
            'schedulingType':'automatic', 'mode':mode, 'assets':[],
        }
        if i: payload['dueAt']=due.isoformat().replace('+00:00','Z')
        entry={'id':p['id'],'topic':p['topic'],'status':'unknown',
               'scheduled_for':due.isoformat(),'source_tier':p['tier'],
               'copy_sha256':hashlib.sha256(p['text'].encode()).hexdigest()}
        ledger['posts'][p['id']]=entry
        save(ledger)
        try:
            response=client._graphql(CREATE_MUTATION,{'input':payload},mutation=True)
            created=response.get('createPost') or {}
            posted=created.get('post')
            if not isinstance(posted,dict) or not posted.get('id'):
                entry['status']='review_buffer_error'
                save(ledger)
                print(f"REVIEW {p['id']}: Buffer did not return a post ID; do not retry without dashboard verification")
                break
            entry['buffer_post_id']=str(posted['id'])
            entry['status']='accepted'
            save(ledger)
            print(f"BUFFER_ACCEPTED {p['id']} mode={mode} id={entry['buffer_post_id']}")
            result.append(entry)
        except BufferAPIError:
            print(f"REVIEW {p['id']}: ambiguous or failed Buffer response; no automatic retry")
            break
    return result


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('preview','publish'),default='preview')
    args=parser.parse_args(argv)
    now=datetime.now(timezone.utc)
    ledger=load_ledger()
    try: items=eligible(now, ledger)
    except ValueError as err:
        print(f'PULSE_UNAVAILABLE reason={err}')
        return 2
    print(f'PULSE {VERSION} mode={args.mode} eligible={len(items)} UTC={now.isoformat()}')
    for n,p in enumerate(items,1):
        print(f'POST {n} topic={p["topic"]} tier={p["tier"]} x_weight={weighted_length(p["text"])}')
        print(p['text']+'\n')
    if args.mode=='preview': return 0
    if not items:
        print('NO_NEW_POSTS; nothing was sent')
        return 0
    # Explicit one-time run and expected username prevent accidental crossposting.
    from buffer_publisher import BufferClient
    client=BufferClient(expected_username=EXPECTED_HANDLE)
    result=dispatch(client, items, now, ledger)
    print(f'PULSE_SUMMARY accepted={len(result)} planned={len(items)}')
    # Buffer acceptance != successful publication on X.
    return 0 if len(result)==len(items) else 1


if __name__=='__main__':
    sys.exit(main())
