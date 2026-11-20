"""Read-only comparison of today's GTA VI Buffer queue sample and GitHub ledger.

The 15 most recent Sent, 15 earliest Scheduled and 15 Error posts are
samples, NEVER a complete inventory of X publications or proof of replies.
No Buffer mutation, network requests, credential access or X API usage.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import re

LEDGER = Path(".state/editorial-autopilot-v137.json")
ROME = ZoneInfo("Europe/Rome")
SCHEMA = "buffer-launch-slot-comparison-v1"
SOURCE = "Guide GTA VI Italia"
VALID_STATUSES = {"scheduled", "sent", "error", "reserved", "attempted", "uncertain"}
STATES = ("sent", "scheduled", "error")


def aware(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.utcoffset() is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def compare(sample, ledger, now):
    """Match exact Buffer IDs; absence from 15-item samples is NOT a failure."""
    if now.utcoffset() is None:
        raise ValueError("Timezone-aware clock required")
    if not isinstance(ledger, dict) or not isinstance(ledger.get("entries"), dict):
        raise ValueError("Editorial ledger unavailable or malformed")
    if not isinstance(sample, dict) or sample.get("status") != "ok":
        return {"schema": SCHEMA, "status": "api_unavailable", "day": now.astimezone(ROME).date().isoformat(),
                "rows": [], "counts": {}, "note": "Dati Buffer non disponibili: il registro da solo non prova nulla."}
    found = {}
    for state in STATES:
        posts = sample.get(state)
        if not isinstance(posts, list) or len(posts) > 15:
            raise ValueError("Sample is not bounded")
        for row in posts:
            if not isinstance(row, dict):
                raise ValueError("Invalid Buffer sample")
            bid = row.get("id")
            if not isinstance(bid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{6,80}", bid):
                raise ValueError("Untrusted Buffer post ID")
            if bid in found:
                raise ValueError("Conflicting Buffer ID in multiple sample statuses")
            found[bid] = (state, aware(row.get("dueAt")))
    day = now.astimezone(ROME).date()
    rows, seen = [], set()
    for entry in ledger["entries"].values():
        if not isinstance(entry, dict) or entry.get("source") != SOURCE:
            continue
        if not (isinstance(entry.get("thread"), list) and len(entry["thread"]) == 2):
            continue
        due = aware(entry.get("due_at") or entry.get("reserved_utc"))
        if due is None or due.astimezone(ROME).date() != day:
            continue
        bid = entry.get("buffer_id")
        ledger_status = entry.get("status")
        if (not isinstance(bid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{6,80}", bid)
                or ledger_status not in VALID_STATUSES or bid in seen):
            raise ValueError("Ambiguous ledger Buffer ID or status")
        seen.add(bid)
        observed, buffer_due = found.get(bid, (None, None))
        delta = (abs((buffer_due-due).total_seconds()) if buffer_due else None)
        mismatch = observed == "scheduled" and (delta is None or delta > 5*60)
        if observed == "error":
            verdict = "buffer_error"
        elif mismatch:
            verdict = "buffer_time_mismatch"
        elif observed == "scheduled" and ledger_status == "scheduled":
            verdict = "scheduled_verified"
        elif observed == "sent" and ledger_status == "sent":
            verdict = "sent_in_sample"
        elif observed == "sent" and ledger_status == "scheduled":
            verdict = "ledger_needs_receipt_reconcile"
        elif observed == "scheduled" and ledger_status == "sent":
            verdict = "status_conflict"
        elif observed is None and ledger_status == "scheduled" and due <= now.astimezone(timezone.utc):
            verdict = "past_due_not_in_sample"
        elif observed is None:
            verdict = "ledger_only_not_in_sample"
        else:
            verdict = "unverified_status"
        title = entry.get("title")
        rows.append({"due_at": due.astimezone(ROME).strftime("%H:%M"),
                     "utc": due.isoformat(), "title": (title[:110] if isinstance(title, str) else "Senza titolo"),
                     "ledger": ledger_status, "buffer": observed, "verdict": verdict})
    rows.sort(key=lambda x: x["utc"])
    if len(rows) > 16:
        raise ValueError("More than 16 editorial thread slots in local launch day")
    return {"schema": SCHEMA, "status": "ok", "day": day.isoformat(),
            "rows": rows, "counts": dict(Counter(x["verdict"] for x in rows)),
            "note": "Il campione Buffer contiene al massimo 15 elementi per stato. "
                    "Assenza dal campione NON significa mancata pubblicazione. "
                    "Sent conferma il solo stato Buffer, mai la risposta del thread o follower."}


LABELS = {
    "scheduled_verified": "Programmato: confermato nel campione Buffer",
    "sent_in_sample": "Sent: confermato da Buffer (solo primo post)",
    "ledger_needs_receipt_reconcile": "Sent in Buffer, registro non ancora riconciliato",
    "past_due_not_in_sample": "Scaduto nel registro, non presente nel campione: verifica",
    "ledger_only_not_in_sample": "Solo registro: fuori campione, non confermato",
    "buffer_error": "Errore Buffer: controllare, NON ripubblicare",
    "buffer_time_mismatch": "Stesso ID ma orario Buffer diverso: verifica",
    "status_conflict": "Disallineamento registro e Buffer: verifica",
    "unverified_status": "Stato da verificare",
}


def render(result):
    if result.get("schema") != SCHEMA:
        raise ValueError("Invalid slot comparison")
    lines = ["## 🔎 Riconciliazione slot GitHub ↔ Buffer (sola lettura)", "",
             "Giorno locale Roma: "+result["day"]+". "
             "Vengono confrontati solo thread editoriali a due messaggi con ID Buffer identico.", ""]
    if result["status"] != "ok":
        return "\n".join(lines+[result["note"], "",
                                 "Nessuna pubblicazione effettuata o recuperata automaticamente.", ""])
    if not result["rows"]:
        return "\n".join(lines+["Nessuno slot editoriale del giorno trovato nel registro. "
                                 "Non significa zero pubblicazioni su X.", "", result["note"], ""])
    lines += ["| Ora (Roma) | Guida / argomento | GitHub | Buffer (campione) | Esito |",
              "| --- | --- | --- | --- | --- |"]
    for row in result["rows"]:
        title = escape(re.sub(r"[\x00-\x1f\x7f]", " ", row["title"]), quote=True)
        title = title.replace("\\", r"\\").replace("|", r"\|")
        lines.append("| "+row["due_at"]+" | "+title+" | "+row["ledger"]+" | "+
                     (row["buffer"] or "non trovato") + " | "+LABELS[row["verdict"]]+" |")
    lines += ["",
              "Slot con stato Scheduled **confermato nel campione**: "+
              str(result["counts"].get("scheduled_verified", 0))+" · Sent **confermato nel campione**: "+
              str(result["counts"].get("sent_in_sample", 0))+" · "
              "Confronti da esaminare: "+str(sum(n for k,n in result["counts"].items()
                   if k not in ("scheduled_verified", "sent_in_sample")))+".",
              "",
              result["note"],
              "**Niente retry automatici, mutazioni Buffer o metriche X inventate.**",
              ""]
    return "\n".join(lines)


def from_ledger(sample, now, path=LEDGER):
    if not path.is_file():
        return ("## 🔎 Riconciliazione slot GitHub ↔ Buffer\n\n"
                "Registro GitHub non trovato: verifica non disponibile, non equivale a zero post.\n")
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
        return render(compare(sample, ledger, now))
    except (OSError, ValueError, KeyError, TypeError) as err:
        return ("## 🔎 Riconciliazione slot GitHub ↔ Buffer\n\n"
                "Confronto non disponibile: "+type(err).__name__+
                ". Non effettuare retry senza verificare Buffer.\n")
