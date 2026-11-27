"""Network-free regression tests for Buffer API-budget scheduling.

Protect scarce quota while leaving separate official breaking-news scanning
and the 07:00-23:00 Europe/Rome editorial delivery policy unchanged.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).parent / ".github" / "workflows"


def schedule_times(name):
    text = (ROOT / name).read_text(encoding="utf-8")
    crons = re.findall(r"(?m)^\s+- cron: '([^']+)'", text)
    return text, crons


class BufferApiBudgetScheduleTests(unittest.TestCase):
    def test_editorial_attempts_seven_spaced_local_slots(self):
        text, expressions = schedule_times("gta6-editorial-autopilot-v137.yml")
        self.assertEqual(len(expressions), 7)
        minutes = []
        for expression in expressions:
            fields = expression.split()
            self.assertEqual(len(fields), 5)
            self.assertEqual(fields[2:], ["*", "*", "*"])
            minutes.append(int(fields[1]) * 60 + int(fields[0]))
        self.assertEqual(minutes, sorted(minutes))
        self.assertGreaterEqual(minutes[0], 7 * 60)
        self.assertLess(minutes[-1], 23 * 60)
        self.assertGreaterEqual(min(b - a for a, b in zip(minutes, minutes[1:])), 120)
        self.assertEqual(text.count("timezone: Europe/Rome"), len(expressions))
        self.assertIn("vars.AUTO_PUBLISH == 'true'", text)

    def test_read_only_buffer_workflows_one_daily_scan_each(self):
        for name in (
            "gta6-x-permalinks-v1.yml",
            "gta6-buffer-queue-health-v1.yml",
            "gta6-bot-health-v1.yml",
        ):
            with self.subTest(name=name):
                text, expressions = schedule_times(name)
                self.assertEqual(len(expressions), 1)
                self.assertEqual(text.count("timezone: Europe/Rome"), 1)
                self.assertEqual(expressions[0].split()[2:], ["*", "*", "*"])

    def test_urgent_news_monitor_still_separate(self):
        text, expressions = schedule_times("launch-watch-v134.yml")
        self.assertGreaterEqual(len(expressions), 1)
        self.assertIn("LAUNCH_WATCH_V134_AUTOPUBLISH", text)


if __name__ == "__main__":
    unittest.main()
