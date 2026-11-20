"""A genuine first article comment may trigger ONE original X thread.

No replies to visitors, no copying their text, no mentions or automatic likes.
Reading only public first-party GitHub Issues; Buffer publication uses the
existing editorial director's quota, cooldown, receipt and no-retry controls.
A stored Buffer reservation counts as already attempted even when unknown.
"""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from urllib.parse import urlsplit
import re
import requests
from editorial_seo_v135 import x_weight
from portal_links_v148 import PORTAL_BASE,page_live

API="https://api.github.com/repos/xFederiko11/gta-6"
FIRST_PARTY="https://github.com/xFederiko11/gta-6/issues/"
LABEL="community-discussion"
KEYPREFIX="community-first-comment-v1:"
MAX_ISSUES=50
MAX_BODY=25000
MAX_DAILY=1
MAX_COMMENT_CHECKS=5
AGE=timedelta(days=7)
BAD=re.compile(r"(?i)(?:https?://|www\.|t\.me/|discord\.gg|free\s+followers|guadagn[ai]\s+facil[ei]|crypto|airdrop|buy\s+now|casino|\bseo\b)")
TOPIC=re.compile(r"(?i)(?:gta|vi\b|ps5|auto|veicol|trofe|platino|gioco|mission|garage|mappa|soldi|guid|posizion|salvat|funzion|prova|quest|capitol|sfid)")


def allowed_issue(issue):
    if not isinstance(issue,dict) or issue.get("state")!="open" or issue.get("pull_request"):
        return None
    if LABEL not in [x.get("name") for x in issue.get("labels",[]) if isinstance(x,dict)]:
        return None
    number=issue.get("number")
    if not isinstance(number,int) or not 1<=number<=999999999:return None
    if issue.get("html_url")!=FIRST_PARTY+str(number):return None
    title=str(issue.get("title") or "")
    if not title.startswith("💬 GTA VI | "):return None
    match=re.search(r"<!-- gta6-discussion-v1 path=([a-z0-9-]+(?:/[a-z0-9-]+)*/?) -->",
                    str(issue.get("body") or ""))
    if not match:return None
    path=match.group(1)
    if not path.endswith("/") or not (
        path in {"scoperte/","soldi-facili/","auto-speciali/","salvare-auto/","trofei/"}
        or re.fullmatch(r"guide-e-tutorial/[a-z0-9-]+/",path)):return None
    if len(title)>180:return None
    return {"number":number,"path":path,"title":title.removeprefix("💬 GTA VI | ").strip()[:90]}


def eligible_comment(value,now):
    if not isinstance(value,dict):return False
    author=value.get("user") or {}
    if author.get("type")!="User" or not author.get("login") or author.get("login","").endswith("[bot]"):
        return False
    body=str(value.get("body") or "").strip()
    if not 36<=len(body)<=MAX_BODY or BAD.search(body) or not TOPIC.search(body):
        return False
    if body.count("\n")>30 or body.count("@")>3:
        return False
    stamp=value.get("created_at")
    try:
        date=datetime.fromisoformat(str(stamp).replace("Z","+00:00"))
        if date.tzinfo is None:return False
    except (ValueError,TypeError):return False
    return timedelta(0)<=now-date.astimezone(timezone.utc)<=AGE


def get_json(path,*,session=None):
    if not path.startswith("/") or "://" in path or ".." in path:
        raise ValueError("Unsafe GitHub path")
    http=session or requests.Session()
    response=http.get(API+path,timeout=(5,12),headers={
        "Accept":"application/vnd.github+json",
        "User-Agent":"Federiko11-GTA6-Community-Comment-Trigger/1.0"})
    response.raise_for_status()
    return response.json()


def candidate(state,now,*,read=get_json,live_checker=page_live):
    if now.tzinfo is None:raise ValueError("Timezone-aware clock required")
    now=now.astimezone(timezone.utc)
    entries=state.get("entries",{})
    if any(e.get("tip_id","").startswith(KEYPREFIX)
           and str(e.get("reserved_utc","")).startswith(now.date().isoformat())
           for e in entries.values() if isinstance(e,dict)):
        return None
    try:
        issues=read("/issues?state=open&labels="+LABEL+"&per_page=50")
    except (requests.RequestException,ValueError,TypeError):
        return None
    if not isinstance(issues,list):return None
    checked=0
    for issue in sorted(issues[:MAX_ISSUES],key=lambda i:i.get("updated_at",""),reverse=True):
        known=allowed_issue(issue)
        if not known or not isinstance(issue.get("comments"),int) or issue["comments"]<1:continue
        target=PORTAL_BASE+"/"+known["path"]
        parsed=urlsplit(target)
        if parsed.scheme!="https" or parsed.hostname!="xfederiko11.github.io":continue
        if any(isinstance(e,dict) and str(e.get("url","")).rstrip("/")==target.rstrip("/")
               and e.get("status") in {"sent","scheduled","reserved","attempted","uncertain","accepted_pending"}
               for e in entries.values()):continue
        key=sha256((KEYPREFIX+str(known["number"])).encode()).hexdigest()[:24]
        if key in entries:continue
        if checked>=MAX_COMMENT_CHECKS:break
        checked+=1
        try:
            comments=read(f"/issues/{known['number']}/comments?per_page=30")
        except (requests.RequestException,ValueError,TypeError):
            continue
        if not isinstance(comments,list) or not any(eligible_comment(c,now) for c in comments):
            continue
        if not live_checker(target):continue
        topic=known["title"][:72].rstrip(" ,-.")
        main=("💬 GTA VI | Si parla di "+topic+
              ".\n\nRaccogliamo prove, passaggi e posizioni verificabili nella guida italiana. "
              "Hai una conferma o un dubbio da condividere?\n\n#GTAVI")
        reply=("🗺️ Guida e discussione aperta:\n"+target+
               "\n\n⚠️ I commenti sono segnalazioni: controlla patch e trofei prima di usarli.")
        if max(x_weight(main),x_weight(reply))>280:continue
        return {"key":key,"sig":"community-comments-"+str(known["number"]),
                "url":target,"title":"Discussione GTA VI: "+topic,
                "source":"Community GTA VI Italia","text":main,"thread":[main,reply],
                "tip_id":KEYPREFIX+str(known["number"])}
    return None
