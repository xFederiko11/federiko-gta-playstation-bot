"""Small public heartbeat plus a fingerprint of meaningful private bot state.

Health clocks are persisted separately so a quiet poll need not rewrite a whole
encrypted database in Git. Queue contents, source snapshots and credentials are
never exported to the public health file.
"""

import base64
import hashlib
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _value(value, column=""):
    if isinstance(value, bytes):
        return {"__sqlite_blob__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, str) and column.endswith("_json"):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _tables(db):
    return [row[0] for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def _quoted(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def meaningful_fingerprint(db):
    """SHA-256 of logical durable state, excluding observation/health clocks.

    JSON key order and SQLite row order do not affect the fingerprint. Delivery
    state, retry times, source cursors, download facts and Buffer usage do.
    """
    payload = []
    for table in _tables(db):
        cursor = db.execute("SELECT * FROM " + _quoted(table))
        columns = [item[0] for item in cursor.description]
        rows = [dict(zip(columns, tuple(row))) for row in cursor]
        normalized = []
        for row in rows:
            if table == "monitors":
                normalized.append({"id": row["id"], "state_json": _value(row.get("state_json"), "state_json")})
            elif table == "meta":
                if row.get("key") != "xbox_checked":
                    normalized.append({column: _value(value, column) for column, value in row.items()})
            elif table == "download_history":
                record = _value(row.get("record_json"), "record_json")
                if isinstance(record, dict):
                    record = {key: value for key, value in record.items() if key not in {
                        "observed_at", "first_observed_at", "last_observed_at", "evidence_sha256"}}
                normalized.append({"record_id": row["record_id"], "record_json": record})
            else:
                normalized.append({column: _value(value, column) for column, value in row.items()})
        normalized.sort(key=_canonical)
        payload.append({"table": table, "rows": normalized})
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _timestamp(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def _safe_error(value):
    if value is None:
        return None
    # Export categories, never remote response text, auth headers or URLs.
    categories = {"Timeout", "ReadTimeout", "ConnectTimeout", "HTTPError", "ConnectionError",
                  "ProxyError", "SSLError", "JSONDecodeError", "ParseError", "ValueError", "KeyError",
                  "IndexError", "TypeError", "OSError", "ImportError", "ModuleNotFoundError",
                  "APIError", "InvalidURL", "Error", "SourceError"}
    if isinstance(value, str) and value in categories:
        return value
    return "SourceError"


def _history_time(value):
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        return None
    return stamp.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="." + path.name + ".", delete=False) as stream:
            temporary = stream.name
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def save_health(db, path):
    """Publish IDs and clocks, never source snapshots or private queue data."""
    tables = set(_tables(db))
    monitors = []
    if "monitors" in tables:
        for row in db.execute("SELECT id,last_success,last_error,next_due FROM monitors ORDER BY id"):
            monitors.append({"id": row[0], "last_success": _timestamp(row[1]),
                             "last_error": _safe_error(row[2]), "next_due": _timestamp(row[3]) or 0})
    meta = {}
    if "meta" in tables:
        row = db.execute("SELECT value FROM meta WHERE key='xbox_checked'").fetchone()
        if row and _timestamp(row[0]) is not None:
            meta["xbox_checked"] = _timestamp(row[0])
    history_observed = []
    if "download_history" in tables:
        for row in db.execute("SELECT record_id,last_observed_at FROM download_history ORDER BY record_id"):
            stamp = _history_time(row[1])
            if stamp:
                history_observed.append({"record_id": row[0], "last_observed_at": stamp})
    payload = {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "monitors": monitors, "meta": meta, "history_observed": history_observed}
    destination = Path(path)
    _atomic_json(destination, payload)
    return destination


def load_health(db, path):
    """Restore only health fields on existing rows; invalid health is ignored.

    This file is informational and cannot insert a source, replace state_json,
    alter a cursor or overwrite queue/history data.
    """
    source = Path(path)
    if not source.is_file():
        return False
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError):
        return False
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return False
    records = payload.get("monitors", [])
    history_observed = payload.get("history_observed", [])
    if not isinstance(records, list) or not isinstance(payload.get("meta", {}), dict) or not isinstance(history_observed, list):
        return False
    tables = set(_tables(db))
    with db:
        if "monitors" in tables:
            for row in records:
                if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                    continue
                updates, values = [], []
                if "last_success" in row and (row["last_success"] is None or _timestamp(row["last_success"]) is not None):
                    updates.append("last_success=?")
                    values.append(_timestamp(row["last_success"]))
                if "last_error" in row:
                    updates.append("last_error=?")
                    values.append(_safe_error(row["last_error"]))
                if "next_due" in row and _timestamp(row["next_due"]) is not None:
                    updates.append("next_due=?")
                    values.append(_timestamp(row["next_due"]))
                if updates:
                    db.execute("UPDATE monitors SET " + ",".join(updates) + " WHERE id=?", values + [row["id"]])
        xbox_checked = _timestamp(payload.get("meta", {}).get("xbox_checked"))
        if "meta" in tables and xbox_checked is not None:
            db.execute("UPDATE meta SET value=? WHERE key='xbox_checked'", (str(xbox_checked),))
        if "download_history" in tables:
            for row in history_observed:
                if not isinstance(row, dict) or not isinstance(row.get("record_id"), str):
                    continue
                incoming = _history_time(row.get("last_observed_at"))
                if not incoming:
                    continue
                known = db.execute("SELECT last_observed_at,record_json FROM download_history WHERE record_id=?",
                                   (row["record_id"],)).fetchone()
                if not known:
                    continue
                previous = _history_time(known[0])
                if previous is not None and incoming <= previous:
                    continue
                try:
                    record = json.loads(known[1])
                except (TypeError, ValueError):
                    continue
                if not isinstance(record, dict):
                    continue
                # Only the reading clock is restored. Facts and the first
                # observation always come from the authenticated private state.
                record["observed_at"] = incoming
                db.execute("UPDATE download_history SET last_observed_at=?,record_json=? WHERE record_id=?",
                           (incoming, _canonical(record), row["record_id"]))
    return True
