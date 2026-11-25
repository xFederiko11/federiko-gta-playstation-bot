import json
import importlib.util
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import online
from buffer_publisher import BufferAPIError, BufferPending, Delivery
from free_editor import article_event, article_events, catalog_event, platforms_from


def event(platform="PS5", size=100):
    return {"event_key": "shared-release", "game": "GTA VI", "category": "PATCH",
            "data_kind": "package", "region": "EU", "platforms": [platform],
            "title": "Nuovo pacchetto", "facts": [{"label": "Download", "value": size, "unit": "byte"}],
            "trust": "official", "source_name": "Publisher", "source_url": "https://example.org/release"}


class OnlineTests(unittest.TestCase):
    def setUp(self):
        self.db = online.open_db(":memory:")
        self.cfg = {"scope": "gta", "sources": [], "allow_community_fallback": False}

    def tearDown(self):
        self.db.close()

    def queue(self, key, payload):
        with self.db:
            self.db.execute("INSERT INTO posts(key,source_id,source_json) VALUES (?,?,?)", (key, key, json.dumps(payload)))

    def draft(self, key="a", payload=None):
        self.queue(key, {"key": key, "presentation": payload or event(), "trust": "official"})
        online.prepare_jobs(self.db, self.cfg)

    def state(self):
        return self.db.execute("SELECT status FROM publish_jobs").fetchone()[0]

    def test_same_values_produce_one_common_post(self):
        self.queue("a", {"key": "a", "presentation": event(), "trust": "official"})
        self.queue("b", {"key": "b", "presentation": event("Xbox Series X|S"), "trust": "official"})
        self.assertEqual(online.prepare_jobs(self.db, self.cfg), 1)
        value = json.loads(self.db.execute("SELECT event_json FROM publish_jobs").fetchone()[0])
        self.assertEqual(value["platforms"], ["PS5", "Xbox Series X|S"])

    def test_different_values_produce_console_specific_posts(self):
        for key, payload in [("a", event()), ("b", event("Xbox Series X|S", 200))]:
            self.queue(key, {"key": key, "presentation": payload, "trust": "official"})
        self.assertEqual(online.prepare_jobs(self.db, self.cfg), 2)

    def test_community_not_published_when_primary_policy_enabled(self):
        self.queue("a", {"key": "a", "text": "GTA VI new patch", "trust": "community"})
        self.assertEqual(online.prepare_jobs(self.db, self.cfg), 0)

    def test_quota_blocks_before_new_http_call(self):
        budget = online.FreeRequestBudget(self.db)
        for _ in range(40):
            budget()
        with self.assertRaises(online.FreeQuotaExceeded):
            budget()
        self.assertEqual(self.db.execute("SELECT count(*) FROM buffer_requests").fetchone()[0], 40)

    def test_monthly_quota_preserves_requests_outside_daily_window(self):
        budget = online.FreeRequestBudget(self.db)
        with self.db:
            self.db.executemany("INSERT INTO buffer_requests VALUES (?)", [(time.time() - 2*86400,)] * 900)
        with self.assertRaises(online.FreeQuotaExceeded):
            budget()

    def test_paid_read_sources_are_rejected(self):
        with self.assertRaises(ValueError):
            online.source_policy({"sources": [{"type": "x"}]})

    @patch.dict(os.environ, {"ALLOW_PAID_SERVICES": "false", "OPENAI_API_KEY": "unused-test"})
    @unittest.skipUnless(importlib.util.find_spec("bot"), "I moduli API a pagamento non sono inclusi nel pacchetto gratuito")
    def test_old_paid_paths_are_off_by_default(self):
        import bot
        with patch("bot.requests.post") as post:
            with self.assertRaises(ValueError):
                bot.Writer()
            with self.assertRaises(ValueError):
                bot.XClient()
            with self.assertRaises(ValueError):
                bot.Writer(require_api=False).generate({"text": "GTA VI", "id": "1"})
            post.assert_not_called()

    def test_catalog_baseline_does_not_publish_old_observation(self):
        signal = {"id": "1", "game": "GTA VI", "platforms": ["Xbox Series X|S"], "region": "US",
                  "metric_kind": "max_download", "metric_label": "Limite dimensione download catalogo",
                  "value_bytes": 100, "version": None, "source_url": "https://example.org/catalog",
                  "source_name": "Catalogo", "observed_at": "2026-11-17T00:00:00Z"}
        fetcher = Mock(return_value={"records": [], "signals": [signal]})
        cfg = {**self.cfg, "catalog_interval": 0}
        online.collect_catalog(self.db, cfg, fetcher)
        self.assertEqual(self.db.execute("SELECT count(*) FROM posts").fetchone()[0], 0)
        fetcher.return_value = {"records": [], "signals": [{**signal, "id": "2", "value_bytes": 200}]}
        online.collect_catalog(self.db, cfg, fetcher)
        online.prepare_jobs(self.db, cfg)
        text = self.db.execute("SELECT event_json FROM publish_jobs").fetchone()[0]
        self.assertIn("Limite dimensione download catalogo", text)
        self.assertIn("METADATI", text)
        for value in (100, 200):
            fetcher.return_value = {"records": [], "signals": [{**signal, "value_bytes": value}]}
            online.collect_catalog(self.db, cfg, fetcher)
            online.prepare_jobs(self.db, cfg)
        self.assertEqual(self.db.execute("SELECT count(*) FROM publish_jobs").fetchone()[0], 3)

    def test_persist_sending_before_mutation_and_then_posted(self):
        self.draft()
        sequence = []
        client = Mock()
        client.last_delivery = Delivery("buffer-id", "sent", "https://x.com/user/status/123")
        client.publish.side_effect = lambda *args, **kwargs: sequence.append("publish") or "buffer-id"
        def checkpoint():
            sequence.append(self.state())
        online.deliver(self.db, client, lambda p: "https://example.org/card.png", "/tmp/cards",
                       render=Mock(), checkpoint=checkpoint)
        self.assertEqual(sequence, ["sending", "publish", "posted"])

    def test_accepted_is_not_claimed_posted_and_not_resent(self):
        self.draft()
        client = Mock()
        client.publish.side_effect = BufferPending("buffer-123", "pending")
        online.deliver(self.db, client, lambda p: "https://example.org/card.png", "/tmp/cards", render=Mock())
        self.assertEqual(self.state(), "accepted")
        with self.db:
            self.db.execute("UPDATE publish_jobs SET next_attempt=0")
        client.delivery_status.return_value = Delivery("buffer-123", "sent", "https://x.com/test/status/321")
        online.deliver(self.db, client, Mock(), "/tmp/cards", render=Mock())
        self.assertEqual(self.state(), "posted")
        client.publish.assert_called_once()
        self.assertEqual(self.db.execute("SELECT buffer_id FROM publish_jobs").fetchone()[0], "buffer-123")

    def test_unknown_timeout_does_not_repeat_post(self):
        self.draft()
        client = Mock()
        client.publish.side_effect = BufferAPIError("timeout", outcome_unknown=True)
        online.deliver(self.db, client, Mock(return_value="https://example.org/a.png"), "/tmp/cards", render=Mock())
        self.assertEqual(self.state(), "uncertain")
        online.deliver(self.db, client, Mock(), "/tmp/cards", render=Mock())
        client.publish.assert_called_once()

    def test_unknown_outage_stops_further_creations_in_same_run(self):
        for number in range(21):
            self.draft(str(number), {**event(), "event_key": str(number)})
        client = Mock()
        client.publish.side_effect = BufferAPIError("timeout", outcome_unknown=True)
        online.deliver(self.db, client, Mock(return_value="https://example.org/a.png"), "/tmp/cards", render=Mock())
        client.publish.assert_called_once()

    def test_image_missing_before_buffer_is_review_without_attempt_or_retry(self):
        self.draft()
        client=Mock(destination={'id':'channel-1'})
        upload=Mock(return_value=None)
        renderer=Mock()
        online.deliver(self.db,client,upload,'/tmp/cards',render=renderer)
        row=self.db.execute('SELECT status,last_error,attempted_at FROM publish_jobs').fetchone()
        self.assertEqual(row['status'],'review')
        self.assertEqual(row['last_error'],'image_missing_before_buffer')
        self.assertEqual(row['attempted_at'],0.0)
        client.publish.assert_not_called()
        client.publish_thread.assert_not_called()
        upload.assert_called_once()
        renderer.assert_called_once()
        online.deliver(self.db,client,upload,'/tmp/cards',render=renderer)
        client.publish.assert_not_called()
        upload.assert_called_once()

    def test_bad_destination_does_not_become_uncertain(self):
        self.draft()
        client = Mock(destination=None)
        client.verify_destination.side_effect = ValueError("wrong account")
        with self.assertRaises(ValueError):
            online.deliver(self.db, client, Mock(), "/tmp/cards", render=Mock())
        self.assertEqual(self.state(), "draft")
        client.publish.assert_not_called()

    def test_quota_preserves_draft(self):
        self.draft()
        client = Mock()
        client.publish.side_effect = online.FreeQuotaExceeded()
        with self.assertRaises(online.FreeQuotaExceeded):
            online.deliver(self.db, client, Mock(return_value="https://example.org/a.png"), "/tmp/cards", render=Mock())
        self.assertEqual(self.state(), "draft")

    def test_demo_cannot_be_sent(self):
        self.draft(payload={**event(), "demo": True})
        client = Mock()
        upload = Mock()
        online.deliver(self.db, client, upload, "/tmp/cards", render=Mock())
        self.assertEqual(self.state(), "review")
        client.publish.assert_not_called()
        upload.assert_not_called()

    def test_daily_cap_uses_delivery_attempt_not_old_queue_date(self):
        for number in range(20):
            self.draft(str(number), {**event(), "event_key": str(number)})
        with self.db:
            self.db.execute("UPDATE publish_jobs SET status='posted',created_at=?,attempted_at=?", (time.time()-2*86400,time.time()))
        self.draft("new", {**event(), "event_key": "new"})
        client = Mock()
        online.deliver(self.db, client, Mock(), "/tmp/cards", render=Mock())
        client.publish.assert_not_called()

    def test_free_editor_uses_primary_title_without_fake_version(self):
        value = article_event({"key": "a", "headline": "New GTA Online bonuses", "text": "GTA Online offers 2X GTA$ & RP and 30% off.",
                               "source_url": "https://example.org/a", "trust": "official"})
        self.assertEqual(value["game"], "GTA Online")
        self.assertEqual(value["category"], "EVENTI")
        self.assertEqual(len(value["facts"]), 2)
        self.assertEqual(platforms_from("PS5 and Xbox Series X|S"), ["PS5", "Xbox Series X|S"])

    def test_article_console_sizes_are_split_before_grouping(self):
        self.queue("size", {"key": "size", "text": "GTA VI update. PS5: 10 GB; Xbox Series X|S: 12 GB.",
                            "headline": "GTA VI update", "trust": "official", "source_url": "https://example.org/update"})
        self.assertEqual(online.prepare_jobs(self.db, self.cfg), 2)
        events = [json.loads(row[0]) for row in self.db.execute("SELECT event_json FROM publish_jobs")]
        self.assertEqual({e["facts"][0]["value"] for e in events}, {"10 GB", "12 GB"})

    def test_equal_explicit_console_sizes_can_be_unified(self):
        self.queue("same", {"key": "same", "text": "GTA VI update worldwide. PS5: 10 GB; Xbox Series X|S: 10 GB.",
                            "headline": "GTA VI update", "trust": "official", "source_url": "https://example.org/update"})
        self.assertEqual(online.prepare_jobs(self.db, self.cfg), 1)

    def test_ambiguous_shared_platform_statement_is_not_assigned_to_one_console(self):
        values = article_events({"key": "a", "text": "GTA VI on PS5 and Xbox Series X|S requires up to 212 GB.", "trust": "official"})
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0]["data_kind"], "announcement")
        self.assertEqual(values[0]["platforms"], ["PS5", "Xbox Series X|S"])

    def test_xbox_models_remain_explicit(self):
        self.assertEqual(platforms_from("Xbox Series X and Xbox Series S"), ["Xbox Series X", "Xbox Series S"])
        self.assertEqual(platforms_from("Xbox Series X|S"), ["Xbox Series X|S"])

    def test_dispatch_work_is_an_event_not_a_patch(self):
        value = article_event({"key": "a", "headline": "GTA Online Dispatch Work Bonuses",
                               "text": "Earn 2X GTA$ & RP on Dispatch Work this week.", "trust": "official"})
        self.assertEqual(value["category"], "EVENTI")

    def test_patch_note_revision_does_not_reannounce_old_facts(self):
        item = {"key": "revision:2", "headline": "GTAV Title Update 1.73 Notes", "text": "GTAV Title Update 1.73 Notes. PS5: 10 GB; Xbox Series X|S: 12 GB.",
                "trust": "official", "source_url": "https://example.org/notes", "change_context": "patch note aggiornata"}
        values = article_events(item)
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0]["title"], "Patch note aggiornata")
        self.assertEqual(values[0]["data_kind"], "page_revision")
        self.assertNotIn("10 GB", json.dumps(values[0]["facts"]))

    @patch("sources.get_html")
    def test_support_watch_discovers_new_notes_and_their_revisions(self, get_html):
        import sources
        source = {"id": "support", "name": "Support", "trust": "official", "type": "web_links",
                  "url": "https://example.org/support", "selector": "a", "article_selector": "article",
                  "watch_existing_pattern": "title-update"}
        index = "<a href='/title-update-1'>GTAV Title Update</a>"
        body1 = "<article><h3 data-testid='page-title'>GTAV Title Update</h3>Old content</article>"
        body2 = "<article><h3 data-testid='page-title'>GTAV Title Update</h3>New correction</article>"
        get_html.side_effect = [index, body1, index, body2, index, body1, index, body2]
        entries, state = sources.collect(source, {}, None)
        self.assertEqual(entries, [])
        keys = []
        for _ in range(3):
            entries, state = sources.collect(source, state, None)
            self.assertEqual(entries[0]["change_context"], "patch note aggiornata")
            keys.append(entries[0]["key"])
        self.assertEqual(len(set(keys)), 3)


if __name__ == "__main__":
    unittest.main()
