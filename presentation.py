"""Card e testo locali, senza API: origine visibile e dati per piattaforma.

Schema evento: event_key, game, category, data_kind, region, platforms,
title, facts=[{label, value, unit?}], trust, source_name, source_url,
observed_at, version_namespace? e demo?.
facts deve contenere tutti i dati significativi da confrontare. None / stringa
vuota significa dato mancante e impedisce l'unione di più eventi. Una versione
di pacchetto richiede un version_namespace condiviso per poter essere unita
fra piattaforme; il solo fatto che due numeri coincidano non basta.
"""

from __future__ import annotations

import copy
import html
import json
import os
import re
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

from seo_policy import search_label, search_context, relevant_tags


WIDTH, HEIGHT = 1600, 900
TRUST_LABELS = {
    "official": "FONTE UFFICIALE",
    "observation": "RILEVATO DAL BOT",
    "community": "SEGNALAZIONE COMMUNITY",
}
PLATFORM_ORDER = {"PS5": 0, "PS4": 1, "Xbox Series X|S": 2, "Xbox Series X": 3,
                  "Xbox Series S": 4, "Xbox One": 5, "PC": 6}
TECHNICAL_KEYS = ("version", "build", "download_bytes", "install_bytes", "patch_bytes",
                  "size_bytes", "sha256", "md5", "measurements", "files", "data")
_URL = re.compile(r"https?://\S+")


def _text(value):
    return " ".join(unicodedata.normalize("NFC", str(value)).split())


def _missing(value):
    if value is None or value == "":
        return True
    if isinstance(value, Mapping):
        return not value or any(_missing(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return not value or any(_missing(item) for item in value)
    return False


def _normal(value):
    """Conserva tipi e unità: niente equivalenze inventate GB/GiB o stringhe/numeri."""
    if isinstance(value, Mapping):
        return {str(key): _normal(item) for key, item in sorted(value.items(), key=lambda p: str(p[0]))}
    if isinstance(value, (list, tuple)):
        return [_normal(item) for item in value]
    if isinstance(value, str):
        return _text(value)
    return {"type": type(value).__name__, "value": value}


def _platforms(event):
    platforms = event.get("platforms")
    if platforms is None:
        platforms = [event["platform"]] if event.get("platform") else []
    if isinstance(platforms, str):
        platforms = [platforms]
    return sorted({_text(value) for value in platforms if value is not None and _text(value)},
                  key=lambda value: (PLATFORM_ORDER.get(value, 100), value.casefold()))


def _fingerprint(event):
    # Senza un'identità condivisa non si può dedurre che due rilevamenti
    # appartengano alla stessa release o allo stesso annuncio.
    if any(_missing(event.get(key)) for key in ("event_key", "game", "category", "data_kind", "region")):
        return None
    if not _platforms(event):
        return None
    facts = event.get("facts", [])
    if not isinstance(facts, list) or not facts:
        return None
    ordered = []
    for fact in facts:
        if not isinstance(fact, Mapping) or _missing(fact.get("label")) or _missing(fact.get("value")):
            return None
        ordered.append({"label": _text(fact["label"]).casefold(), "value": _normal(fact["value"]),
                        "unit": _text(fact.get("unit", ""))})
    ordered.sort(key=lambda fact: json.dumps(fact, sort_keys=True, ensure_ascii=False))
    versioned = any(not _missing(event.get(key)) for key in ("version", "build")) or any(
        any(word in fact["label"] for word in ("version", "versione", "build", "firmware")) for fact in ordered)
    if versioned and _missing(event.get("version_namespace")):
        return None
    details = {key: event[key] for key in TECHNICAL_KEYS if key in event}
    if any(_missing(value) for value in details.values()):
        return None
    signature = {
        "event_key": _text(event["event_key"]), "game": _text(event["game"]),
        "category": _text(event["category"]).casefold(), "data_kind": _text(event["data_kind"]).casefold(),
        "region": _text(event["region"]).casefold(), "trust": event.get("trust", "unknown"),
        "spoiler": bool(event.get("spoiler")), "demo": bool(event.get("demo")),
        "facts": ordered, "technical": _normal(details),
        "version_namespace": _text(event.get("version_namespace", "")),
    }
    return json.dumps(signature, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _source_records(event):
    records = list(event.get("sources", []))
    if event.get("source_name") or event.get("source_url"):
        records.append({"name": event.get("source_name", ""), "url": event.get("source_url", ""),
                        "observed_at": event.get("observed_at", "")})
    unique = []
    for record in records:
        if record not in unique:
            unique.append(copy.deepcopy(record))
    return unique


def group_platform_events(events):
    """Unisce solo eventi completi con dati significativi identici.

    Ignora console, autore, URL e timestamp nel confronto; conserva l'elenco
    delle prove in sources. Regioni, unità, dimensioni, namespace di versione,
    livelli di provenienza e dati diversi restano separati. L'input non cambia.
    """
    groups, lookup = [], {}
    for original in events:
        event = copy.deepcopy(original)
        event["platforms"] = _platforms(event)
        event["sources"] = _source_records(event)
        signature = _fingerprint(event)
        if signature is None or signature not in lookup:
            groups.append(event)
            if signature is not None:
                lookup[signature] = event
            continue
        target = lookup[signature]
        if _text(target.get("title", "")) != _text(event.get("title", "")):
            target["title"] = target.get("shared_title") or event.get("shared_title") or "Aggiornamento per più piattaforme"
        target["platforms"] = _platforms({"platforms": target["platforms"] + event["platforms"]})
        for source in event["sources"]:
            if source not in target["sources"]:
                target["sources"].append(source)
        # Non scegliere arbitrariamente il timestamp più recente come data
        # di pubblicazione: ogni osservazione conserva la propria data.
        target["observations"] = sorted({str(source.get("observed_at", "")) for source in target["sources"]
                                          if source.get("observed_at")})
    return groups


def _value(fact):
    value = fact.get("value")
    if _missing(value):
        return "Non disponibile"
    if isinstance(value, bool):
        value = "Sì" if value else "No"
    elif isinstance(value, (dict, list, tuple)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    text = _text(value)
    unit = _text(fact.get("unit", ""))
    return text + (" " + unit if unit else "")


def _escape(value):
    return html.escape(_text(value), quote=True)


def render_card_html(event):
    """HTML autosufficiente 1600x900: nessun font, immagine o risorsa remota."""
    game = _escape(event.get("game", "GTA"))
    brand = "PLAYSTATION / UPDATE LOG" if event.get("game") == "PlayStation" else "GTA / UPDATE LOG"
    category = _escape(event.get("category", "AGGIORNAMENTO")).upper()
    if event.get("spoiler"):
        category += " · SPOILER"
    title = _escape(event.get("title", "Nuovo aggiornamento"))
    origin = TRUST_LABELS.get(event.get("trust"), "ORIGINE DA VERIFICARE")
    platforms = _platforms(event)
    platforms_html = "".join(f'<span class="platform">{_escape(value)}</span>' for value in platforms)
    if not platforms_html:
        platforms_html = '<span class="platform missing">Piattaforma non disponibile</span>'
    source_name = _text(event.get("source_name") or "Fonte non disponibile")
    source_url = str(event.get("source_url") or "")
    source_host = urlsplit(source_url).hostname or ""
    date = _text(event.get("observed_at") or "Data non disponibile")
    region = _text(event.get("region") or "Regione non disponibile")
    demo = '<div class="demo">DEMO · DATI FITTIZI</div>' if event.get("demo") else ""
    facts = event.get("facts", [])
    if not facts:
        facts = [{"label": "Dati tecnici", "value": None}]
    tiles = []
    for fact in facts[:6]:
        value = _value(fact)
        size = "small" if len(value) > 36 else "medium" if len(value) > 16 else "large"
        missing = " missing" if _missing(fact.get("value")) else ""
        tiles.append(f'<div class="tile{missing}"><div class="label">{_escape(fact.get("label", "Dato"))}</div>'
                     f'<div class="value {size}">{_escape(value)}</div></div>')
    more = f'<span class="more">+{len(facts) - 6} dettagli nella fonte</span>' if len(facts) > 6 else ""
    origin_color = "#f3c67a" if event.get("trust") == "community" else "#76e7ed"
    layout = "single" if len(tiles) == 1 else "few" if len(tiles) <= 4 else "many"
    title_class = "long" if len(str(event.get("title", ""))) > 66 else ""
    return f'''<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=1600, initial-scale=1">
<style>
* {{box-sizing:border-box}} html,body {{margin:0;width:1600px;height:900px;overflow:hidden}}
body {{font-family:Arial,Helvetica,sans-serif;color:#f5f5fc;background:#0b1021}}
.card {{width:1600px;height:900px;position:relative;overflow:hidden;padding:62px 70px 45px;
background:radial-gradient(ellipse at 88% 12%,#47356e55 0,transparent 45%),radial-gradient(ellipse at 8% 96%,#00566350 0,transparent 46%),linear-gradient(135deg,#10152b,#0c1020 54%,#151126)}}
.grid {{position:absolute;inset:0;opacity:.06;background-image:linear-gradient(#e7e9ff 1px,transparent 1px),linear-gradient(90deg,#e7e9ff 1px,transparent 1px);background-size:64px 64px;mask-image:linear-gradient(90deg,transparent,#000)}}
.orb {{position:absolute;right:-170px;top:220px;width:660px;height:660px;border:1px solid #d17be41c;border-radius:50%}}
.orb:after {{content:"";position:absolute;inset:62px;border:1px solid #d17be420;border-radius:50%}}
.top {{position:relative;display:flex;align-items:center;justify-content:space-between}}
.brand {{font-size:25px;font-weight:700;letter-spacing:4px;color:#c8cee5;display:flex;gap:18px;align-items:center}}
.brand:before {{content:"";display:block;width:10px;height:27px;background:linear-gradient(#7ce7ec,#f47ac6);border-radius:5px}}
.origin {{font-size:18px;letter-spacing:1.5px;font-weight:700;color:{origin_color};padding:12px 18px;border:1px solid #8adce22b;border-radius:9px;background:#77d9e007}}
.demo {{position:absolute;top:116px;right:70px;background:#ed79bd;color:#1b1025;padding:10px 18px;border-radius:8px;font-size:20px;font-weight:800;letter-spacing:1px;z-index:2}}
.content {{position:relative;display:grid;grid-template-columns:570px 1fr;gap:70px;margin-top:89px;height:520px}}
.eyebrow {{display:flex;align-items:center;gap:17px;margin-bottom:27px}}
.game {{font-size:22px;font-weight:800;letter-spacing:1px;background:#efecff;color:#17162b;border-radius:7px;padding:9px 13px;white-space:nowrap}}
.category {{font-size:19px;letter-spacing:2px;font-weight:700;color:#b8aecf}}
h1 {{font-size:65px;line-height:1.06;letter-spacing:-2.5px;font-weight:750;margin:0 0 30px;overflow-wrap:break-word;max-height:285px;overflow:hidden}}
h1.long {{font-size:53px;letter-spacing:-1.6px}}
.accent {{height:5px;width:92px;border-radius:4px;background:linear-gradient(90deg,#7be7e9,#eb7fc2);margin:0 0 29px}}
.platforms {{display:flex;flex-wrap:wrap;gap:11px;max-width:570px}}
.platform {{font-size:21px;line-height:1.2;color:#ced6eb;border:1px solid #707c9e50;background:#131a2e;padding:10px 15px;border-radius:9px}}
.data {{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-content:start;margin-top:4px}}
.tile {{min-height:156px;border:1px solid #abb1d226;background:linear-gradient(135deg,#ffffff08,#ffffff03);border-radius:19px;padding:25px 26px;position:relative;overflow:hidden}}
.tile:first-child {{border-color:#69e4e04d;background:linear-gradient(135deg,#76e9e90b,#ffffff03)}}
.label {{color:#9da7c6;text-transform:uppercase;font-size:17px;letter-spacing:1.5px;font-weight:700;line-height:1.3;margin-bottom:17px}}
.value {{color:#ecf4ff;font-size:44px;line-height:1.18;letter-spacing:-1.1px;font-weight:650;overflow-wrap:anywhere}}
.value.medium {{font-size:32px;letter-spacing:-.5px}} .value.small {{font-size:23px;line-height:1.33;letter-spacing:.05px;font-family:Arial,Helvetica,sans-serif}}
.single .tile {{grid-column:1/-1;min-height:237px;display:flex;flex-direction:column;justify-content:center}}
.single .value {{font-size:59px}} .single .value.small {{font-size:31px}} .single .value.medium {{font-size:42px}}
.many .tile {{min-height:140px;padding:20px 23px}} .many .label {{font-size:16px;margin-bottom:13px}}
.many .value.large {{font-size:39px}} .missing .value,.platform.missing {{color:#8994b4}}
.footer {{position:absolute;bottom:47px;left:70px;right:70px;border-top:1px solid #9dabc22c;padding-top:27px;display:flex;justify-content:space-between;gap:26px;color:#7f8cae}}
.source {{font-size:21px;line-height:1.3;color:#c1cbe0;max-width:770px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.host {{font-size:17px;color:#7c8aaa;margin-top:7px;letter-spacing:.3px}}
.stamp {{text-align:right;font-size:18px;line-height:1.55;color:#a2aec9;max-width:480px}}
.more {{grid-column:1/-1;font-size:17px;color:#9ba8c6;margin-left:3px}}
</style></head><body><main class="card">
<div class="grid"></div><div class="orb"></div>
<div class="top"><div class="brand">{brand}</div><div class="origin">{origin}</div></div>{demo}
<div class="content"><section>
<div class="eyebrow"><span class="game">{game}</span><span class="category">{category}</span></div>
<h1 class="{title_class}">{title}</h1><div class="accent"></div>
<div class="platforms">{platforms_html}</div>
</section><section class="data {layout}">{''.join(tiles)}{more}</section></div>
<div class="footer"><div><div class="source">{_escape(source_name)}</div><div class="host">{_escape(source_host or 'Fonte pubblica non disponibile')}</div></div>
<div class="stamp">{_escape(date)}<br>{_escape(region)}</div></div>
</main></body></html>'''


def render_card(event, png_path):
    """Esporta una PNG con Chromium locale. Non fa richieste di rete."""
    path = Path(png_path)
    if path.suffix.lower() != ".png":
        raise ValueError("render_card richiede un percorso .png")
    path.parent.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(Path(__file__).with_name(".browsers")))
    from playwright.sync_api import sync_playwright
    temporary = path.with_name("." + path.name + ".tmp.png")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
            page.route("**/*", lambda route: route.abort())
            page.set_content(render_card_html(event), wait_until="load")
            page.evaluate("document.fonts.ready")
            page.screenshot(path=str(temporary), type="png", animations="disabled")
        finally:
            browser.close()
    temporary.replace(path)
    return path


def _post_weight(text):
    last, weight = 0, 0
    for match in _URL.finditer(text):
        weight += sum(1 if ord(c) <= 0x10FF or 0x2000 <= ord(c) <= 0x2037 else 2 for c in text[last:match.start()])
        weight += 23
        last = match.end()
    return weight + sum(1 if ord(c) <= 0x10FF or 0x2000 <= ord(c) <= 0x2037 else 2 for c in text[last:])


def format_post(event):
    """Post ricercabile in italiano, max 280 pesati, senza tag fuori contesto.

    Fonte, origine e contenuto hanno priorita' assoluta sugli hashtag. Il testo
    viene ricostruito anche per bozze gia' in coda prima dell'invio.
    """
    label = f"{_text(search_label(event) or event.get('game', 'GTA'))} · {_text(event.get('category', 'AGGIORNAMENTO')).upper()}"
    if event.get("spoiler"):
        label += " · SPOILER"
    if event.get("demo"):
        label = "DEMO · DATI FITTIZI\n" + label
    platform = " + ".join(_platforms(event)) or "Piattaforma non disponibile"
    context = search_context(event)
    origin = TRUST_LABELS.get(event.get("trust"), "ORIGINE DA VERIFICARE")
    original_title = _text(event.get("title", "Nuovo aggiornamento"))
    footer = str(event.get("source_url") or "Fonte pubblica non disponibile")

    prefix = [label, platform] + ([context] if context and context.casefold() not in platform.casefold() else [])
    # Riserva spazio ai tag contestuali, ma non rimuovere mai fonte o etichetta di verifica.
    for number in range(2, -1, -1):
        tags = relevant_tags(event, "\n".join(prefix + [original_title, origin, footer]))[:number]
        tail = [origin, footer] + ([" ".join(tags)] if tags else [])
        title = original_title
        while title and _post_weight("\n".join(prefix + [title + "…"] + tail)) > 280:
            title = title[:-1]
        if title and (len(title) >= min(18, len(original_title)) or number == 0):
            title = title if title == original_title else title + "…"
            break
    else:
        raise ValueError("Metadati del post troppo lunghi")

    base = prefix + [title]
    for fact in event.get("facts", []):
        line = f"• {_text(fact.get('label', 'Dato'))}: {_value(fact)}"
        if _post_weight("\n".join(base + [line] + tail)) <= 280:
            base.append(line)
    result = "\n".join(base + tail)
    if _post_weight(result) > 280:
        raise ValueError("Metadati del post troppo lunghi")
    return result


def demo_events():
    """Dati fittizi: nessuna versione o dimensione reale di GTA VI."""
    base = {"event_key": "demo-update", "game": "GTA VI", "category": "PATCH",
            "data_kind": "package_update", "region": "DEMO / DATI NON REALI",
            "trust": "observation", "title": "Nuova versione disponibile",
            "source_name": "ANTEPRIMA GRAFICA · DATI FITTIZI", "source_url": "https://example.org/demo",
            "observed_at": "17 NOV 2026 · 14:30 UTC", "demo": True,
            "version_namespace": "DEMO_SHARED_BUILD"}
    shared = {**base, "platforms": ["PS5", "Xbox Series X|S"], "facts": [
        {"label": "Versione dimostrativa", "value": "DEMO 0.1"},
        {"label": "Download di esempio", "value": "1.25", "unit": "GiB"},
        {"label": "File modificati", "value": 12},
        {"label": "Patch note", "value": None},
    ]}
    console = {**base, "event_key": "demo-console", "platforms": ["PS5"],
               "title": "Download aggiornato su PS5", "version_namespace": "DEMO_PS5_PACKAGE",
               "facts": [
                   {"label": "Versione dimostrativa", "value": "DEMO 0.2"},
                   {"label": "Download di esempio", "value": "1.60", "unit": "GiB"},
                   {"label": "Dimensione precedente", "value": "1.25", "unit": "GiB"},
                   {"label": "Differenza di esempio", "value": "+0.35", "unit": "GiB"},
               ]}
    return shared, console


if __name__ == "__main__":
    output = Path(__file__).with_name("previews")
    for name, event in zip(("shared-demo", "ps5-demo"), demo_events()):
        output.mkdir(exist_ok=True)
        (output / (name + ".html")).write_text(render_card_html(event), encoding="utf-8")
        render_card(event, output / (name + ".png"))
        print(output / (name + ".png"))
