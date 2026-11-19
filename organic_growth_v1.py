"""GTA VI organic X growth planner: GitHub-native, no social mutations.

Generates a human-reviewed seven-day rotating mix of original Italian posts
using only existing site pages. Never invents engagement metrics or contacts
users on X. Buffer quick-tips recovery gate is completely separate.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.parse import urlsplit
import re

from editorial_autopilot_v137 import weight_x
from growth_metrics_v142 import report as growth_report
from editorial_director_v142 import read_reservations, MAX_AUTOMATED_DELIVERIES_24H, MIN_GAP
from x_community_review_v1 import plan as conversation_plan, markdown as conversation_markdown

PUBLIC = "https://xfederiko11.github.io/gta-6/"
START_DATE = date(2026, 11, 19)
ISSUE_TITLE = "GTA VI - Crescita organica X"
SCHEMA = "gta6-organic-x-plan-v1"
MAX_X_WEIGHT = 280
PROFILE_STATE = Path("data/x-profile-status-v1.json")
PROFILE_SCHEMA = "gta6-x-profile-status-v1"


def load_profile_status(path=PROFILE_STATE):
    """Manual screenshot snapshot, never a live X API read or proof of verification."""
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema")!=PROFILE_SCHEMA or data.get("evidence")!="user_provided_screenshots_not_live_x_api":
        raise ValueError("Unknown or unproven X profile state")
    for key in ("website_link_visible","pinned_welcome_post_visible","authenticity_prompt_visible"):
        if type(data.get(key)) is not bool:
            raise ValueError("Invalid screenshot observation: "+key)
    if data.get("authenticity_verified") is not None:
        raise ValueError("Manual popup screenshot cannot prove live X authenticity verification")
    if data.get("followers_live") is not None:
        raise ValueError("Static screenshot is not live follower analytics")
    if data.get("preview_card_status") not in ("uncertain_grey_placeholder","unknown","checked_ok"):
        raise ValueError("Unknown social preview state")
    return data



PINNED = (
    "🎮 GTA VI / GTA 6 ITALIA | PS5 & PS5 Pro\n\n"
    "🏆 Trofei e platino con checklist\n"
    "⚡ Guide rapide in italiano\n"
    "📺 HDR OLED per codice TV\n"
    "🔎 Notizie con fonti e verifica\n\n"
    "Niente rumor spacciati per fatti.\n"
    "👇 " + PUBLIC + "\n\n#GTAVI #PS5"
)
BIO = (
    "🎮 GTA VI in italiano | Fan indipendente\n"
    "🎮 PS5 & PS5 Pro | 🏆 Trofei e guide\n"
    "📺 HDR OLED per modello\n"
    "🔎 Fonti, rumor etichettati. Non affiliato"
)

DRAFTS = (
    {
        "id": "cecchino-checklist", "format": "Soluzione rapida + risorsa",
        "text": (
            "🎯 GTA VI | Trofeo Cecchino (PS5)\n\n"
            "Le medaglie Oro dei poligoni non sono le medaglie delle missioni storia. "
            "La checklist ti aiuta a segnare le prove una per una.\n\n"
            "🔗 " + PUBLIC + "trofei/trofeo-17-cecchino/\n\n#GTAVI #Platino"
        ),
        "url": PUBLIC + "trofei/trofeo-17-cecchino/",
    },
    {
        "id": "hdr-tre-valori", "format": "Passaggi brevi + fonte",
        "text": (
            "📺 GTA VI su OLED (PS5)\n\n"
            "Options → Impostazioni → Schermo → Calibrazione HDR.\n"
            "Controlla Max Brightness, Black Levels e Paper White. "
            "Non copiare i numeri di un pannello differente.\n\n"
            "🔗 " + PUBLIC + "hdr-oled/\n\n#GTAVI #OLED"
        ),
        "url": PUBLIC + "hdr-oled/",
    },
    {
        "id": "trophy-safety", "format": "Consiglio originale (senza link)",
        "text": (
            "🏆 Glitch in GTA VI? Prima di usarlo per il platino, verifica:\n\n"
            "1️⃣ La patch PS5 effettiva\n"
            "2️⃣ L'effetto sui trofei\n"
            "3️⃣ Il rischio per i salvataggi\n\n"
            "Un video con scritto «working» non è una prova aggiornata.\n\n#GTAVI #PS5"
        ), "url": None,
    },
    {
        "id": "oled-model-search", "format": "Trucco di navigazione",
        "text": (
            "📺 Hai una LG, Samsung, Sony o Philips OLED?\n\n"
            "Per GTA VI cerca il codice completo della TV, non solo la marca: "
            "le impostazioni HDR variano tra famiglie e diagonali.\n\n"
            "🔎 " + PUBLIC + "hdr-oled/\n\n#GTAVI #PS5Pro"
        ),
        "url": PUBLIC + "hdr-oled/",
    },
    {
        "id": "community-question", "format": "Conversazione autentica (manuale)",
        "text": (
            "🎮 GTA VI | PS5 e PS5 Pro\n\n"
            "Quale guida ti sarebbe utile adesso: trofei, veicoli, missioni "
            "oppure calibrazione HDR?\n\n"
            "Sto organizzando i tutorial per andare subito al punto, "
            "senza passaggi inutili. Mi interessa capire le priorità reali.\n\n#GTAVI"
        ), "url": None,
    },
    {
        "id": "scoperte-etichettate", "format": "Trasparenza e fiducia",
        "text": (
            "🔎 GTA VI | Scoperta ≠ conferma.\n\n"
            "Distinguiamo guide specialistiche, community, rumor e datamining. "
            "Fonti e date sono visibili: trofei e glitch richiedono prove separate.\n\n"
            "📖 " + PUBLIC + "scoperte/\n\n#GTAVI"
        ), "url": PUBLIC + "scoperte/",
    },
    {
        "id": "platino-roadmap", "format": "Valore della guida + risorsa",
        "text": (
            "🏆 GTA VI | Puntiamo al platino su PS5.\n\n"
            "Raccolgo requisiti, attività, checklist e avvisi sulle scelte "
            "da non perdere. Le guide restano collegate alle fonti originali.\n\n"
            "🔗 " + PUBLIC + "trofei/\n\n#GTAVI #Platino"
        ), "url": PUBLIC + "trofei/",
    },
)


def validate_drafts() -> None:
    seen = set()
    for draft in DRAFTS:
        ident = draft["id"]
        if not re.fullmatch(r"[a-z0-9-]{4,60}", ident) or ident in seen:
            raise ValueError("Invalid or duplicated draft ID")
        seen.add(ident)
        text = draft["text"]
        if not 40 <= weight_x(text) <= MAX_X_WEIGHT:
            raise ValueError("X length limit exceeded: " + ident)
        links = re.findall(r"https://[^\s]+", text)
        for link in links:
            p = urlsplit(link)
            if p.scheme != "https" or p.hostname != "xfederiko11.github.io" or not p.path.startswith("/gta-6/"):
                raise ValueError("Unexpected link host")
        if links != ([draft["url"]] if draft["url"] else []):
            raise ValueError("Draft URL does not match its source")
    if weight_x(PINNED) > MAX_X_WEIGHT or weight_x(BIO) > 160:
        raise ValueError("Profile setup exceeds character budget")


def cadence_snapshot(now: datetime, ledger_root=Path(".state")) -> dict:
    """Assess ledger reservations only; no X reach, follower data or live API."""
    if now.tzinfo is None:
        raise ValueError("Timezone-aware clock required")
    start=now.astimezone(timezone.utc)-timedelta(hours=24)
    rows=read_reservations(ledger_root)
    delivery=[r for r in rows
              if r["status"] in ("sent","accepted")
              and start <= r["at"] <= now.astimezone(timezone.utc)]
    by_workflow={}
    for r in delivery:
        by_workflow[r["workflow"]]=by_workflow.get(r["workflow"],0)+1
    return {
        "window_hours":24,
        "sent_or_accepted_ledger_entries":len(delivery),
        "by_workflow":by_workflow,
        "review_high_volume":len(delivery)>=8,
        "not_x_reach_or_guaranteed_post_visibility":True,
    }


def make_plan(*, now: datetime | None = None, ledger_root=Path(".state"),
              manual_path=Path("metrics-manual-v142.csv"), profile_path=PROFILE_STATE) -> dict:
    validate_drafts()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    day = max(0, (now.astimezone(timezone.utc).date() - START_DATE).days)
    upcoming = [dict(DRAFTS[(day+i) % len(DRAFTS)]) for i in range(3)]
    metrics = growth_report(ledger_path=ledger_root, manual_path=manual_path)
    profile = load_profile_status(profile_path)
    pace = cadence_snapshot(now, ledger_root)
    # A busy new account should not be prompted to add even more original
    # posts; discovery searches remain available for selective human reading.
    if pace["review_high_volume"]:
        upcoming=[]
    community = conversation_plan(now)
    return {
        "schema": SCHEMA,
        "generated_utc": now.astimezone(timezone.utc).isoformat(),
        "mode": "manual_review_only_no_buffer_no_x_api",
        "account": "@xFederiko11",
        "pinned_draft": PINNED,
        "bio_suggestion": BIO,
        "profile_website": PUBLIC,
        "profile_snapshot": profile,
        "cadence": pace,
        "community_queue": community,
        "drafts": upcoming,
        "delivery_reservations": metrics["delivery_reservations"],
        "delivery_status": metrics["by_status"],
        "actual_x_metrics_available": metrics["actual_x_metrics_available"],
        "x_metrics_count": len(metrics["x_metrics"]),
        "warning": "Buffer sent is not impressions or followers. Never infer growth.",
    }


def markdown(plan: dict) -> str:
    if plan.get("schema") != SCHEMA:
        raise ValueError("Unexpected organic growth plan schema")
    fence = "~" * 3
    lines = [
        "<!-- gta6-organic-growth-v1 -->",
        "# GTA VI - Crescita organica di @xFederiko11", "",
        "**Questa issue non invia post, commenti, menzioni, follow o like.**",
        "Follower e impression non vengono letti direttamente da X.", "",
        "## Profilo: stato osservato dagli screenshot", "",
        "Questo stato riflette **solo le schermate del 19 novembre 2026**, non un controllo live di X. "
        "Non mostra follower aggiornati, impression o un risultato di autenticità.",
        "- [x] Sito web visibile nel profilo." if plan["profile_snapshot"]["website_link_visible"]
        else "- [ ] Verificare manualmente il collegamento al sito web.",
        "- [x] Post di presentazione fissato in alto." if plan["profile_snapshot"]["pinned_welcome_post_visible"]
        else "- [ ] Pubblicare e fissare un post di presentazione originale.",
        "- [ ] Controllare che la bio spieghi cosa riceve chi segue il canale.",
        "- [ ] Esaminare personalmente l'avviso «Sblocca di più su X» nell'app ufficiale; "
        "non significa automaticamente shadowban, né prova che X abbia richiesto "
        "una verifica biometrica. Se una verifica autentica appare, seguirne solo il percorso ufficiale."
        if plan["profile_snapshot"]["authenticity_prompt_visible"] else
        "- [ ] Verificare se il profilo ha limitazioni effettive nella ricerca o nei suggerimenti.",
        "- [ ] Controllare da un altro browser l'anteprima grigia del post fissato: "
        "potrebbe essere il caricamento di una card, non un media definitivamente rotto.",
        "- [ ] Seguire e commentare manualmente soltanto account GTA e PlayStation di vero interesse.",
        "", "### Bio suggerita", fence+"text", plan["bio_suggestion"], fence,
        "Sito web: " + plan["profile_website"], "",
        "### Post da fissare - archivio (già visibile nel profilo)" if plan["profile_snapshot"]["pinned_welcome_post_visible"]
        else "### Post da fissare - non pubblicato", fence+"text",
        plan["pinned_draft"], fence, "",
        "## Tre bozze da verificare prima di pubblicare", "",
        "Non sono nella coda Buffer. Mai copiarle tutte in blocco; "
        "verificare i fatti, aggiornare il contesto e variarne la forma.", "",
    ]
    if not plan["drafts"]:
        lines.extend([
            "**Bozze promozionali sospese nella coda di crescita**: volume recente "
            "elevato. Non aggiungere altri post soltanto per aumentare la visibilità; "
            "concentrati su lettura e risposte autentiche se realmente utili.", "",
        ])
    for d in plan["drafts"]:
        lines.extend([
            "### " + escape(d["format"]) + " - " + d["id"],
            fence+"text", d["text"], fence,
            "Caratteri stimati X: " + str(weight_x(d["text"])) + "/280. "
            "**Stato: revisione e pubblicazione manuale**.", "",
        ])
    lines.extend(conversation_markdown(plan["community_queue"]).rstrip().splitlines())
    lines.append("")
    states = plan["delivery_status"]
    status_line = (", ".join(escape(k)+": "+str(v)
                             for k,v in sorted(states.items())) if states else "non disponibili")
    actual = ("disponibili per "+str(plan["x_metrics_count"])+" post"
              if plan["actual_x_metrics_available"] else "non disponibili")
    lines.extend([
        "## Monitor di prudenza: cadenza del bot nelle ultime 24 ore", "",
        "- Righe ledger `sent` o `accepted` nelle ultime 24 ore: " +
        str(plan["cadence"]["sent_or_accepted_ledger_entries"]) +
        ". Sono stati delle prenotazioni/pubblicazioni Buffer, **non impression X**.",
        "- Workflow coinvolti: " +
        (", ".join(k+": "+str(v) for k,v in sorted(
            plan["cadence"]["by_workflow"].items())) or "nessuno") + ".",
        ("- ⚠️ **Volume elevato da riesaminare manualmente.** "
         "Su un account nuovo evitare di aumentare la frequenza; "
         "questo dato non prova shadowban o violazioni della piattaforma."
         if plan["cadence"]["review_high_volume"] else
         "- Nessuna soglia di attenzione superata dal ledger osservato. "
         "Non significa che X consideri l'account verificato."),
        "Il monitor delle **notizie** continua anche quando gli invii sono trattenuti. "
        "Il coordinatore automatico limita le **prenotazioni pubblicabili** "
        "a "+str(MAX_AUTOMATED_DELIVERIES_24H)+" nelle 24 ore mobili, con almeno "
        +str(int(MIN_GAP.total_seconds()/60))+
        " minuti di intervallo complessivo. Soglie volontarie, NON limiti ufficiali di X; "
        "un thread può contenere più di un tweet. Non garantiscono immunità da restrizioni. "
        "Il controllo non elimina post, non riscrive ledger e non ferma la ricerca delle notizie.", "",
        "## Numeri effettivi, non impression inventate", "",
        "- Prenotazioni dei workflow nei ledger: " + str(plan["delivery_reservations"]) +
        " (non equivalgono a post letti su X).",
        "- Esiti ledger: " + status_line + ".",
        "- Metriche X compilate manualmente: " + actual + ".",
        "- Se il file X è vuoto, i nuovi follower sono **non disponibili**, "
        "non automaticamente zero.", "",
        "Metriche da confrontare, quando disponibili: impression, visite al profilo, "
        "nuovi follower, risposte pertinenti e clic sul sito. "
        "Misurare almeno una settimana prima di cambiare formato.", "",
        "## Priorità iniziali finché l'account è nuovo", "",
        "- Non aumentare le automazioni solo perché lo screenshot mostra 0 follower; "
        "il numero è un'osservazione storica, non una metrica live.",
        "- Preferire contenuti unici, originali e verificati: una risposta breve e utile può "
        "generare più fiducia di una sequenza di titoli di video.",
        "- Non aprire ticket né usare servizi di sblocco a pagamento sulla base del solo popup.",
        "- Niente follow/unfollow, like o risposte automatiche. "
        "L'account deve restare riconoscibilmente gestito da una persona.", "",
        "## Routine manuale senza spam", "",
        "1. Leggere un post recente rilevante su GTA VI/PS5. "
        "Rispondere solo quando si ha un dettaglio utile sul caso reale.",
        "2. Rispondere a chi commenta il proprio account, "
        "correggendo gli errori con fonti verificabili.",
        "3. Alternare consigli rapidi, notizie confermate e conversazioni sincere. "
        "Non imporsi una quota di risposte o follower.",
        "4. Inserire solo dati effettivi letti da X in metrics-manual-v142.csv.", "",
        "## Limiti non negoziabili", "",
        "- No follower acquistati, scambi di engagement, follow/unfollow massivo, "
        "risposte automatizzate non richieste, like automatici o commenti seriali.",
        "- Quick Tips Buffer restano sospesi fino alla riconferma; "
        "questo workflow non modifica alcuna variabile.",
        "- Rumor, community e video non sono comunicati Rockstar. "
        "Un titolo non prova la sicurezza dei trofei.",
        "- Nessuna chiamata API a X o Buffer, nessuna modifica ai ledger.", "",
        "Regole: https://help.x.com/en/rules-and-policies/x-automation "
        "e https://help.x.com/en/rules-and-policies/authenticity", "",
        "_Questa coda propone attività di qualità ma non garantisce follower._"
    ])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = make_plan()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown(plan), encoding="utf-8")
    print("ORGANIC_GROWTH", len(plan["drafts"]),
          "manual_only=true x_metrics_available="+str(plan["actual_x_metrics_available"]))


if __name__ == "__main__":
    main()
