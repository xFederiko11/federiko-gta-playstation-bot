"""GTA VI X Social Radar: official API recent search, read-only, draft-only.

A post is VERIFIED here only in the limited sense that X API returned its
ID, text, author and timestamp. This is not a verification of factual claims.
No third-party HTML scraping, credential sharing, automated replies, likes,
follows or reposts. One manually enabled, budget-bounded daily API sweep.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ENDPOINT = "https://api.x.com/2/tweets/search/recent"
SCHEMA = "gta6-x-social-radar-v1"
MAX_QUERIES_PER_RUN = 2
MAX_RESULTS_PER_QUERY = 10
MAX_POSTS_IN_DIGEST = 5
MAX_AGE_HOURS = 36
HISTORY_TAG = 'x-social-radar-v1-seen:'
MAX_HISTORY = 200
# A conservative upper bound on resource reads from this workflow only;
# it is NOT a spending cap in X. Configure a billing cap in console.x.com.
MAX_RESOURCES_PER_SWEEP = MAX_QUERIES_PER_RUN * MAX_RESULTS_PER_QUERY * 2
QUERIES = (
    '("GTA VI" OR "GTA 6") (trofei OR platino OR missioni OR HDR OR PS5) lang:it -is:retweet -is:reply',
    '("GTA VI" OR "GTA 6") (trophy OR missions OR PS5 OR patch OR HDR) lang:en -is:retweet -is:reply',
)
# Templates are editorial starting points bound to a grounded keyword/theme.
# No external LLM and no claim that this reply has been human fact-checked.
TOPICS = (
    ("soundtrack", ("overmono", "justice", "soundtrack", "colonna sonora", "musica"),
     "Per la colonna sonora, hai già trovato una conferma ufficiale dei brani o degli artisti presenti?",
     "Has Rockstar confirmed the exact artists or tracks for the soundtrack yet?"),
    ("glitch", ("glitch", "exploit", "duplication", "duplicazione"),
     "Sai indicare la patch PS5 su cui è stato verificato e se i trofei rimangono ottenibili?",
     "Do you know which PS5 patch this was tested on and whether trophies remain obtainable?"),
    ("hdr", ("hdr", "oled", "luminosit", "paper white"),
     "Hai il codice completo della TV e stai usando PS5 o PS5 Pro? Sarebbe utile per confrontare la calibrazione.",
     "Which exact TV model and console are you using? That would make the HDR comparison much more useful."),
    ("trophies", ("trofeo", "trofei", "platino", "platinum", "trophy", "trophies"),
     "Per il platino, ci sono requisiti perdibili oppure attività da completare prima di avanzare nella storia?",
     "Are there any missable requirements or optional objectives worth doing before progressing the story?"),
    ("patch", ("patch", "hotfix", "changelog", "aggiornamento", "update"),
     "È disponibile il changelog ufficiale con la versione esatta? Vorrei distinguere conferme e segnalazioni.",
     "Is there an official changelog with the exact version? It would help separate confirmed changes from reports."),
    ("missions", ("missione", "missioni", "mission", "chapter", "walkthrough"),
     "Hai notato qualche obiettivo opzionale o passaggio perdibile in questa missione?",
     "Did you spot any optional objectives or missable steps in that mission?"),
    ("performance", ("ps5 pro", "fps", "performance", "framerate", "frame rate"),
     "Quale versione del gioco e modalità grafica hai verificato su PS5 Pro?",
     "Which build and graphics mode did you test on PS5 Pro?"),
)
BANNED = re.compile(r"(?i)\b(?:giveaway|airdrop|crypto|follow ?back|onlyfans|free ?money|leak(?:ed)?|pirated|spoiler(?:s)?)\b")
HANDLE_RE = re.compile(r"[A-Za-z0-9_]{1,15}")
POST_ID_RE = re.compile(r"\d{8,25}")


def api_recent(token: str, query: str, *, opener=urlopen) -> dict:
    if query not in QUERIES:
        raise ValueError("Non-approved search query")
    if not token or len(token.strip()) < 15:
        raise ValueError("X Bearer token missing or invalid")
    args = urlencode({
        "query": query,
        "max_results": MAX_RESULTS_PER_QUERY,
        "tweet.fields": "author_id,created_at,lang,public_metrics,reply_settings",
        "expansions": "author_id",
        "user.fields": "username,name",
    })
    request = Request(ENDPOINT + "?" + args, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "User-Agent": "FederikoGTA6-SocialRadar/1.0 read-only",
    }, method="GET")
    with opener(request, timeout=12) as response:
        payload = response.read(350_001)
    if len(payload) > 350_000:
        raise ValueError("Oversized X API response")
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict) or data.get("errors") or not isinstance(data.get("data", []), list):
        raise ValueError("Malformed or partial X API response")
    return data


def classify(content: str, language: str) -> tuple[str, str] | None:
    lower = content.casefold()
    if not ("gta" in lower or "grand theft auto" in lower or "leonida" in lower):
        return None
    for theme, terms, it, en in TOPICS:
        if any(term in lower for term in terms):
            return theme, it if language == "it" else en
    return None


def select(responses: list[dict], now: datetime, *, limit=MAX_POSTS_IN_DIGEST,
           exclude_ids=None) -> list[dict]:
    if now.tzinfo is None or not 1 <= limit <= MAX_POSTS_IN_DIGEST:
        raise ValueError("Invalid selection parameters")
    clock = now.astimezone(timezone.utc)
    candidates, ids = [], set()
    excluded = set(exclude_ids or [])
    for response in responses:
        if response.get("errors"):
            continue
        include = response.get("includes", {})
        users = {str(u.get("id")): u for u in include.get("users", [])
                 if isinstance(u, dict)}
        for item in response.get("data", []):
            if not isinstance(item, dict):
                continue
            post_id = str(item.get("id", ""))
            author = users.get(str(item.get("author_id", "")))
            if not POST_ID_RE.fullmatch(post_id) or post_id in ids or post_id in excluded or not author:
                continue
            handle = str(author.get("username", ""))
            if not HANDLE_RE.fullmatch(handle) or handle.lower() == "xfederiko11":
                continue
            raw = item.get("text")
            lang = item.get("lang")
            if lang not in ("it", "en") or not isinstance(raw, str):
                continue
            if len(raw.split()) < 9 or raw.lstrip().startswith(("RT @", "@")):
                continue
            if BANNED.search(raw) or item.get("reply_settings") not in (None, "everyone"):
                continue
            classified = classify(raw, lang)
            if classified is None:
                continue
            try:
                stamp = datetime.fromisoformat(str(item["created_at"]).replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    continue
            except (ValueError, KeyError, TypeError):
                continue
            age = clock - stamp.astimezone(timezone.utc)
            if not timedelta(0) <= age <= timedelta(hours=MAX_AGE_HOURS):
                continue
            ids.add(post_id)
            theme, reply = classified
            metrics = item.get("public_metrics")
            if not isinstance(metrics, dict):
                metrics = {}
            # Avoid trusting unbounded/non-numeric metrics. Max one suggestion
            # per creator. A score is a ranking aid, not audience reach.
            likes = safe_count(metrics.get("like_count"))
            replies = safe_count(metrics.get("reply_count"))
            score = (1000 if lang == "it" else 0) + min(likes, 150) + min(replies * 4, 80)
            score -= int(age.total_seconds() / 3600) * 6
            candidates.append({
                "post_id": post_id, "author": "@" + handle,
                "url": "https://x.com/" + handle + "/status/" + post_id,
                "published_utc": stamp.astimezone(timezone.utc).isoformat(),
                "source_excerpt": re.sub(r"\s+", " ", raw).strip()[:100],
                "language": lang, "theme": theme,
                "reply": reply,
                "reply_url": "https://x.com/intent/tweet?" + urlencode({
                    "in_reply_to": post_id, "text": reply
                }),
                "score": score,
                "verified_by": "x_api_v2_recent_search",
            })
    candidates.sort(key=lambda p: (-p["score"], p["post_id"]))
    result, authors, themes = [], set(), set()
    for item in candidates:
        if item["author"].lower() in authors or item["theme"] in themes:
            continue
        authors.add(item["author"].lower())
        themes.add(item["theme"])
        result.append(item)
        if len(result) >= limit:
            break
    return result


def safe_count(value) -> int:
    try:
        return max(0, min(100_000_000, int(value)))
    except (TypeError, ValueError, OverflowError):
        return 0


def collect(now: datetime, *, token: str | None = None, enabled: bool = False,
            fetch=api_recent, previous_ids=None) -> dict:
    if now.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    if not enabled:
        return {"schema": SCHEMA, "status": "disabled_pending_cost_authorization",
                "posts": [], "errors": [], "requests": 0}
    token = token or ""
    if len(token.strip()) < 15:
        return {"schema": SCHEMA, "status": "missing_x_bearer_token",
                "posts": [], "errors": [], "requests": 0}
    responses, errors = [], []
    for query in QUERIES[:MAX_QUERIES_PER_RUN]:
        try:
            responses.append(fetch(token, query))
        except HTTPError as exc:
            errors.append("HTTP_" + str(exc.code))
            break
        except (URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
            errors.append(type(exc).__name__)
            break
    # Fail closed on any search failure: do not mix partial claims with a
    # supposedly complete daily verified radar.
    posts = [] if errors else select(responses, now, exclude_ids=previous_ids)
    return {"schema": SCHEMA, "status": "api_error" if errors else
            "ok" if posts else "no_matches", "posts": posts, "errors": errors,
            "requests": len(responses) + len(errors), "previous_ids": sorted(previous_ids or [])}


def read_previous_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    body = path.read_text(encoding="utf-8", errors="replace")
    if len(body) > 150_000:
        raise ValueError("Previous issue unexpectedly large")
    match = re.search(r"<!-- " + re.escape(HISTORY_TAG) + r"([0-9,]*) -->", body)
    if match is None:
        return set()
    return {x for x in match.group(1).split(",") if POST_ID_RE.fullmatch(x)}


def markdown(report: dict) -> str:
    if report.get("schema") != SCHEMA:
        raise ValueError("Unrecognised X radar report")
    lines = [
        "# GTA VI - Social Radar: post verificati e risposte pronte", "",
        "**Metodo:** X API v2 Recent Search, sola lettura. Il termine verificato "
        "significa che ID, autore, testo e data provengono dall'API X; "
        "non significa che le affermazioni del tweet siano vere.", "",
        "**Interazioni:** solo umane. Il bot non mette cuori e non invia "
        "commenti, repost, follow o messaggi.", "",
    ]
    if report["status"] == "disabled_pending_cost_authorization":
        lines.extend(["**Ricerca X API a consumo disattivata.** Lo scanner gratuito "
                      "RSS + oEmbed opera separatamente e non richiede pagamenti. "
                      "Per la ricerca completa nell'archivio recente di X, "
                      "serve l'API ufficiale.", "",
                      "**Stato API: pronto ma non autorizzato a consumare crediti X.** "
                      "Serve attivare la variabile repository X_SOCIAL_RADAR_ENABLED=true "
                      "dopo aver impostato un limite di spesa su console.x.com.", ""])
    elif report["status"] == "missing_x_bearer_token":
        lines.extend(["**Stato: manca il segreto GitHub X_BEARER_TOKEN.** "
                      "Non inserire mai la chiave in Issue, workflow, chat o codice.", ""])
    elif report["status"] == "api_error":
        lines.extend(["**X API non disponibile:** " +
                      ", ".join(report["errors"]) +
                      ". Non sono stati inventati tweet o inviati commenti.", ""])
    elif report["status"] == "no_matches":
        lines.extend(["Nessun post recente pertinente e verificabile oggi.", ""])
    for index, post in enumerate(report["posts"], 1):
        lines.extend([
            "## " + str(index) + ". " + escape(post["author"]) +
            " - " + post["theme"] + " (" + post["language"] + ")",
            "[Apri tweet / metti cuore](" + post["url"] + ") | "
            "[Apri risposta precompilata](" + post["reply_url"] + ")", "",
            "Pubblicato UTC: " + post["published_utc"], "",
            "Estratto dal post originale (massimo 100 caratteri): "
            + escape(post["source_excerpt"]), "",
            "**Testo già pronto da copiare:**", "",
            "~~~text", post["reply"], "~~~", "",
            "Controlla il contenuto del tweet prima di inviare: "
            "la bozza è selezionata per argomento, non approvata "
            "editorialmente. Nessun invio automatico.", "",
        ])
    if report.get("free_scout") is not None:
        from x_free_public_embed_scout_v1 import section
        lines.extend(section(report["free_scout"]).rstrip().splitlines())
        lines.append("")
    old = list(report.get("previous_ids", []))
    current = ([p["post_id"] for p in report["posts"]]
               +[p["post_id"] for p in report.get("free_scout",{}).get("posts",[])])
    history = list(dict.fromkeys(old + current))[-MAX_HISTORY:]
    lines.extend([
        "---", "",
        "Costi: al massimo 2 ricerche da 10 risultati per esecuzione. "
        "I costi X sono per risorsa e possono cambiare; gli utenti espansi "
        "possono essere fatturati separatamente. Configura e controlla "
        "il limite di spesa nella X Developer Console.", "",
        "https://docs.x.com/x-api/posts/search/introduction", "",
        "https://docs.x.com/x-api/getting-started/pricing", "",
        "<!-- " + HISTORY_TAG + ",".join(history) + " -->",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous-report", type=Path)
    args = parser.parse_args()
    enabled = os.getenv("X_SOCIAL_RADAR_ENABLED", "false").lower() == "true"
    previous_ids = read_previous_ids(args.previous_report) if args.previous_report else set()
    result = collect(datetime.now(timezone.utc),
                     token=os.getenv("X_BEARER_TOKEN", ""),
                     enabled=enabled, previous_ids=previous_ids)
    result["previous_ids"] = sorted(previous_ids)
    if not enabled:
        # Zero-cost fallback uses only exact X status links already present
        # in trusted RSS and validates them via the public official embed.
        try:
            from x_free_public_embed_scout_v1 import collect as free_collect
            result["free_scout"]=free_collect(datetime.now(timezone.utc),
                                               previous_ids=previous_ids)
        except (ValueError,OSError,TypeError) as error:
            result["free_scout"]={"status":"source_unavailable","posts":[],
                                   "feed_errors":[type(error).__name__],
                                   "oembed_checks":0,"discovered_links":0}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown(result), encoding="utf-8")
    print("X_RADAR_STATUS", result["status"], "official_api_posts", len(result["posts"]),
          "free_oembed_posts",len(result.get("free_scout",{}).get("posts",[])),
          "api_requests", result["requests"], "manual_only", True)


if __name__ == "__main__":
    main()
