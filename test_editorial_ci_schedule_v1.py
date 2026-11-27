from pathlib import Path
import unittest
class EditorialCIScheduleTests(unittest.TestCase):
    def test_push_and_pr_are_qa_only_and_night_slots_bounded(self):
        raw=Path(".github/workflows/gta6-editorial-autopilot-v137.yml").read_text(encoding="utf-8")
        self.assertNotIn("workflow_run:",raw)
        self.assertIn("10,40 5-21 * * *",raw)
        self.assertIn("25,55 7-19 19-30 11 *",raw)
        qa,production=raw.split("\n  editorial:\n",1)
        self.assertIn("if: github.event_name == 'pull_request' || github.event_name == 'push'",qa)
        self.assertNotIn("BUFFER_API_KEY",qa)
        self.assertNotIn("github.event_name == 'push'",production)
        self.assertIn("gta-v142-publication-global",raw)
        self.assertIn("cancel-in-progress: false",raw)
        self.assertNotIn("GTA6_REQUIRE_ALL_POST_PHOTOS: 'true'",production)
if __name__=="__main__":unittest.main()
