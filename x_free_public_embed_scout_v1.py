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
MAX_EMBEDS=8
MAX_DAILY_POSTS=5
MAX_ARTICLES=4
ARTICLE_HOSTS=frozenset({
    "www.powerpyx.com","powerpyx.com",
    "www.videogameschronicle.com","videogameschronicle.com",
    "www.pushsquare.com","pushsquare.com",
    "www.ign.com","ign.com",
    "www.gamespot.com","gamespot.com",
    "www.everyeye.it","everyeye.it",
    "www.multiplayer.it","multiplayer.it",
})
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

class _ArticleAnchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.posts=[]
    def handle_starttag(self,tag,attrs):
        if tag!="a":
            return
        for k,v in attrs:
            if k=="href" and isinstance(v,str):
                href=unescape(v)
                if len(href)<400 and POST_URL.fullmatch(href) and href not in self.posts:
                    self.posts.append(href)


def article_links_from_feed(content:bytes):
    """Extract only GTA VI publisher articles; NEVER synthesize X status URLs."""
    if len(content)>MAX_BYTES:
        raise ValueError("Feed too large")
    root=ET.fromstring(content)
    links=[]
    for node in root.iter():
        if node.tag.rsplit("}",1)[-1].lower() not in ("item","entry"):
            continue
        body=" ".join((x.text or "") for x in node.iter()).casefold()
        if not any(term in body for term in ("gta 6","gta vi","grand theft auto vi","leonida")):
            continue
        for child in node:
            if child.tag.rsplit("}",1)[-1].lower()!="link":
                continue
            url=(child.text or child.get("href") or "").strip()
            try:
                u=urlsplit(url)
                if (u.scheme!="https" or u.hostname not in ARTICLE_HOSTS or
                    u.username or u.password or u.port not in (None,443) or
                    u.query or u.fragment or not u.path.startswith("/") or len(url)>600):
                    continue
            except ValueError:
                continue
            if url not in links:links.append(url)
    return links


def links_from_article(content:bytes):
    """Only direct <a href=X/status/id> links in bounded trusted publisher HTML."""
    if len(content)>MAX_BYTES:
        raise ValueError("Publisher article HTML exceeds budget")
    parser=_ArticleAnchors()
    parser.feed(content.decode("utf-8","replace"))
    return parser.posts


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
    if handle.casefold()=="xfederiko11":
        return None
    lang="it" if re.search(r"(?i)\b(?:trofei|platino|missioni|aggiornamento|luminosit[aà]|guida)\b",body) else "en"
    kind=classify(body,lang)
    if not kind:
        return None
    topic,reply=kind
    # Publishing a news report is not an invitation to a discussion.
    # A question permits an editable human draft; other posts are source
    # references only and must NOT be described as reply opportunities.
    question=bool("?" in body or re.search(r"(?i)\b(?:come|dove|sapete|qualcun[oa]|aiuto|how|anyone|which|where|help)\b",body))
    return {"post_id":pid,"url":post_url,
            "author":"@"+handle,"created_utc":when.isoformat(),
            "excerpt":re.sub(r"\s+"," ",body)[:110],
            "topic":topic,"language":lang,"reply":reply if question else "",
            "intent":"question" if question else "source_reference",
            "verified_via":"public_x_oembed","human_send_only":True}

def collect(now,*,previous_ids=None,session=None,feeds=FEEDS):
    if now.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    http=session or requests.Session()
    config=json.loads(Path(feeds).read_text(encoding="utf-8"))
    if config.get("schema")!="v13.7":
        raise ValueError("Unrecognized trusted RSS config")
    urls=[]
    article_urls=[]
    article_checks=0
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
            article_urls.extend(article_links_from_feed(content))
        except (requests.RequestException,ET.ParseError,ValueError,TypeError,OSError):
            errors.append(src["name"])
    # A publisher often embeds a real tweet in its HTML while its RSS
    # description does not include the status URL. Read no more than four
    # explicitly allowlisted publisher articles and validate every X post
    # through the official oEmbed endpoint before showing a conversation.
    for article in dict.fromkeys(article_urls):
        if article_checks>=MAX_ARTICLES:
            break
        article_checks+=1
        try:
            with http.get(article,timeout=(4,10),stream=True,allow_redirects=False,
                          headers={"User-Agent":"FederikoGTAVI-PublisherLinks/1.0"}) as response:
                if response.status_code!=200:
                    continue
                typ=response.headers.get("Content-Type","") if hasattr(response,"headers") else ""
                if typ and "text/html" not in typ.lower():
                    continue
                body=b""
                for block in response.iter_content(65536):
                    body+=block
                    if len(body)>MAX_BYTES:
                        raise ValueError("Oversized publisher HTML")
            urls.extend(links_from_article(body))
        except (requests.RequestException,ValueError,TypeError,OSError):
            continue
    seen=set(previous_ids or [])
    posts=[]
    # Prioritize newest independently discovered post IDs. A publisher may
    # list stale embedded X messages first; chronological sorting avoids
    # exhausting the eight official oEmbed calls on old article decorations.
    clock=now.astimezone(timezone.utc)
    eligible=[]
    for url in dict.fromkeys(urls):
        match=POST_URL.fullmatch(url)
        if match and match.group(2) not in seen:
            timestamp=status_time(match.group(2))
            if timestamp is not None and timedelta(0)<=clock-timestamp<=MAX_AGE:
                eligible.append((timestamp,url))
    eligible.sort(reverse=True)
    for _,url in eligible:
        if checks>=MAX_EMBEDS or len(posts)>=MAX_DAILY_POSTS:
            break
        match=POST_URL.fullmatch(url)
        if not match or match.group(2) in seen:
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
    posts.sort(key=lambda p:(p["intent"]!="question",p["created_utc"]),reverse=False)
    return {"status":"ok" if posts else "no_source_verified_tweets",
            "posts":posts,"feed_errors":errors,"oembed_checks":checks,
            "eligible_recent_links":len(eligible),
            "verified_questions":sum(p["intent"]=="question" for p in posts),
            "verified_source_references":sum(p["intent"]=="source_reference" for p in posts),
            "article_checks":article_checks,"article_x_link_discoveries":len(set(urls)),
            "discovered_links":len(set(urls))}


def section(data):
    lines=["## 🆓 Tweet trovati senza API X a pagamento", "",
           "Fonti: permalink diretti nei feed RSS o nei link HTML delle pagine "
           "delle testate già monitorate, poi verifica dell'embed pubblico ufficiale X. "
           "**Non è una ricerca completa di X**: se le "
           "fonti non riportano URL a tweet recenti, non vengono inventati risultati.",""]
    lines+=["Articoli di testate controllati: "+str(data.get("article_checks",0))+
            " (limite "+str(MAX_ARTICLES)+").",
            "Permalink X candidati rintracciati (non tutti verificati): "+
            str(data.get("discovered_links",0))+
            "; embed originali interrogati: "+str(data.get("oembed_checks",0))+".",
            "Candidati recenti dall'ID X (NON verificati): "+str(data.get("eligible_recent_links",0))+".",
            "Domande esterne confermate da oEmbed: "+str(data.get("verified_questions",sum(p.get("intent")=="question" for p in data["posts"])))+
            "; altri post verificati usabili solo come riferimenti: "+
            str(data.get("verified_source_references",sum(p.get("intent")=="source_reference" for p in data["posts"])))+".",""]
    if not data["posts"]:
        lines+=["Nessun permalink esterno recente confermato tramite X oEmbed. "
                "Le ricerche generiche NON sono post verificati.",""]
    for p in data["posts"]:
        lines+=["### "+p["author"]+" · "+p["topic"],
                "[Apri il post originale]("+p["url"]+")","",
                "Pubblicazione stimata dall'ID X: "+p["created_utc"],
                "Estratto dall'embed: "+p["excerpt"],""]
        if p.get("intent")=="question" and p.get("reply"):
            lines+=["**Domanda verificata nell'embed: bozza condizionale da adattare solo dopo la lettura:**","",
                    "~~~text",p["reply"],"~~~",""]
        else:
            lines+=["**Solo fonte verificata, NON una richiesta d'aiuto.** "
                    "Nessuna bozza automatica: apri il post soltanto se pertinente.",""]
        lines+=["La verifica conferma la presenza di un embed pubblico, non "
                "l'accuratezza del tweet né l'appropriatezza della risposta.",""]
    return "\n".join(lines)+"\n"
