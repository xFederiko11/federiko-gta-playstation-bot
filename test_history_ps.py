import json
from pathlib import Path
import tempfile
import unittest

import history
import online
from editorial_policy import history_record_allowed


class PlayStationHistoryTests(unittest.TestCase):
    def test_seed_has_only_official_ps_records_and_explicit_gaps(self):
        seed = json.loads(Path(__file__).with_name("history-ps-seed.json").read_text())
        policy = {"official_only": True, "playstation_and_common_only": True}
        self.assertEqual(seed["coverage"]["starts_with_official_preload"], "2026-11-10")
        self.assertFalse(seed["coverage"]["complete"])
        self.assertTrue(all(history_record_allowed(row, policy) for row in seed["records"]))
        self.assertTrue(all(row["version"] is None for row in seed["records"]))
        self.assertNotIn("research_candidates", seed)

    def test_import_idempotent_and_dates_remain_distinct(self):
        seed = json.loads(Path(__file__).with_name("history-ps-seed.json").read_text())
        db = online.open_db(":memory:")
        self.addCleanup(db.close)
        self.assertEqual(history.import_history(db, seed), 2)
        self.assertEqual(history.import_history(db, seed), 0)
        with tempfile.TemporaryDirectory() as directory:
            exported = history.export_history(db, Path(directory) / "history.json")
        preload = next(row for row in exported["records"] if row["metric_kind"] == "availability")
        self.assertEqual(preload["occurred_at"], "2026-11-10T00:00:00")
        self.assertEqual(preload["date_precision"], "local_time")
        self.assertNotEqual(preload["observed_at"], preload["occurred_at"])
        storage = next(row for row in exported["records"] if row["metric_kind"] == "storage_required")
        self.assertIsNone(storage["size_bytes"])
        self.assertEqual(storage["qualifier"], "up_to")


if __name__ == "__main__":
    unittest.main()
