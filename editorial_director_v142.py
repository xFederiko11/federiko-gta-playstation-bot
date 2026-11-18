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

STATE_DIR=Path(".state")
MIN_GAP=timedelta(minutes=22)
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

def allowed(now:datetime, *,root:Path|None=None, gap:timedelta=MIN_GAP)->tuple[bool,str]:
    if os.getenv("EDITORIAL_DIRECTOR_V142_ENABLED","false").lower()!="true":
        return True,"disabled"
    if now.tzinfo is None:raise ValueError("Timezone-aware time required")
    entries=read_reservations(root)
    if not entries:return True,"empty"
    latest=max(x["at"] for x in entries)
    dt=now.astimezone(timezone.utc)-latest
    if dt < gap:return False,"global_spacing"
    return True,"ready"

def candidate_sort_key(item):
    return (-priority(item["title"],item.get("source","")),item["published"])

def explain():
    items=read_reservations()
    last=max((x["at"] for x in items),default=None)
    now=datetime.now(timezone.utc)
    print("DIRECTOR",{"reservations":len(items),"last":last.isoformat() if last else None,
                       "allowed":allowed(now)[0],"reason":allowed(now)[1]})
if __name__=="__main__":
    explain()
