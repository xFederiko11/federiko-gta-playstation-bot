"""Advisory read-only lookup for old rejected Buffer threads; no retries/writes.

An unavailable historical record is not evidence of current channel failure.
The workflow separately requires a live destination preflight and verifies the
receipt of each new publication. This diagnostic must never replace those gates.
"""
import json
from pathlib import Path
import re

from buffer_publisher import BufferAPIError, BufferClient, BufferConfigurationError

QUERY = """query RejectedPostDetails($id: PostId!) {
  post(input: {id: $id}) {
    id
    status
    error { message supportUrl }
  }
}"""


def category(message: str) -> str:
    terms = [
        ("media", r"image|photo|media|asset|upload|dimension|download|attachment|size|file"),
        ("thread", r"thread|reply|replies|conversation"),
        ("duplicate", r"duplicate|similar|recently|already\s+(posted|shared)"),
        ("limit", r"limit|quota|too\s+many|rate|over.*characters|length"),
        ("authorization", r"auth|token|permission|disconnect|account"),
        ("url", r"link|url|domain|unsafe"),
    ]
    for name, pattern in terms:
        if re.search(pattern, message, re.I):
            return name
    return "other" if message else "not_reported"


def summary(post: dict) -> dict:
    error = post.get("error") or {}
    raw = str(error.get("message") or "")
    safe = re.sub(r"https?://\S+", "[URL]", raw)
    safe = re.sub(r"\b[A-Za-z0-9_-]{32,}\b", "[ID]", safe)
    safe = re.sub(r"[\r\n\t]+", " ", safe)[:160]
    return {"post_id": str(post.get("id") or "")[:40],
            "status": str(post.get("status") or "unknown"),
            "category": category(raw),
            "error_short": safe or "(nessun dettaglio disponibile)"}


def _report(outcome: str, **details) -> dict:
    result = {"outcome": outcome, "scope": "historical_rejected_thread_only",
              "current_channel_preflight_required": True,
              "mode": "read_only_no_retry", **details}
    print("BUFFER_READONLY_DIAGNOSTIC", json.dumps(result, ensure_ascii=False))
    print("BUFFER_DIAGNOSTIC_NO_MUTATION")
    return result


def inspect(*, client=None, ledger_path=None) -> dict:
    ledger = Path(ledger_path) if ledger_path is not None else Path(".state/editorial-autopilot-v137.json")
    try:
        state = json.loads(ledger.read_text("utf-8"))
    except FileNotFoundError:
        return _report("ledger_missing")
    except (OSError, UnicodeError, ValueError):
        return _report("historical_diagnostic_unavailable", reason="ledger_unreadable")
    entries = state.get("entries") if isinstance(state, dict) else None
    if not isinstance(entries, dict):
        return _report("historical_diagnostic_unavailable", reason="ledger_schema")
    failed = [x for x in entries.values() if isinstance(x, dict)
              and x.get("source") == "PowerPyx Tips"
              and x.get("status") == "rejected" and x.get("buffer_id")]
    if not failed:
        return _report("no_failed_tips")
    last = max(failed, key=lambda x: str(x.get("reserved_utc") or ""))
    post_id = str(last["buffer_id"])
    try:
        reader = client if client is not None else BufferClient(expected_username="xFederiko11")
        reader.verify_destination()
        data = reader._graphql(QUERY, {"id": post_id})
    except (BufferAPIError, BufferConfigurationError) as exc:
        # Do not print API response bodies, credentials or exception messages.
        # The mandatory live preflight still runs before any new reservation.
        return _report("historical_diagnostic_unavailable", reason=type(exc).__name__)
    post = data.get("post") if isinstance(data, dict) else None
    if not isinstance(post, dict) or post.get("id") != post_id:
        return _report("historical_diagnostic_unavailable", reason="post_missing_or_mismatched")
    if post.get("error") is not None and not isinstance(post["error"], dict):
        return _report("historical_diagnostic_unavailable", reason="malformed_historical_error")
    return _report("historical_record_available", detail=summary(post))


if __name__ == "__main__":
    inspect()
