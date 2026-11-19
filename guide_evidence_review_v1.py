"""Evidence-based guide review queue; no fabricated claims or automatic article posts.

Produces stable topic clusters and actionable review templates from independently
attributed source leads. Corroboration is only about matching headlines, NOT
verification of the actual gameplay method or trophy safety.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
from html import escape
from community_editorial_queue_v1 import safe_md
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

SCHEMA = "gta6-guide-review-v1"
TOPICS = (
    ("trofei", re.compile(r"\b(troph(?:y|ies)|achievement|platinum|platino)\b",re.I)),
    ("glitch", re.compile(r"\b(glitch|exploit|duplication|duplicate|money farm|xp farm)\b",re.I)),
    ("trucchi", re.compile(r"\b(cheat|code|codici|trucchi)\b",re.I)),
    ("missioni", re.compile(r"\b(mission|walkthrough|chapter|heist)\b",re.I)),
    ("veicoli", re.compile(r"\b(vehicle|car|bike|boat|jet ski|garage)\b",re.I)),
    ("collezionabili", re.compile(r"\b(collectible|collectable|hidden package|easter egg)\b",re.I)),
    ("hdr", re.compile(r"\b(hdr|oled|brightness|graphics|display)\b",re.I)),
)
SOURCES = {
    "PowerPyx": {"powerpyx.com","www.powerpyx.com"},
    "GTA Series Videos": {"youtube.com","www.youtube.com"},
    "GTABase": {"gtabase.com", "www.gtabase.com"},
}
MAX_ITEMS = 50


def topic(title: str) -> str:
    for label, pattern in TOPICS:
        if pattern.search(title):
            return label
    return "altro"


def validate(digest: dict) -> list[dict]:
    if digest.get("schema")!="gta6-research-digest-v1":
        raise ValueError("Unknown research schema")
    entries=digest.get("candidates")
    if not isinstance(entries,list) or len(entries)>MAX_ITEMS:
        raise ValueError("Invalid research size")
    results=[]
    for item in entries:
        if not isinstance(item,dict):
            raise ValueError("Invalid research entry")
        source=item.get("source")
        if source not in SOURCES:
            continue
        uri=urlsplit(str(item.get("url","")))
        if (uri.scheme!="https" or uri.hostname not in SOURCES[source]
                or uri.username or uri.password or uri.port not in (None,443)):
            raise ValueError("Untrusted source URL")
        title=str(item.get("title",""))
        if not 5<=len(title)<=300:
            raise ValueError("Invalid title")
        stamp=datetime.fromisoformat(str(item["published_utc"]).replace("Z","+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("Unzoned publication date")
        results.append(item)
    return results


def make_report(digest:dict) -> dict:
    entries=validate(digest)
    grouped=defaultdict(list)
    for item in entries:
        grouped[topic(item["title"])].append({
            "source":item["source"],"title":item["title"],
            "url":item["url"],"published_utc":item["published_utc"]})
    sections=[]
    target_pages={"trofei":["trofei/"],"trucchi":["trucchi/"],
                  "glitch":["guide-e-tutorial/"],"missioni":["guide-e-tutorial/"],
                  "veicoli":["guide-e-tutorial/scansionare-veicoli/"],
                  "collezionabili":["guide-e-tutorial/"],"hdr":["hdr-oled/"],
                  "altro":["scoperte/"]}
    for name in sorted(grouped):
        rows=grouped[name]
        sections.append({
            "topic":name,
            "source_count":len({x["source"] for x in rows}),
            "lead_count":len(rows),
            "leads":rows[:12],
            # Two sources discussing "missions" does not corroborate the same claim.
            "claim_verified":False,
            "trophy_safe_verified":False,
            "platform_verified":False,
            "patch_verified":False,
            "ready_to_publish":False,
            "editorial_action":"review_original_sources_and_independent_in_game_evidence",
            "target_page_candidates":target_pages.get(name,["scoperte/"]),
        })
    return {"schema":SCHEMA,"generated_utc":digest.get("generated_utc"),
            "sections":sections,"publication":"review_only__no_site_or_buffer_changes"}


def markdown(report:dict) -> str:
    if report.get("schema")!=SCHEMA:
        raise ValueError("Unknown review schema")
    lines=["<!-- gta6-guide-review-v1 -->","# GTA VI — revisione guide e scoperte","",
           "Questa è una **lista di verifiche**, non una guida già verificata.",
           "Titoli simili non provano che descrivano lo stesso glitch o metodo.",
           "Nessun testo di articoli copiato; nessun post X o modifica del sito.",""]
    if not report["sections"]:
        lines.append("Nessuna pista recente adatta alla revisione.")
    for section in report["sections"]:
        lines.extend([
            "## "+escape(section["topic"].title())+
            f" — {section['lead_count']} titoli, {section['source_count']} fonti",
            "",
            "- [ ] Aprire le fonti originali e identificare una **stessa affermazione specifica**",
            "- [ ] Cercare una seconda conferma **indipendente** sulla stessa affermazione",
            "- [ ] Verificare versione/patch, data, PS5/PS5 Pro e passaggi esatti",
            "- [ ] Verificare **separatamente** trofei e salvataggi; non inferire trophy-safe",
            "- [ ] Confrontare la guida già pubblicata e preparare solo modifiche supportate",
            "- [ ] Usare media con diritti e citare gli autori",
            "",
        ])
        lines.append("Pagine da confrontare: " + ", ".join(
            "`"+p+"`" for p in section["target_page_candidates"]))
        lines.append("")
        for lead in section["leads"]:
            title=safe_md(lead["title"])
            url=lead["url"].replace(")","%29")
            lines.append(f"- {safe_md(lead['source'])}: [{title}]({url}) ({escape(lead['published_utc'][:10])})")
        lines.append("")
    lines.extend(["**Regola:** la verifica dei titoli non abilita mai la pubblicazione automatica.",
                  "Per pubblicare una guida occorre evidenza verificata sul contenuto e sui trofei.",""])
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--json",type=Path,required=True)
    p.add_argument("--markdown",type=Path,required=True)
    a=p.parse_args()
    report=make_report(json.loads(a.input.read_text(encoding="utf-8")))
    for path in (a.json,a.markdown):
        path.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    a.markdown.write_text(markdown(report),encoding="utf-8")
    print("GUIDE_REVIEW",len(report["sections"]),"ready_to_publish=0")


if __name__=="__main__":
    main()
