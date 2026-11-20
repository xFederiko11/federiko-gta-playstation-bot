"""Verified-owned-post conversation pack for GTA VI follower growth.

Transforms our OWN Buffer-delivered X permalink ledger into a compact list
of existing conversations to revisit manually. No X API / Buffer writes;
no fake impressions, auto replies, follows, likes, or unsolicited mentions.
"""
from __future__ import annotations
from datetime import datetime,timezone
import json,re
from pathlib import Path
from urllib.parse import urlsplit
from html import escape

SOURCE=Path("data/x-permalinks-v1.json")
BASE="https://xfederiko11.github.io/gta-6/"
SCHEMA="verified-buffer-x-permalinks-v1"
SCORE=(
    ("soldi",("soldi-","money-"),"💰 Soldi e farming",0),
    ("auto",("scansionare-veicoli","salvare-auto","auto-speciali"),"🚘 Auto e garage",1),
    ("platino",("trofei/","70-sfide-","meditazione-"),"🏆 Trofei e platino",2),
    ("guide",("guide-e-tutorial/",),"🎮 Guide operative",3),
)

def valid(post):
    if not isinstance(post,dict) or post.get("verified_by")!="Buffer sent Post.externalLink on verified @xFederiko11 channel":
        return None
    url,x=post.get("article_url"),post.get("x_url")
    if not isinstance(url,str) or not isinstance(x,str):return None
    try:article=urlsplit(url);xs=urlsplit(x)
    except ValueError:return None
    if (article.scheme!="https" or article.hostname!="xfederiko11.github.io"
        or not article.path.startswith("/gta-6/") or not article.path.endswith("/")
        or article.username or article.password or article.query or article.fragment):
        return None
    if (xs.scheme!="https" or xs.hostname!="x.com" or xs.query or xs.fragment
        or xs.username or xs.password or not re.fullmatch(r"/xFederiko11/status/[0-9]{8,25}",xs.path)):
        return None
    if not isinstance(post.get("sent_at"),str):return None
    try:
        stamp=datetime.fromisoformat(post["sent_at"].replace("Z","+00:00"))
        if stamp.tzinfo is None:return None
    except (ValueError,TypeError):return None
    if not isinstance(post.get("excerpt"),str) or len(post["excerpt"].strip())<12:return None
    return post

def classify(post):
    path=urlsplit(post["article_url"]).path.lower()
    for _key,parts,title,rank in SCORE:
        if any(part in path for part in parts):return rank,title
    return 4,"📌 Altri contenuti"

def choose(path=SOURCE,limit=4):
    if limit<1 or limit>6:raise ValueError("Unsafe capacity")
    if not Path(path).is_file():return []
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema")!=SCHEMA or not isinstance(data.get("posts"),list):
        raise ValueError("Untrusted X verified permalink list")
    entries=[valid(p) for p in data["posts"][:200]]
    entries=[x for x in entries if x]
    # Balance categories: at most one per cluster before filling other slots.
    entries.sort(key=lambda x:x["sent_at"],reverse=True)
    result=[];seen=set();seen_types=set()
    for entry in entries:
        rank,title=classify(entry)
        if rank in seen_types or entry["x_url"] in seen:continue
        result.append((rank,title,entry));seen_types.add(rank);seen.add(entry["x_url"])
        if len(result)==limit:return result
    for entry in entries:
        if entry["x_url"] in seen:continue
        rank,title=classify(entry)
        result.append((rank,title,entry));seen.add(entry["x_url"])
        if len(result)==limit:break
    return result

def markdown(path=SOURCE):
    posts=choose(path)
    lines=["## 🎯 Conversazioni nostre da valorizzare (post X reali)","",
           "Qui trovi SOLO post pubblicati e associati a una guida dalle ricevute "
           "Buffer verificate. Non sono opportunità di risposta ad altri utenti, "
           "né garantiscono impression, like o nuovi follower.","",
           "**Obiettivo:** quando arriva una domanda vera, rispondi con un "
           "passaggio utile e una fonte. Non ripubblicare in serie gli stessi "
           "thread e non taggare persone estranee.",""]
    if not posts:lines.extend(["Nessun permalink verificato disponibile. "
                               "Il flusso automatico non inventa post.", ""])
    for _rank,title,p in posts:
        lines.extend([f"### {title}",
            f"- [Apri la conversazione originale]({p['x_url']})",
            f"- [Guida di riferimento]({p['article_url']})",
            "- Azione proposta: leggi eventuali domande e rispondi SOLO se "
            "puoi chiarire un requisito, un luogo, una patch o un rischio trofei.",
            "- Niente auto-reply, quote-farming o richieste di follow non sollecitate.", ""])
    lines.extend(["### Mini-routine per 5 minuti", "",
       "1. Apri **Mentions** in Buffer Community e rispondi prima alle richieste autentiche.",
       "2. Apri al massimo due conversazioni nostre pertinenti e valuta eventuali domande.",
       "3. Cerca una domanda su GTA VI in italiano tramite i link della coda precedente; "
       "contribuisci soltanto se puoi dare una risposta realmente verificata.",
       "4. Per crescita reale servono dati X di visite profilo e follower: "
       "senza accesso alle metriche non attribuire risultati ai singoli post.",
       "",
       "Profilo: [@xFederiko11](https://x.com/xFederiko11) · "
       "[Buffer Community](https://publish.buffer.com/) · "
       "[Regole X](https://help.x.com/en/rules-and-policies/x-automation)",
       ""])
    return "\n".join(lines)
