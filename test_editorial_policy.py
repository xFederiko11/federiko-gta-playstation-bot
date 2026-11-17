import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import history
import online
from editorial_policy import event_allowed, approved_source, ROCKSTAR_YOUTUBE_CHANNEL
from playstation_system import parse_system_page

POLICY = {"official_only": True, "playstation_and_common_only": True}


def system(version="14.02", note="Esempio di correzione."):
    raw = f"<div><h3>Versione: {version}</h3><ul><li>{note}</li></ul></div><span>Aggiornamenti precedenti del software</span>"
    return parse_system_page(raw, "PS4", observed_at="2026-11-17T15:00:00Z")


def event(platforms=None, **extra):
    return {"event_key": "announcement", "game": "GTA VI", "category": "NEWS", "data_kind": "announcement",
            "region": None, "title": "Aggiornamento GTA VI", "platforms": platforms or [], "facts": [],
            "source_url": "https://www.rockstargames.com/newswire/article/example", "trust": "official", **extra}


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.db = online.open_db(":memory:")
        self.config = {"publication_policy": POLICY, "system_software": {"enabled": True, "platforms": ["PS4"], "announce_current": True}}

    def tearDown(self):
        self.db.close()

    def force_next(self):
        with self.db:
            self.db.execute("UPDATE monitors SET next_due=0")

    def test_common_and_playstation_stay(self):
        for values in ([], ["PS5"], ["PS4"], ["PS5", "Xbox Series X|S"], ["PS4", "PC"]):
            self.assertTrue(event_allowed(event(values), POLICY))

    def test_xbox_and_pc_exclusive_are_filtered(self):
        for values in (["PC"], ["Xbox Series X|S"], ["Xbox Series X", "Xbox Series S"], ["Xbox One", "PC"]):
            self.assertFalse(event_allowed(event(values), POLICY))
        self.assertFalse(event_allowed(event(["PS5"], title="PC-only update, PS5 unaffected"), POLICY))

    def test_community_and_domain_impersonation_are_filtered(self):
        self.assertFalse(event_allowed(event(["PS5"], trust="community"), POLICY))
        self.assertFalse(event_allowed(event(["PS5"], source_url="https://playstation.com.example.org/"), POLICY))
        self.assertFalse(event_allowed(event(["PS5"], source_url="https://rockstarintel.com/news"), POLICY))
        self.assertFalse(event_allowed(event(["PS5"], sources=[{"url": "https://example.org/?youtube.com"}]), POLICY))

    def test_youtube_requires_verified_official_channel_config(self):
        feed = {"type": "feed", "trust": "official", "url": "https://www.youtube.com/feeds/videos.xml?channel_id=" + ROCKSTAR_YOUTUBE_CHANNEL,
                "official_channel_id": ROCKSTAR_YOUTUBE_CHANNEL}
        self.assertTrue(approved_source(feed))
        self.assertFalse(approved_source({**feed, "url": "https://www.youtube.com/feeds/videos.xml?channel_id=other"}))
        self.assertFalse(event_allowed(event(source_url="https://youtube.com/watch?v=example"), POLICY))
        self.assertTrue(event_allowed(event(source_url="https://youtube.com/watch?v=example", official_channel_id=ROCKSTAR_YOUTUBE_CHANNEL), POLICY))

    def test_first_system_version_announced_once_and_no_note_duplicates(self):
        fetch = Mock(return_value=system())
        self.assertEqual(online.collect_system_updates(self.db, self.config, fetch), 0)
        self.assertEqual(online.prepare_jobs(self.db, self.config), 1)
        self.force_next()
        fetch.return_value = system(note="Testo aggiornato senza nuova versione.")
        online.collect_system_updates(self.db, self.config, fetch)
        self.assertEqual(online.prepare_jobs(self.db, self.config), 0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM publish_jobs").fetchone()[0], 1)

    def test_new_version_and_later_rollback_are_distinct_observations(self):
        for version in ("14.02", "14.03", "14.02"):
            self.force_next()
            online.collect_system_updates(self.db, self.config, Mock(return_value=system(version=version)))
            self.assertEqual(online.prepare_jobs(self.db, self.config), 1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM publish_jobs").fetchone()[0], 3)

    def test_source_failure_keeps_previous_version(self):
        online.collect_system_updates(self.db, self.config, Mock(return_value=system()))
        self.force_next()
        self.assertEqual(online.collect_system_updates(self.db, self.config, Mock(side_effect=ValueError("missing current"))), 1)
        state = json.loads(self.db.execute("SELECT state_json FROM monitors").fetchone()[0])
        self.assertEqual(state["version"], "14.02")
        self.assertEqual(self.db.execute("SELECT count(*) FROM posts").fetchone()[0], 1)

    def test_existing_disallowed_drafts_are_not_sent(self):
        with self.db:
            self.db.execute("INSERT INTO publish_jobs(key,event_json,status,text,created_at) VALUES (?,?,?,?,?)",
                            ("old", json.dumps(event(["Xbox Series X|S"])), "draft", "old draft", 0))
        client = Mock()
        online.deliver(self.db, client, Mock(), "/tmp/cards", policy=POLICY)
        client.publish.assert_not_called()
        self.assertEqual(self.db.execute("SELECT status FROM publish_jobs").fetchone()[0], "filtered")

    def test_public_history_filters_old_xbox_and_unofficial_records(self):
        base = {"game": "GTA VI", "platform": "PS5", "region": "EU", "event_type": "availability_fixture",
                "metric_kind": "availability", "observed_at": "2026-11-17T00:00:00Z", "source_tier": "primary",
                "verification": "verified", "source_url": "https://www.rockstargames.com/newswire/fixture"}
        history.import_history(self.db, [base,
            {**base, "game": "PlayStation", "platform": "PS4", "source_url": "https://www.playstation.com/support/fixture/"},
            {**base, "platform": "Xbox Series X|S", "source_url": "https://www.xbox.com/fixture/"},
            {**base, "source_tier": "secondary", "verification": "reported", "source_url": "https://example.org/report"}])
        with tempfile.TemporaryDirectory() as directory, patch.object(online, "ROOT", Path(directory)):
            payload = online.export_public_history(self.db, Path(directory) / "public.json", POLICY)
        self.assertEqual(len(payload["records"]), 2)
        self.assertTrue(all(row["platform"].startswith("PS") and row["verification"] == "verified" for row in payload["records"]))
        self.assertNotIn("research_candidates", payload)


if __name__ == "__main__":
    unittest.main()
