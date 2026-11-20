"""Offline checks for read-only GitHub vs authenticated Buffer sample comparison."""
from __future__ import annotations
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from pathlib import Path
from copy import deepcopy
import json
import unittest

from buffer_slot_reconcile_v1 import compare, render, from_ledger

NOW = datetime(2026, 11, 20, 18, 29, tzinfo=timezone.utc)
IDS = ["6b000a86ca85ebefb00ce100", "6b000a867b0a126cebbf90c8",
       "6b000a860f5eda1a57d6121e", "6b000a854c1afd05de072532"]
BASE = "https://xfederiko11.github.io/gta-6/"


def entry(title, status, due, bid):
    return {"source": "Guide GTA VI Italia", "title": title,
            "url": BASE+"trofei/", "status": status, "due_at": due,
            "reserved_utc": due, "buffer_id": bid,
            "thread": ["Passo A", "Fonte e guida"]}


def ledger():
    return {"schema": "v13.7", "entries": {
        "current": entry("Checklist trofei", "scheduled", "2026-11-20T17:35:00Z", IDS[0]),
        "next": entry("Veicoli per il 100%", "scheduled", "2026-11-20T18:35:00Z", IDS[1]),
        "published": entry("Meditazione <una>| due", "sent", "2026-11-20T15:35:00Z", IDS[2]),
        "unverified": entry("Altri luoghi", "scheduled", "2026-11-20T16:35:00Z", IDS[3]),
        "other": entry("Altro giorno", "scheduled", "2026-11-21T13:35:00Z", "6afbeeef1111111111d123ab"),
        "non-guide": {**entry("Source", "sent", "2026-11-20T13:35:00Z", "6afeee1111111111123a"), "source": "PowerPyx"},
        "one-post": {**entry("One post", "sent", "2026-11-20T13:35:00Z", "6afeee1111111111123b"), "thread": ["single"]},
    }}


def sample():
    return {"status": "ok", "sample_limit_per_state": 15, "sent": [
            {"id": IDS[2], "dueAt": "2026-11-20T15:35:00Z", "externalLink": None}],
            "scheduled": [
            {"id": IDS[0], "dueAt": "2026-11-20T17:35:00Z", "externalLink": None},
            {"id": IDS[1], "dueAt": "2026-11-20T18:35:00Z", "externalLink": None}],
            "error": [], "is_queue_paused": False}


class ComparisonTests(unittest.TestCase):
    def test_matches_exact_ids_and_never_invents_x_delivery(self):
        result=compare(sample(), ledger(), NOW)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["rows"]), 4)
        self.assertEqual(result["counts"]["scheduled_verified"], 2)
        self.assertEqual(result["counts"]["sent_in_sample"], 1)
        self.assertEqual(result["counts"]["past_due_not_in_sample"], 1)
        body=render(result)
        self.assertIn("19:35", body)
        self.assertIn("18:35", body)
        self.assertIn("16:35", body)
        self.assertIn("non presente nel campione", body)
        self.assertIn("NON significa mancata pubblicazione", body)
        self.assertIn("mai la risposta del thread", body)
        self.assertNotIn("<una>", body)
        self.assertIn("&lt;una&gt;", body)
        self.assertNotIn("new_followers", body)
        self.assertNotIn("impression", body)
        self.assertNotIn("Trophy Safe", body)

    def test_scheduled_ledger_when_buffer_sent_is_not_auto_written(self):
        original=ledger(); before=deepcopy(original); status=sample()
        status["scheduled"]=[x for x in status["scheduled"] if x["id"]!=IDS[0]]
        status["sent"].append({"id": IDS[0], "dueAt": "2026-11-20T17:35:00Z", "externalLink": None})
        result=compare(status, original, NOW)
        self.assertEqual(result["counts"]["ledger_needs_receipt_reconcile"], 1)
        self.assertEqual(original,before)
        self.assertIn("registro non ancora riconciliato",render(result))

    def test_error_cannot_trigger_auto_retry(self):
        s=sample()
        s["scheduled"]=[x for x in s["scheduled"] if x["id"]!=IDS[1]]
        s["error"].append({"id": IDS[1], "dueAt": "2026-11-20T18:35:00Z", "externalLink": None})
        result=compare(s,ledger(),NOW)
        self.assertEqual(result["counts"]["buffer_error"],1)
        self.assertIn("NON ripubblicare",render(result))

    def test_same_buffer_id_different_due_is_flagged(self):
        s=sample()
        s["scheduled"][0]["dueAt"]="2026-11-20T17:50:00Z"
        result=compare(s,ledger(),NOW)
        self.assertEqual(result["counts"]["buffer_time_mismatch"],1)
        self.assertIn("orario Buffer diverso",render(result))

    def test_missing_ledger_and_api_are_not_zero_conversions(self):
        with TemporaryDirectory() as tmp:
            self.assertIn("Registro GitHub non trovato",from_ledger(sample(),NOW,Path(tmp)/"missing.json"))
            p=Path(tmp)/"ledger.json";p.write_text(json.dumps(ledger()),encoding="utf-8")
            text=from_ledger({"status":"unavailable","reason":"BufferAPIError"},NOW,p)
            self.assertIn("Dati Buffer non disponibili",text)
            self.assertNotIn("| Checklist trofei",text)
            self.assertIn("Slot con stato Scheduled",from_ledger(sample(),NOW,p))

    def test_untrusted_or_duplicated_buffer_ids_fail_closed(self):
        s=sample();s["sent"].append(s["scheduled"][0])
        with self.assertRaises(ValueError):
            compare(s,ledger(),NOW)
        l=ledger();l["entries"]["duplicate"]=deepcopy(l["entries"]["current"])
        with self.assertRaises(ValueError):
            compare(sample(),l,NOW)
        with self.assertRaises(ValueError):
            compare(sample(),ledger(),datetime(2026,11,20,18,29))
        with self.assertRaises(ValueError):
            compare({"status":"ok","sent":[],"scheduled":[]} ,ledger(),NOW)
        with self.assertRaises(ValueError):
            compare(sample(),{"entries":[]},NOW)

    def test_ledger_only_is_not_assumed_failed(self):
        s={"status":"ok","sent":[],"scheduled":[],"error":[]}
        r=compare(s,ledger(),NOW)
        self.assertEqual(len(r["rows"]),4)
        self.assertEqual(r["counts"]["ledger_only_not_in_sample"],1)
        self.assertEqual(r["counts"]["past_due_not_in_sample"],3)
        self.assertNotIn("mancata pubblicazione:",render(r))


if __name__=="__main__":
    unittest.main()
