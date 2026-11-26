import unittest
from actions_runtime_sample_v1 import measure,seconds,MAX_RUNS
class RuntimeTests(unittest.TestCase):
    def test_job_not_workflow_elapsed_and_rounded_minutes(self):
        runs=[{"id":1,"name":"Monitor","status":"completed","event":"schedule"},
              {"id":2,"name":"Push","status":"completed","event":"push"}]
        rows=[{"conclusion":"success","started_at":"2026-11-26T12:00:00Z","completed_at":"2026-11-26T12:01:57Z"},
              {"conclusion":"failure","started_at":"2026-11-26T12:02:00Z","completed_at":"2026-11-26T12:02:06Z"},
              {"conclusion":"skipped"},{"conclusion":"cancelled"}]
        result=measure(runs,lambda i:rows)
        self.assertEqual((result["runs"],result["jobs"],result["seconds"],result["rounded_minutes_model"],result["missing_job_times"]),(1,2,123,3,1))
    def test_invalid_duration_fails(self):
        with self.assertRaises(ValueError):seconds({"started_at":"2026-11-26T12:01:00Z","completed_at":"2026-11-26T12:00:00Z"})
if __name__=="__main__":unittest.main()
