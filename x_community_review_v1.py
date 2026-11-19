"""Human-reviewed Italian GTA VI discussion discovery for the owner's X profile.

No X API, account login, scraping, automation of replies/likes/reposts/follows,
or attempt to claim specific posts exist. Search links open X manually.
Exact post suggestions are accepted ONLY if a human adds them with their context.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import quote, urlencode, urlsplit

SCHEMA = "gta6-x-conversations-v1"
DATA = Path("data/x-conversation-candidates-v1.json")
SEARCHES = (
    {"id": "italia-domande",
     "query": '("GTA VI" OR "GTA 6") lang:it -filter:retweets',
     "title": "Discussioni italiane su GTA VI",
     "look_for": "Domande precise su gameplay, novità o progressione",
     "tip": "Rispondi solo dopo aver letto il post. Dai prima la soluzione, senza link promozionale non richiesto."},
    {"id": "trofei-platino",
     "query": '("GTA VI" OR "GTA 6") (trofei OR platino) lang:it -filter:retweets',
     "title": "Trofei, platino e requisiti PS5",
     "look_for": "Dubbi su medaglie Oro, trofei mancabili e progressione",
     "tip": "Verifica il requisito preciso nella guida e distingui i metodi testati dalle ipotesi."},
    {"id": "playstation-italia",
     "query": 'from:PlayStationIT (GTA OR "Grand Theft Auto")',
     "title": "Comunicazioni PlayStation Italia",
     "look_for": "Post ufficiali pertinenti ai giocatori italiani",
     "tip": "Se aggiungi un commento, limitati a dettagli verificati per PS5; evita di usare lo stesso testo ovunque."},
    {"id": "guide-missioni",
     "query": '("GTA VI" OR "GTA 6") (missione OR guida OR consigli) lang:it -filter:retweets',
     "title": "Richieste pratiche su missioni e guide",
     "look_for": "Una domanda concreta di un giocatore, non una discussione casuale",
     "tip": "Chiedi un dettaglio soltanto se serve; meglio un passaggio utile di una presentazione del tuo progetto."},
    {"id": "hdr-oled",
     "query": '("GTA VI" OR "GTA 6") (HDR OR OLED OR PS5) lang:it -filter:retweets',
     "title": "HDR OLED e impostazioni PS5",
     "look_for": "Codici TV, problemi di calibrazione e impostazioni effettivamente disponibili",
     "tip": "Richiedi il modello completo del pannello, non suggerire numeri universali o preset non documentati."},
    {"id": "rockstar-comunita",
     "query": '("GTA VI" OR "GTA 6") (@RockstarGames OR Rockstar) lang:it -filter:retweets',
     "title": "Discussione italiana sulle notizie Rockstar",
     "look_for": "Reazioni e domande a comunicazioni ufficiali",
     "tip": "Distingui l'annuncio ufficiale dai rumor; evita repost seriali per sola visibilità."},
    {"id": "ps5-pro",
     "query": '("GTA VI" OR "GTA 6") "PS5 Pro" lang:it -filter:retweets',
     "title": "Esperienze PS5 Pro",
     "look_for": "Confronti visivi documentati o domande sulle impostazioni",
     "tip": "Non affermare miglioramenti FPS, patch o risoluzioni senza prove pertinenti."},
)
MAX_MANUAL_POSTS = 8

# Accounts and conversation examples come from user-supplied X screenshots,
# NOT a live X search or proof of current post context. Do not initiate contact.
TARGETS = (
    {"handle":"PlayStationIT", "name":"PlayStation Italia", "language":"it",
     "topic":"GTA VI e disponibilità PS5", "priority":1,
     "query":'from:PlayStationIT ("GTA VI" OR "Grand Theft Auto")',
     "when":"Solo sotto un annuncio GTA VI/PS5, non sotto comunicati estranei.",
     "reply":"Buon lancio! Sono previste indicazioni ufficiali sulle differenze tra PS5 e PS5 Pro, soprattutto per HDR e modalità grafiche?",
     "observed_reply":True},
    {"handle":"GTASeries", "name":"GTA Series Videos", "language":"en",
     "topic":"Walkthrough e missioni GTA VI", "priority":1,
     "query":'from:GTASeries ("GTA 6" OR "GTA VI")',
     "when":"Sotto un nuovo walkthrough visto davvero; non ripetere la domanda già inviata sulla missione 3.",
     "reply":"For this mission, is there an optional objective that's easy to miss on a completionist playthrough?",
     "observed_reply":True},
    {"handle":"RockstarINTEL", "name":"Rockstar INTEL", "language":"en",
     "topic":"Notizie Rockstar e fonti", "priority":1,
     "query":'from:RockstarINTEL ("GTA VI" OR "GTA 6")',
     "when":"Se parlano della colonna sonora (Overmono/Justice), resta sul tema musicale; non chiedere dei trofei.",
     "reply":"Overmono alongside Justice is an exciting combination. I'm curious how that sound will fit different areas of Leonida.",
     "observed_reply":True},
    {"handle":"GTAVI_Countdown", "name":"GTA 6 Countdown", "language":"en",
     "topic":"Discussione GTA VI e screenshot", "priority":2,
     "query":'from:GTAVI_Countdown ("GTA 6" OR "GTA VI")',
     "when":"Solo su uno screenshot specifico e con un'osservazione originale; non ripetere la domanda già pubblicata.",
     "reply":"That sunset lighting really stands out. Has the team confirmed whether this is captured directly on PS5 or promotional footage?",
     "observed_reply":True},
    {"handle":"TexFunz2", "name":"Tex2", "language":"en",
     "topic":"Datamining con cautela", "priority":2,
     "query":'from:TexFunz2 ("GTA" OR "Rockstar")',
     "when":"Soltanto per analisi pubbliche di file/patch documentate; evita di trattare il datamining come conferma.",
     "reply":"Interesting find. Which game build or file supports it, and is this present in the released build or unused data?",
     "observed_reply":False},
    {"handle":"RockstarGames", "name":"Rockstar Games", "language":"en",
     "topic":"Aggiornamenti ufficiali", "priority":2,
     "query":'from:RockstarGames ("GTA VI" OR "GTA 6")',
     "when":"Solo sotto comunicazioni recenti pertinenti; se contengono già la risposta non fare domande ripetitive.",
     "reply":"Is there an official page listing the PS5 update notes and any changes to gameplay progression?",
     "observed_reply":False},
    {"handle":"PlayStation", "name":"PlayStation", "language":"en",
     "topic":"PS5 e PS5 Pro", "priority":3,
     "query":'from:PlayStation ("GTA VI" OR "Grand Theft Auto")',
     "when":"Solo sotto aggiornamenti sul gioco e specificamente su console, non su altri titoli.",
     "reply":"Will there be a detailed PS5 and PS5 Pro settings guide, including official HDR information?",
     "observed_reply":False},
)
# Drafts are conditional examples, NOT permission to send. Existing user
# interactions observed in screenshots must never be repeated automatically.


def search_link(query: str) -> str:
    return "https://x.com/search?q=" + quote(query, safe="") + "&f=live"


def manual_candidates(path=DATA) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA or not isinstance(data.get("posts"), list) or len(data["posts"]) > MAX_MANUAL_POSTS:
        raise ValueError("Unknown Italian engagement candidate schema")
    results, seen = [], set()
    for item in data["posts"]:
        if not isinstance(item,dict):
            raise ValueError("Invalid candidate entry")
        uri=urlsplit(str(item.get("post_url","")))
        # No user/password, query, redirect or disguised X hostname.
        if (uri.scheme!="https" or uri.hostname not in ("x.com", "www.x.com")
                or uri.username or uri.password or uri.port not in (None,443)
                or uri.query or uri.fragment):
            raise ValueError("Candidate URL must be an exact X post")
        hit=re.fullmatch(r"/([A-Za-z0-9_]{1,15})/status/([0-9]{5,25})/?",uri.path)
        if hit is None or uri.path in seen:
            raise ValueError("Invalid or duplicate exact X post")
        seen.add(uri.path)
        if item.get("reviewed_original") is not True:
            raise ValueError("Only human-read original posts can appear")
        if item.get("language") != "it":
            raise ValueError("Italian-only review queue")
        context=item.get("original_context")
        if not isinstance(context,str) or not 20 <= len(context.strip()) <= 450:
            raise ValueError("Need context from the actual post")
        note=item.get("editorial_note")
        if not isinstance(note,str) or not 12 <= len(note.strip()) <= 320:
            raise ValueError("Need one concrete reason to participate")
        reply=item.get("draft_reply_it","")
        if not isinstance(reply,str) or len(reply) > 260:
            raise ValueError("Reply draft too long or invalid")
        if re.search(r"(?i)https?://|@\w+|#\w+",reply):
            raise ValueError("No unsolicited links, mentions or hashtags in draft replies")
        if reply and len(reply.strip()) < 20:
            raise ValueError("Reply draft is too generic")
        reviewed=item.get("reviewed_utc")
        try:
            stamp=datetime.fromisoformat(str(reviewed).replace("Z","+00:00"))
            if stamp.tzinfo is None:
                raise ValueError("Timezone required")
        except (TypeError,ValueError):
            raise ValueError("Invalid human review date")
        intent = ("https://x.com/intent/tweet?" +
                  urlencode({"in_reply_to":hit[2],"text":reply})) if reply else None
        results.append({
            "post_url":"https://x.com"+uri.path.rstrip("/"),
            "reply_intent_url":intent,
            "author":"@"+hit[1],
            "original_context":context,
            "editorial_note":note,
            "draft_reply_it":reply,
            "reviewed_utc":stamp.astimezone(timezone.utc).isoformat(),
            "approved_for_auto_reply":False,
        })
    return results


def plan(now:datetime, *, manual_path=DATA, limit=5) -> dict:
    if now.tzinfo is None:
        raise ValueError("Timezone-aware date required")
    if not isinstance(limit,int) or not 1 <= limit <= 5:
        raise ValueError("At most five searches, never post claims")
    day=now.astimezone(timezone.utc).date().toordinal()
    # The general Italian discussion search always comes first; rotate the
    # other niches so GitHub's daily issue does not become a repetitive list.
    picks=[SEARCHES[0]]+[SEARCHES[1+((day+i)%(len(SEARCHES)-1))]
                        for i in range(limit-1)]
    searches=[{**x,"url":search_link(x["query"]),"is_specific_post":False} for x in picks]
    # Show a daily selection of *known accounts*, never invent individual
    # tweets or claim they have posted on a particular date.
    ordered=sorted(TARGETS,key=lambda item:(item["priority"],item["handle"]))
    featured=ordered[:2] + [ordered[2+((day+i)%(len(ordered)-2))]
                         for i in range(2)]
    targets=[{**x,"search_url":search_link(x["query"]),
              "profile_url":"https://x.com/"+x["handle"],
              "specific_post_verified":False} for x in featured]
    return {
        "schema":SCHEMA,
        "generated_utc":now.astimezone(timezone.utc).isoformat(),
        "searches":searches,
        "conversation_targets":targets,
        "exact_posts":manual_candidates(manual_path),
        "live_x_posts_verified_by_bot":0,
        "manual_actions_only":True,
        "buffer_actions":0,
        "external_reply_automation_enabled":False,
    }


def markdown(report) -> str:
    if report.get("schema") != SCHEMA:
        raise ValueError("Bad review report")
    lines=[
        "## 🔎 Community Italia: conversazioni da trovare manualmente", "",
        "**Questi sono link a ricerche X, non link a tweet verificati.** "
        "Il bot non legge il feed X, non identifica autori interessati "
        "e non invia risposte, repost, like, DM o follow.", "",
    ]
    for item in report["searches"]:
        lines.extend([
            "### "+escape(item["title"]),
            "[Cerca su X tra i post recenti]("+item["url"]+")",
            "- Cerca: "+escape(item["look_for"]),
            "- Possibile contributo: "+escape(item["tip"]),
            "- **Azione:** apri un vero post, leggi il contenuto e decidi personalmente "
            "se rispondere in italiano, citare la fonte o non intervenire.", "",
        ])
    lines.extend([
        "## 🎯 Account rilevanti e conversazioni da valutare", "",
        "Selezione dai profili **visibili negli screenshot del 19/11/2026**, "
        "non monitorati in tempo reale. Il bot offre una bozza *condizionale* "
        "per un argomento concreto; prima di inviarla verifica che il post "
        "tratti proprio quell'argomento. Se hai già commentato, non replicare.", "",
    ])
    for target in report["conversation_targets"]:
        lines.extend([
            "### "+escape(target["name"])+" (@"+target["handle"]+")",
            "[Apri profilo]("+target["profile_url"]+") · "
            "[Cerca post pertinenti]("+target["search_url"]+")",
            "- Tema: "+escape(target["topic"])+" · lingua della bozza: "+target["language"],
            "- **Quando intervenire:** "+escape(target["when"]),
            "- **Esempio pertinente solo se il post corrisponde:**", "",
            "~~~text", target["reply"], "~~~",
            "- Nota: "+("hai già interagito su un loro post negli screenshot, "
                        "quindi non ripetere quella risposta." if target["observed_reply"]
                        else "non è noto alcun scambio diretto da questo screenshot."),
            "- **Azione finale:** apri il post specifico su X, rileggilo, "
            "adatta la bozza e premi Invia personalmente.", "",
        ])
    lines.extend([
        "## 💬 Post specifici aggiunti dopo lettura umana", "",
        "I candidati con link al singolo tweet vengono inseriti **soltanto** "
        "da un revisore nel repository, con il testo letto e la ragione della risposta. "
        "Una bozza non è approvazione alla pubblicazione automatica.", "",
    ])
    if not report["exact_posts"]:
        lines.append("Nessun tweet specifico ancora verificato manualmente.")
        lines.append("")
    for item in report["exact_posts"]:
        lines.extend([
            "### "+escape(item["author"])+" · revisione umana",
            "[Apri il post originale]("+item["post_url"]+")" +
            (" · [Apri bozza nella finestra Rispondi]("+item["reply_intent_url"]+")"
             if item["reply_intent_url"] else ""),
            "- Contesto letto: "+escape(item["original_context"]),
            "- Motivo per intervenire: "+escape(item["editorial_note"]),
            "- Bozza **facoltativa**, da adattare al contesto attuale: "
              + (escape(item["draft_reply_it"]) if item["draft_reply_it"] else "da scrivere personalmente"),
            "- Stato: **nessun invio, né approvazione ad auto-rispondere**. "
            "L'intent apre soltanto un composer da verificare e inviare manualmente, "
            "se X supporta questo collegamento nel tuo browser.", "",
        ])
    lines.extend([
        "### Regole operative di protezione account", "",
        "- Mai ripetere in serie una stessa risposta, neppure tradotta.",
        "- Niente like automatici. Niente follow/unfollow per aumentare i numeri.",
        "- Niente risposte con IA pubblicate automaticamente: X richiede approvazione "
        "scritta preventiva per i bot che rispondono con IA.",
        "- Niente repost programmati in blocco: qui si preparano soltanto ricerche e bozze.",
        "- Il commento deve essere pertinente al **contenuto reale** del post. "
        "La scoperta automatica da una parola chiave non autorizza una risposta.",
        "- Se X richiede una verifica, svolgerla soltanto nell'app ufficiale. "
        "Un popup non dimostra automaticamente un ban.", "",
        "Regole X: https://help.x.com/en/rules-and-policies/x-automation "
        "e https://help.x.com/en/rules-and-policies/authenticity", "",
    ])
    return "\n".join(lines)+"\n"
