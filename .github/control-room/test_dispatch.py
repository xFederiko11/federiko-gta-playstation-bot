import unittest
from datetime import datetime, timedelta, timezone
from dispatch import plan, parse_request, TARGETS

NOW = datetime(2026, 11, 28, 16, 0, tzinfo=timezone.utc)

def req(action="grafica", minutes=0):
    return {"action": action, "requested_at": (NOW + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")}

class SafeDispatchTests(unittest.TestCase):
    def plan(self, action="grafica", minutes=0, previous=None, latest=None, runs=None):
        current = req(action, minutes)
        return plan(current, previous or req("idle", -120), latest or current, runs or [], NOW)

    def test_exact_allowlist(self):
        self.assertEqual(set(TARGETS), {"grafica", "community", "pubblicazione", "sito"})
        self.assertEqual(self.plan("grafica")[0], ("gta6-photo-review-inbox-v1.yml", {"mode": "preview"}))
        self.assertEqual(self.plan("community")[0], ("gta6-x-verified-social-radar-v1.yml", {"action": "preview"}))
        self.assertEqual(self.plan("pubblicazione")[0], ("gta6-editorial-autopilot-v137.yml", {"action": "preview"}))
        self.assertEqual(self.plan("sito")[0], ("site-editorial-integration-v1.yml", {}))

    def test_idle(self):
        self.assertIsNone(self.plan("idle")[0])

    def test_unknown_command(self):
        for action in ("run", "schedule", "../other.yml", "publish", None):
            with self.assertRaises(ValueError):
                self.plan(action)

    def test_extra_input_rejected(self):
        with self.assertRaises(ValueError):
            parse_request({**req(), "inputs": {"action": "run"}})

    def test_timestamp_requires_utc(self):
        with self.assertRaises(ValueError):
            parse_request({"action": "sito", "requested_at": "2026-11-28T16:00:00+01:00"})

    def test_stale_request(self):
        self.assertIsNone(self.plan(minutes=-31)[0])

    def test_future_request(self):
        self.assertIsNone(self.plan(minutes=3)[0])

    def test_replay(self):
        self.assertIsNone(self.plan(previous=req("community"))[0])
        self.assertIsNone(self.plan(previous=req("community", 1))[0])

    def test_superseded(self):
        self.assertIsNone(self.plan(latest=req("community", 1))[0])

    def test_active(self):
        self.assertIsNone(self.plan(runs=[{"status": "in_progress"}])[0])

    def test_recent(self):
        for event in ("schedule", "workflow_dispatch"):
            run = {"status": "completed", "event": event, "created_at": req(minutes=-59)["requested_at"]}
            self.assertIsNone(self.plan(runs=[run])[0])

    def test_old_run_and_qa_not_blocking(self):
        runs = [{"status": "completed", "event": "schedule", "created_at": req(minutes=-61)["requested_at"]},
                {"status": "completed", "event": "push", "created_at": req(minutes=-1)["requested_at"]}]
        self.assertIsNotNone(self.plan(runs=runs)[0])

if __name__ == "__main__":
    unittest.main()
