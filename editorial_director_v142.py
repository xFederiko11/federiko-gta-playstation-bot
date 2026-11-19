"""Read-only coordination for independent no-cost GTA VI publishing workflows.

The jobs are serialised by one GitHub Actions concurrency group. Each of them
inspects the other jobs' existing ledgers to enforce global spacing. This
does not erase their own dedupe journals or attempt to act as a paid service.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import hashlib

STATE_DIR=Path(".state")
# Balanced launch-phase voluntary limits for a new X profile. These are NOT
# official X thresholds and provide no immunity from account restrictions.
# Applies across editorial, official news, special campaigns and monitor jobs.
MIN_GAP=timedelta(minutes=90)
MAX_AUTOMATED_DELIVERIES_24H=8
# Use the stronger launch pulse only during the first release window.
# Thereafter automatically reduce volume without changing GitHub settings.
BOOST_UNTIL=datetime(2026,11,30,0,0,tzinfo=timezone.utc)
STEADY_MAX_AUTOMATED_DELIVERIES_24H=6
STEADY_MIN_GAP=timedelta(minutes=120)
ROLLING_WINDOW=timedelta(hours=24)


def current_limits(now:datetime)->tuple[int,timedelta]:
    """Temporary release boost, automatically tapering to a steady cadence."""
    if now.tzinfo is None:
        raise ValueError("Timezone-aware date required")
    clock=now.astimezone(timezone.utc)
    return ((MAX_AUTOMATED_DELIVERIES_24H,MIN_GAP) if clock<BOOST_UNTIL
            else (STEADY_MAX_AUTOMATED_DELIVERIES_24H,STEADY_MIN_GAP))
BLOCK=re.compile(r"\b(?:parodi[ae]|spoof|parody|volvy|devolver|gta[- ]?like|rumou?r(?:s|ed)?|leaks?|fake|fan[- ]?made|deepfake|clickbait|giveaway|sponsored|sponsorizzat[oa]|gossip|actress\s+based|basat[oa]\s+su\s+un['a]?\s+attrice)\b",re.I)
HIGH=re.compile(r"\b(?:trofe[io]|troph(?:y|ies)|platino|platinum|powerpyx|100\s?%|ps5\s*pro|performance|fps|patch|hotfix|rockstar\s+games|launch|lancio|guida|walkthrough|glitch|veicol[io]|collezionabil[ie]|collectibles?)\b",re.I)
MID=re.compile(r"\b(?:gta\s*\+|bonus|missioni|mission|gameplay|trailer|armi|weapon|online|mappa|map|vice city)\b",re.I)

def priority(title: str, source: str="") -> int:
    """Score topic relevance without claiming article facts are verified."""
    if BLOCK.search(title):return -100
    score=30
    if source in {"PowerPyx","Rockstar Games","PlayStation"}:score+=35
    if HIGH.search(title):score+=35
    elif MID.search(title):score+=15
    if re.search(r"\b(?:how\s+to|come\s+fare|guide|guida|troph(?:y|ies)|trofe[io])\b",title,re.I):score+=10
    return min(score,100)

def _dt(value):
    if not value:return None
    try:
        if isinstance(value,(int,float)):return datetime.fromtimestamp(value,tz=timezone.utc)
        x=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return x.astimezone(timezone.utc) if x.tzinfo else None
    except (ValueError,OverflowError,TypeError):return None

def read_reservations(root:Path|None=None):
    """Read only existing delivery ledgers; never mutate their schema."""
    root=root or STATE_DIR
    names={
        "editorial-autopilot-v137.json":"entries",
        "special-campaign-v139.json":"entries",
        "launch-watch-v134.json":"posts",
        "trophies-v142.json":"entries",
        "monitor-publication-v142.json":"entries",
    }
    result=[]
    for filename,field in names.items():
        path=root/filename
        if not path.exists():continue
        try:
            data=json.loads(path.read_text(encoding="utf-8"))
            records=data.get(field,{})
            if not isinstance(records,dict):continue
            for key,entry in records.items():
                if not isinstance(entry,dict):continue
                stamp=_dt(entry.get("reserved_utc") or entry.get("reserved_at"))
                if stamp and entry.get("status") not in ("rejected",):
                    result.append({"at":stamp,"key":key,"workflow":filename,
                                   "status":entry.get("status","reserved"),
                                   "url":str(entry.get("url") or "")})
        except (OSError,ValueError):
            # Fail closed: malformed existing ledger must not be bypassed.
            raise RuntimeError("Publication ledger cannot be read: "+filename)
    return result

def allowed(now:datetime, *,root:Path|None=None, gap:timedelta|None=None)->tuple[bool,str]:
    if os.getenv("EDITORIAL_DIRECTOR_V142_ENABLED","false").lower()!="true":
        return True,"disabled"
    if now.tzinfo is None:raise ValueError("Timezone-aware time required")
    entries=read_reservations(root)
    if not entries:return True,"empty"
    clock=now.astimezone(timezone.utc)
    daily_budget, policy_gap = current_limits(clock)
    effective_gap = policy_gap if gap is None else max(gap,policy_gap)
    # Reservations/uncertain submissions count too: false positives reduce
    # volume, while assuming failed deliveries could produce duplicates.
    recent=[x for x in entries if clock-ROLLING_WINDOW <= x["at"] <= clock]
    if len(recent)>=daily_budget:
        return False,"global_rolling_24h_budget"
    latest=max(x["at"] for x in entries)
    dt=clock-latest
    if dt < effective_gap:return False,"global_spacing"
    return True,"ready"

def candidate_sort_key(item):
    return (-priority(item["title"],item.get("source","")),item["published"])

def note_monitor_attempt(event:dict, now:datetime, root:Path|None=None):
    """Append a privacy-minimal monitor publication reservation BEFORE Buffer.

    The monitor Action commits this file on completion. Combined with a global
    Actions concurrency group, subsequent jobs can observe its timestamp.
    """
    if os.getenv("EDITORIAL_DIRECTOR_V142_ENABLED","false").lower()!="true":
        return
    root=root or STATE_DIR
    root.mkdir(exist_ok=True,parents=True)
    path=root/"monitor-publication-v142.json"
    if path.exists():
        state=json.loads(path.read_text(encoding="utf-8"))
        if state.get("schema")!="monitor-publication-v142":
            raise ValueError("Unknown monitor posting ledger")
    else:
        state={"schema":"monitor-publication-v142","entries":{}}
    source=str(event.get("event_key") or event.get("source_url") or "new_event")
    identifier=os.getenv("GITHUB_RUN_ID","local") + "-" + hashlib.sha256(source.encode()).hexdigest()[:16]
    if identifier in state["entries"]:
        raise ValueError("Duplicate monitor publish attempt")
    state["entries"][identifier]={
        "reserved_utc":now.astimezone(timezone.utc).isoformat(),
        "status":"attempted","kind":"official-monitor"}
    # Truncate bounded historical entries; old records are still in encrypted bot state.
    if len(state["entries"])>400:
        state["entries"]=dict(list(state["entries"].items())[-400:])
    temp=path.with_suffix(".tmp")
    temp.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(path)


def explain():
    items=read_reservations()
    last=max((x["at"] for x in items),default=None)
    now=datetime.now(timezone.utc)
    print("DIRECTOR",{"reservations":len(items),"last":last.isoformat() if last else None,
                       "allowed":allowed(now)[0],"reason":allowed(now)[1]})
if __name__=="__main__":
    explain()
