"""Reviewed article rotation. The existing editorial director and publisher
remain the only reservation and delivery authorities. No direct mutations.
"""
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
from pathlib import Path
from html.parser import HTMLParser
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
        article_release=stamp(article.get("updated_utc")) or released
        if article_release>now:continue
        if last<article_release and age>=GAPS["updated"]:reason,rank="updated",0
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
                title=article["title"],text=text,source=SOURCE,media_url=cover_for(url),sig="",
                rotation_variant=variant["id"],rotation_revision=cfg["revision"],
                rotation_reason=reason)))
            break
    return [r[-1] for r in sorted(ranked,key=lambda r:r[:4])]


class ArticleCover(HTMLParser):
    """Exact canonical, single H1, and shared 1200x630 cover immediately after H1."""
    def __init__(self):
        super().__init__()
        self.canon=[];self.og=[];self.twitter=[];self.covers=[]
        self.h1=0;self.after_h1=False;self.in_cover=False;self.banner=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="link" and a.get("rel")=="canonical":self.canon.append(a.get("href"))
        if tag=="meta" and a.get("property")=="og:image":self.og.append(a.get("content"))
        if tag=="meta" and a.get("name")=="twitter:image":self.twitter.append(a.get("content"))
        if tag=="h1":self.h1+=1
        if tag=="figure" and "ci-section-cover" in a.get("class","").split():self.banner=True
        if tag=="figure" and a.get("data-article-cover")=="shared-social":
            self.in_cover=True
            self.covers.append({"after_h1":self.after_h1,"images":[]})
        if tag=="img" and self.in_cover:
            self.covers[-1]["images"].append((a.get("src"),a.get("width"),a.get("height")))
        if tag not in {"figure","img","figcaption","a"}:self.after_h1=False
    def handle_endtag(self,tag):
        if tag=="h1":self.after_h1=True
        if tag=="figure":
            self.in_cover=False;self.after_h1=False
    def valid(self,url):
        cover=cover_for(url)
        return (cover is not None and self.h1==1 and not self.banner
                and self.canon==[url] and self.og==self.twitter==[cover]
                and self.covers==[{"after_h1":True,"images":[(cover,"1200","630")]}])


def live_article(url,session=None):
    """Read public HTML; no redirect, API, secret, or arbitrary host."""
    import requests
    if not canonical_page_path(url):return False
    try:
        with (session or requests).get(url,timeout=(3,7),stream=True,
                allow_redirects=False,headers={"User-Agent":"GTA6Italia-ArticleRotation/1.0"}) as r:
            if r.status_code!=200 or r.url!=url:return False
            data=bytearray()
            for chunk in r.iter_content(16384):
                data.extend(chunk)
                if len(data)>1_500_000:return False
            parser=ArticleCover()
            parser.feed(data.decode("utf-8",errors="replace"))
            return parser.valid(url)
    except (requests.RequestException,OSError,ValueError):
        return False


def reviewed_config(now,config=None):
    """Only explicitly reviewed articles may progress from inventory to queue."""
    cfg=load() if config is None else config
    return dict(cfg,articles=[a for a in cfg.get("articles",[])
              if (at:=stamp(a.get("reviewed_utc"))) is not None and at<=now])


def receipt_ids(path=Path("data/x-permalinks-v1.json")):
    """Bind past Sent receipts to exactly the same canonical article."""
    try:
        d=json.loads(Path(path).read_text(encoding="utf-8"))
        if d.get("schema")!="verified-buffer-x-permalinks-v1":return set()
        return {(p["article_url"],p["buffer_id"]) for p in d["posts"]
                if p.get("verified_by")=="Buffer sent Post.externalLink on verified @xFederiko11 channel"
                and canonical_page_path(p.get("article_url"))
                and isinstance(p.get("buffer_id"),str)
                and stamp(p.get("sent_at"))}
    except (OSError,KeyError,TypeError,ValueError):
        return set()


def receipt_confirmed(url,state,receipts):
    return any(e.get("url")==url and e.get("status")=="sent"
               and (url,e.get("buffer_id")) in receipts
               for e in state.get("entries",{}).values())


def ready_plans(state,now,*,config=None,receipts=None,interest=None):
    cfg=reviewed_config(now,config)
    if cfg.get("enabled") is not True:return []
    receipts=receipt_ids() if receipts is None else receipts
    interest=measured_interest(now) if interest is None else interest
    return [i for i in plans(state,now,config=cfg,interest=interest)
            if receipt_confirmed(i["url"],state,receipts)]


def candidate(state,now,*,live_checker=live_article,config=None,receipts=None):
    # Bounded work: at most two reviewed, eligible article probes per scan.
    for item in ready_plans(state,now,config=config,receipts=receipts)[:2]:
        if live_checker(item["url"]):return item
    return None


def authorize(item,state,now,*,config=None,receipts=None):
    """Exact generated variant + prior Sent + narrow same-article image reuse."""
    if item.get("source")!=SOURCE:return False
    from image_registry_v12 import identity
    from social_media_gate_v2 import ACTIVE_STATUSES
    url=item.get("url");image=cover_for(url)
    if not image or item.get("media_url")!=image:return False
    # Even an authorized rotation cannot reuse a different article's image.
    for row in state.get("entries",{}).values():
        if row.get("status") in ACTIVE_STATUSES and identity(row.get("media_url"))==identity(image):
            if row.get("url")!=url or row.get("status")!="sent":return False
    for plan in ready_plans(state,now,config=config,receipts=receipts):
        expected=plan
        if item.get("photo_kind"):
            from game_photo_policy_v1 import single_photo_item
            expected=single_photo_item(plan,item["photo_kind"])
            if not expected or item.get("thread"):
                continue
        if all(item.get(k)==expected.get(k) for k in
               ("key","url","source","text","media_url","rotation_reason","rotation_revision","rotation_variant","photo_kind")):
            return True
    return False


def delivery_authorized(entry,state,now,*,live_checker=live_article,config=None,receipts=None):
    key=entry.get("key")
    if not key or state.get("entries",{}).get(key)!=entry or entry.get("status")!="reserved":
        return False
    # Recheck without counting only this reservation against itself; all other
    # pending entries, cooldowns and same-cover conflicts remain in force.
    prior=dict(state,entries={k:e for k,e in state["entries"].items() if k!=key})
    return authorize(entry,prior,now,config=config,receipts=receipts) and live_checker(entry["url"])
