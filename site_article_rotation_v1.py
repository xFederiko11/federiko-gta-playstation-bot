"""Read-only owned-article rotation planning, pending final site approval.

Never mutates the delivery ledger or creates Buffer posts.
"""
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
from pathlib import Path
import csv
import hashlib
import json
from editorial_seo_v135 import x_weight
from social_media_gate_v2 import canonical_page_path, cover_for

BASE="https://xfederiko11.github.io/gta-6/"
SOURCE="Rilanci GTA VI Italia"
ROME=ZoneInfo("Europe/Rome")
CONFIG=Path("site-article-rotation-v1.json")
PENDING={"reserved","attempted","accepted_pending","scheduled","uncertain","review"}
GAPS={"updated":7,"measured_interest":14,"periodic":30}


def stamp(value):
    try:
        d=datetime.fromisoformat(value.replace("Z","+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (AttributeError,TypeError,ValueError):
        return None


def load():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def measured_interest(now,metrics=Path("metrics-manual-v142.csv"),
                      receipts=Path("data/x-permalinks-v1.json")):
    """Actual recent replies/reposts linked to verified owned X receipts."""
    try:
        data=json.loads(Path(receipts).read_text(encoding="utf-8"))
        if data.get("schema")!="verified-buffer-x-permalinks-v1":
            return {}
        urls={p["x_url"]:p["article_url"] for p in data["posts"]
              if p.get("verified_by")=="Buffer sent Post.externalLink on verified @xFederiko11 channel"
              and canonical_page_path(p.get("article_url")) is not None}
        result={}
        with Path(metrics).open(encoding="utf-8",newline="") as f:
            for row in csv.DictReader(f):
                url=urls.get(row.get("post_url"))
                if not url:continue
                try: day=date.fromisoformat(row["date"])
                except (ValueError,TypeError,KeyError):continue
                if not 0<=(now.astimezone(ROME).date()-day).days<=7:continue
                replies=row.get("replies") or ""
                shares=row.get("reposts") or ""
                a=int(replies) if replies.isdigit() else 0
                b=int(shares) if shares.isdigit() else 0
                if a>=3 or b>=5:
                    result[url]=max(result.get(url,0),a+b)
        return result
    except (OSError,ValueError,TypeError,KeyError):
        return {}


def normalize(text):
    return " ".join(str(text or "").casefold().split())


def plans(state,now,*,config=None,interest=None):
    """Rank reviewed variants without authorizing a publication."""
    if now.tzinfo is None:raise ValueError("Timezone required")
    now=now.astimezone(timezone.utc)
    cfg=load() if config is None else config
    released=stamp(cfg.get("released_utc"))
    if (cfg.get("schema")!="owned-article-rotation-v1"
        or cfg.get("enabled") is not True or not released or released>now
        or not cfg.get("revision")):return []
    entries=state["entries"]
    for e in entries.values():
        if e.get("source")!=SOURCE:continue
        at=stamp(e.get("reserved_utc"))
        if (not at or at.astimezone(ROME).date()==now.astimezone(ROME).date()
                or now-at<timedelta(hours=20)):return []
    interest=interest or {}
    ranked=[];seen=set()
    for article in cfg["articles"]:
        url=BASE+article["path"]
        if not canonical_page_path(url) or url in seen:
            raise ValueError("Invalid or duplicate article")
        seen.add(url)
        history=[e for e in entries.values() if e.get("url")==url]
        if any(e.get("status") in PENDING for e in history):continue
        sent=[e for e in history if e.get("status")=="sent"]
        if not sent:continue
        times=[stamp(e.get("completed_utc") or e.get("reserved_utc")) for e in sent]
        if any(t is None or t>now for t in times):continue
        last=max(times);age=(now-last).total_seconds()/86400
        score=interest.get(url,0)
        if not isinstance(score,int) or isinstance(score,bool) or score<0:score=0
        if last<released and age>=GAPS["updated"]:reason,rank="updated",0
        elif score and age>=GAPS["measured_interest"]:reason,rank="measured_interest",1
        elif age>=GAPS["periodic"]:reason,rank="periodic",2
        else:continue
        old={normalize(e.get("text")) for e in history}
        for e in history:
            old.update(normalize(x) for x in (e.get("thread") or []) if isinstance(x,str))
        for variant in article["variants"]:
            body=variant["text"].strip()
            if not body or "://" in body or "@" in body:raise ValueError("Invalid original copy")
            text=body+"\n\n"+url+"\n\n#GTAVI"
            if not 80<=x_weight(text)<=235:raise ValueError("Copy budget")
            key=hashlib.sha256(("rotation-v1:"+url+":"+variant["id"]).encode()).hexdigest()[:24]
            if key in entries or normalize(text) in old:continue
            ranked.append((rank,-score,last,url,dict(key=key,url=url,
                title=article["title"],text=text,source=SOURCE,media_url=cover_for(url),
                rotation_variant=variant["id"],rotation_revision=cfg["revision"],
                rotation_reason=reason)))
            break
    return [r[-1] for r in sorted(ranked,key=lambda r:r[:4])]
