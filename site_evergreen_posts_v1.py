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
    {"id": "ps5-first-person-glitch", "path": "/guide-e-tutorial/glitch-prima-persona-ps5/",
     "title": "GTA VI PS5: glitch prima persona, comandi e rischi trofei",
     "text": "🎮 GTA VI | PRIMA PERSONA PS5\n\nIn auto apri il telefono (↑), chiudi (○) e premi subito il touchpad.\n\n🟡 Segnalato funzionante; ⚠️ trofei NON verificati. Salva prima.\n\n📖 Procedura e video:"},
    {"id": "money-early-four", "path": "/guide-e-tutorial/soldi-facili-capitolo-1/",
     "title": "GTA VI: quattro luoghi per trovare soldi subito",
     "text": "💰 GTA VI | SOLDI NEL CAPITOLO 1\n\nQuattro luoghi nel Capitolo 1 per trovare soldi e oggetti utili. ⚠️ Spoiler sulle posizioni.\n\n📍 Passaggi e fonte:"},
    {"id": "money-liquor", "path": "/guide-e-tutorial/soldi-2500-three-sheets-liquor/",
     "title": "GTA VI: denaro nascosto al Three Sheets Liquor",
     "text": "💵 GTA VI | THREE SHEETS LIQUOR\n\nDurante l'incarico di Shirley, cerca dietro al negozio: secondo Insider Gaming, vicino al generatore ci sono 1.200 GTA$. ⚠️ Spoiler.\n\n📍 Procedura illustrata e fonte:"},
    {"id": "oled-catalog", "path": "/hdr-oled/",
     "title": "TV OLED: trova il codice preciso",
     "text": "📺 GTA VI su PS5/Pro: prima di copiare una calibrazione HDR, cerca il codice della TV. Un numero visto su un'altra OLED non è un preset universale.\n\n🔎 Modelli, impostazioni e affidabilità:"},
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
     "text": "⚠️ GTA VI | Prima di proseguire la storia, controlla le attività del Capitolo 1 potenzialmente perdibili. L'impatto sui trofei è ancora incerto.\n\n💾 Verifica prima di avanzare:"},
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
# Per-model original content. Each live URL has its own unique editorial cover;
# promotional Rockstar pictures are never mislabeled as vehicle gameplay.
# This queue is read-only until the site deploys and the image gate succeeds.
# Moses' Sultan is intentionally excluded from automation (final story spoiler).
VEHICLE_CONTENT = (
    {"id":"car-canis-crawler","path":"/veicoli/canis-crawler/","title":"GTA VI: Canis Crawler — dove trovarla","text":"🚘 GTA VI | Canis Crawler\n\n📍 Dopo Moses, avvia Daily Driver e cerca il Crawler a Gellhorn Avenue.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-declasse-yosemite-1500","path":"/veicoli/declasse-yosemite-1500/","title":"GTA VI: Declasse Yosemite 1500 — dove trovarla","text":"🚘 GTA VI | Declasse Yosemite 1500\n\n📍 Su Bastion Street il pickup giallo è sul carro attrezzi: sgancialo.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-karin-futo","path":"/veicoli/karin-futo/","title":"GTA VI: Karin Futo — dove trovarla","text":"🚘 GTA VI | Karin Futo\n\n📍 Ai Draper Island Docks entra dal lato nord: la Futo è nel garage occidentale.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-annis-hellion","path":"/veicoli/annis-hellion/","title":"GTA VI: Annis Hellion — dove trovarla","text":"🚘 GTA VI | Annis Hellion\n\n📍 A Orchard Avenue cerca il vialetto della casa al centro della zona di ricerca.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-bf-bandito","path":"/veicoli/bf-bandito/","title":"GTA VI: BF Bandito — dove trovarla","text":"🚘 GTA VI | BF Bandito\n\n📍 A Buckskin Swamp cerca il buggy argentato in movimento: ha un solo posto.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-declasse-vamos","path":"/veicoli/declasse-vamos/","title":"GTA VI: Declasse Vamos — dove trovarla","text":"🚘 GTA VI | Declasse Vamos\n\n📍 A nord-est di Grayson la Vamos è nel capanno: digita 2727 sulla porta laterale.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-western-nightblade","path":"/veicoli/western-nightblade/","title":"GTA VI: Western Nightblade — dove trovarla","text":"🚘 GTA VI | Western Nightblade\n\n📍 Ad Ambrosia cerca la moto arancione nel piano inferiore del garage centrale.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-granforma-zorrusso","path":"/veicoli/granforma-zorrusso/","title":"GTA VI: Granforma Zorrusso — dove trovarla","text":"🚘 GTA VI | Granforma Zorrusso\n\n📍 Agli Hathaway Apartments di Ocean Beach: garage recintato, poi Key Cloner.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-pegassi-vitello","path":"/veicoli/pegassi-vitello/","title":"GTA VI: Pegassi Vitello — dove trovarla","text":"🚘 GTA VI | Pegassi Vitello\n\n📍 Nella zona Waning Sands consulta la richiesta di Randy e scansiona con WAiNK.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-pegassi-infernus","path":"/veicoli/pegassi-infernus/","title":"GTA VI: Pegassi Infernus — dove trovarla","text":"🚘 GTA VI | Pegassi Infernus\n\n📍 Cerca la Infernus a Vice City; WAiNK indica se Randy la sta richiedendo.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-pegassi-tempesta","path":"/veicoli/pegassi-tempesta/","title":"GTA VI: Pegassi Tempesta — dove trovarla","text":"🚘 GTA VI | Pegassi Tempesta\n\n📍 GTABase segnala Ambrosia: controlla la mappa di Randy prima di cercarla.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-ascot-paragon","path":"/veicoli/ascot-paragon/","title":"GTA VI: Ascot Paragon — dove trovarla","text":"🚘 GTA VI | Ascot Paragon\n\n📍 La mappa richieste indica Waning Sands: verifica modello e tracker con WAiNK.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-bravado-gauntlet-hellfire","path":"/veicoli/bravado-gauntlet-hellfire/","title":"GTA VI: Bravado Gauntlet Hellfire — dove trovarla","text":"🚘 GTA VI | Bravado Gauntlet Hellfire\n\n📍 Per Randy consulta la zona di Hamlet sulla mappa GTABase.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-piccia-furia","path":"/veicoli/piccia-furia/","title":"GTA VI: Piccia Furia — dove trovarla","text":"🚘 GTA VI | Piccia Furia\n\n📍 La richiesta è segnalata nell'area di Hamlet: controlla WAiNK prima del furto.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-benefactor-dubsta","path":"/veicoli/benefactor-dubsta/","title":"GTA VI: Benefactor Dubsta — dove trovarla","text":"🚘 GTA VI | Benefactor Dubsta\n\n📍 GTABase segnala un parcheggio a Vice Beach: controlla il modello con WAiNK.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-bravado-banshee","path":"/veicoli/bravado-banshee/","title":"GTA VI: Bravado Banshee — dove trovarla","text":"🚘 GTA VI | Bravado Banshee\n\n📍 A Hamlet consulta l'area della richiesta e verifica la Banshee con WAiNK.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
)
# Interleave car topics with the existing evergreen diversity. One owned-site
# story per day is still enforced by DAY_BUDGET and SPACING below.
ORIGINAL_CONTENT = CONTENT
CONTENT = tuple(
    part for i in range(max(len(ORIGINAL_CONTENT),len(VEHICLE_CONTENT)))
    for part in (
        *((ORIGINAL_CONTENT[i],) if i<len(ORIGINAL_CONTENT) else ()),
        *((VEHICLE_CONTENT[i],) if i<len(VEHICLE_CONTENT) else ())
    )
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
        if x_weight(result)>235 or x_weight(result)<80:
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
        from social_media_gate_v2 import cover_for
        return {"key":key,"sig":similarity_key(item["title"]),
                "url":url, "title":item["title"],"source":SOURCE,
                "text":item["text"]+"\n"+url+"\n\n#GTAVI",
                "media_url":cover_for(url)}
    return None


validate()
