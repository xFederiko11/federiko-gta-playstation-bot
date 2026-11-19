"""Read-only GTA VI bot health assessment from GitHub run metadata and Buffer preflight.

Runs on GitHub Actions without ChatGPT, write keys or publication calls.
This script does not mutate GitHub issues, Buffer, or the editorial ledger.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import os
import sys
import requests

RUNS_API = "https://api.github.com/repos/xFederiko11/federiko-gta-playstation-bot/actions/runs?per_page=100"
REQUIRED = (
    "GTA Monitor gratuito",
    "GTA VI - Breaking News Watch v13.4",
    "GTA VI - Editorial Autopilot v13.7",
    "GTA VI - Ricerca fonti indipendenti (sola lettura)",
)
MAX_AGE_HOURS = 36


def summarize_runs(runs: list[dict], now: datetime) -> list[dict]:
    """Find latest successful/failed completed production run per service."""
    checked = []
    for name in REQUIRED:
        relevant = [
            run for run in runs
            if run.get("name") == name
            and run.get("event") in ("schedule", "workflow_run", "workflow_dispatch", "push")
            and run.get("status") == "completed"
        ]
        latest = max(relevant, key=lambda x: x.get("created_at") or "", default=None)
        if latest is None:
            checked.append({"name": name, "health": "unknown", "reason": "no_completed_production_run"})
            continue
        date_value = str(latest.get("created_at") or "")
        try:
            date = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
        except ValueError:
            checked.append({"name": name, "health": "unknown", "reason": "invalid_timestamp"})
            continue
        if date.tzinfo is None:
            checked.append({"name": name, "health": "unknown", "reason": "timezone_missing"})
            continue
        age = (now.astimezone(timezone.utc) - date.astimezone(timezone.utc)).total_seconds() / 3600
        health = "degraded" if latest.get("conclusion") != "success" else (
            "stale" if age > MAX_AGE_HOURS else "healthy")
        checked.append({
            "name": name, "health": health, "age_hours": round(age, 1),
            "conclusion": latest.get("conclusion"), "run_url": latest.get("html_url", "")
        })
    return checked


def buffer_health(stdout: str, exit_code: int) -> dict:
    """Only interpret the existing read-only diagnostic output."""
    if exit_code:
        return {"status": "degraded", "reason": "buffer_preflight_failed"}
    if "BUFFER_PREFLIGHT_OK" not in stdout:
        return {"status": "unknown", "reason": "missing_preflight_result"}
    if "QUICK_TIPS_PAUSED" in stdout:
        return {"status": "degraded", "reason": "quick_tips_paused_after_failure"}
    if "QUICK_TIPS_STATUS_UNKNOWN" in stdout:
        return {"status": "unknown", "reason": "quick_tips_status_not_readable"}
    return {"status": "healthy", "reason": "connected_read_only"}


def assess(runs: list[dict], buffer_output: str, buffer_code: int, now: datetime) -> dict:
    if now.tzinfo is None:
        raise ValueError("Timezone-aware date required")
    jobs = summarize_runs(runs, now)
    buff = buffer_health(buffer_output, buffer_code)
    overall = ("degraded" if buff["status"] == "degraded" or
               any(x["health"] in ("degraded", "stale") for x in jobs) else
               "unknown" if buff["status"] == "unknown" or
               any(x["health"] == "unknown" for x in jobs) else "healthy")
    return {"schema": "gta6-bot-health-v1",
            "checked_utc": now.astimezone(timezone.utc).isoformat(),
            "overall": overall,
            "workflows": jobs, "buffer": buff,
            "publication": "read_only_diagnostics"}


def fetch_runs(token: str | None = None) -> list[dict]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "FederikoGTA6BotHealth/1"}
    if token:
        headers["Authorization"] = "Bearer " + token
    response = requests.get(RUNS_API, headers=headers, timeout=(5, 20))
    response.raise_for_status()
    rows = response.json().get("workflow_runs", [])
    if not isinstance(rows, list):
        raise ValueError("Malformed run API response")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--buffer-log", type=Path, required=True)
    parser.add_argument("--buffer-exit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    runs = fetch_runs(os.getenv("GH_TOKEN"))
    try:
        code = int(args.buffer_exit.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        code = -1
    try:
        lines = args.buffer_log.read_text(encoding="utf-8")
    except OSError:
        lines = ""
    result = assess(runs, lines, code, now)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("GTA6_BOT_HEALTH", result["overall"])
    for job in result["workflows"]:
        print("CHECK", job["name"], job["health"], job.get("run_url", ""))
    print("BUFFER", result["buffer"]["status"], result["buffer"]["reason"])
    # Do not leak Buffer tokens, IDs or the unredacted diagnostic log.
    if result["overall"] == "degraded":
        sys.exit(2)


if __name__ == "__main__":
    main()
