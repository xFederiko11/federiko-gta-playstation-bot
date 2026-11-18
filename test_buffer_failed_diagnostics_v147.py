"""Network-free tests for safe read-only diagnosis and fail-closed tip queue."""
import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from buffer_failed_diagnostics_v147 import category,summary
from quick_tips_v146 import candidate

class RejectedThreadTests(unittest.TestCase):
    def test_error_is_sanitized(self):
        row=summary({"id":"post123","status":"error",
                     "error":{"message":"Failed to fetch image at https://private.example/token123"}})
        self.assertEqual(row["category"],"media")
        self.assertNotIn("private.example",row["error_short"])
        self.assertEqual(row["status"],"error")

    def test_categories(self):
        self.assertEqual(category("Thread replies are not supported"),"thread")
        self.assertEqual(category("Exceeded posting quota"),"limit")
        self.assertEqual(category(""),"not_reported")

    def test_rejected_first_thread_pauses_future_tips_without_writing(self):
        state={"entries":{"x":{"source":"PowerPyx Tips","status":"rejected",
              "reserved_utc":"2026-11-18T21:06:20+00:00"}}}
        self.assertIsNone(candidate(state,datetime(2026,11,19,12,tzinfo=timezone.utc)))
        self.assertEqual(state["entries"]["x"]["status"],"rejected")
if __name__=="__main__":
    unittest.main()
