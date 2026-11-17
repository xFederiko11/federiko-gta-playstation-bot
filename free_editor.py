"""Titoli e schede deterministici: nessun servizio AI o lettura API X."""

import re
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def compact(text, limit=105):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def game_from(text):
    patterns = [("GTA Online", r"gta\s*online|grand theft auto online|gta\+"),
                ("GTA VI", r"grand theft auto\s*(?:vi|6)\b|gta\s*(?:vi|6)\b|gtavi\b"),
                ("GTA V", r"grand theft auto\s*(?:v|5)\b|gta\s*(?:v|5)\b|gtav\b")]
    return next((name for name, pattern in patterns if re.search(pattern, text, re.I)), None)


def platforms_from(text):
    platforms = []
    for name, pattern in [
        ("PS5", r"\bps5\b|playstation\s*5"), ("PS4", r"\bps4\b|playstation\s*4"),
        ("Xbox Series X|S", r"xbox\s*series\s*x(?:\s*[|/]|\s+and|\s+e)?\s*s\b|xbox\s*series\s*x\s*\|\s*s"),
        ("Xbox Series X", r"xbox\s*series\s*x\b(?!\s*[|/]\s*s\b)"),
        ("Xbox Series S", r"xbox\s*series\s*s\b"),
        ("Xbox One", r"xbox\s*one\b"), ("PC", r"\bpc\b|personal computer")]:
        if re.search(pattern, text, re.I):
            platforms.append(name)
    return platforms


def article_event(item, allow_community=False):
    if item.get("trust") == "community" and not allow_community:
        return None
    if item.get("presentation"):
        return dict(item["presentation"])
    body = str(item.get("text", ""))
    headline = str(item.get("headline") or body.split("\n", 1)[0]).strip()
    game = game_from(headline) or game_from(body)
    if not game:
        return None
    category = "NEWS"
    lower = (headline + " " + body).lower()
    if re.search(r"\bpatch(?:es)?\b|\bhotfix(?:es)?\b|\btitle update\b|\bbug fix|\bcorrezion", lower):
        category = "PATCH"
    elif re.search(r"bonus|discount|\d+%|gta\+|rewards|event week", lower):
        category = "EVENTI"
    elif re.search(r"maintenance|service status|server outage|manutenzione", lower):
        category = "SERVIZI"
    facts = []
    for label, pattern in [
        ("Moltiplicatore indicato", r"\b\d+(?:\.\d+)?\s*[x×]\s*(?:GTA\$\s*(?:&\s*RP)?|RP)"),
        ("Sconto indicato", r"\b\d{1,3}\s*%\s*(?:off|discount|di sconto)")]:
        for match in re.finditer(pattern, body, re.I):
            value = " ".join(match.group().split())
            fact = {"label": label, "value": value}
            if fact not in facts:
                facts.append(fact)
    if not facts:
        facts = [{"label": "Titolo dalla fonte", "value": compact(headline, 140)},
                 {"label": "Numero versione", "value": None}]
    editorial_title = compact(headline)
    data_kind = "announcement"
    if item.get("change_context"):
        editorial_title = "Patch note aggiornata" if category == "PATCH" else "Pagina della fonte aggiornata"
        facts = [{"label": "Pagina osservata", "value": compact(headline, 140)},
                 {"label": "Variazione", "value": "Testo della pagina modificato"}]
        data_kind = "page_revision"
    identity = item.get("source_url") or item["key"]
    if item.get("change_context"):
        identity += ":observation:" + item["key"]
    return {"event_key": identity, "game": game,
            "category": category, "data_kind": data_kind, "region": item.get("region"),
            "platforms": item.get("platforms") or platforms_from(body), "title": editorial_title,
            "facts": facts, "trust": item.get("trust", "official"),
            "source_name": item.get("source_name", "Fonte"), "source_url": item.get("source_url", ""),
            "official_channel_id": item.get("official_channel_id"),
            "official_image_url": item.get("official_image_url"),
            "observed_at": item.get("observed_at") or now(),
            "spoiler": bool(item.get("spoiler")) or bool(re.search(r"story trailer|story mission|plot|trama", lower))}


def article_events(item, allow_community=False):
    """Separa solo dati console espressi in clausole inequivocabili, senza indovinarli."""
    base = article_event(item, allow_community)
    if base is None:
        return []
    if item.get("presentation") or item.get("change_context"):
        return [base]
    text = str(item.get("text", ""))
    # Il separatore è obbligatorio: 'PS5 and Xbox require 100 GB' è comune,
    # non una misura assegnabile arbitrariamente all'ultima console nominata.
    platform = r"(?:PlayStation\s*5|PS5|PlayStation\s*4|PS4|Xbox\s*Series\s*X\s*[|/]\s*S|Xbox\s*One|PC)"
    clauses = list(re.finditer(r"(?P<platform>" + platform + r")\s*[:：–-]\s*", text, re.I))
    details = []
    for index, match in enumerate(clauses):
        end = clauses[index + 1].start() if index + 1 < len(clauses) else min(len(text), match.end() + 180)
        clause = text[match.end():end].split(";", 1)[0].split("\n", 1)[0]
        facts = []
        size = re.search(r"(?:circa\s+|about\s+|~\s*)?\d+(?:[.,]\d+)?\s*(?:GiB|MiB|GB|MB|byte)\b", clause, re.I)
        version = re.search(r"\b\d{1,2}\.\d{1,3}\.\d{1,3}(?:\.\d{1,3})?\b", clause)
        if size:
            facts.append({"label": "Dimensione indicata dalla fonte", "value": size.group().strip()})
        if version:
            facts.append({"label": "Versione piattaforma", "value": version.group()})
        if not facts:
            continue
        names = platforms_from(match.group("platform"))
        if not names:
            continue
        value = {**base, "platforms": names, "facts": facts, "data_kind": "source_console_details",
                 "region": item.get("region") or ("GLOBAL" if re.search(r"worldwide|globally|all regions|tutte le regioni", text, re.I) else None)}
        if version:
            value["version_namespace"] = "PS_PACKAGE" if names[0].startswith("PS") else "XBOX_PACKAGE" if names[0].startswith("Xbox") else "PC_PACKAGE"
        details.append(value)
    return details or [base]


def catalog_event(signal):
    value = signal["value_bytes"]
    return {"event_key": f"gta6-catalog:{signal['region']}:{signal['metric_kind']}",
            "game": signal["game"], "category": "METADATI", "data_kind": signal["metric_kind"],
            "region": signal["region"], "platforms": signal["platforms"],
            "title": "Metadati installazione del catalogo aggiornati" if signal["metric_kind"] == "max_install" else "Metadati download del catalogo aggiornati",
            "facts": [{"label": signal["metric_label"], "value": value, "unit": "byte"},
                      {"label": "Numero build", "value": signal.get("version")},
                      {"label": "Misura effettiva della patch", "value": None}],
            "source_url": signal["source_url"], "source_name": signal["source_name"],
            "trust": "observation", "observed_at": signal["observed_at"]}
