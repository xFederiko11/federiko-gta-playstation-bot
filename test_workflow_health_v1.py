"""Network-free checks for autonomous bot, Buffer ledger and Pages watchdog."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from workflow_health_v1 import CHECKS, check_one, check_buffer_ledger, markdown, HEALTH_MARKER

NOW=datetime(2026,11,19,9,0,tzinfo=timezone.utc)


def run(*,hours=1,conclusion="success",event="schedule"):
    return {"event":event,"status":"completed","conclusion":conclusion,
            "created_at":(NOW-timedelta(hours=hours)).isoformat(),
            "html_url":"https://github.com/example/actions/runs/123"}


class HealthTests(unittest.TestCase):
    def test_monitoring_targets_are_exact_production_repos(self):
        self.assertEqual(len(CHECKS),4)
        self.assertEqual({x["repo"] for x in CHECKS},
                         {"xFederiko11/gta-6","xFederiko11/federiko-gta-playstation-bot"})
        self.assertTrue(all(x["file"].endswith(".yml") for x in CHECKS))

    def test_recent_success_and_failures(self):
        c=CHECKS[0]
        self.assertEqual(check_one(c,[run()],NOW)["status"],"ok")
        self.assertEqual(check_one(c,[run(conclusion="failure")],NOW)["status"],"attention")
        self.assertEqual(check_one(c,[run(hours=40)],NOW)["status"],"attention")
        self.assertEqual(check_one(c,[],NOW)["status"],"attention")
        self.assertEqual(check_one(c,[run(event="pull_request")],NOW)["status"],"attention")
        self.assertEqual(check_one(c,[run(hours=1),run(hours=2,conclusion="failure")],NOW)["status"],"ok")

    def test_buffer_state_is_read_only_and_age_limited(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"editorial.json"
            p.write_text(json.dumps({"entries":{
               "old":{"status":"rejected","reserved_utc":(NOW-timedelta(hours=9)).isoformat()},
               "new":{"status":"rejected","completed_utc":(NOW-timedelta(hours=1)).isoformat()},
               "sent":{"status":"sent","completed_utc":NOW.isoformat()}
            }}),encoding="utf-8")
            self.assertEqual(check_buffer_ledger(p,NOW)["status"],"attention")
            self.assertIn("1 esiti",check_buffer_ledger(p,NOW)["reason"])
            self.assertEqual(check_buffer_ledger(p,NOW+timedelta(hours=9))["status"],"ok")
            self.assertTrue(p.exists())
            with self.assertRaises(ValueError):
                p.write_text('{"entries":[]}');check_buffer_ledger(p,NOW)

    def test_health_issue_is_only_an_alert_not_a_retry(self):
        report={"schema":"gta6-health-v1","checked_utc":NOW.isoformat(),
                "systems":[{"name":"Test","status":"attention",
                            "reason":"Nessun nuovo messaggio","url":""}]}
        text=markdown(report)
        self.assertIn(HEALTH_MARKER,text)
        self.assertIn("ATTENZIONE",text)
        self.assertIn("non ritentano invii",text)
        self.assertNotIn("BUFFER_API_KEY",text)
        with self.assertRaises(ValueError):markdown({"schema":"unknown"})


if __name__=="__main__":
    unittest.main()
