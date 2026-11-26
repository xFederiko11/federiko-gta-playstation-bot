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
# Only strict reviewed-photo first publications get a wider inventory window.
PHOTO_DAY_BUDGET = 3
PHOTO_SPACING = timedelta(hours=4)
# Every entry is original editorial copy pointing to an existing public
# informational landing page; do not claim the third-party source verified it.
CONTENT = (
    # Informative original post linking our own editorial index, not a copy of
    # the creators' gameplay. The unique in-house social cover is separately
    # verified before Buffer. Live page + photo + daily caps all still required.
    {"id": "creator-showcase-original", "path": "/video-tutorial/",
     "title": "GTA VI: video dei creator con guida italiana",
     "text": "🎬 GTA VI | VIDEO DEI CREATOR\n\n4 filmati originali selezionati fra TGG, IGN e community. Vai al minuto utile e segui i passaggi in italiano.\n\n🎥 Video, fonti e guide:"},
    {"id": "patch-archive-20261123", "path": "/patch/2026-11-23/",
     "title": "GTA VI: archivio della patch del 23 novembre",
     "text": "🔧 GTA VI | PATCH DEL 23 NOVEMBRE\n\nLe note Rockstar confermano 7 correzioni, tra cui salvataggi, chiamate e livello di ricercato.\n\n📖 Riepilogo italiano e fonte ufficiale:"},
    {"id": "ps5-first-person-glitch", "path": "/guide-e-tutorial/glitch-prima-persona-ps5/",
     "title": "GTA VI PS5: glitch prima persona, comandi e rischi trofei",
     "text": "🎮 GTA VI | PRIMA PERSONA PS5\n\nCommunity: segnalato dopo patch 23/11. ⚠️ trofei NON verificati. Salva prima.\n\n📖 Comandi e video:"},
    {"id": "money-early-four", "path": "/guide-e-tutorial/soldi-facili-capitolo-1/",
     "title": "GTA VI: quattro luoghi per trovare soldi subito",
     "text": "💰 GTA VI | SOLDI NEL CAPITOLO 1\n\nPrima di Recalibration salva a parte: i soldi ordinari non passano al Capitolo 2. ⚠️ Spoiler.\n\n📍 Quattro luoghi e fonte:"},
    {"id": "money-liquor", "path": "/guide-e-tutorial/soldi-2500-three-sheets-liquor/",
     "title": "GTA VI: denaro nascosto al Three Sheets Liquor",
     "text": "💵 GTA VI | THREE SHEETS LIQUOR\n\nConsegna il rum a Shirley, poi torna con l'icona gialla. Cerca il pappagallo e il generatore. ⚠️ Spoiler.\n\n📍 Procedura e fonte:"},
    {"id": "oled-catalog", "path": "/hdr-oled/",
     "title": "TV OLED: trova il codice preciso",
     "text": "📺 GTA VI su PS5/Pro: prima di copiare una calibrazione HDR, cerca il codice della TV. Un numero visto su un'altra OLED non è un preset universale.\n\n🔎 Modelli, impostazioni e affidabilità:"},
    {"id": "challenge-roadmap", "path": "/guide-e-tutorial/70-sfide-100-percento/",
     "title": "Guida alle sfide per il 100%",
     "text": "🧭 GTA VI | 50 sfide per One Last Thing, 70 su 80 per il 100%. Apri Progressi → Sfide e controlla le spunte.\n\n🎯 Guida:"},
    {"id": "vehicle-guide", "path": "/guide-e-tutorial/scansionare-veicoli/",
     "title": "Veicoli: guida alla scansione",
     "text": "🚘 GTA VI | Per completare la collezione dei veicoli conviene capire subito come registrarli. La guida PS5 raccoglie i passaggi e i controlli da verificare.\n\n🔎 Procedura in italiano:"},
    {"id": "animal-guide", "path": "/guide-e-tutorial/studiare-animali/",
     "title": "Fauna: come studiare gli animali",
     "text": "🦩 GTA VI | Per il 100% studia 100 specie su 255 con il binocolo. Tieni R1 e verifica Progressi → Animali. Caccia separata.\n\n📖 Guida:"},
    {"id": "taxi-fast-travel", "path": "/guide-e-tutorial/viaggio-rapido-taxi/",
     "title": "Viaggio rapido: procedura taxi",
     "text": "🚕 GTA VI | Taxi dopo Gone Fishing. Saltare il tragitto costa 100 GTA$ oltre alla tariffa della corsa.\n\n📍 Comandi PS5:"},
    {"id": "range-focus", "path": "/guide-e-tutorial/poligoni-concentrazione/",
     "title": "Poligoni: Concentrazione e Oro",
     "text": "🎯 GTA VI | Pass poligono: 5 GTA$. Servono 42 medaglie Oro per il trofeo e il 100%. La Concentrazione è separata.\n\n🏆 Guida:"},
    {"id": "meditation-risk", "path": "/guide-e-tutorial/meditazione-capitolo-1/",
     "title": "Meditazioni: lezione alternativa dopo il Capitolo 1",
     "text": "🧘 GTA VI | Hai saltato la prima meditazione? PowerPyx indica una lezione alternativa dopo Coffee Break. Per il 100% bastano 15 sessioni su 18.\n\n📖 Guida e checklist:"},
    {"id": "randy-advanced-tracker", "path": "/guide-e-tutorial/sportive-randy-posizioni/",
     "title": "Randy: sbloccare Advanced Tracker",
     "text": "🚘 GTA VI | Advanced Tracker: completa Dale Mamba nella catena di Randy. Non servono necessariamente tutte le 16 consegne.\n\n📖 Guida e fonti:"},
    {"id": "trophy-index", "path": "/trofei/",
     "title": "Trofei GTA VI: checklist completa",
     "text": "🏆 GTA VI | Stai puntando al platino su PS5? La checklist in italiano separa requisiti, attività e avvisi su possibili trofei mancabili.\n\n✅ Consulta i singoli trofei:"},
    {"id": "cheats-trophy-risk", "path": "/trucchi/",
     "title": "Trucchi PS5: rischio trofei",
     "text": "🎮 GTA VI | Prima di usare i trucchi su PS5 controlla gli avvisi su salvataggi e trofei. Per il platino non dare per scontato che un codice sia innocuo.\n\n⚠️ Sequenze e precauzioni:"},
    {"id": "leonida-six-official-photos", "path": "/articoli/gta-vi-leonida-sei-luoghi/",
     "title": "GTA VI: Leonida in sei immagini Rockstar",
     "text": "🌴 GTA VI | LEONIDA IN SEI SCATTI\n\nDa Vice City alle Leonida Keys, sei ambienti nelle immagini ufficiali Rockstar. Nessuno spoiler della storia.\n\n📸 Galleria e fonti:"},
    {"id": "ultimate-edition-auto-garage", "path": "/articoli/gta-vi-ultimate-edition-auto-garage/",
     "title": "GTA VI Ultimate Edition: auto e garage in quattro immagini",
     "text": "🚘 GTA VI | AUTO E GARAGE\n\nRideout Customs, interni, collezione Wyman e veicoli del rifugio: quattro immagini ufficiali. Non sono istruzioni di sblocco.\n\n📸 Foto e guide:"},
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
    {"id":"car-pegassi-vitello","path":"/veicoli/pegassi-vitello/","title":"GTA VI: Pegassi Vitello — dove trovarla","text":"🚘 GTA VI | Pegassi Vitello\n\n📍 Indizio Randy: villa a Waning Sands, garage destro.\n⚠️ Attiva la richiesta. Non è uno spawn garantito.\n\n📖 Passaggi e fonti:"},
    {"id":"car-pegassi-infernus","path":"/veicoli/pegassi-infernus/","title":"GTA VI: Pegassi Infernus — dove trovarla","text":"🚘 GTA VI | Pegassi Infernus\n\n📍 Indizio Randy: deposito della polizia a Crosstown, settimo piano.\n⚠️ Segui la richiesta. Non è uno spawn garantito.\n\n📖 Passaggi e fonti:"},
    {"id":"car-pegassi-tempesta","path":"/veicoli/pegassi-tempesta/","title":"GTA VI: Pegassi Tempesta — dove trovarla","text":"🚘 GTA VI | Pegassi Tempesta\n\n📍 PowerPyx segnala un vialetto a Vespucci Island.\n⚠️ Controlla WAiNK. Non è uno spawn garantito.\n\n📖 Passaggi e fonti:"},
    {"id":"car-ascot-paragon","path":"/veicoli/ascot-paragon/","title":"GTA VI: Ascot Paragon — dove trovarla","text":"🚘 GTA VI | Ascot Paragon\n\n📍 La mappa richieste indica Waning Sands: verifica modello e tracker con WAiNK.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-bravado-gauntlet-hellfire","path":"/veicoli/bravado-gauntlet-hellfire/","title":"GTA VI: Bravado Gauntlet Hellfire — dove trovarla","text":"🚘 GTA VI | Bravado Gauntlet Hellfire\n\n📍 Per Randy consulta la zona di Hamlet sulla mappa GTABase.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-piccia-furia","path":"/veicoli/piccia-furia/","title":"GTA VI: Piccia Furia — dove trovarla","text":"🚘 GTA VI | Piccia Furia\n\n📍 La richiesta è segnalata nell'area di Hamlet: controlla WAiNK prima del furto.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-benefactor-dubsta","path":"/veicoli/benefactor-dubsta/","title":"GTA VI: Benefactor Dubsta — dove trovarla","text":"🚘 GTA VI | Benefactor Dubsta\n\n📍 GTABase segnala un parcheggio a Vice Beach: controlla il modello con WAiNK.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-bravado-banshee","path":"/veicoli/bravado-banshee/","title":"GTA VI: Bravado Banshee — dove trovarla","text":"🚘 GTA VI | Bravado Banshee\n\n📍 A Hamlet consulta l'area della richiesta e verifica la Banshee con WAiNK.\n⚠️ Non è uno spawn garantito fuori dall'incarico: controlla WAiNK.\n\n📖 Passaggi e fonti:"},
    {"id":"car-buckingham-windsor-drop","path":"/veicoli/buckingham-windsor-drop/","title":"GTA VI: Buckingham Windsor Drop — dove trovarla","text":"🚘 GTA VI | Windsor Drop\n\n📍 Concessionaria a Bayside, a ovest di Dynamix Fitness. Non è uno spawn garantito.\n\n📖 Passaggi e fonti:"},
    {"id":"car-pegassi-toros","path":"/veicoli/pegassi-toros/","title":"GTA VI: Pegassi Toros — dove trovarla","text":"🚘 GTA VI | Toros\n\n📍 A Southside cerca il salone esagonale centrale. Non è uno spawn garantito.\n\n📖 Passaggi e fonti:"},
    {"id":"car-ocelot-jagular","path":"/veicoli/ocelot-jagular/","title":"GTA VI: Ocelot Jagular — dove trovarla","text":"🚘 GTA VI | Ocelot Jagular\n\n📍 Indizio Randy: Belville. Attiva la richiesta e verifica WAiNK.\n⚠️ Non è uno spawn garantito.\n\n📖 Passaggi e fonti:"},
    {"id":"car-buckingham-jubilee","path":"/veicoli/buckingham-jubilee/","title":"GTA VI: Buckingham Jubilee — dove trovarla","text":"🚘 GTA VI | Buckingham Jubilee\n\n📍 Indizio Randy: Bayside. Attiva la richiesta e verifica WAiNK.\n⚠️ Non è uno spawn garantito.\n\n📖 Passaggi e fonti:"},
    {"id":"car-grotti-itali-rsx","path":"/veicoli/grotti-itali-rsx/","title":"GTA VI: Grotti Itali RSX — dove trovarla","text":"🚘 GTA VI | Grotti Itali RSX\n\n📍 Indizio Randy: Bayside. Attiva la richiesta e verifica WAiNK.\n⚠️ Non è uno spawn garantito.\n\n📖 Passaggi e fonti:"},
    {"id":"car-pfister-growler","path":"/veicoli/pfister-growler/","title":"GTA VI: Pfister Growler — dove trovarla","text":"🚘 GTA VI | Pfister Growler\n\n📍 Indizio Randy: Southside. Attiva la richiesta e verifica WAiNK.\n⚠️ Non è uno spawn garantito.\n\n📖 Passaggi e fonti:"},
    {"id":"car-gallivanter-baller-st-d","path":"/veicoli/gallivanter-baller-st-d/","title":"GTA VI: Gallivanter Baller ST-D — dove trovarla","text":"🚘 GTA VI | Gallivanter Baller ST-D\n\n📍 Indizio Randy: Casanova Island. Attiva la richiesta e verifica WAiNK.\n⚠️ Non è uno spawn garantito.\n\n📖 Passaggi e fonti:"},
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


def _owned_path(value):
    """Recognize the owned canonical article even with tracking parameters."""
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or parsed.hostname != "xfederiko11.github.io"
                or parsed.username or parsed.password or parsed.port not in (None,443)):
            return None
    except ValueError:
        return None
    if not parsed.path.startswith("/gta-6/"):
        return None
    return parsed.path.rstrip("/") + "/"


def candidate(state:dict, now:datetime, *, live_checker=page_live, photo_checker=None) -> dict | None:
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
    from game_photo_policy_v1 import active as photo_active
    from quality_publish_policy_v1 import local
    strict_photo = photo_checker is not None and photo_active(now)
    day_budget = PHOTO_DAY_BUDGET if strict_photo else DAY_BUDGET
    gap = PHOTO_SPACING if strict_photo else SPACING
    if sum(local(t).date()==local(now).date() for t in recent)>=day_budget:
        return None
    if strict_photo and sum(now-timedelta(hours=24)<=t<=now for t in recent)>=PHOTO_DAY_BUDGET:
        return None
    if recent and now-max(recent)<gap:
        return None
    # A legacy entry may have a different key for the same article. The
    # evergreen queue is first-publication only; reviewed article rotation
    # owns all repeat delivery, including cooldown and Sent receipt checks.
    previous_paths = {_owned_path(entry.get("url")) for entry in entries.values()
                      if isinstance(entry, dict)}
    # A reviewed photographic story is the first useful fallback, not the last
    # of dozens of illustrated candidates. Preserve the historical queue order
    # for inventory and offline tests; no extra slot or bypass of cooldown.
    photo_editorials = {"leonida-six-official-photos", "ultimate-edition-auto-garage"}
    ordered = sorted(CONTENT,key=lambda item: item['id'] not in photo_editorials) if photo_checker else CONTENT
    for item in ordered:
        url=PORTAL_BASE+item["path"]
        if _owned_path(url) in previous_paths:
            continue
        if urlsplit(url).hostname!="xfederiko11.github.io":
            raise ValueError("Unsafe publisher target")
        key=hashlib.sha256(("site-evergreen-v1:"+item["id"]).encode()).hexdigest()[:24]
        if key in entries:
            continue
        kind=photo_checker(url) if photo_checker is not None else None
        if photo_checker is not None and not kind:
            continue
        if not live_checker(url):
            continue
        from social_media_gate_v2 import cover_for
        proposed={"key":key,"sig":similarity_key(item["title"]),
                "url":url, "title":item["title"],"source":SOURCE,
                "text":item["text"]+"\n"+url+"\n\n#GTAVI",
                "media_url":cover_for(url)}
        # Do not let an oversized first candidate obstruct the next photo.
        if strict_photo:
            from game_photo_policy_v1 import single_photo_item
            if not single_photo_item(proposed,kind):
                continue
        return proposed
    return None


validate()
