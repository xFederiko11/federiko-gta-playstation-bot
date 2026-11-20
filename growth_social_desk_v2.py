"""Daily mobile-first growth desk from already verified, read-only X radar.

Read the existing GitHub Issue #48 body (may be empty). Extract a small number
of exact, attributed X post permalinks plus validated review-only replies.
Never claim unverifiable search results are live tweets, and NEVER send replies.
If the official API is disabled and RSS/oEmbed finds nothing, offer targeted
X searches clearly labelled as unverified discovery links instead.
"""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from pathlib import Path
import re
from urllib.parse import parse_qs,quote,urlsplit
from x_community_review_v1 import search_link
from x_free_public_embed_scout_v1 import status_time
from editorial_seo_v135 import x_weight

MAX_REPLIES=5
MAX_AGE_HOURS=72
POST_LINK=re.compile(r"https://x\.com/([A-Za-z0-9_]{1,15})/status/([0-9]{8,25})")
OFFICIAL_LINE=re.compile(
    r"\[Apri tweet / metti cuore\]\((https://x\.com/[A-Za-z0-9_]{1,15}/status/[0-9]{8,25})\)"
    r"\s*\|\s*\[Apri risposta precompilata\]\((https://x\.com/intent/tweet\?[^\s)]+)\)")
FREE_LINE=re.compile(r"\[❤️ Apri il tweet\]\((https://x\.com/[A-Za-z0-9_]{1,15}/status/[0-9]{8,25})\)")
FREE_REPLY=re.compile(r"\*\*Risposta da copiare e adattare dopo la lettura:\*\*\s+~~~text\s+(.+?)\s+~~~",re.S)
QUERIES=(
    ("💰 Soldi iniziali", '("GTA VI" OR "GTA 6") (soldi OR farming OR guadagnare) lang:it -filter:retweets'),
    ("🚗 Auto rare e garage", '("GTA VI" OR "GTA 6") (auto OR veicoli OR garage) lang:it -filter:retweets'),
    ("🏆 Trofei e platino", '("GTA VI" OR "GTA 6") (trofei OR platino) lang:it -filter:retweets'),
    ("🗺️ Mappe e posizioni", '("GTA VI" OR "GTA 6") (mappa OR posizione OR dove) lang:it -filter:retweets'),
    ("🎮 Missioni PS5", '("GTA VI" OR "GTA 6") (missioni OR PS5 Pro) lang:it -filter:retweets')
)


def _tweet(url:str,now:datetime,seen:set):
    match=POST_LINK.fullmatch(url)
    if not match or match.group(2) in seen or match.group(1).casefold()=="xfederiko11":
        return None
    created=status_time(match.group(2))
    if created is None or not timedelta(0)<=now.astimezone(timezone.utc)-created<=timedelta(hours=MAX_AGE_HOURS):
        return None
    return {"id":match.group(2),"author":"@"+match.group(1),"url":url,"created_utc":created.isoformat()}


def _reply(text:str):
    text=text.strip()
    if not 20<=len(text)<=280 or x_weight(text)>280:
        return None
    if re.search(r"https?://|@\w+|#\w+",text):
        return None
    return text


def parse_verified(markdown:str,now:datetime,*,limit=MAX_REPLIES)->list[dict]:
    if now.tzinfo is None:raise ValueError("Timezone-aware UTC required")
    if not 1<=limit<=MAX_REPLIES:raise ValueError("Maximum five replies")
    result=[]
    seen=set()
    # The official radar provides both tweet URL and an intent created from
    # the exact API post ID. Reject changed IDs, non-X hosts, external links,
    # untrusted lengths and any unsupported HTML in a human-facing draft.
    for match in OFFICIAL_LINE.finditer(markdown):
        url,intent=match.groups()
        post=_tweet(url,now,seen)
        if not post:continue
        parts=urlsplit(intent)
        if parts.scheme!="https" or parts.hostname!="x.com" or parts.path!="/intent/tweet":
            continue
        args=parse_qs(parts.query,strict_parsing=True)
        if set(args)!={"text","in_reply_to"} or args["in_reply_to"]!=[post["id"]]:
            continue
        reply=_reply(args["text"][0])
        if not reply:continue
        seen.add(post["id"])
        result.append({**post,"reply":reply,"language":"und",
                       "evidence":"x_api_v2_recent_search","needs_human_review":True})
        if len(result)>=limit:return result
    # Official free oEmbed validates author and text, but is not a substitute
    # for the paid complete X search. Only add when a real permalink exists.
    for block in re.split(r"(?=^### @)",markdown,flags=re.M):
        source=FREE_LINE.search(block)
        reply_match=FREE_REPLY.search(block)
        if not source or not reply_match:continue
        post=_tweet(source.group(1),now,seen)
        if not post:continue
        reply=_reply(reply_match.group(1))
        if not reply:continue
        seen.add(post["id"])
        result.append({**post,"reply":reply,"language":"und",
                       "evidence":"official_public_oembed","needs_human_review":True})
        if len(result)>=limit:break
    return result


def render(report:str,now:datetime,*,max_posts=MAX_REPLIES)->str:
    posts=parse_verified(report,now,limit=max_posts)
    lines=["## ⚡ 5 minuti al giorno: opportunità X verificabili","",
           "Bio e post fissato: **già aggiornati il 20 novembre**; non rifarli.","",
           f"**Tweet specifici recenti verificati: {len(posts)} / {max_posts}.** "
           "La coda non aggiunge post al calendario Buffer e non mette cuori, follow o risposte al posto tuo.",""]
    if posts:
        lines.extend(["### 👀 Tweet reali da valutare",""])
        for index,post in enumerate(posts,1):
            q=quote(post["reply"],safe="")
            intent="https://x.com/intent/tweet?in_reply_to="+post["id"]+"&text="+q
            lines.extend([f"#### {index}. {post['author']}",
                          f"[Apri il tweet]({post['url']}) · [Rispondi con bozza]({intent})",
                          f"- Evidenza: {post['evidence']}; **non è approvazione dei fatti**.",
                          "- Leggi il tweet intero prima di premere Invia. Se non è pertinente, salta.",
                          "~~~text",post["reply"],"~~~",""])
    else:
        lines.extend(["**Nessun tweet specifico verificabile oggi.** Le ricerche qui sotto sono link a risultati di X, **non tweet confermati**. Non copiare una bozza fuori contesto.",""])
    lines.extend(["### 🔎 Ricerche prioritarie — apri soltanto se hai 2 minuti",""])
    for title,query in QUERIES:
        lines.append("- ["+title+"]("+search_link(query)+")")
    lines.extend(["","### ✅ L'unica parte manuale","",
                  "1. Apri un tweet pertinente e leggilo.",
                  "2. Se c'è una soluzione verificabile, apri la risposta precompilata e adattala.",
                  "3. Premi **Invia** su X soltanto se la risposta contribuisce realmente alla conversazione.",
                  "4. I like e i follow rimangono facoltativi e manuali; mai engagement automatico.",
                  "","**No spam:** niente risposte promozionali non richieste, ripetute o create per keyword; non inserire link al sito senza una richiesta pertinente.",
                  "","[Social Radar verificato (#48)](https://github.com/xFederiko11/federiko-gta-playstation-bot/issues/48)"
                  " · [Regole X](https://help.x.com/en/rules-and-policies/x-automation)",""])
    return "\n".join(lines)


def render_file(path:Path|str,now:datetime)->str:
    p=Path(path)
    text=p.read_text(encoding="utf-8") if p.is_file() else ""
    return render(text,now)
