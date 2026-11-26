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

RUNS_APIS = (
    "https://api.github.com/repos/xFederiko11/federiko-gta-playstation-bot/actions/runs?per_page=100",
    "https://api.github.com/repos/xFederiko11/gta-6/actions/runs?per_page=30",
)
REQUIRED = (
    "GTA Monitor gratuito",
    "GTA VI - Breaking News Watch v13.4",
    "GTA VI - Editorial Autopilot v13.7",
    "GTA VI - Ricerca fonti indipendenti (sola lettura)",
    "GTA 6 Italia - Website",
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
            # Editorial push runs now exercise read-only QA, not publication.
            and not (name == "GTA VI - Editorial Autopilot v13.7" and run.get("event") == "push")
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
        # Website deployments are push-based: no recent changes is not an outage.
        health = "degraded" if latest.get("conclusion") != "success" else (
            "stale" if name != "GTA 6 Italia - Website" and age > MAX_AGE_HOURS else "healthy")
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
    results = []
    for api in RUNS_APIS:
        response = requests.get(api, headers=headers, timeout=(5, 20))
        response.raise_for_status()
        rows = response.json().get("workflow_runs", [])
        if not isinstance(rows, list):
            raise ValueError("Malformed run API response")
        results.extend(rows)
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--buffer-log", type=Path, required=True)
    parser.add_argument("--buffer-exit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--issue-output", type=Path)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    api_error = None
    try:
        runs = fetch_runs(os.getenv("GH_TOKEN"))
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        # Always produce the health issue even when GitHub metadata is unreachable.
        runs = []
        api_error = "github_runs_api_" + type(exc).__name__
    try:
        code = int(args.buffer_exit.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        code = -1
    try:
        lines = args.buffer_log.read_text(encoding="utf-8")
    except OSError:
        lines = ""
    result = assess(runs, lines, code, now)
    if api_error:
        result["overall"] = "degraded"
        result["api_error"] = api_error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.issue_output:
        args.issue_output.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# GTA VI — salute bot GitHub", "",
            f"**Stato: {result['overall'].upper()}** · UTC: {result['checked_utc']}", "",
            "Valutazione automatica di log GitHub e preflight Buffer in sola lettura.",
            ("⚠️ GitHub API: " + result["api_error"] if result.get("api_error") else ""),
            "Nessun post creato né ritentato.", "",
            "## Workflow", ""
        ]
        lines.extend(f"- **{j['name']}**: {j['health']} · {j.get('run_url', 'nessun run trovato')}" for j in result["workflows"])
        lines += ["", "## Buffer / X", "",
                  f"**{result['buffer']['status']}** — {result['buffer']['reason']}", "",
                  "Per ripristinare un canale scollegato serve conferma manuale; non riattivare i Quick Tips senza controllare i post su X.",
                  "Se questa issue viene chiusa, le prossime verifiche potranno riaprirla su nuovi errori."]
        args.issue_output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("GTA6_BOT_HEALTH", result["overall"])
    for job in result["workflows"]:
        print("CHECK", job["name"], job["health"], job.get("run_url", ""))
    print("BUFFER", result["buffer"]["status"], result["buffer"]["reason"])
    # Do not leak Buffer tokens, IDs or the unredacted diagnostic log.
    if result["overall"] == "degraded":
        sys.exit(2)


if __name__ == "__main__":
    main()
