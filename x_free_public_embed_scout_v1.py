"""Free best-effort Social Radar using trusted news RSS links and X's public oEmbed.

No X search API, no X session, no Nitter/proxies, no login or guest scraping.
Only exact public post URLs discovered in already trusted publisher feeds are
checked through the official public embed provider. Low yield is expected.
"""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
import requests

from x_verified_social_radar_v1 import classify

FEEDS=Path("editorial-autopilot-v137-sources.json")
OEMBED="https://publish.x.com/oembed"
MAX_FEEDS=8
MAX_BYTES=500_000
MAX_EMBEDS=6
MAX_DAILY_POSTS=5
MAX_AGE=timedelta(hours=72)
POST_URL=re.compile(r"https?://(?:www\.)?(?:x\.com|twitter\.com)/([A-Za-z0-9_]{1,15})/status/([0-9]{8,25})",re.I)
TWITTER_EPOCH_MS=1288834974657

class _TweetBody(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth=0
        self.chunks=[]
    def handle_starttag(self,tag,attrs):
        if tag=="p":
            self.depth+=1
    def handle_endtag(self,tag):
        if tag=="p":
            self.depth=max(0,self.depth-1)
    def handle_data(self,data):
        if self.depth:
            self.chunks.append(data)

def status_time(post_id):
    try:
        stamp=((int(post_id)>>22)+TWITTER_EPOCH_MS)/1000
        return datetime.fromtimestamp(stamp,tz=timezone.utc)
    except (ValueError,OverflowError,OSError):
        return None

def links_from_feed(content):
    if len(content)>MAX_BYTES:
        raise ValueError("Feed too large")
    root=ET.fromstring(content)
    found=[]
    for node in root.iter():
        if node.tag.rsplit("}",1)[-1].lower() not in ("item","entry"):
            continue
        body=" ".join((x.text or "") for x in node.iter())
        body=unescape(body)
        for match in POST_URL.finditer(body):
            handle,pid=match.groups()
            url="https://x.com/"+handle+"/status/"+pid
            if url not in found:
                found.append(url)
    return found

def embed_to_candidate(post_url,data,now):
    parsed=urlsplit(post_url)
    match=POST_URL.fullmatch(post_url)
    if parsed.scheme!="https" or not match:
        return None
    handle,pid=match.groups()
    clock=now.astimezone(timezone.utc)
    when=status_time(pid)
    if when is None or not timedelta(0)<=clock-when<=MAX_AGE:
        return None
    if not isinstance(data,dict):
        return None
    author_url=data.get("author_url")
    ap=urlsplit(author_url or "")
    if ap.scheme!="https" or ap.hostname not in ("twitter.com","x.com","www.x.com","www.twitter.com"):
        return None
    if ap.path.strip("/").casefold()!=handle.casefold():
        return None
    html=data.get("html","")
    if not isinstance(html,str) or len(html)>20_000:
        return None
    parser=_TweetBody()
    parser.feed(html)
    body=unescape(" ".join(parser.chunks)).strip()
    if len(body.split())<8:
        return None
    if re.search(r"(?i)\b(giveaway|airdrop|follow ?back|crypto|leak|spoiler)\b",body):
        return None
    lang="it" if re.search(r"(?i)\b(?:trofei|platino|missioni|aggiornamento|luminosit[aà]|guida)\b",body) else "en"
    kind=classify(body,lang)
    if not kind:
        return None
    topic,reply=kind
    return {"post_id":pid,"url":post_url,
            "author":"@"+handle,"created_utc":when.isoformat(),
            "excerpt":re.sub(r"\s+"," ",body)[:110],
            "topic":topic,"language":lang,"reply":reply,
            "verified_via":"public_x_oembed","human_send_only":True}

def collect(now,*,previous_ids=None,session=None,feeds=FEEDS):
    if now.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    http=session or requests.Session()
    config=json.loads(Path(feeds).read_text(encoding="utf-8"))
    if config.get("schema")!="v13.7":
        raise ValueError("Unrecognized trusted RSS config")
    urls=[]
    checks=0
    errors=[]
    for src in config.get("sources",[])[:MAX_FEEDS]:
        if not src.get("enabled",True):
            continue
        url=src["feed"]
        host=urlsplit(url).hostname
        if urlsplit(url).scheme!="https" or host not in src.get("feed_domains",[]):
            continue
        try:
            with http.get(url,timeout=(4,10),stream=True,allow_redirects=False,
                          headers={"User-Agent":"FederikoGTAVI-RSS-Curation/1.0"}) as response:
                if response.status_code!=200:
                    continue
                content=b""
                for block in response.iter_content(65536):
                    content+=block
                    if len(content)>MAX_BYTES:
                        raise ValueError("Oversized RSS")
            urls.extend(links_from_feed(content))
        except (requests.RequestException,ET.ParseError,ValueError,TypeError,OSError):
            errors.append(src["name"])
    seen=set(previous_ids or [])
    posts=[]
    for url in dict.fromkeys(urls):
        if checks>=MAX_EMBEDS or len(posts)>=MAX_DAILY_POSTS:
            break
        match=POST_URL.fullmatch(url)
        if not match or match.group(2) in seen:
            continue
        stamp=status_time(match.group(2))
        if stamp is None or not timedelta(0)<=now.astimezone(timezone.utc)-stamp<=MAX_AGE:
            continue
        checks+=1
        try:
            with http.get(OEMBED,params={"url":url,"omit_script":"true"},
                          timeout=(4,10),allow_redirects=False,
                          headers={"User-Agent":"FederikoGTAVI-PublicEmbed/1.0"}) as response:
                if response.status_code!=200:
                    continue
                if len(response.content)>30_000:
                    continue
                data=response.json()
            entry=embed_to_candidate(url,data,now)
            if entry:
                posts.append(entry)
                seen.add(entry["post_id"])
        except (requests.RequestException,ValueError,TypeError,OSError):
            continue
    return {"status":"ok" if posts else "no_source_verified_tweets",
            "posts":posts,"feed_errors":errors,"oembed_checks":checks,
            "discovered_links":len(set(urls))}


def section(data):
    lines=["## 🆓 Tweet trovati senza API X a pagamento", "",
           "Fonti: permalink in RSS di testate già monitorate, poi verifica dell'embed "
           "pubblico ufficiale X. **Non è una ricerca completa di X**: se le "
           "fonti non riportano URL a tweet recenti, non vengono inventati risultati.",""]
    if not data["posts"]:
        lines+=["Nessun permalink recente verificabile dagli RSS oggi.",""]
    for p in data["posts"]:
        lines+=["### "+p["author"]+" · "+p["topic"],
                "[❤️ Apri il tweet]("+p["url"]+")","",
                "Pubblicazione stimata dall'ID X: "+p["created_utc"],
                "Estratto dall'embed: "+p["excerpt"],"",
                "**Risposta da copiare e adattare dopo la lettura:**", "",
                "~~~text",p["reply"],"~~~","",
                "La verifica conferma la presenza di un embed pubblico, non "
                "l'accuratezza del tweet né l'appropriatezza della risposta.",""]
    return "\n".join(lines)+"\n"
