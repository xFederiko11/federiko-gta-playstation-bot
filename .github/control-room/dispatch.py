"""Restricted GitHub-only Control Room bridge. No external API or social writes."""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

REPO = "xFederiko11/federiko-gta-playstation-bot"
PATH = ".github/control-room/request.json"
TARGETS = {
    "grafica": ("gta6-photo-review-inbox-v1.yml", {"mode": "preview"}),
    "community": ("gta6-x-verified-social-radar-v1.yml", {"action": "preview"}),
    "pubblicazione": ("gta6-editorial-autopilot-v137.yml", {"action": "preview"}),
    "sito": ("site-editorial-integration-v1.yml", {}),
}
TTL = timedelta(minutes=30)
COOLDOWN = timedelta(minutes=60)

def timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ValueError("UTC timestamp required")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

def parse_request(value):
    if not isinstance(value, dict) or set(value) != {"action", "requested_at"}:
        raise ValueError("Unexpected request schema")
    action = value["action"]
    if not isinstance(action, str) or action not in {*TARGETS, "idle"}:
        raise ValueError("Unsupported action")
    return action, timestamp(value["requested_at"])

def plan(current, previous, latest, runs, now):
    action, requested = parse_request(current)
    _, old = parse_request(previous)
    if action == "idle":
        return None, "idle"
    if requested <= old:
        return None, "duplicate or older request"
    if not now - TTL <= requested <= now + timedelta(minutes=2):
        return None, "expired or future request"
    if current != latest:
        return None, "superseded request"
    for run in runs:
        if run["status"] != "completed":
            return None, "target already active"
        if run["event"] in ("schedule", "workflow_dispatch") and timestamp(run["created_at"]) > now - COOLDOWN:
            return None, "target recently executed; reuse its result"
    return TARGETS[action], "accepted"

def api(path, payload=None, raw=False):
    headers = {
        "Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    data = None if payload is None else json.dumps(payload).encode()
    req = Request("https://api.github.com/repos/" + REPO + "/" + path, data=data, headers=headers)
    # No retries: an uncertain POST must never be attempted twice.
    with urlopen(req, timeout=15) as response:
        body = response.read(2_000_000)
        return json.loads(body) if body else None

def main():
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    if (os.environ.get("GITHUB_REPOSITORY") != REPO or os.environ.get("GITHUB_EVENT_NAME") != "push"
        or os.environ.get("GITHUB_REF") != "refs/heads/main" or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"
        or event.get("forced") or event.get("deleted") or event.get("repository", {}).get("private") is not False):
        raise ValueError("Unexpected execution context")
    current = json.loads(Path(PATH).read_text())
    action, _ = parse_request(current)
    if action == "idle":
        print("CONTROL_ROOM_SKIPPED idle")
        return
    before = event["before"]
    if not re.fullmatch(r"[a-f0-9]{40}", before) or before == "0" * 40:
        raise ValueError("Invalid previous revision")
    previous = api("contents/" + PATH + "?ref=" + before, raw=True)
    latest = api("contents/" + PATH + "?ref=main", raw=True)
    workflow, _ = TARGETS[action]
    route = "actions/workflows/" + workflow
    runs = api(route + "/runs?branch=main&per_page=10")["workflow_runs"]
    target, reason = plan(current, previous, latest, runs, datetime.now(timezone.utc))
    if target is None:
        print("CONTROL_ROOM_SKIPPED", reason)
        return
    payload = {"ref": "main"}
    if target[1]:
        payload["inputs"] = target[1]
    api(route + "/dispatches", payload)
    print("CONTROL_ROOM_DISPATCH_ACCEPTED", workflow, "preview/read-only; not proof of target completion")
    print("https://github.com/" + REPO + "/actions/workflows/" + workflow)

if __name__ == "__main__":
    main()
