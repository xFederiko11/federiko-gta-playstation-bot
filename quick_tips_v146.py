"""GTA VI: verified micro-guides, genuine 2-post Buffer X threads.

These editorial tips have been checked against PowerPyx articles dated
2026-11-18. No automated conversion of arbitrary long articles to instructions:
unverified steps are more harmful than a missed post.
"""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json
import re
from urllib.parse import urlsplit
from editorial_seo_v135 import x_weight

# The original Rockstar screenshots are illustrative, not screenshots of the
# WAiNK controls, animal studies or shooting-range results.
IMAGES={
    "vehicles":"https://www.rockstargames.com/VI/_next/static/media/Vice_City_02.0c5.7qx17u9kl.jpg?akim=1&imdensity=1&imwidth=3840",
    "animals":"https://www.rockstargames.com/VI/_next/static/media/Leonida_Keys_02.0~ptk-53gl0lq.jpg?akim=1&imdensity=1&imwidth=3840",
    "activities":"https://www.rockstargames.com/VI/_next/static/media/Vice_City_03.0nqz~lrqdmlze.jpg?akim=1&imdensity=1&imwidth=3840",
    "meditation":"https://www.rockstargames.com/VI/_next/static/media/Lucia_Caminos_02.16n.5umvlu_48.jpg?akim=1&imdensity=1&imwidth=3840",
    "ranges":"https://www.rockstargames.com/VI/_next/static/media/Vice_City_04.06evqutgh7624.jpg?akim=1&imdensity=1&imwidth=3840",
    "taxi":"https://www.rockstargames.com/VI/_next/static/media/Vice_City_01.135x56yoeu.6t.jpg?akim=1&imdensity=1&imwidth=3840",
}
TIPS=[
    {
        "id":"waink-vehicles-ps5",
        "title":"GTA VI PS5: scansiona i veicoli in pochi secondi",
        "source_url":"https://www.powerpyx.com/gta-6-how-to-study-animals-scan-vehicles/",
        "media_url":IMAGES["vehicles"],
        "main":"🚗 GTA VI | SCANSIONA AUTO SU PS5\n\n1️⃣ Tieni premuto ↑: apri WAiNK.\n2️⃣ Inquadra un veicolo.\n3️⃣ Tieni premuto R1 per registrarlo.\n\n🎯 Per il 100% ne servono 200. Contano anche barche e aerei!\n\n#GTAVI #GTA6",
    },
    {
        "id":"study animals",
        "title":"GTA VI PS5: studia gli animali senza cacciare",
        "source_url":"https://www.powerpyx.com/gta-6-how-to-study-animals-scan-vehicles/",
        "media_url":IMAGES["animals"],
        "main":"🦩 GTA VI | ANIMALI: 100% RAPIDO\n\n1️⃣ Apri la ruota armi e scegli il binocolo.\n2️⃣ Avvicina con ↑.\n3️⃣ Tieni premuto R1 sull'animale.\n\n🎯 Studia 100 specie su 255. Non serve cacciarle!\n\n#GTAVI #Platino",
    },
    {
        "id":"70 challenges",
        "title":"GTA VI PS5: come evitare 10 sfide difficili per il 100%",
        "source_url":"https://www.powerpyx.com/gta-6-all-challenges-guide/",
        "media_url":IMAGES["activities"],
        "main":"🎯 GTA VI | RISPARMIA TEMPO SUL 100%\n\n1️⃣ Vai su Progressi → Sfide.\n2️⃣ Controlla quelle già completate.\n3️⃣ Scegli le più semplici.\n\n✅ Bastano 70 sfide su 80: puoi saltarne 10!\n\n#GTAVI #Platino",
    },
    {
        "id":"chapter one meditation",
        "title":"GTA VI PS5: meditazione perdibile Capitolo 1",
        "source_url":"https://www.powerpyx.com/gta-6-all-meditation-spot-locations/",
        "media_url":IMAGES["meditation"],
        "main":"⚠️ GTA VI | MEDITAZIONE PERDIBILE\n\n1️⃣ Capitolo 1: segui Lucia sul balcone.\n2️⃣ Inquadrala con L2.\n3️⃣ Seleziona «Accetta».\n\n💾 Salva prima: il suo impatto sul trofeo è ancora incerto!\n\n#GTAVI #Platino",
    },
    {
        "id":"fast travel taxi",
        "title":"GTA VI PS5: sblocca il viaggio rapido con il taxi",
        "source_url":"https://www.powerpyx.com/gta-6-how-to-fast-travel/",
        "media_url":IMAGES["taxi"],
        "main":"🚕 GTA VI | VIAGGIO RAPIDO SU PS5\n\n1️⃣ Dopo la prima missione, chiama Paradise Taxi dai Contatti.\n2️⃣ Segna una meta e sali a bordo.\n3️⃣ Tieni L2 e premi △.\n\n💵 Costa 100 $ e ti porta subito a destinazione!\n\n#GTAVI #GTA6",
    },
    {
        "id":"shooting ranges",
        "title":"GTA VI PS5: come potenziare Concentrazione nei poligoni",
        "source_url":"https://www.powerpyx.com/gta-6-all-shooting-range-gold-medal-challenges/",
        "media_url":IMAGES["ranges"],
        "main":"🎯 GTA VI | FARMING CONCENTRAZIONE\n\n1️⃣ Vai a un poligono di tiro.\n2️⃣ Avvia una sfida e completala o esci.\n3️⃣ Ripeti per aumentare Concentrazione.\n\n🥇 Per il platino servono 42 medaglie Oro.\n\n#GTAVI #Platino",
    },
]
MAX_PER_DAY=2
GAP=timedelta(minutes=110)

def validate():
    urls=set()
    for t in TIPS:
        assert t["id"] and t["title"] and t["main"]
        assert t["source_url"].startswith("https://www.powerpyx.com/gta-6-")
        assert t["media_url"].startswith("https://www.rockstargames.com/VI/_next/static/media/")
        assert t["media_url"] not in urls
        urls.add(t["media_url"])
        # X counts the attached image against the first post's character budget.
        # Keep extra room for unicode/Buffer counting differences.
        assert x_weight(t["main"])<=235,(t["id"],x_weight(t["main"]))
        assert t["main"].count("\n\n")>=2
        assert "#GTAVI" in t["main"]
        answer=reply(t)
        assert x_weight(answer)<=280
        assert "PowerPyx" in answer
        assert t["source_url"] in answer
    return True

def reply(t, portal_link=None):
    if portal_link:
        return ("📖 Guida completa in italiano:\n"+portal_link+
                "\n\n🔎 Fonte PowerPyx e crediti immagini nella pagina.")
    return "📖 Fonte: PowerPyx\n\n🔗 Procedura completa e dettagli:\n"+t["source_url"]+"\n\n📸 Foto illustrativa: Rockstar Games."

def _reserved_time(value):
    """Reservation dates are RFC3339 ISO timestamps, not RSS publication dates."""
    if not value:
        return None
    try:
        result=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo is not None else None
    except (ValueError,TypeError):
        return None

def candidate(state,now):
    """One already-verified quick tip; no false promise of live scraping."""
    if now.tzinfo is None:raise ValueError("UTC aware datetime required")
    now=now.astimezone(timezone.utc)
    if not (datetime(2026,11,18,tzinfo=timezone.utc)<=now<datetime(2026,12,16,tzinfo=timezone.utc)):
        return None
    from editorial_autopilot_v137 import similarity_key,MAX_POSTS_DAY,MIN_SPACING_MIN
    entries=state["entries"]
    stamps=[_reserved_time(e.get("reserved_utc")) for e in entries.values() if e.get("reserved_utc")]
    stamps=[dt for dt in stamps if dt is not None]
    if sum(dt.date()==now.date() for dt in stamps)>=MAX_POSTS_DAY:return None
    if stamps and now-max(stamps)<timedelta(minutes=MIN_SPACING_MIN):return None
    tip_entries=[e for e in entries.values() if e.get("source")=="PowerPyx Tips"]
    # A real Buffer/X failure means the channel or the media/thread payload
    # may be incompatible. Stop all further tips until the cause is reviewed.
    if any(e.get("status") in ("rejected","error","uncertain") for e in tip_entries):
        return None
    tip_times=[_reserved_time(e.get("reserved_utc")) for e in tip_entries if e.get("reserved_utc")]
    tip_times=[dt for dt in tip_times if dt is not None]
    if sum(dt.date()==now.date() for dt in tip_times)>=MAX_PER_DAY:return None
    if tip_times and now-max(tip_times)<GAP:return None
    for t in TIPS:
        # Tips from the same article use distinct IDs, not same URL hash.
        # The id is stable across reruns and changes to copy.
        from hashlib import sha256
        key=sha256(("tips-v146:"+t["id"]).encode()).hexdigest()[:24]
        if key in entries:continue
        from portal_links_v148 import guide_if_live
        portal_link=guide_if_live(t["id"])
        return {"key":key,"sig":similarity_key(t["title"]),
                "source":"PowerPyx Tips","title":t["title"],
                "url":portal_link or t["source_url"],"text":t["main"],
                "thread":[t["main"],reply(t,portal_link=portal_link)],
                "media_url":t["media_url"],"tip_id":t["id"]}
    return None
validate()
