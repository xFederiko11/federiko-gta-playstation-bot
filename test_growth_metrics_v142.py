"""Verify that X engagement numbers are never fabricated from Buffer receipts."""
from pathlib import Path
import json
import tempfile
import unittest
import growth_metrics_v142 as m

class GrowthMetricTests(unittest.TestCase):
    def test_no_external_metrics_are_claimed_from_buffer_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"editorial-autopilot-v137.json").write_text(json.dumps({"entries":{
                "p":{"reserved_utc":"2026-11-18T12:00:00+00:00","status":"sent"}}}))
            summary=m.report(root,manual_path=root/"not-there.csv")
            self.assertEqual(summary["delivery_reservations"],1)
            self.assertFalse(summary["actual_x_metrics_available"])
            self.assertEqual(summary["x_metrics"],[])
            self.assertEqual(summary["by_status"]["sent"],1)
            self.assertIn("NOT X reach",summary["warning"])

    def test_manual_metrics_are_only_loaded_from_specific_x_urls(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            template=root/"x.csv"
            template.write_text("post_url,date,impressions,likes,reposts,replies,profile_visits,new_followers\n"
                                "https://x.com/example/status/123,2026-11-18,120,4,1,2,8,0\n"
                                "https://invalid.example/a,2026-11-18,999,999,,,,\n",encoding="utf-8")
            summary=m.report(root,manual_path=template)
            self.assertTrue(summary["actual_x_metrics_available"])
            self.assertEqual(len(summary["x_metrics"]),1)
            self.assertEqual(summary["x_metrics"][0]["impressions"],120)

if __name__=='__main__':
    unittest.main()
