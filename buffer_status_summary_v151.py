"""Read-only Buffer/X connection diagnostic for scheduled editorial posting.

Uses the existing destination query (one read, no createPost). Reports actionable
connection and quick-tip gate state without exposing tokens, IDs, or post bodies.
This check MUST NOT lift the opt-in, retry failed posts, or mutate the ledger.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from buffer_publisher import BufferAPIError, BufferClient, BufferConfigurationError

LEDGER = Path(".state/editorial-autopilot-v137.json")
CHANNELS_URL = "https://publish.buffer.com/settings/channels"


def tip_gate(state: dict | None, opted_in: bool) -> str:
    """Mirror the deliberate one-time recovery gate in quick_tips_v146."""
    if not isinstance(state, dict) or not isinstance(state.get("entries"), dict):
        return "unknown"
    entries = state["entries"].values()
    failures = [
        entry for entry in entries
        if isinstance(entry, dict) and entry.get("source") == "PowerPyx Tips"
        and entry.get("status") in {"rejected", "error", "uncertain"}
    ]
    if not failures:
        return "ready"
    expected = (
        len(failures) == 1
        and failures[0].get("tip_id") == "waink-vehicles-ps5"
        and failures[0].get("status") == "rejected"
    )
    return "resumed_after_review" if expected and opted_in else "paused"


def _read_ledger(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None


def _report(lines: list[str], summary_path: str | None) -> None:
    for line in lines:
        print(line)
    if summary_path:
        try:
            with Path(summary_path).open("a", encoding="utf-8") as stream:
                stream.write("\n".join(lines) + "\n\n")
        except OSError:
            # A GitHub Step Summary problem must never change publication safety.
            print("BUFFER_SUMMARY_UNAVAILABLE")


def check(*, client=None, ledger_path: Path | None = None,
          opt_in: bool | None = None, summary_path: str | None = None) -> int:
    """Return 0 only if Buffer's intended X destination is accessible.

    The editorial workflow stops before reservation on a failing return code.
    A healthy channel does not imply an earlier failed post was delivered.
    """
    if summary_path is None:
        summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    try:
        destination = (client or BufferClient(expected_username="xFederiko11")).verify_destination()
    except (BufferAPIError, BufferConfigurationError) as exc:
        _report([
            "## ❌ Buffer/X: collegamento non verificato",
            f"BUFFER_PREFLIGHT_FAILED type={type(exc).__name__}; no posts created",
            f"Apri {CHANNELS_URL} e aggiorna il canale @xFederiko11.",
            "Verifica poi Buffer → Sent e X prima di ritentare post falliti.",
            "Nessuna prenotazione o pubblicazione deve iniziare prima del ripristino.",
        ], summary_path)
        return 2

    state = _read_ledger(ledger_path or LEDGER)
    if opt_in is None:
        opt_in = os.getenv("TIPS_REAUTH_CONFIRMED_V149", "false").lower() == "true"
    gate = tip_gate(state, opt_in)
    messages = [
        "## ✅ Buffer/X: canale verificato",
        "BUFFER_PREFLIGHT_OK account=@xFederiko11; read-only; no posts created",
    ]
    if destination.get("isQueuePaused"):
        messages.append("BUFFER_QUEUE_PAUSED: Buffer indica una coda in pausa; nessuna nuova prenotazione consentita.")
        _report(messages, summary_path)
        return 3
    if gate == "paused":
        messages += [
            "QUICK_TIPS_PAUSED: le guide rapide restano sospese dopo un precedente errore.",
            "Dopo aver verificato almeno un post pubblicato DOPO il refresh, imposta "
            "TIPS_REAUTH_CONFIRMED_V149=true nelle Repository variables di GitHub.",
            "Il vecchio thread WAiNK rifiutato NON verrà ripetuto.",
        ]
    elif gate == "resumed_after_review":
        messages.append("QUICK_TIPS_READY: conferma manuale presente; storico e deduplicazione invariati.")
    elif gate == "unknown":
        messages.append("QUICK_TIPS_STATUS_UNKNOWN: ledger non leggibile; nessuno sblocco automatico.")
    else:
        messages.append("QUICK_TIPS_READY: nessun precedente errore registrato.")
    _report(messages, summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(check())
