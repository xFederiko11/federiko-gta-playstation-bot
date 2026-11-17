"""Thread X brevi, verificabili e deterministici per eventi gia' approvati.

Non consulta servizi AI, social o notizie esterne; NON crea fatti nuovi e non
presenta la data di osservazione come data di pubblicazione della fonte.
Ogni thread e' una sola createPost Buffer, con array metadata.twitter.thread.
"""

import re

from presentation import format_post, _post_weight
from seo_policy import append_relevant_tags, search_context

MAX_WEIGHT = 280
MAX_THREAD_POSTS = 4


def _plain(value):
    return " ".join(str(value or "").split())


def _shorten(text, limit=130):
    text = _plain(text)
    if len(text) <= limit:
        return text
    end = text[: limit - 1].rsplit(" ", 1)[0] or text[: limit - 1]
    return end + "…"


def _fact_lines(event):
    result = []
    title = _plain(event.get("title")).casefold()
    for fact in event.get("facts", []):
        if not isinstance(fact, dict):
            continue
        value = fact.get("value")
        if value is None or value == "" or isinstance(value, (dict, list, tuple)):
            continue
        label = _plain(fact.get("label"))
        fact_value = _plain(value)
        if not label or not fact_value:
            continue
        # Un titolo ripetuto non e' una notizia aggiuntiva.
        if label.casefold() in {"titolo dalla fonte", "pagina osservata"} and fact_value.casefold() == title:
            continue
        result.append(f"• {label}: {_shorten(fact_value, 160)}")
    return result[:6]


def _intro(event):
    game = _plain(event.get("game"))
    if game == "PlayStation":
        header = "🕹️ PLAYSTATION NEWS CENTER"
    elif game == "GTA VI":
        header = "🎮 GTA VI / GTA 6 NEWS CENTER"
    else:
        return None
    platforms = event.get("platforms") or []
    if isinstance(platforms, str):
        platforms = [platforms]
    platforms = " + ".join(_plain(p) for p in platforms if _plain(p))
    title = _shorten(event.get("title") or "Aggiornamento ufficiale", 115)
    version = _plain(event.get("version"))
    context = search_context(event)
    result = [header, _shorten(platforms, 55) if platforms else "", context, title]
    if version and version not in title:
        result.append("Versione indicata: " + _shorten(version, 50))
    return "\n".join(row for row in result if row)


def thread_for_event(event):
    """Lista di post o None per mantenere il post singolo originale.

    Thread solo per PS system e GTA VI, solo fonte ufficiale, senza rumor.
    Una notizia senza dettagli affidabili resta post singolo.
    """
    if event.get("trust") != "official" or event.get("demo") or event.get("spoiler"):
        return None
    introduction = _intro(event)
    if not introduction:
        return None
    facts = _fact_lines(event)
    if not facts or not _plain(event.get("source_url")):
        return None
    source_url = _plain(event["source_url"])
    if not re.fullmatch(r"https://[^\s]+", source_url):
        return None

    detail_posts = []
    current = ""
    for line in facts:
        line = _shorten(line, 195)
        attempt = (current + "\n" + line).strip()
        if _post_weight("2/4 — DETTAGLI DALLA FONTE\n" + attempt) <= MAX_WEIGHT:
            current = attempt
        else:
            if current:
                detail_posts.append(current)
            current = line
        if len(detail_posts) >= MAX_THREAD_POSTS - 2:
            break
    if current and len(detail_posts) < MAX_THREAD_POSTS - 2:
        detail_posts.append(current)
    if not detail_posts:
        return None

    n = 2 + len(detail_posts)
    posts = [append_relevant_tags(f"1/{n} — {introduction}", event, _post_weight)]
    for i, content in enumerate(detail_posts, 2):
        posts.append(f"{i}/{n} — DATI CONFERMATI\n{content}")
    posts.append(f"{n}/{n} — FONTE UFFICIALE\n{source_url}\n\nNota: versione osservata non equivale a data di rilascio.")

    # Rifiuta un thread ambiguo invece di troncare fonte o singole evidenze.
    if any(_post_weight(post) > MAX_WEIGHT for post in posts):
        return None
    return posts


def news_center_preview(event):
    """Preview esplicita: una bozza non significa post pubblicato."""
    thread = thread_for_event(event)
    if not thread:
        return [format_post(event)]
    return thread
