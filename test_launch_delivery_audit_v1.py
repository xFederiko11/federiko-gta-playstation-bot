"""Offline regressions for read-only GTA VI campaign receipt accounting."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from launch_delivery_audit_v1 import audit, markdown, valid_receipts, PROVENANCE

NOW = datetime(2026, 11, 20, 15, 0, tzinfo=timezone.utc)
URL = "https://xfederiko11.github.io/gta-6/salvare-auto/"
X_URL = "https://x.com/xFederiko11/status/2123741902625218841"
POST_ID = "6b0009d8d5f8acdd0d856bd9"
FUTURE_ID = "6b000a860f5eda1a57d61243"
UNKNOWN_ID = "6b0007e3738ce4635f9d533b"

def ledger():
    return {"schema": "editorial-autopilot-v137", "entries": {
        "sent": {"status": "sent", "buffer_id": POST_ID, "url": URL,
                 "thread": ["Azione utile per GTA VI PS5", "Link alla guida"],
                 "reserved_utc": "2026-11-20T11:35:00Z"},
        "future": {"status": "scheduled", "buffer_id": FUTURE_ID, "url": URL,
                   "thread": ["Testo nuovo", "Guida collegata"],
                   "due_at": "2026-11-20T16:35:00Z"},
        "unconfirmed": {"status": "sent", "buffer_id": UNKNOWN_ID,
                        "url": "https://xfederiko11.github.io/gta-6/trofei/",
                        "thread": ["Testo", "Guida"],
                        "completed_utc": "2026-11-20T08:42:14Z"},
        "other": {"status": "sent", "buffer_id": "somethingelse1234567",
                  "url": "https://example.com/news",
                  "completed_utc": "2026-11-20T08:35:00Z"},
    }}

def feed():
    return {"schema": "verified-buffer-x-permalinks-v1",
            "posts": [{"buffer_id": POST_ID, "article_url": URL,
                       "x_url": X_URL, "sent_at": "2026-11-20T11:35:01Z",
                       "verified_by": PROVENANCE}]}


class LaunchDeliveryAuditTests(unittest.TestCase):
    def test_exact_match_distinguishes_delivery_and_reservations(self):
        snapshot = audit(ledger(), feed(), NOW)
        day = snapshot["days"][-1]
        self.assertEqual(day["date"], "2026-11-20")
        self.assertEqual(day["verified_parent_posts"], 1)
        self.assertEqual(day["verified_double_thread_parents"], 1)
        self.assertEqual(day["scheduled_double_threads_in_ledger"], 1)
        self.assertEqual(day["sent_entries_without_verified_parent"], 1)
        self.assertEqual(day["gap_to_min_verified_parents"], 9)
        self.assertIsNone(day["second_thread_replies_verified"])
        body = markdown(snapshot)
        self.assertIn("Secondi post di risposta dei thread: non verificati", body)
        self.assertIn('Mancanti al vecchio minimo (10)',body)
        self.assertIn('Obiettivo STORICO (2026-11-19–2026-11-22)',body)
        self.assertIn('Questi valori NON sono più attivi',body)
        self.assertIn('**Politica X dal 2026-11-23:** 5–6 post originali',body)
        self.assertIn('07:00–23:00 Europe/Rome',body)
        self.assertIn('nessuna risposta automatica ad altri utenti',body)
        self.assertIn("ZERO post", body)
        self.assertNotIn("follower acquisiti: 1", body)

    def test_untrusted_receipts_are_never_counted(self):
        for override in (
            {"verified_by": "untrusted"},
            {"x_url": "https://x.com/another/status/2123741902625218841"},
            {"x_url": "https://x.com.evil.test/xFederiko11/status/2123741902625218841"},
            {"article_url": "https://bad.example/gta-6/"},
            {"article_url": "https://xfederiko11.github.io/gta-6/trofei/"},
            {"sent_at": "2030-01-01T00:00:00Z"},
            {"buffer_id": "unexpectedbuffer123456"},
        ):
            v = feed()
            v["posts"][0].update(override)
            self.assertEqual(audit(ledger(), v, NOW)["days"][-1]["verified_parent_posts"], 0, override)

    def test_original_ledger_unchanged(self):
        first = ledger()
        original = deepcopy(first)
        audit(first, feed(), NOW)
        self.assertEqual(first, original)

    def test_only_two_message_threads_count_as_double(self):
        l = ledger()
        l["entries"]["sent"]["thread"] = ["One standalone post"]
        result = audit(l, feed(), NOW)["days"][-1]
        self.assertEqual(result["verified_parent_posts"], 1)
        self.assertEqual(result["verified_double_thread_parents"], 0)

    def test_conflicting_receipts_fail_closed(self):
        f = feed()
        f["posts"].append({**f["posts"][0], "x_url":
                           "https://x.com/xFederiko11/status/2123741902625218842"})
        with self.assertRaises(ValueError):
            audit(ledger(), f, NOW)

    def test_duplicate_buffer_ids_fail_closed(self):
        l = ledger()
        l["entries"]["duplicate"] = deepcopy(l["entries"]["sent"])
        with self.assertRaises(ValueError):
            audit(l, feed(), NOW)

    def test_invalid_schema_and_naive_clock_rejected(self):
        with self.assertRaises(ValueError):
            audit(ledger(), {"schema": "unverified", "posts": []}, NOW)
        with self.assertRaises(ValueError):
            audit(ledger(), feed(), datetime(2026, 11, 20, 15, 0))

    def test_only_passed_campaign_dates_reported(self):
        older = audit(ledger(), feed(), datetime(2026, 11, 19, 10, 0, tzinfo=timezone.utc))
        self.assertEqual(len(older["days"]), 1)
        self.assertEqual(older["days"][0]["date"], "2026-11-19")
        self.assertEqual(older["days"][0]["verified_parent_posts"], 0)

if __name__ == "__main__":
    unittest.main()
