"""No-network tests for read-only Buffer reauthorization diagnostics."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from buffer_publisher import BufferConfigurationError
from buffer_status_summary_v151 import check, tip_gate


class BufferStatusSummaryTests(unittest.TestCase):
    def test_single_rejected_waink_requires_manual_opt_in(self):
        state = {"entries": {"old": {
            "source": "PowerPyx Tips", "status": "rejected",
            "tip_id": "waink-vehicles-ps5"
        }}}
        self.assertEqual(tip_gate(state, False), "paused")
        self.assertEqual(tip_gate(state, True), "resumed_after_review")
        self.assertEqual(state["entries"]["old"]["status"], "rejected")

    def test_any_additional_failed_thread_blocks_automatic_resume(self):
        state = {"entries": {
            "old": {"source": "PowerPyx Tips", "status": "rejected",
                    "tip_id": "waink-vehicles-ps5"},
            "another": {"source": "PowerPyx Tips", "status": "uncertain",
                        "tip_id": "study animals"},
        }}
        self.assertEqual(tip_gate(state, True), "paused")
        self.assertEqual(tip_gate(None, True), "unknown")

    def test_verified_channel_is_read_only_and_has_no_token_in_summary(self):
        client = Mock()
        client.verify_destination.return_value = {
            "name": "xFederiko11", "isQueuePaused": True
        }
        with tempfile.TemporaryDirectory() as tmp:
            summary = str(Path(tmp) / "summary.md")
            code = check(client=client, ledger_path=Path(tmp) / "missing.json",
                         opt_in=False, summary_path=summary)
            result = Path(summary).read_text(encoding="utf-8")
        self.assertEqual(code, 0)
        self.assertIn("BUFFER_PREFLIGHT_OK", result)
        self.assertIn("QUICK_TIPS_STATUS_UNKNOWN", result)
        self.assertIn("coda in pausa", result)
        client.verify_destination.assert_called_once_with()
        self.assertEqual(client.method_calls[0][0], "verify_destination")
        self.assertEqual(len(client.method_calls), 1)

    def test_invalid_connection_fails_closed_no_mutations(self):
        client = Mock()
        client.verify_destination.side_effect = BufferConfigurationError("secret id")
        with tempfile.TemporaryDirectory() as tmp:
            summary = str(Path(tmp) / "summary.md")
            code = check(client=client, summary_path=summary)
            result = Path(summary).read_text(encoding="utf-8")
        self.assertEqual(code, 2)
        self.assertIn("BUFFER_PREFLIGHT_FAILED", result)
        self.assertNotIn("secret id", result)
        self.assertEqual(len(client.method_calls), 1)

    def test_missing_opt_in_does_not_change_environment(self):
        with patch.dict("os.environ", {"TIPS_REAUTH_CONFIRMED_V149": "false"}):
            state = {"entries": {"old": {"source": "PowerPyx Tips",
                                      "status": "rejected",
                                      "tip_id": "waink-vehicles-ps5"}}}
            self.assertEqual(tip_gate(state, False), "paused")


if __name__ == "__main__":
    unittest.main()
