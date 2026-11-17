"""Regression checks: unposted backlog must never be sent after activation."""

import json
import unittest
from unittest.mock import Mock

import online


EVENT = {
    "event_key": "ps5-system-test", "game": "PlayStation", "category": "SISTEMA",
    "data_kind": "system_software_available", "region": "EU", "platforms": ["PS5"],
    "title": "Aggiornamento di sistema disponibile", "trust": "official",
    "facts": [{"label": "Versione", "value": "14.23"}],
    "source_name": "Sony", "source_url": "https://www.playstation.com/it-it/",
}


class PublicationGuardTests(unittest.TestCase):
    def setUp(self):
        self.db = online.open_db(":memory:")
        self.config = {"scope": "gta", "sources": []}

    def tearDown(self):
        self.db.close()

    def add_draft(self, ident="old"):
        item = {"key": ident, "trust": "official", "presentation": {**EVENT, "event_key": ident}}
        with self.db:
            self.db.execute(
                "INSERT INTO posts(key,source_id,source_json) VALUES (?,?,?)",
                (ident, ident, json.dumps(item)),
            )
        online.prepare_jobs(self.db, self.config)
        return self.db.execute("SELECT key FROM publish_jobs WHERE status='draft'").fetchone()[0]

    def test_archives_old_draft_but_keeps_published_and_accepted(self):
        self.add_draft("one")
        self.add_draft("two")
        with self.db:
            self.db.execute("UPDATE publish_jobs SET status='posted' WHERE key=(SELECT key FROM publish_jobs ORDER BY created_at,key LIMIT 1)")
        self.assertEqual(online.suppress_unpublished(self.db, "pre_launch_baseline"), 1)
        self.assertEqual({r[0] for r in self.db.execute("SELECT status FROM publish_jobs")}, {"posted", "suppressed"})
        self.assertEqual(online.suppress_unpublished(self.db), 0)

    def test_first_baseline_marker_is_persistent(self):
        self.assertTrue(online.needs_first_publication_baseline(self.db))
        online.suppress_unpublished(self.db, "pre_launch_baseline", initialize=True)
        self.assertFalse(online.needs_first_publication_baseline(self.db))
        self.assertIsNotNone(online.get_meta(self.db, "publication_guard_initialized_v1"))

    def test_suppressed_cannot_reappear_and_new_still_can(self):
        old_key = self.add_draft("ps5-old")
        online.suppress_unpublished(self.db)
        self.assertEqual(online.prepare_jobs(self.db, self.config), 0)
        self.add_draft("ps5-new")
        self.assertEqual(self.db.execute("SELECT count(*) FROM publish_jobs WHERE status='draft'").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT status FROM publish_jobs WHERE key=?", (old_key,)).fetchone()[0], "suppressed")

    def test_disabled_drafts_cannot_reach_delivery(self):
        self.add_draft("old")
        online.suppress_unpublished(self.db)
        client, upload, render = Mock(), Mock(), Mock()
        online.deliver(self.db, client, upload, "/tmp", render=render)
        client.publish.assert_not_called()
        client.publish_thread.assert_not_called()
        upload.assert_not_called()
        render.assert_not_called()

    def test_uncertain_and_accepted_are_not_requeued(self):
        self.add_draft("old1")
        self.add_draft("old2")
        with self.db:
            self.db.execute("UPDATE publish_jobs SET status='accepted' WHERE event_json LIKE '%old1%'")
            self.db.execute("UPDATE publish_jobs SET status='uncertain' WHERE event_json LIKE '%old2%'")
        self.assertEqual(online.suppress_unpublished(self.db), 0)
        self.assertEqual({r[0] for r in self.db.execute("SELECT status FROM publish_jobs")}, {"uncertain", "accepted"})


if __name__ == "__main__":
    unittest.main()
