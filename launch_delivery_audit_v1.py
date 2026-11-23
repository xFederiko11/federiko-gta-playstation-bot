"""Daily GTA VI launch publication audit from locally stored verified Buffer receipts.

Read-only. A Buffer-delivered first post does NOT prove the linked X reply
was delivered, nor does a GitHub ledger reservation prove Buffer scheduling.
Never requests X data, creates posts, retries a delivery or computes followers.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from launch_cadence_v1 import START, LAST, TARGET, TARGET_MIN, TARGET_MAX
from quality_publish_policy_v1 import (START as QUALITY_START, DAILY_GOAL_MIN,
    DAILY_GOAL_MAX, HOUR_START, HOUR_END)

ZONE = ZoneInfo("Europe/Rome")
PROVENANCE = "Buffer sent Post.externalLink on verified @xFederiko11 channel"
RECEIPT_SCHEMA = "verified-buffer-x-permalinks-v1"
LEDGER = Path(".state/editorial-autopilot-v137.json")
RECEIPTS = Path("data/x-permalinks-v1.json")
STATUS_URL = re.compile(r"https://x\.com/xFederiko11/status/[0-9]{8,25}")
ARTICLE_URL = re.compile(r"https://xfederiko11\.github\.io/gta-6/(?:[a-z0-9-]+/)*")


def aware(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.utcoffset() is not None else None
    except (ValueError, OverflowError, TypeError):
        return None


def own_guide(value):
    if not isinstance(value, str) or not ARTICLE_URL.fullmatch(value):
        return False
    try:
        p = urlsplit(value)
        return p.scheme == "https" and p.hostname == "xfederiko11.github.io" and not (
            p.query or p.fragment or p.username or p.password or p.port not in (None, 443)
        )
    except ValueError:
        return False


def valid_receipts(feed, now):
    """Trust the independently generated receipt format, never raw ledger status."""
    if feed.get("schema") != RECEIPT_SCHEMA or not isinstance(feed.get("posts"), list):
        raise ValueError("Unrecognized Buffer receipt feed")
    by_id = {}
    for item in feed["posts"]:
        if not isinstance(item, dict) or item.get("verified_by") != PROVENANCE:
            continue
        bid = item.get("buffer_id")
        url = item.get("article_url")
        xurl = item.get("x_url")
        stamp = aware(item.get("sent_at"))
        if (not isinstance(bid, str) or not re.fullmatch(r"[a-z0-9]{15,40}", bid)
                or not own_guide(url) or not isinstance(xurl, str)
                or not STATUS_URL.fullmatch(xurl) or stamp is None
                or stamp > now + timedelta(minutes=5)
                or stamp.date() < START - timedelta(days=2)):
            continue
        record = (url, xurl, stamp)
        if bid in by_id and by_id[bid] != record:
            raise ValueError("Conflicting verified receipt for same Buffer ID")
        by_id[bid] = record
    return by_id


def audit(ledger, feed, now):
    if now.utcoffset() is None:
        raise ValueError("Timezone-aware clock required")
    now = now.astimezone(timezone.utc)
    if not isinstance(ledger, dict) or not isinstance(ledger.get("entries"), dict):
        raise ValueError("Invalid editorial ledger")
    if not isinstance(feed, dict):
        raise ValueError("Invalid receipt feed")
    receipts = valid_receipts(feed, now)
    rows = defaultdict(lambda: {
        "verified_parent_posts": 0,
        "verified_double_thread_parents": 0,
        "scheduled_double_threads_in_ledger": 0,
        "sent_entries_without_verified_parent": 0,
    })
    seen_ids = set()
    for entry in ledger["entries"].values():
        if not isinstance(entry, dict):
            continue
        bid, url, status = entry.get("buffer_id"), entry.get("url"), entry.get("status")
        if not isinstance(bid, str) or not own_guide(url):
            continue
        if bid in seen_ids:
            raise ValueError("Ambiguous duplicate Buffer ID in editorial ledger")
        seen_ids.add(bid)
        is_double = isinstance(entry.get("thread"), list) and len(entry["thread"]) == 2
        receipt = receipts.get(bid)
        # A receipt belongs to this exact owned guide, and it must be marked sent
        # in the editorial ledger after the dedicated reconciliation step.
        if status == "sent" and receipt and receipt[0] == url:
            day = receipt[2].astimezone(ZONE).date()
            if START <= day <= LAST:
                rows[day.isoformat()]["verified_parent_posts"] += 1
                if is_double:
                    rows[day.isoformat()]["verified_double_thread_parents"] += 1
            continue
        if status == "scheduled" and is_double:
            scheduled_at = aware(entry.get("due_at"))
            if scheduled_at is not None:
                day = scheduled_at.astimezone(ZONE).date()
                if START <= day <= LAST and scheduled_at <= now + timedelta(days=3):
                    rows[day.isoformat()]["scheduled_double_threads_in_ledger"] += 1
        elif status == "sent":
            # Only own-guide sent entries; avoids treating news/other posts as campaign proof.
            completed = aware(entry.get("completed_utc")) or aware(entry.get("reserved_utc"))
            if completed is not None:
                day = completed.astimezone(ZONE).date()
                if START <= day <= LAST:
                    rows[day.isoformat()]["sent_entries_without_verified_parent"] += 1

    current = min(max(now.astimezone(ZONE).date(), START), LAST)
    result = []
    day = START
    while day <= current:
        info = dict(rows[day.isoformat()])
        info.update({
            "date": day.isoformat(),
            "daily_min_target": TARGET_MIN,
            "daily_target": TARGET,
            "daily_max": TARGET_MAX,
            "gap_to_min_verified_parents": max(
                0, TARGET_MIN - info["verified_double_thread_parents"]
            ),
            "second_thread_replies_verified": None,
        })
        result.append(info)
        day += timedelta(days=1)
    return {
        "schema": "gta6-launch-buffer-audit-v1",
        "checked_utc": now.isoformat().replace("+00:00", "Z"),
        "period": f"{START} / {LAST}",
        "days": result,
        "provenance": "Owned editorial ledger matched to authenticated Buffer sent permalink bridge",
        "warning": "Only first X post delivery is supported by Buffer receipts. "
                   "Second thread replies, X reach, profile visits and followers are unverified. "
                   "Scheduled ledger entries are NOT proof of Buffer queue state.",
    }


def markdown(report):
    lines = [
        "## 📅 Campagna GTA VI: pubblicazioni verificate / obiettivi",
        "",
        "Fonte: registro editoriale e permalink originali presenti nelle ricevute Buffer. "
        "**Non è un conteggio di impression né di thread doppi completi.**",
        "",
        "| Giorno (Roma) | Primo post X con ricevuta | Di cui thread doppi previsti | "
        "Prenotazioni nel registro | Mancanti al vecchio minimo (10) |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for item in report["days"]:
        lines.append(
            f"| {item['date']} | {item['verified_parent_posts']} | "
            f"{item['verified_double_thread_parents']} | "
            f"{item['scheduled_double_threads_in_ledger']} | "
            f"{item['gap_to_min_verified_parents']} |"
        )
    if not report["days"]:
        lines.append("| Nessun giorno di campagna trascorso | — | — | — | — |")
    lines.extend([
        "",
        f"Obiettivo STORICO ({START}–{LAST}): **{TARGET_MIN} minimo / {TARGET} riferimento / "
        f"{TARGET_MAX} tetto**, subordinati alle fonti e alla qualità. Questi valori NON sono più attivi.",
        f"**Politica X dal {QUALITY_START}:** {DAILY_GOAL_MIN}–{DAILY_GOAL_MAX} post originali al giorno, "
        f"fascia {HOUR_START.strftime('%H:%M')}–{HOUR_END.strftime('%H:%M')} Europe/Rome, "
        "più soltanto notizie urgenti verificate. Nessun post riempitivo, "
        "nessuna risposta automatica ad altri utenti. Questa tabella resta "
        "uno storico di novembre, non un obiettivo corrente.",
        "**Secondi post di risposta dei thread: non verificati.** "
        "Il bridge attuale conserva soltanto il permalink del primo post.",
        "**Prenotazioni = registro GitHub**, non un controllo live della coda Buffer. "
        "Lo stato Buffer Sent/Scheduled/Error è riportato separatamente sopra.",
        "Nessuna creazione di post, nessun recupero automatico, nessuna spesa API X. "
        "Un workflow verde può aver prodotto ZERO post.",
        "",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--append-to", type=Path, required=True)
    args = parser.parse_args()
    report = audit(json.loads(args.ledger.read_text(encoding="utf-8")),
                   json.loads(args.receipts.read_text(encoding="utf-8")),
                   datetime.now(timezone.utc))
    with args.append_to.open("a", encoding="utf-8") as f:
        f.write("\n" + markdown(report) + "\n")
    print("GTA6_LAUNCH_DELIVERY_AUDIT_OK",
          "days", len(report["days"]),
          "latest", report["days"][-1] if report["days"] else "not_started",
          "no_x_api=true", "no_posts_created=true")


if __name__ == "__main__":
    main()
