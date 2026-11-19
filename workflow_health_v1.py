"""GitHub-native health check for GTA VI bot, Pages and Buffer delivery ledger.

Read-only monitoring, with an issue as the sole alert surface. Does not call
Buffer, retry posts, alter credentials, change publication limits or scrape sites.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path

import requests

BOT = "xFederiko11/federiko-gta-playstation-bot"
SITE = "xFederiko11/gta-6"
API_ROOT = "https://api.github.com/repos/"
HEALTH_MARKER = "<!-- gta6-github-health-v1 -->"
CHECKS = (
    {"name":"Monitor ufficiale GTA/PlayStation", "repo":BOT,
     "file":"gta-monitor.yml", "max_age_h":8},
    {"name":"Editorial Autopilot", "repo":BOT,
     "file":"gta6-editorial-autopilot-v137.yml", "max_age_h":8},
    {"name":"Ricerca indipendente community", "repo":BOT,
     "file":"gta6-community-research-v1.yml", "max_age_h":18},
    {"name":"Sito GitHub Pages", "repo":SITE,
     "file":"deploy-site.yml", "max_age_h":18},
)
VALID_EVENTS = {"schedule","push","workflow_run","workflow_dispatch"}
BUFFER_WINDOW_H = 6


def as_time(value: str) -> datetime:
    dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timestamp must have UTC offset")
    return dt.astimezone(timezone.utc)


def check_one(check: dict, runs: list[dict], now: datetime) -> dict:
    rows = [x for x in runs if x.get("event") in VALID_EVENTS and
            x.get("status")=="completed"]
    rows.sort(key=lambda x:x.get("created_at",""),reverse=True)
    if not rows:
        return {"name":check["name"],"status":"attention",
                "reason":"Nessuna esecuzione di produzione completata", "url":""}
    recent = rows[0]
    age = now - as_time(recent["created_at"])
    if age > timedelta(hours=check["max_age_h"]):
        status, why="attention","Ultimo workflow troppo vecchio"
    elif recent.get("conclusion") != "success":
        status, why="attention","Ultimo workflow fallito o non concluso correttamente"
    else:
        status, why="ok","Esecuzione recente riuscita"
    return {"name":check["name"],"status":status,"reason":why,
            "url":str(recent.get("html_url","")),
            "latest_run_utc":recent["created_at"],
            "conclusion":recent.get("conclusion")}


def check_buffer_ledger(path: Path, now: datetime) -> dict:
    if not path.exists():
        return {"name":"Consegne Buffer (registro locale)","status":"attention",
                "reason":"Registro di consegna non disponibile in checkout", "url":""}
    data=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("entries"),dict):
        raise ValueError("Malformed Buffer delivery ledger")
    recent=[]
    for x in data["entries"].values():
        if not isinstance(x,dict) or x.get("status") not in ("rejected","uncertain"):
            continue
        stamp=x.get("completed_utc") or x.get("attempted_utc") or x.get("reserved_utc")
        if stamp:
            when=as_time(stamp)
            if timedelta(0) <= now-when <= timedelta(hours=BUFFER_WINDOW_H):
                recent.append(x["status"])
    if recent:
        return {"name":"Consegne Buffer (registro locale)", "status":"attention",
                "reason":f"{len(recent)} esiti rejected/uncertain nelle ultime {BUFFER_WINDOW_H} ore",
                "url":"https://github.com/"+BOT+"/actions"}
    return {"name":"Consegne Buffer (registro locale)", "status":"ok",
            "reason":"Nessun esito rejected/uncertain recente nel ledger", "url":""}


def fetch_runs(check:dict, token:str, *, session=None) -> list[dict]:
    http=session or requests
    uri=API_ROOT+check["repo"]+"/actions/workflows/"+check["file"]+"/runs?per_page=25"
    headers={"Accept":"application/vnd.github+json",
             "User-Agent":"GTA-VI-health-watch/1.0",
             "X-GitHub-Api-Version":"2022-11-28"}
    if token:
        headers["Authorization"]="Bearer "+token
    r=http.get(uri,headers=headers,timeout=(5,12))
    r.raise_for_status()
    payload=r.json()
    if not isinstance(payload.get("workflow_runs"),list):
        raise ValueError("Invalid actions runs API response")
    return payload["workflow_runs"]


def inspect(now=None, *,token="",session=None,ledger=None) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware time required")
    systems=[]
    for check in CHECKS:
        try:
            runs=fetch_runs(check,token,session=session)
            systems.append(check_one(check,runs,now))
        except (requests.RequestException,ValueError,TypeError,KeyError) as exc:
            systems.append({"name":check["name"],"status":"attention",
                            "reason":"Errore monitor: "+type(exc).__name__,"url":""})
    systems.append(check_buffer_ledger(ledger or
                   Path(".state/editorial-autopilot-v137.json"),now))
    return {"schema":"gta6-health-v1","checked_utc":now.isoformat(),
            "status":"attention" if any(x["status"]!="ok" for x in systems) else "ok",
            "systems":systems}


def markdown(report:dict) -> str:
    if report.get("schema")!="gta6-health-v1":
        raise ValueError("Unknown health report")
    lines=[HEALTH_MARKER,"# GTA VI — salute automatismi",
           "", "Controllo automatico GitHub Actions. Nessuna credenziale Buffer utilizzata.",
           "", "Ultimo controllo (UTC): "+escape(report["checked_utc"]),""]
    for x in report["systems"]:
        label="✅ OK" if x["status"]=="ok" else "⚠️ ATTENZIONE"
        lines.extend([f"## {label} — {escape(x['name'])}",
                      escape(x["reason"])])
        if x.get("url","").startswith("https://github.com/"):
            lines.append("[Apri l'esecuzione]("+x["url"]+")")
        lines.append("")
    lines.extend(["Le verifiche non ritentano invii falliti né intervengono sulla coda X.",
                  "Controllare manualmente la dashboard Buffer per gli errori specifici.",
                  "Nessun aggiornamento ChatGPT necessario.",""])
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=("validate","check"),required=True)
    p.add_argument("--output",type=Path,default=Path("previews/gta6-health.md"))
    args=p.parse_args()
    if args.mode=="validate":
        assert len({(x["repo"],x["file"]) for x in CHECKS}) == len(CHECKS)
        print("HEALTH_CONFIG_VALID",len(CHECKS))
        return
    data=inspect(token=os.getenv("GH_TOKEN",""))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(markdown(data),encoding="utf-8")
    Path("previews/gta6-health.json").write_text(
        json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("HEALTH_CHECK",data["status"],[(x["name"],x["status"]) for x in data["systems"]])


if __name__=="__main__":
    main()
