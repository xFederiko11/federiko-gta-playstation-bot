import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from state_health import load_health, meaningful_fingerprint, save_health


class StateHealthTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript("""
          CREATE TABLE meta (key TEXT PRIMARY KEY,value TEXT);
          CREATE TABLE monitors (id TEXT PRIMARY KEY,state_json TEXT,last_success REAL,last_error TEXT,next_due REAL);
          CREATE TABLE posts (key TEXT PRIMARY KEY,source_json TEXT,status TEXT);
          CREATE TABLE publish_jobs (key TEXT PRIMARY KEY,event_json TEXT,status TEXT,next_attempt REAL);
          CREATE TABLE buffer_requests (at REAL);
          CREATE TABLE download_history (record_id TEXT PRIMARY KEY,first_observed_at TEXT,last_observed_at TEXT,record_json TEXT);
          CREATE TABLE history_metadata (key TEXT PRIMARY KEY,value_json TEXT);
        """)
        self.db.execute("INSERT INTO meta VALUES ('xbox_checked','100')")
        self.db.execute("INSERT INTO meta VALUES ('xbox_signature','actual-catalog-cursor')")
        self.db.execute("INSERT INTO monitors VALUES ('official',?,100,NULL,200)",
                        (json.dumps({"cursor": "42", "private_local_marker": "DO_NOT_EXPORT_THIS"}),))
        self.db.execute("INSERT INTO posts VALUES ('p',?, 'queued')", (json.dumps({"text": "PRIVATE_QUEUE_TEXT"}),))
        self.db.execute("INSERT INTO publish_jobs VALUES ('job', '{}', 'draft',0)")
        self.record = {"game": "GTA VI", "version": "1", "observed_at": "2026-11-17T00:00:00Z",
                       "evidence_sha256": "response-hash-1", "size_bytes": 100}
        self.db.execute("INSERT INTO download_history VALUES ('record','a','b',?)", (json.dumps(self.record),))
        self.db.commit()
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "monitor-health.json"

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_clocks_and_evidence_rechecks_do_not_change_meaningful_fingerprint(self):
        first = meaningful_fingerprint(self.db)
        self.db.execute("UPDATE monitors SET last_success=300,next_due=400,last_error='Timeout'")
        self.db.execute("UPDATE meta SET value='300' WHERE key='xbox_checked'")
        record = {**self.record, "observed_at": "2026-11-18T00:00:00Z", "evidence_sha256": "response-hash-2"}
        self.db.execute("UPDATE download_history SET first_observed_at='c',last_observed_at='d',record_json=?", (json.dumps(record),))
        self.assertEqual(meaningful_fingerprint(self.db), first)

    def test_cursor_change_is_meaningful(self):
        first = meaningful_fingerprint(self.db)
        self.db.execute("UPDATE monitors SET state_json=?", (json.dumps({"cursor": "43"}),))
        self.assertNotEqual(meaningful_fingerprint(self.db), first)

    def test_buffer_usage_and_delivery_retry_are_meaningful(self):
        first = meaningful_fingerprint(self.db)
        self.db.execute("INSERT INTO buffer_requests VALUES (123)")
        second = meaningful_fingerprint(self.db)
        self.assertNotEqual(second, first)
        self.db.execute("UPDATE publish_jobs SET next_attempt=600")
        self.assertNotEqual(meaningful_fingerprint(self.db), second)

    def test_real_download_fact_and_metadata_changes_are_meaningful(self):
        first = meaningful_fingerprint(self.db)
        self.db.execute("UPDATE download_history SET record_json=?", (json.dumps({**self.record, "size_bytes": 101}),))
        second = meaningful_fingerprint(self.db)
        self.assertNotEqual(second, first)
        self.db.execute("INSERT INTO history_metadata VALUES (?,?)", ("gaps", json.dumps(["PS5 version unknown"])))
        self.assertNotEqual(meaningful_fingerprint(self.db), second)

    def test_json_key_order_and_row_order_are_irrelevant(self):
        first = meaningful_fingerprint(self.db)
        reversed_record = dict(reversed(list(self.record.items())))
        self.db.execute("UPDATE download_history SET record_json=?", (json.dumps(reversed_record, indent=2),))
        self.assertEqual(meaningful_fingerprint(self.db), first)
        self.db.executemany("INSERT INTO buffer_requests VALUES (?)", [(1,), (2,)])
        before = meaningful_fingerprint(self.db)
        self.db.execute("DELETE FROM buffer_requests")
        self.db.executemany("INSERT INTO buffer_requests VALUES (?)", [(2,), (1,)])
        self.assertEqual(meaningful_fingerprint(self.db), before)

    def test_public_health_contains_no_snapshot_queue_or_error_secrets(self):
        self.db.execute("UPDATE monitors SET last_error='Authorization: Bearer VERY_SECRET_TOKEN'")
        save_health(self.db, self.path)
        text = self.path.read_text()
        for private in ("DO_NOT_EXPORT_THIS", "PRIVATE_QUEUE_TEXT", "VERY_SECRET_TOKEN", "actual-catalog-cursor", "state_json"):
            self.assertNotIn(private, text)
        payload = json.loads(text)
        self.assertEqual(payload["monitors"][0]["last_error"], "SourceError")
        self.assertEqual(set(payload["monitors"][0]), {"id", "last_success", "last_error", "next_due"})

    def test_load_only_updates_existing_health_never_cursors_or_queue(self):
        original = meaningful_fingerprint(self.db)
        payload = {"schema_version": 1, "monitors": [
            {"id": "official", "last_success": 900, "next_due": 1000, "last_error": "Timeout",
             "state_json": '{"cursor":"ATTACK"}', "cursor": "ATTACK"},
            {"id": "new-source", "last_success": 900, "next_due": 1000}],
            "meta": {"xbox_checked": 800, "xbox_signature": "ATTACK"},
            "posts": [{"status": "posted"}]}
        self.path.write_text(json.dumps(payload))
        self.assertTrue(load_health(self.db, self.path))
        self.assertEqual(meaningful_fingerprint(self.db), original)
        self.assertEqual(self.db.execute("SELECT last_success,next_due,last_error FROM monitors").fetchone(), (900, 1000, "Timeout"))
        self.assertEqual(self.db.execute("SELECT count(*) FROM monitors").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT value FROM meta WHERE key='xbox_checked'").fetchone()[0], "800.0")
        self.assertEqual(self.db.execute("SELECT status FROM posts").fetchone()[0], "queued")

    def test_save_and_load_health_do_not_change_fingerprint(self):
        before = meaningful_fingerprint(self.db)
        save_health(self.db, self.path)
        load_health(self.db, self.path)
        self.assertEqual(meaningful_fingerprint(self.db), before)

    def test_history_clock_restore_is_monotone_and_cannot_inject_facts(self):
        record = {**self.record, "observed_at": "2026-11-17T00:00:00Z"}
        self.db.execute("UPDATE download_history SET first_observed_at=?,last_observed_at=?,record_json=?",
                        ("2026-11-16T00:00:00Z", "2026-11-17T00:00:00Z", json.dumps(record)))
        before = meaningful_fingerprint(self.db)
        save_health(self.db, self.path)
        payload = json.loads(self.path.read_text())
        self.assertEqual(set(payload["history_observed"][0]), {"record_id", "last_observed_at"})
        payload["history_observed"] = [
            {"record_id": "record", "last_observed_at": "2026-11-18T01:00:00+01:00",
             "version": "UNTRUSTED", "size_bytes": 999},
            {"record_id": "new-record", "last_observed_at": "2026-11-18T00:00:00Z", "version": "INJECTED"}]
        self.path.write_text(json.dumps(payload))
        self.assertTrue(load_health(self.db, self.path))
        row = self.db.execute("SELECT first_observed_at,last_observed_at,record_json FROM download_history").fetchone()
        updated = json.loads(row[2])
        self.assertEqual(row[:2], ("2026-11-16T00:00:00Z", "2026-11-18T00:00:00Z"))
        self.assertEqual(updated["version"], "1")
        self.assertEqual(updated["size_bytes"], 100)
        self.assertEqual(updated["observed_at"], row[1])
        self.assertEqual(self.db.execute("SELECT count(*) FROM download_history").fetchone()[0], 1)
        self.assertEqual(meaningful_fingerprint(self.db), before)
        payload["history_observed"][0]["last_observed_at"] = "2026-11-17T00:00:00Z"
        self.path.write_text(json.dumps(payload))
        load_health(self.db, self.path)
        self.assertEqual(self.db.execute("SELECT last_observed_at FROM download_history").fetchone()[0], "2026-11-18T00:00:00Z")

    def test_weekly_radar_clocks_restore_without_changing_private_state(self):
        from datetime import datetime, timezone
        from weekly_radar_v12 import init, poll
        init(self.db)
        self.db.row_factory = sqlite3.Row
        now = datetime.now(timezone.utc).timestamp()
        signature = "PRIVATE_RADAR_SIGNATURE"
        links = '["PRIVATE_LINK_FINGERPRINT"]'
        old = now - 900
        due = now + 900
        self.db.execute("INSERT INTO weekly_radar_v12_sources VALUES (?,?,?,?,?,?)",
                        ("rsg-online-us", signature, links, old, old, "render_content_missing"))
        before = meaningful_fingerprint(self.db)
        self.db.execute("UPDATE weekly_radar_v12_sources SET next_due=? WHERE id=?", (due,"rsg-online-us"))
        self.assertEqual(meaningful_fingerprint(self.db),before)
        save_health(self.db,self.path)
        payload = json.loads(self.path.read_text())
        self.assertNotIn(signature,self.path.read_text())
        self.assertNotIn("PRIVATE_LINK_FINGERPRINT",self.path.read_text())
        self.assertEqual(set(payload["weekly_radar_clocks"][0]),
                         {"id","last_success","next_due","has_error"})
        self.db.execute("UPDATE weekly_radar_v12_sources SET next_due=?", (old,))
        with self.assertLogs("state_health", level="INFO") as captured:
            self.assertTrue(load_health(self.db,self.path))
        self.assertEqual(captured.output, [
            "INFO:state_health:MONITOR_HEALTH_RADAR_RESTORE accepted=1 advanced=1 future=1"])
        restored = self.db.execute("SELECT * FROM weekly_radar_v12_sources").fetchone()
        self.assertEqual(restored["next_due"],due)
        self.assertEqual(restored["last_error"],"render_content_missing")
        self.assertEqual(restored["signature"],signature)
        self.assertEqual(restored["link_ids_json"],links)
        self.assertEqual(meaningful_fingerprint(self.db),before)
        # A restarted process should not read a source whose retry is not due.
        from unittest.mock import patch, Mock
        fetch = Mock(side_effect=AssertionError("Premature network read"))
        with patch("weekly_radar_v12.TARGETS", ({"id":"rsg-online-us"},)):
            result = poll(self.db,fetcher=fetch,now=now)
        self.assertEqual(result["checked"]+result["errors"],0)
        fetch.assert_not_called()

    def test_weekly_radar_heartbeat_cannot_clear_errors_or_create_success(self):
        from datetime import datetime, timezone
        from weekly_radar_v12 import init
        init(self.db)
        now = datetime.now(timezone.utc).timestamp()
        old = now-900
        self.db.execute("INSERT INTO weekly_radar_v12_sources VALUES (?,?,?,?,?,?)",
                        ("rsg-online-us","private",'[]',old,None,"render_content_missing"))
        self.db.execute("INSERT INTO weekly_radar_v12_sources VALUES (?,?,?,?,?,?)",
                        ("rsg-gta-online","private",'[]',old,old,None))
        save_health(self.db,self.path)
        payload=json.loads(self.path.read_text())
        payload["weekly_radar_clocks"]=[
            {"id":"rsg-online-us","last_success":now,"next_due":now+900,"has_error":False},
            {"id":"rsg-gta-online","last_success":now,"next_due":now+86400,"has_error":False},
            {"id":"injected","last_success":now,"next_due":now+900,"has_error":False},
        ]
        self.path.write_text(json.dumps(payload))
        before=meaningful_fingerprint(self.db)
        with self.assertLogs("state_health", level="INFO") as captured:
            load_health(self.db,self.path)
        self.assertEqual(captured.output, [
            "INFO:state_health:MONITOR_HEALTH_RADAR_RESTORE accepted=0 advanced=0 future=0"])
        self.assertEqual(self.db.execute("SELECT last_success,next_due,last_error FROM weekly_radar_v12_sources WHERE id='rsg-online-us'").fetchone(),
                         (None,old,"render_content_missing"))
        self.assertEqual(self.db.execute("SELECT last_success,next_due FROM weekly_radar_v12_sources WHERE id='rsg-gta-online'").fetchone(),(old,old))
        self.assertEqual(self.db.execute("SELECT count(*) FROM weekly_radar_v12_sources").fetchone()[0],2)
        self.assertEqual(meaningful_fingerprint(self.db),before)
        payload["weekly_radar_clocks"]=[
            {"id":"rsg-gta-online","last_success":now,"next_due":now+600,"has_error":False}]
        self.path.write_text(json.dumps(payload))
        load_health(self.db,self.path)
        self.assertEqual(self.db.execute("SELECT last_success,next_due FROM weekly_radar_v12_sources WHERE id='rsg-gta-online'").fetchone(),(now,now+600))
        self.assertEqual(meaningful_fingerprint(self.db),before)
        payload["weekly_radar_clocks"][0]["next_due"]=old
        self.path.write_text(json.dumps(payload))
        load_health(self.db,self.path)
        self.assertEqual(self.db.execute("SELECT next_due FROM weekly_radar_v12_sources WHERE id='rsg-gta-online'").fetchone()[0],now+600)

    def test_radar_restore_telemetry_distinguishes_unchanged_overdue_clocks(self):
        from datetime import datetime, timezone
        from weekly_radar_v12 import init
        init(self.db)
        old = datetime.now(timezone.utc).timestamp() - 900
        self.db.execute("INSERT INTO weekly_radar_v12_sources VALUES (?,?,?,?,?,?)",
                        ("PRIVATE_SOURCE_ID", "PRIVATE_SIGNATURE", '["PRIVATE_LINK"]',
                         old, old, None))
        self.db.commit()
        before = meaningful_fingerprint(self.db)
        save_health(self.db, self.path)
        with self.assertLogs("state_health", level="INFO") as captured:
            self.assertTrue(load_health(self.db, self.path))
        self.assertEqual(captured.output, [
            "INFO:state_health:MONITOR_HEALTH_RADAR_RESTORE accepted=1 advanced=0 future=0"])
        self.assertEqual(meaningful_fingerprint(self.db), before)

    def test_radar_restore_does_not_report_success_when_transaction_rolls_back(self):
        from datetime import datetime, timezone
        from weekly_radar_v12 import init
        init(self.db)
        old = datetime.now(timezone.utc).timestamp() - 900
        self.db.execute("INSERT INTO weekly_radar_v12_sources VALUES (?,?,?,?,?,?)",
                        ("source", "PRIVATE_SIGNATURE", '[]', old, old, None))
        self.db.executescript("""
          CREATE TRIGGER reject_clock_update BEFORE UPDATE ON weekly_radar_v12_sources
          BEGIN SELECT RAISE(ABORT, 'test rollback'); END;
        """)
        self.db.commit()
        save_health(self.db, self.path)
        before = meaningful_fingerprint(self.db)
        with self.assertNoLogs("state_health", level="INFO"):
            with self.assertRaises(sqlite3.IntegrityError):
                load_health(self.db, self.path)
        self.assertEqual(meaningful_fingerprint(self.db), before)
        self.assertEqual(self.db.execute("SELECT next_due FROM weekly_radar_v12_sources").fetchone()[0], old)

    def test_missing_or_corrupt_health_is_ignored(self):
        self.assertFalse(load_health(self.db, self.path))
        self.path.write_text("not JSON")
        self.assertFalse(load_health(self.db, self.path))


if __name__ == "__main__":
    unittest.main()
