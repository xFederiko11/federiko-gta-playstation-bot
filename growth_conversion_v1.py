"""One high-value, non-duplicative community question among existing GTA VI posts.

This module prepares ORIGINAL posts to OUR OWN X profile, not responses
to other people's tweets. Its first message teaches a sourced action and
asks one relevant question; the second links the corresponding Italian guide
through the existing verified double-thread Buffer publisher.

No AI-generated unsolicited replies, DMs, follows, likes or vanity claims.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta, timezone
from hashlib import sha256
from urllib.parse import urlsplit

from launch_cadence_v1 import active as in_launch, local
from portal_links_v148 import PORTAL_BASE, page_live
from editorial_seo_v135 import x_weight

FIRST_DAY=date(2026,11,21)
LAST_DAY=date(2026,12,2)
SOURCE="Guide GTA VI Italia"
CATEGORY="community-question"
# Dates are mapped to specific useful guides. Each copy is written and reviewed
# here, not inferred from unverified headlines or scraped conversations.
PROMPTS=(
    {"id":"chapter-1-money","path":"/guide-e-tutorial/soldi-facili-capitolo-1/",
     "title":"Quattro luoghi utili nel Capitolo 1",
     "text":"💰 GTA VI | Nelle prime ore non devi vagare senza meta: la guida raccoglie quattro luoghi da esplorare per denaro e oggetti utili. Le posizioni sono sotto spoiler.\n\nQuale tipo di bottino ti interessa di più?"},
    {"id":"ps5-original-screenshots","path":"/screenshot-ps5/",
     "title":"Aiutaci a documentare GTA VI con schermate PS5 vere",
     "text":"📸 GTA VI PS5 | Le nostre guide hanno bisogno di mappe, menu e risultati autentici: niente schermate inventate. Abbiamo organizzato 55 richieste fotografiche, con procedure e consenso al riuso.\n\nQuale screenshot ti aiuterebbe di più?"},
    {"id":"garage-slot","path":"/salvare-auto/",
     "title":"Conservare le auto speciali senza perdere slot",
     "text":"🚘 GTA VI | Prima di salvare un'auto speciale, verifica gli slot occupati e il metodo di registrazione. Un garage pieno richiede una scelta.\n\nTi serve di più una mappa delle auto rare o dei garage?"},
    {"id":"platino-sicuro","path":"/trofei/",
     "title":"Pianificare il platino prima di giocare",
     "text":"🏆 GTA VI PS5 | Se punti al platino, segna le attività progressivamente e verifica i possibili trofei mancabili prima di avanzare. La checklist è consultabile per obiettivo.\n\nQuale requisito vuoi approfondire per primo?"},
    {"id":"shirley-cash","path":"/guide-e-tutorial/soldi-2500-three-sheets-liquor/",
     "title":"Un nascondiglio da controllare durante un incarico",
     "text":"💵 GTA VI | L'incarico di Shirley contiene un nascondiglio da cercare nel retro del negozio. Nella guida trovi riferimenti e schermate, con spoiler protetti.\n\nPreferisci una mappa prima o le immagini dell'ingresso?"},
    {"id":"taxi-shortcut","path":"/guide-e-tutorial/viaggio-rapido-taxi/",
     "title":"Ridurre gli spostamenti in taxi",
     "text":"🚕 GTA VI | Per accelerare gli spostamenti, il taxi consente di saltare il tragitto pagando il supplemento previsto. Controlla sempre tariffa e destinazione.\n\nQuale spostamento ti fa perdere più tempo?"},
    {"id":"complete-challenges","path":"/guide-e-tutorial/70-sfide-100-percento/",
     "title":"Sfide e checklist verso il 100%",
     "text":"🏆 GTA VI | Per il completamento al 100% la guida PowerPyx segnala una selezione di sfide, non necessariamente tutte. Organizzale per zona e attività.\n\nTi serve prima la lista completa o un percorso rapido?"},
    {"id":"study-fauna","path":"/guide-e-tutorial/studiare-animali/",
     "title":"Studiare la fauna senza caccia",
     "text":"🦩 GTA VI | Studiare la fauna può contribuire al completamento senza cacciare. Prima di uscire, controlla l'obiettivo e il metodo di osservazione della guida.\n\nTi sarebbe più utile una mappa per specie o per area?"},
    {"id":"range-focus","path":"/guide-e-tutorial/poligoni-concentrazione/",
     "title":"Poligoni: distinguere medaglie e Concentrazione",
     "text":"🎯 GTA VI | Ai poligoni, ottenere l'Oro e sviluppare Concentrazione non sono lo stesso obiettivo. Verifica quale requisito stai seguendo prima di ripetere le prove.\n\nVuoi una guida per poligono o una checklist unica?"},
    {"id":"meditation-warning","path":"/guide-e-tutorial/meditazione-capitolo-1/",
     "title":"Capitolo 1: meditazione e rischi da verificare",
     "text":"⚠️ GTA VI | Prima di lasciare il Capitolo 1, controlla le attività che potrebbero non essere recuperabili facilmente. La guida distingue le prove dai dubbi sui trofei.\n\nTi servirebbe un avviso prima di ogni passaggio irreversibile?"},
    {"id":"oled-hdr","path":"/hdr-oled/",
     "title":"HDR OLED: identificare il modello preciso",
     "text":"📺 GTA VI PS5 | Due OLED della stessa marca non richiedono sempre identiche impostazioni HDR. Parti dal codice TV completo, non da un preset generico.\n\nQuale modello e diagonale utilizzi?"},
    {"id":"whereto-first","path":"/auto-speciali/",
     "title":"Auto e garage: scegliere le priorità di ricerca",
     "text":"🚙 GTA VI | Le auto speciali vanno individuate, controllate e conservate: sono tre problemi diversi. Le guide separano ricerca, tracker e garage.\n\nPreferisci una lista dei mezzi o mappe con posizione esatta?"},
)


def validate():
    assert len(PROMPTS)==12
    ids=set()
    for item in PROMPTS:
        assert item["id"] not in ids
        ids.add(item["id"])
        assert item["path"].startswith("/") and item["path"].endswith("/")
        assert "?" in item["text"] and item["text"].count("?")==1
        assert 90 <= x_weight(item["text"]) <= 255
        assert "https://" not in item["text"] and "@" not in item["text"]
    return True


def candidate(state:dict, now:datetime, *, live_checker=page_live)->dict | None:
    """At most one pre-reviewed original question daily, 12:00–20:30 Rome.

    The question replaces a normal editorial slot instead of creating an
    independent publishing channel or extra posts.
    """
    if now.tzinfo is None:
        raise ValueError("Timezone-aware now required")
    if not in_launch(now):
        return None
    clock=local(now)
    if not FIRST_DAY<=clock.date()<=LAST_DAY or not 12<=clock.hour<=20:
        return None
    entries=state["entries"]
    if any(str(e.get("tip_id") or "").startswith("growth-question-")
           and (ts:=e.get("reserved_utc")) and
           (parsed:=_parse_time(ts)) is not None and
           local(parsed).date()==clock.date()
           for e in entries.values()):
        return None
    prompt=PROMPTS[(clock.date()-FIRST_DAY).days]
    url=PORTAL_BASE+prompt["path"]
    parsed=urlsplit(url)
    if parsed.scheme!="https" or parsed.hostname!="xfederiko11.github.io":
        raise ValueError("Unknown first-party guide host")
    key=sha256(("gta6-growth-original:"+prompt["id"]).encode()).hexdigest()[:24]
    if key in entries:
        return None
    # If a guide has appeared elsewhere within the last 18 hours, use no
    # candidate rather than competing with ourselves for attention.
    for e in entries.values():
        when=_parse_time(e.get("reserved_utc"))
        if (when is not None and timedelta(0)<=now.astimezone(timezone.utc)-when<timedelta(hours=18)
            and str(e.get("url") or "").rstrip("/")==url.rstrip("/")):
            return None
    if not live_checker(url):
        return None
    return {"key":key,"sig":"growth-"+prompt["id"],
            "url":url,"source":SOURCE,
            "title":prompt["title"],"text":prompt["text"],
            "tip_id":"growth-question-"+prompt["id"]}


def _parse_time(value):
    if not value:
        return None
    try:
        result=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (TypeError,ValueError):
        return None


validate()
