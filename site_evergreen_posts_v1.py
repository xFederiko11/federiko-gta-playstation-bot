"""Autonomous, one-per-day GTA VI owned-site tips: source checks before sharing.

A fixed editorial collection, not scraped generative claims. Never repeats
an already reserved tip. No invented gameplay steps, no X API or external
engagement actions. A failed/unknown landing page remains unpublished.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from urllib.parse import urlsplit

from editorial_seo_v135 import x_weight
from portal_links_v148 import PORTAL_BASE, page_live

SOURCE = "Guide GTA VI Italia"
DAY_BUDGET = 1
SPACING = timedelta(hours=20)
# Every entry is original editorial copy pointing to an existing public
# informational landing page; do not claim the third-party source verified it.
CONTENT = (
    {"id": "money-early-four", "path": "/guide-e-tutorial/soldi-facili-capitolo-1/",
     "title": "GTA VI: quattro luoghi per trovare soldi subito",
     "text": "💰 GTA VI | SOLDI NEL CAPITOLO 1\n\nQuattro posti da controllare per trovare denaro e oggetti di valore. La guida spiega dove andare, cosa cercare e quali rischi evitare. ⚠️ Spoiler sulle posizioni.\n\n📍 Passaggi e fonte:"},
    {"id": "money-liquor", "path": "/guide-e-tutorial/soldi-2500-three-sheets-liquor/",
     "title": "GTA VI: denaro nascosto al Three Sheets Liquor",
     "text": "💵 GTA VI | THREE SHEETS LIQUOR\n\nDurante l'incarico di Shirley, controlla il retro del negozio: secondo Insider Gaming, vicino al generatore c'è un nascondiglio con 1.200 GTA$. ⚠️ Spoiler.\n\n📍 Procedura illustrata e fonte:"},
    {"id": "oled-catalog", "path": "/hdr-oled/",
     "title": "TV OLED: trova il codice preciso",
     "text": "📺 GTA VI su PS5 e PS5 Pro: prima di copiare una calibrazione HDR, cerca il codice completo della TV. Un numero visto su un'altra OLED non è un preset universale.\n\n🔎 Modelli, impostazioni e affidabilità:"},
    {"id": "challenge-roadmap", "path": "/guide-e-tutorial/70-sfide-100-percento/",
     "title": "Guida alle sfide per il 100%",
     "text": "🧭 GTA VI | Verso il 100% su PS5. Nella guida trovi quali sfide completare e quali requisiti verificare prima di investire ore di gioco.\n\n🎯 Procedura e fonti:"},
    {"id": "vehicle-guide", "path": "/guide-e-tutorial/scansionare-veicoli/",
     "title": "Veicoli: guida alla scansione",
     "text": "🚘 GTA VI | Per completare la collezione dei veicoli conviene capire subito come registrarli. La guida PS5 raccoglie i passaggi e i controlli da verificare.\n\n🔎 Procedura in italiano:"},
    {"id": "animal-guide", "path": "/guide-e-tutorial/studiare-animali/",
     "title": "Fauna: come studiare gli animali",
     "text": "🦩 GTA VI | Ti interessa il completamento? Abbiamo separato la guida per studiare gli animali dalle normali attività di caccia. Controlla i requisiti prima di iniziare.\n\n📖 Tutorial e fonte:"},
    {"id": "taxi-fast-travel", "path": "/guide-e-tutorial/viaggio-rapido-taxi/",
     "title": "Viaggio rapido: procedura taxi",
     "text": "🚕 GTA VI | Se vuoi ridurre i tempi fra una missione e l'altra, verifica quando puoi usare il taxi per spostarti più rapidamente.\n\n📍 Requisiti e pulsanti PS5:"},
    {"id": "range-focus", "path": "/guide-e-tutorial/poligoni-concentrazione/",
     "title": "Poligoni: Concentrazione e Oro",
     "text": "🎯 GTA VI PS5 | Poligoni: medaglie Oro e Concentrazione sono due aspetti da distinguere. Nella guida trovi requisiti, procedura e avvisi sul percorso verso il platino.\n\n🏆 Leggi i passaggi:"},
    {"id": "meditation-risk", "path": "/guide-e-tutorial/meditazione-capitolo-1/",
     "title": "Meditazione: attenzione al Capitolo 1",
     "text": "⚠️ GTA VI | Prima di proseguire la storia, controlla le attività del Capitolo 1 potenzialmente perdibili. La guida distingue requisiti osservati e impatto sui trofei ancora incerto.\n\n💾 Verifica prima di avanzare:"},
    {"id": "trophy-index", "path": "/trofei/",
     "title": "Trofei GTA VI: checklist completa",
     "text": "🏆 GTA VI | Stai puntando al platino su PS5? La checklist in italiano separa requisiti, attività e avvisi su possibili trofei mancabili.\n\n✅ Consulta i singoli trofei:"},
    {"id": "cheats-trophy-risk", "path": "/trucchi/",
     "title": "Trucchi PS5: rischio trofei",
     "text": "🎮 GTA VI | Prima di usare i trucchi su PS5 controlla gli avvisi su salvataggi e trofei. Per il platino non dare per scontato che un codice sia innocuo.\n\n⚠️ Sequenze e precauzioni:"},
    {"id": "community-sources", "path": "/scoperte/",
     "title": "Scoperte community: verifica le fonti",
     "text": "🔎 GTA VI | Rumor e datamining non sono notizie confermate. Nella sezione Scoperte trovi titoli, fonti e classificazioni, senza promesse di glitch trophy-safe.\n\n🧪 Consulta le segnalazioni:"},
)


def validate():
    keys=set()
    urls=set()
    for item in CONTENT:
        if item["id"] in keys or not item["id"] or item["path"] in urls:
            raise ValueError("Duplicate GTA VI landing or ID")
        keys.add(item["id"])
        urls.add(item["path"])
        if not item["path"].startswith("/") or not item["path"].endswith("/"):
            raise ValueError("Noncanonical owned-site URL")
        if any(u in item["text"] for u in ("http://","https://","@Rockstar")):
            raise ValueError("Unexpected link/mention in owned-site post body")
        result=item["text"]+"\n"+PORTAL_BASE+item["path"]+"\n\n#GTAVI"
        if x_weight(result)>280 or x_weight(result)<80:
            raise ValueError("Evergreen tip exceeds X copy budget")
    return True


def candidate(state:dict, now:datetime, *, live_checker=page_live) -> dict | None:
    if now.tzinfo is None:
        raise ValueError("Aware timestamp required")
    now=now.astimezone(timezone.utc)
    entries=state["entries"]
    recent=[]
    from editorial_autopilot_v137 import published, similarity_key
    for e in entries.values():
        if e.get("source")!=SOURCE:
            continue
        stamp=published(e.get("reserved_utc"))
        if stamp:
            recent.append(stamp)
    if sum(t.date()==now.date() for t in recent)>=DAY_BUDGET:
        return None
    if recent and now-max(recent)<SPACING:
        return None
    for item in CONTENT:
        url=PORTAL_BASE+item["path"]
        if urlsplit(url).hostname!="xfederiko11.github.io":
            raise ValueError("Unsafe publisher target")
        key=hashlib.sha256(("site-evergreen-v1:"+item["id"]).encode()).hexdigest()[:24]
        if key in entries:
            continue
        if not live_checker(url):
            continue
        return {"key":key,"sig":similarity_key(item["title"]),
                "url":url, "title":item["title"],"source":SOURCE,
                "text":item["text"]+"\n"+url+"\n\n#GTAVI"}
    return None


validate()
