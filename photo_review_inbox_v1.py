"""Read-only PS5 screenshot review inbox. Public posts are LEADS, not licensed images.

One optional X recent-search request (requires explicit billing opt-in); exact
owner-curated URLs can be checked via public oEmbed with no X login. No binary
downloads, account actions, approval, screenshot reuse or social publishing.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
from html import escape, unescape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

SCHEMA="gta6-photo-intake-review-v1"
SEED_SCHEMA="gta6-manual-photo-links-v1"
RECENT="https://api.x.com/2/tweets/search/recent"
OEMBED="https://publish.x.com/oembed"
QUERY="@xFederiko11 #GTA6Italia FOTO has:images -is:retweet"
MAX_BYTES=250000
MAX_MANUAL=5
AGE=timedelta(days=7)
GUIDES={"soldi-facili-capitolo-1","soldi-2500-three-sheets-liquor",
        "registrare-auto-personale","scansionare-veicoli","sportive-randy-posizioni",
        "viaggio-rapido-taxi","studiare-animali","70-sfide-100-percento",
        "meditazione-capitolo-1","poligoni-concentrazione","prima-persona-glitch-ps5"}
POST_RE=re.compile(r"https://x\.com/([A-Za-z0-9_]{1,15})/status/([0-9]{8,25})")
CLAIM="sono autore e autorizzo gta vi italia a ripubblicare questa mia foto sul sito e sui social con credito"
SUBMISSION=re.compile(r"@xfederiko11\s+#gta6italia\s+foto\s+([a-z0-9-]+)\s+step:([1-5])/5\s+(PS5(?: Pro)?)\b",re.I)


def canonical(url):
    if not isinstance(url,str) or len(url)>160:
        return None
    try: p=urlsplit(url)
    except ValueError: return None
    if (p.scheme!="https" or p.hostname not in {"x.com","www.x.com","twitter.com","www.twitter.com"}
        or p.username or p.password or p.query or p.fragment or p.port not in (None,443)):
        return None
    m=re.fullmatch(r"/([A-Za-z0-9_]{1,15})/status/([0-9]{8,25})/?",p.path)
    return "https://x.com/"+m.group(1)+"/status/"+m.group(2) if m else None


def parse_time(raw):
    try:
        dt=datetime.fromisoformat(raw.replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (AttributeError,ValueError,OverflowError,TypeError): return None


def classify(text,author,post_id,when,now,proof):
    if now.tzinfo is None: raise ValueError("Timezone required")
    if (not isinstance(text,str) or not 35<=len(text)<=2500 or
        not isinstance(author,str) or not re.fullmatch(r"[A-Za-z0-9_]{1,15}",author) or
        not isinstance(post_id,str) or not re.fullmatch(r"[0-9]{8,25}",post_id) or
        when is None or not timedelta(0)<=now.astimezone(timezone.utc)-when<=AGE):
        return None
    m=SUBMISSION.search(text)
    if not m or m.group(1).lower() not in GUIDES or CLAIM not in " ".join(text.casefold().split()):
        return None
    return {"url":"https://x.com/"+author+"/status/"+post_id,"post_id":post_id,
            "author":"@"+author,"guide":m.group(1).lower(),"role":int(m.group(2)),
            "platform":m.group(3),"posted":when.isoformat(),
            "evidence":proof,"rights":"unverified_public_claim_only","review":"HUMAN_REQUIRED"}


def recent_api(token,open_fn=urlopen):
    if not isinstance(token,str) or len(token.strip())<15:
        raise ValueError("X API Bearer token unavailable")
    query=urlencode({"query":QUERY,"max_results":10,"tweet.fields":"created_at,attachments,author_id",
                     "expansions":"author_id,attachments.media_keys","user.fields":"username",
                     "media.fields":"type"})
    req=Request(RECENT+"?"+query,headers={"Authorization":"Bearer "+token,
                "Accept":"application/json","User-Agent":"GTA6Italia-PhotoReview/1.0"})
    with open_fn(req,timeout=10) as res: raw=res.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError("Oversized X response")
    data=json.loads(raw)
    if not isinstance(data,dict) or data.get("errors") or not isinstance(data.get("data",[]),list):
        raise ValueError("Invalid X API response")
    return data


def from_api(data,now):
    if not isinstance(data,dict):return []
    users={str(x.get("id")):x.get("username") for x in data.get("includes",{}).get("users",[])}
    photos={x.get("media_key") for x in data.get("includes",{}).get("media",[]) if x.get("type")=="photo"}
    found=[]
    for item in data.get("data",[])[:10]:
        attached=set((item.get("attachments") or {}).get("media_keys") or [])
        if not attached.intersection(photos):continue
        record=classify(item.get("text"),users.get(str(item.get("author_id"))),
                        str(item.get("id")),parse_time(item.get("created_at")),now,
                        "X_API_PHOTO_METADATA_NOT_VISUALLY_CHECKED")
        if record:found.append(record)
    return found


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,url):return None

class TweetText(HTMLParser):
    def __init__(self):super().__init__();self.depth=0;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag=="p":self.depth+=1
    def handle_endtag(self,tag):
        if tag=="p":self.depth=max(0,self.depth-1)
    def handle_data(self,body):
        if self.depth:self.parts.append(body)


def public_embed(url,open_fn=None):
    checked=canonical(url)
    if not checked:raise ValueError("Invalid exact X status URL")
    target=OEMBED+"?"+urlencode({"url":checked,"omit_script":"true"})
    req=Request(target,headers={"Accept":"application/json","User-Agent":"GTA6Italia-PhotoReview/1.0"})
    fetch=open_fn or build_opener(NoRedirect()).open
    with fetch(req,timeout=10) as res:
        if res.geturl().split("?")[0]!=OEMBED:raise ValueError("Unexpected oEmbed redirect")
        raw=res.read(32001)
    if len(raw)>32000:raise ValueError("Oversized oEmbed response")
    return json.loads(raw)


def from_embed(url,info,now):
    u=canonical(url)
    if not u or not isinstance(info,dict):return None
    handle,post_id=POST_RE.fullmatch(u).groups()
    a=urlsplit(str(info.get("author_url","")))
    if a.scheme!="https" or a.hostname not in {"x.com","www.x.com","twitter.com","www.twitter.com"} or a.path.strip("/").lower()!=handle.lower():
        return None
    html=info.get("html","")
    if not isinstance(html,str) or len(html)>20000:return None
    p=TweetText();p.feed(html)
    from x_free_public_embed_scout_v1 import status_time
    return classify(unescape(" ".join(p.parts)),handle,post_id,status_time(post_id),now,
                    "PUBLIC_OEMBED_TEXT_ONLY_NO_IMAGE_VERIFICATION")


def manual_links(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    urls=data.get("posts")
    if data.get("schema")!=SEED_SCHEMA or not isinstance(urls,list) or len(urls)>MAX_MANUAL:
        raise ValueError("Invalid manual X permalink manifest")
    checked=[canonical(u) for u in urls]
    if any(u is None for u in checked) or len(set(checked))!=len(checked):
        raise ValueError("Duplicate or unsafe X status URL")
    return checked


def collect(now,*,enabled=False,token="",manual=(),api=recent_api,embed=public_embed):
    if now.tzinfo is None:raise ValueError("Timezone required")
    candidates=[];errors=[];requests=0
    for link in list(manual)[:MAX_MANUAL]:
        try:
            item=from_embed(link,embed(link),now)
            if item:candidates.append(item)
        except (HTTPError,URLError,TimeoutError,OSError,TypeError,ValueError,KeyError):
            errors.append("public_oembed_unavailable")
    if enabled:
        if not token or len(token.strip())<15:
            errors.append("missing_X_BEARER_TOKEN")
        else:
            try:
                requests=1
                candidates.extend(from_api(api(token),now))
            except (HTTPError,URLError,TimeoutError,OSError,TypeError,ValueError,KeyError):
                errors.append("X_API_error")
    by_id={x["post_id"]:x for x in candidates}
    rows=sorted(by_id.values(),key=lambda x:x["posted"],reverse=True)[:15]
    state="ok" if rows else "off_without_manual_links" if not enabled and not manual else "no_verified_posts" if not errors else "source_unavailable"
    return {"schema":SCHEMA,"status":state,"candidates":rows,"requests":requests,
            "manual_checked":min(len(manual),MAX_MANUAL),"errors":errors,
            "auto_approved":0,"images_downloaded":0,"posts_published":0}


def markdown(report):
    if report.get("schema")!=SCHEMA:raise ValueError("Unrecognized report schema")
    lines=["# GTA VI — Screenshot PS5 da revisionare","",
           "Coda editoriale di possibili contributi, NON foto approvate e NON prova di consenso verificato.",
           "Ricerca X opzionale: disabilitata finché non viene autorizzata esplicitamente anche la spesa API.","",
           "- Stato: "+report["status"],
           "- Candidati da controllare: "+str(len(report["candidates"])),
           "- Chiamate X API: "+str(report["requests"]),
           "- Foto scaricate/approvate/pubblicate dal bot: 0/0/0.","",
           "## Procedura per la redazione","",
           "1. Aprire il post originale su X e verificare di persona la foto originale e gli spoiler.",
           "2. Accertare paternità e consenso specifico; il testo del post non dimostra da solo i diritti.",
           "3. Solo dopo revisione, preparare WebP locale e voce approvata nel manifest del sito con hash SHA-256.",
           "4. Non richiedere ai visitatori un account GitHub, password PSN o accesso remoto.","",
           "## Post candidati",""]
    if not report["candidates"]:
        lines+=["Nessun candidato verificato con le sorgenti ora disponibili.",""]
    for x in report["candidates"]:
        lines+=["### "+escape(x["author"])+" · "+escape(x["guide"])+" · passaggio "+str(x["role"]),
                "[Apri post X]("+x["url"]+")","","- "+x["platform"]+" · "+x["posted"],
                "- Verifica automatica: "+x["evidence"],
                "- **Da revisionare: foto e diritti non verificati.**",""]
    lines+=["Consulta il modulo pubblico: https://xfederiko11.github.io/gta-6/screenshot-ps5/invia/",""]
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--known",default="data/photo-intake-known-status-v1.json")
    p.add_argument("--output",default="previews/gta6-photo-review-inbox-v1.md")
    a=p.parse_args()
    data=collect(datetime.now(timezone.utc),enabled=os.getenv("X_PHOTO_INTAKE_ENABLED","false").lower()=="true",
                 token=os.getenv("X_BEARER_TOKEN",""),manual=manual_links(a.known))
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(markdown(data),encoding="utf-8")
    print("PHOTO_INBOX",data["status"],"candidates",len(data["candidates"]),
          "api_requests",data["requests"],"auto_approved",data["auto_approved"])


if __name__=="__main__":main()
