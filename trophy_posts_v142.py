"""Spoiler-aware, image-backed GTA VI trophy posts for existing editorial bot.

A new post uses a source-grounded Italian requirement and links to its
individually crawlable GitHub Pages article. Never links to an unavailable site.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit
import requests
from editorial_seo_v135 import x_weight
from build_trophy_site_v142 import BASE, PHOTOS

SOURCE=Path("trophies-gta6-v142.json")
MAX_TROPHIES_PER_UTC_DAY=2
SPACING=timedelta(minutes=160)
# Useful gold trophies and first-run advice first. Hidden stories only after launch.
ORDER=[14,1,17,28,15,35,32,16,31,55,53,54,40,25,30,41,42,43,36,33,34,18,19,20,21,39,37,38,27,26,22,23,24,29,49,48,47,50,51,52,44,45,46,2,3,4,5,6,7,8,9,10,11,12,13]
assert len(ORDER)==55 and len(set(ORDER))==55

def _parse(s):
    try:return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)
    except (ValueError,TypeError,AttributeError):return None

def landing_live(*,session=None):
    """Check for real Pages delivery, not merely a green Actions build."""
    http=session or requests
    try:
        with http.get(BASE+"/",timeout=(4,12),stream=True,allow_redirects=True,
                      headers={"User-Agent":"Federiko-GTA-VI-Trophies/1.0"}) as r:
            if r.status_code!=200 or urlsplit(r.url).hostname!="xfederiko11.github.io":
                return False
            chunk=next(r.iter_content(32768),b"")
            body=chunk.decode("utf-8",errors="replace")
            return "55 trofei" in body and "GTA VI" in body
    except (requests.RequestException,StopIteration,OSError):
        return False

def formatted(t):
    medal={"Platino":"💎","Oro":"🥇","Argento":"🥈","Bronzo":"🥉"}[t["tier"]]
    title=f'{medal} GTA VI | {t["tier"].upper()}: {t["name_it"]}'
    requirement=t["requirement_it"]
    if t["hidden"]:
        prefix="⚠️ SPOILER | Trofeo della storia\n\n"
    else:
        prefix=""
    link=BASE+"/"+t["id"]+".html"
    suffix="\n\n📖 Guida in italiano:\n"+link+"\n\n#GTAVI #Platino"
    tip=t.get("tip_it") or ""
    if tip and t["number"] in {14,17,28,35,32,15}:
        tip="💡 "+tip
    else:tip=""
    post=prefix+title+"\n\n🎯 "+requirement
    if tip:
        attempted=post+"\n\n"+tip+suffix
        if x_weight(attempted)<=280:post+="\n\n"+tip
    post+=suffix
    if x_weight(post)>280:
        # Shorten only the source-reworded requirement, never the external URL.
        while x_weight(post)>280 and len(requirement)>28:
            requirement=requirement[:-1]
            post=prefix+title+"\n\n🎯 "+requirement.rstrip(" .,;:")+"…"+suffix
    if x_weight(post)>280:
        raise ValueError("Trophy text cannot fit X character budget")
    return post

def candidate(state:dict,now:datetime):
    if now.tzinfo is None:raise ValueError("Require aware UTC")
    now=now.astimezone(timezone.utc)
    entries=state["entries"]
    trophy_entries=[e for e in entries.values() if e.get("source")=="Trofei GTA VI"]
    dates=[_parse(e.get("reserved_utc")) for e in trophy_entries]
    dates=[d for d in dates if d]
    if sum(d.date()==now.date() for d in dates)>=MAX_TROPHIES_PER_UTC_DAY:return None
    if dates and now-max(dates)<SPACING:return None
    data=json.loads(SOURCE.read_text(encoding="utf-8"))
    by_number={t["number"]:t for t in data["trophies"]}
    for number in ORDER:
        t=by_number[number]
        if t["hidden"] and now<datetime(2026,11,21,tzinfo=timezone.utc):
            continue
        url=BASE+"/"+t["id"]+".html"
        # Canonical URL SHA is owned by the same editorial journal as normal news.
        from editorial_autopilot_v137 import identity,similarity_key
        key=identity(url)
        if key in entries:continue
        img_index={"city":0,"characters":1,"landscapes":2}.get(t["photo_group"],2)
        return {"key":key,"sig":similarity_key(t["name_it"]),"url":url,
                "title":t["name_it"],"text":formatted(t),
                "source":"Trofei GTA VI","media_url":PHOTOS[img_index],
                "trophy_number":t["number"],"hidden":t["hidden"]}
    return None
