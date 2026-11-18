"""No-cost publication report. X impressions/followers are NEVER invented."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import csv
import json
from pathlib import Path

from editorial_director_v142 import read_reservations

MANUAL=Path("metrics-manual-v142.csv")
OUTPUT=Path("_site/metrics.json")

def report(ledger_path=Path(".state"), manual_path=MANUAL):
    rows=read_reservations(ledger_path)
    by_source=Counter()
    by_day=Counter()
    by_status=Counter()
    for r in rows:
        by_source[r["workflow"]]+=1
        by_day[r["at"].date().isoformat()]+=1
        by_status[r["status"]]+=1
    # These data exist only when the user exports/views them in X analytics.
    actual=[]
    if manual_path.exists():
        with manual_path.open(newline="",encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if not (row.get("post_url") or "").startswith("https://x.com/"):
                    continue
                clean={"post_url":row["post_url"],"date":row.get("date","")}
                for field in ("impressions","likes","reposts","replies","profile_visits","new_followers"):
                    raw=(row.get(field) or "").strip()
                    if raw and (not raw.isdigit() or int(raw)<0):
                        raise ValueError("Invalid manually entered metric "+field)
                    clean[field]=int(raw) if raw else None
                actual.append(clean)
    return {
        "schema":"gta-growth-v142",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "source":"GitHub public Buffer delivery ledgers + optional manual X data",
        "delivery_reservations":len(rows),
        "by_ledger":dict(by_source),
        "by_day":dict(by_day),
        "by_status":dict(by_status),
        "actual_x_metrics_available":bool(actual),
        "x_metrics":actual,
        "warning":"Buffer sent is NOT X reach. Empty/null metrics indicate unavailable X analytics, not zero."
    }

def main():
    summary=report()
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("GROWTH_REPORT",json.dumps({k:v for k,v in summary.items() if k!="x_metrics"},ensure_ascii=False))
if __name__=="__main__":
    main()
