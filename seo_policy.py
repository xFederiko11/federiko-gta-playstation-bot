"""Parole chiave e hashtag pertinenti ai fatti gia' verificati dal bot.

Non usa trend, scraping di X o keyword stuffing. Al massimo 2 hashtag per
messaggio; non inferisce PS5 Pro da PS5 e non associa firmware Sony a GTA VI.
"""

import re

_HASHTAG = re.compile(r"(?<!\w)#[A-Za-z0-9_]+")


def _platform_flags(event):
    platforms = event.get("platforms") or []
    if isinstance(platforms, str):
        platforms = [platforms]
    platform_text = " ".join(str(p) for p in platforms).casefold()
    # PS5 Pro puo' essere nominata esplicitamente anche nel titolo della fonte.
    headline = str(event.get("title") or "").casefold()
    ps5_pro = bool(re.search(r"\bps5\s*pro\b|\bplaystation\s*5\s*pro\b", platform_text + " " + headline))
    ps5 = ps5_pro or bool(re.search(r"\bps5\b|playstation\s*5\b", platform_text))
    ps4 = bool(re.search(r"\bps4\b|playstation\s*4\b", platform_text))
    return ps5_pro, ps5, ps4


def search_label(event):
    """Solo sinonimi di nome: mai trasformare Playstation in GTA VI."""
    game = str(event.get("game") or "").strip()
    if event.get("demo") or event.get("trust") != "official":
        return game
    if game == "GTA VI":
        return "GTA VI (GTA 6)"
    return game


def search_context(event):
    """Keyword descrittiva solo quando e' supportata dal tipo di evento."""
    if event.get("demo") or event.get("trust") != "official":
        return ""
    game = str(event.get("game") or "").strip()
    if game != "PlayStation" or str(event.get("category") or "").casefold() != "sistema":
        return ""
    pro, ps5, ps4 = _platform_flags(event)
    if pro and not ps4:
        return "Firmware PS5 Pro"
    if ps5 and ps4:
        return "Firmware PS5 e PS4"
    if ps5:
        return "Firmware PS5"
    if ps4:
        return "Firmware PS4"
    return "Firmware PlayStation"


def hashtags_for(event):
    """Massimo due tag specifici, mai basati su mere parole trending."""
    if event.get("demo") or event.get("trust") != "official":
        return ()
    game = str(event.get("game") or "").strip()
    pro, ps5, ps4 = _platform_flags(event)
    platform_tag = "#PS5Pro" if pro else "#PS5" if ps5 else "#PS4" if ps4 else None
    if game == "GTA VI":
        return ("#GTAVI", platform_tag or "#GTA6")
    if game == "GTA Online":
        return tuple(t for t in ("#GTAOnline", platform_tag) if t)
    if game == "GTA V":
        return tuple(t for t in ("#GTAV", platform_tag) if t)
    if game == "PlayStation":
        if ps5 and ps4:
            return ("#PS5", "#PS4")
        if platform_tag:
            return (platform_tag, "#PlayStation")
        return ("#PlayStation",)
    return ()


def relevant_tags(event, text=""):
    """Non duplicare hashtag gia' presenti e limita il totale a due."""
    existing = {tag.casefold() for tag in _HASHTAG.findall(text)}
    slots = max(0, 2 - len(_HASHTAG.findall(text)))
    result = []
    for tag in hashtags_for(event):
        if tag.casefold() not in existing and slots > 0:
            result.append(tag)
            existing.add(tag.casefold())
            slots -= 1
    return tuple(result)


def append_relevant_tags(text, event, weight_fn, limit=280):
    """Aggiunge i soli hashtag che entrano, senza tagliare dettagli/fonte."""
    output = text
    for tag in relevant_tags(event, output):
        candidate = output + "\n\n" + tag if output == text else output + " " + tag
        if weight_fn(candidate) <= limit:
            output = candidate
    return output
