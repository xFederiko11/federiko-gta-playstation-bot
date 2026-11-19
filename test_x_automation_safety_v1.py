"""Offline regression checks for the read-only cross-workflow X safety audit."""
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from x_automation_safety_v1 import audit,POSTING,ORGANIC

ROOT=Path(__file__).resolve().parent


class XSustainablePublishingTests(unittest.TestCase):
    def stage(self,directory):
        base=Path(directory)
        for path in (*POSTING,ORGANIC,"x_community_review_v1.py","editorial_director_v142.py"):
            (base/path).parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/path,base/path)
        return base

    def test_all_current_buffer_workflows_serialized_and_limited(self):
        result=audit(ROOT)
        self.assertEqual(len(result["publisher_workflows_audited"]),4)
        self.assertEqual(result["errors"],[])
        self.assertTrue(result["posting_workflows_have_guards"])
        self.assertTrue(result["conversation_workflow_manual_only"])
        self.assertEqual(result["scope"],"static_GitHub_workflow_audit_only_not_X_account_assessment")

    def test_missing_global_gate_fails_closed(self):
        with TemporaryDirectory() as d:
            root=self.stage(d)
            path=root/POSTING[0]
            text=path.read_text(encoding="utf-8")
            self.assertIn("EDITORIAL_DIRECTOR_V142_ENABLED: 'true'",text)
            path.write_text(text.replace("EDITORIAL_DIRECTOR_V142_ENABLED: 'true'",
                                         "EDITORIAL_DIRECTOR_V142_ENABLED: 'false'"),encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError,"director safety switch"):
                audit(root)

    def test_breaking_global_concurrency_fails(self):
        with TemporaryDirectory() as d:
            root=self.stage(d)
            path=root/POSTING[1]
            text=path.read_text(encoding="utf-8").replace("gta-v142-publication-global","uncontrolled-publish")
            path.write_text(text,encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError,"serialized X publication"):
                audit(root)

    def test_manual_workflow_cannot_gain_buffer_credentials(self):
        with TemporaryDirectory() as d:
            root=self.stage(d)
            path=root/ORGANIC
            path.write_text(path.read_text(encoding="utf-8")+"\n# BUFFER_API_KEY\n",encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError,"publishing capability"):
                audit(root)

    def test_scout_cannot_gain_network_mutations(self):
        with TemporaryDirectory() as d:
            root=self.stage(d)
            path=root/"x_community_review_v1.py"
            path.write_text(path.read_text(encoding="utf-8")+"\n# requests.post(\n",encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError,"must not access or mutate"):
                audit(root)

    def test_budget_cannot_be_loosened_without_review(self):
        with TemporaryDirectory() as d:
            root=self.stage(d)
            path=root/"editorial_director_v142.py"
            path.write_text(path.read_text(encoding="utf-8").replace(
                "MAX_AUTOMATED_DELIVERIES_24H=8",
                "MAX_AUTOMATED_DELIVERIES_24H=100"),encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError,"Global publication limit"):
                audit(root)
    def test_boost_expiration_is_a_required_safety_rule(self):
        with TemporaryDirectory() as d:
            root=self.stage(d)
            path=root/"editorial_director_v142.py"
            path.write_text(path.read_text(encoding="utf-8").replace(
                "BOOST_UNTIL=datetime(2026,11,30",
                "BOOST_UNTIL=datetime(2027,11,30"),encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError,"boost expiration"):
                audit(root)



if __name__=="__main__":
    unittest.main()
