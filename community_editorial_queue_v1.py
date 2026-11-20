"""Independent editorial triage for the community research digest.

This is a GitHub-native, no-LLM, no-Buffer safety stage. It labels source
headlines as leads, never asserts the contents of an unread article.
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

CATEGORIES = (
    ("🟣 DATAMINING", re.compile(r"\b(datamin(?:e|ing|ed)|file\s+find|game\s+files)\b", re.I)),
    ("🟠 RUMOR", re.compile(r"\b(rumou?r|unconfirmed|alleged|supposedly|leak(?:ed|s)?|speculation|theory)\b", re.I)),
    ("🟡 COMMUNITY", re.compile(r"\b(community|fan(?:s)?|reddit|forum)\b", re.I)),
)
GTA_TOPIC = re.compile(r"\b(?:gta[\s-]*(?:6|vi|online)|grand theft auto|vice city|lucia|jason duval)\b", re.I)
GUIDE = re.compile(r"\b(?:guide|walkthrough|troph(?:y|ies)|achievement|cheat|glitch|collectible|mission|vehicle|cars|settings|hdr)\b", re.I)
MAX_ENTRIES = 25
ISSUE_MARKER = "<!-- gta6-community-editorial-queue-v1 -->"
BRIDGE_MARKER = "<!-- gta6-verified-source-feed-b64:"


def safe_md(text: str) -> str:
    """Escape Markdown metacharacters from untrusted feed titles."""
    value = re.sub(r"[\x00-\x1f\x7f]+", " ", str(text)).strip()
    return "".join("\\" + char if char in "\\`*_{}[]()#+.!>|" else char for char in escape(value))



def classify(item: dict) -> tuple[str, str]:
    title = item["title"]
    for label, pattern in CATEGORIES:
        if pattern.search(title):
            return label, "Titolo da verificare; non è una conferma."
    if item.get("tier") == "community":
        return "🟡 COMMUNITY", "Segnalazione pubblica di giocatori: verificare nel gioco e con fonti indipendenti."
    if item.get("tier") == "specialist_video":
        return "🔵 GUIDA INDIPENDENTE", "Video del creator: controllare contenuti e versione prima di citarlo."
    if item.get("tier") == "specialist":
        return "🔵 GUIDA INDIPENDENTE", "Titolo di fonte specialistica: verificare testo, piattaforma e patch."
    return "🟡 SEGNALAZIONE", "Notizia non verificata nel dettaglio."


def valid_candidate(item: dict) -> bool:
    try:
        url = urlsplit(item["url"])
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.port not in (None, 443):
            return False
        if not item["title"] or len(item["title"]) > 300:
            return False
        reddit=(item.get("source")=="Reddit r/GTA6"
                and url.hostname in {"www.reddit.com","reddit.com"}
                and url.path.lower().startswith("/r/gta6/comments/")
                and re.search(r"\b(?:money|cash|glitch|vehicle|garage|car|location|map|collectible|mission|trophy|platinum|secret|tips|PS5|100\s*%)\b",
                              item["title"],re.I))
        return bool(GTA_TOPIC.search(item["title"]) or reddit or
                    (item.get("source") == "PowerPyx" and GUIDE.search(item["title"])))
    except (KeyError, TypeError, ValueError):
        return False


def markdown(digest: dict) -> str:
    if digest.get("schema") != "gta6-research-digest-v1":
        raise ValueError("Unexpected research digest schema")
    candidates = [x for x in digest.get("candidates", []) if valid_candidate(x)]
    candidates = candidates[:MAX_ENTRIES]
    # Machine-readable research leads for the independently deployed site.
    # These are explicitly NOT verified article claims or permissions to tweet.
    feed = {"schema": "gta6-community-feed-v1",
            "generated_utc": str(digest.get("generated_utc", "")),
            "items": [
                {"source": x["source"], "tier": x.get("tier", "specialist"),
                 "title": x["title"], "url": x["url"],
                 "published_utc": x["published_utc"], "status": classify(x)[0],
                 "verified": False}
                for x in candidates
            ]}
    encoded = base64.urlsafe_b64encode(
        json.dumps(feed, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    lines = [
        ISSUE_MARKER,
        BRIDGE_MARKER + encoded + " -->",
        "# GTA VI — coda editoriale indipendente",
        "",
        "**Generato automaticamente da GitHub Actions, senza ChatGPT.**",
        "Questi sono **titoli e link da controllare**, non riassunti di articoli letti.",
        "Non rappresentano annunci Rockstar e non vengono inviati a Buffer.",
        "",
        f"Scansione UTC: {escape(str(digest.get('generated_utc', 'non disponibile')))}",
        f" | Candidati pertinenti: {len(candidates)}",
        "",
        "## Nuove piste editoriali",
        "",
    ]
    if not candidates:
        lines.append("Nessun nuovo titolo pertinente nella finestra di scansione.")
    for item in candidates:
        status, note = classify(item)
        title = safe_md(item["title"])
        source = safe_md(item["source"])
        url = item["url"].replace(")", "%29")
        lines.extend([
            f"### {status} — {title}",
            f"Fonte: **{source}** · Data fonte: {safe_md(item['published_utc'])}",
            f" · [Apri originale]({url})",
            f"Verifica: {note} **Nessun controllo trophy-safe implicito.**",
            "",
        ])
    errors = digest.get("errors", [])
    lines.extend(["## Salute dei feed", ""])
    if errors:
        for e in errors:
            lines.append(f"- ⚠️ {safe_md(e['source'])}: {safe_md(e['error'])} — acquisizione non riuscita")
    else:
        lines.append("- Feed interrogati senza errori segnalati.")
    lines.extend([
        "",
        "## Fonti registrate per verifica manuale",
        "",
        ", ".join(safe_md(x["name"]) for x in digest.get("manual_sources", [])) or "Nessuna",
        "",
        "## Regole per la pubblicazione",
        "",
        "Per ogni candidato: verificare fonte originale, patch, piattaforma, riscontri indipendenti,",
        "diritti dei media, duplicazioni, rischi per i trofei. Etichettare rumor e datamining.",
        "Non trasformare una segnalazione in fatto accertato. Il canale Buffer rimane separato.",
        "",
        "Il monitor aggiorna **questa stessa issue**, senza creare duplicati.",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    digest = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown(digest), encoding="utf-8")
    print("EDITORIAL_QUEUE", len(digest.get("candidates", [])), "read_only=true")


if __name__ == "__main__":
    main()
