"""Read-only publishing health report; never contacts Buffer or X.

Run: python publishing_health_v1.py
Exit 2 means monitoring needs attention, not that delivery definitively failed.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from launch_cadence_v1 import (active as launch_active, local as launch_local,
    TARGET_MIN, TARGET, TARGET_MAX, campaign_status)

ROOT = Path(".state")
FILES = {
    "editorial": ("editorial-autopilot-v137.json", "entries"),
    "campaign": ("special-campaign-v139.json", "entries"),
    "launch": ("launch-watch-v134.json", "posts"),
    "trophies": ("trophies-v142.json", "entries"),
    "monitor": ("monitor-publication-v142.json", "entries"),
}

def timestamp(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def launch_progress(now, root=ROOT):
    """Read-only daily record of *sent* atomic two-post threads, not plans."""
    if not launch_active(now):
        return {'active': False}
    stats=campaign_status(now)
    path=root/'editorial-autopilot-v137.json'
    if not path.is_file():
        return {**stats, 'sent_double_threads': 0, 'unconfirmed': 0, 'source_missing': True,
                'under_min_at_close': False}
    entries=json.loads(path.read_text('utf-8')).get('entries',{})
    sent=0
    unconfirmed=0
    singles=0
    for item in entries.values():
        if not isinstance(item,dict): continue
        at=timestamp(item.get('completed_utc') or item.get('reserved_utc'))
        if at is None or launch_local(at).date()!=launch_local(now).date():continue
        thread=item.get('thread')
        if item.get('status')=='sent':
            if isinstance(thread,list) and len(thread)==2:sent+=1
            else:singles+=1
        elif item.get('status') in {'reserved','attempted','accepted_pending','uncertain'}:
            unconfirmed+=1
    when=launch_local(now).time()
    late=when.hour>=20 and when.minute>=30 or when.hour>=21
    return {**stats,'sent_double_threads':sent,'unconfirmed':unconfirmed,
            'single_posts_in_editorial_ledger':singles,
            'missing_to_minimum':max(0,TARGET_MIN-sent),
            'missing_to_default':max(0,TARGET-sent),
            'under_min_at_close':bool(late and sent<TARGET_MIN),
            'receipt_note':'State sent checked via Buffer integration; no independent X impression count'}

def report(now=None, root=ROOT):
    now = now or datetime.now(timezone.utc)
    counts = {}
    latest = {}
    errors = []
    for name, (filename, field) in FILES.items():
        path = root / filename
        if not path.exists():
            counts[name] = {"missing": True}
            continue
        try:
            data = json.loads(path.read_text("utf-8"))
            entries = data.get(field, {})
            if not isinstance(entries, dict):
                raise ValueError("ledger entries not a dictionary")
            by_status = {}
            for item in entries.values():
                if not isinstance(item, dict):
                    continue
                status = str(item.get("status", "unknown"))
                by_status[status] = by_status.get(status, 0) + 1
                at = timestamp(item.get("completed_utc") or item.get("reserved_utc") or item.get("reserved_at"))
                if at and (name not in latest or at > latest[name]):
                    latest[name] = at
            counts[name] = {"total": len(entries), "statuses": by_status}
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"{name}: {type(exc).__name__}")
    health = Path("monitor-health.json")
    scanner = {}
    if health.exists():
        try:
            data = json.loads(health.read_text("utf-8"))
            scanner["generated_at"] = data.get("generated_at")
            at = timestamp(data.get("generated_at"))
            scanner["age_hours"] = round((now-at).total_seconds()/3600, 2) if at else None
            scanner["stale"] = at is None or (now-at).total_seconds() > 6*3600
            scanner["sources"] = {
                x.get("id", "unknown"): {
                    "last_error": x.get("last_error"),
                    "last_success": timestamp(x.get("last_success")).isoformat() if timestamp(x.get("last_success")) else None
                }
                for x in data.get("monitors", []) if isinstance(x, dict)
            }
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"monitor-health: {type(exc).__name__}")
    else:
        scanner["missing"] = True
    launch = launch_progress(now, root)
    return {
        "checked_at": now.isoformat(),
        "launch_campaign": launch,
        "scanner": scanner,
        "ledgers": counts,
        "latest_ledger_activity": {k: v.isoformat() for k, v in latest.items()},
        "errors": errors,
        "attention_required": bool(errors or scanner.get("stale") or scanner.get("missing")
                                    or launch.get('under_min_at_close')),
        "note": "Ledger sent/accepted_pending is not independently verified X delivery; check Buffer Sent and X."
    }

if __name__ == "__main__":
    result = report()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(2 if result["attention_required"] else 0)
