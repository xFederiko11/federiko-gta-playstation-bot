"""Network-free tests of scheduled GTA VI bot workflow/Buffer health check."""
from datetime import datetime, timedelta, timezone
import unittest
import json
import requests
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from bot_health_v1 import summarize_runs, buffer_health, assess, REQUIRED

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)

def run(name, minutes_ago, conclusion="success", event="schedule"):
    at=(NOW - timedelta(minutes=minutes_ago)).isoformat()
    return {"name":name,"event":event,"status":"completed","conclusion":conclusion,
            "created_at":at,"html_url":"https://github.com/xFederiko11/federiko-gta-playstation-bot/actions/runs/12"}

class BotHealthTests(unittest.TestCase):
    def test_all_workflows_healthy_and_connected(self):
        rows=[run(x,60) for x in REQUIRED]
        check=assess(rows,"BUFFER_PREFLIGHT_OK account=@xFederiko11\nQUICK_TIPS_READY",0,NOW)
        self.assertEqual(check["overall"],"healthy")
        self.assertEqual(len(check["workflows"]),5)

    def test_failed_recent_workflow_overrides_past_success(self):
        rows=[run(x,60) for x in REQUIRED]
        rows += [run(REQUIRED[0],10,"failure")]
        check=assess(rows,"BUFFER_PREFLIGHT_OK\nQUICK_TIPS_READY",0,NOW)
        self.assertEqual(check["overall"],"degraded")
        self.assertEqual(check["workflows"][0]["conclusion"],"failure")

    def test_missing_stale_and_pr_runs_are_not_false_successes(self):
        rows=[run(REQUIRED[0],1,event="pull_request"),run(REQUIRED[0],48*60)]
        check=summarize_runs(rows,NOW)
        self.assertEqual(check[0]["health"],"stale")
        self.assertTrue(any(x["health"]=="unknown" for x in check[1:]))

    def test_inactive_site_with_last_successful_deploy_is_not_stale(self):
        rows=[run(x,60) for x in REQUIRED[:-1]]
        rows.append(run("GTA 6 Italia - Website", 14*24*60, event="push"))
        result=assess(rows,"BUFFER_PREFLIGHT_OK\nQUICK_TIPS_READY",0,NOW)
        self.assertEqual(result["overall"],"healthy")

    def test_buffer_read_only_status_never_claims_delivery(self):
        self.assertEqual(buffer_health("BUFFER_PREFLIGHT_OK\nQUICK_TIPS_PAUSED",0)["status"],"degraded")
        self.assertEqual(buffer_health("BUFFER_PREFLIGHT_FAILED",2)["status"],"degraded")
        self.assertEqual(buffer_health("",0)["status"],"unknown")
        self.assertEqual(buffer_health("BUFFER_PREFLIGHT_OK\nQUICK_TIPS_STATUS_UNKNOWN",0)["status"],"unknown")


    def test_github_api_outage_generates_persistent_health_report(self):
        from bot_health_v1 import main
        with tempfile.TemporaryDirectory() as root:
            d=Path(root)
            (d/"buffer.log").write_text("BUFFER_PREFLIGHT_OK\nQUICK_TIPS_READY",encoding="utf-8")
            (d/"buffer.exit").write_text("0",encoding="utf-8")
            report=d/"health.json"
            note=d/"health.md"
            args=["bot_health_v1.py","--buffer-log",str(d/"buffer.log"),
                  "--buffer-exit",str(d/"buffer.exit"),
                  "--output",str(report),"--issue-output",str(note)]
            with patch("sys.argv",args), patch("bot_health_v1.fetch_runs",
                                                side_effect=requests.ConnectionError("offline")):
                with self.assertRaises(SystemExit) as exit_status:
                    main()
            self.assertEqual(exit_status.exception.code,2)
            result=json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(result["overall"],"degraded")
            self.assertEqual(result["api_error"],"github_runs_api_ConnectionError")
            self.assertIn("GitHub API",note.read_text(encoding="utf-8"))

    def test_timezone_required(self):
        with self.assertRaises(ValueError):
            assess([],"BUFFER_PREFLIGHT_OK",0,datetime(2026,11,19,12))

if __name__=="__main__":
    unittest.main()
