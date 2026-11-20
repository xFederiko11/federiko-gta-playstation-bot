"""Network-free tests for historical diagnostics and fail-closed tip selection."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from buffer_failed_diagnostics_v147 import QUERY, category, inspect, summary
from buffer_publisher import BufferAPIError, BufferConfigurationError
from quick_tips_v146 import candidate


class RejectedThreadTests(unittest.TestCase):
    def test_error_is_sanitized(self):
        row = summary({"id": "post123", "status": "error",
                       "error": {"message": "Failed to fetch image at https://private.example/token123"}})
        self.assertEqual(row["category"], "media")
        self.assertNotIn("private.example", row["error_short"])
        self.assertEqual(row["status"], "error")

    def test_categories(self):
        self.assertEqual(category("Thread replies are not supported"), "thread")
        self.assertEqual(category("Exceeded posting quota"), "limit")
        self.assertEqual(category(""), "not_reported")

    def test_rejected_first_thread_pauses_future_tips_without_writing(self):
        state = {"entries": {"x": {"source": "PowerPyx Tips", "status": "rejected",
                 "reserved_utc": "2026-11-18T21:06:20+00:00"}}}
        self.assertIsNone(candidate(state, datetime(2026, 11, 19, 12, tzinfo=timezone.utc)))
        self.assertEqual(state["entries"]["x"]["status"], "rejected")

    def run_lookup(self, client, *, state=None, text=None):
        if state is None:
            state = {"entries": {"x": {"source": "PowerPyx Tips", "status": "rejected",
                     "buffer_id": "old-post", "reserved_utc": "2026-11-18T21:06:20+00:00"}}}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'ledger.json'
            original = text if text is not None else json.dumps(state)
            path.write_text(original, encoding='utf-8')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = inspect(client=client, ledger_path=path)
            self.assertEqual(path.read_text(encoding='utf-8'), original)
        client.publish.assert_not_called()
        client.publish_thread.assert_not_called()
        self.assertTrue(result['current_channel_preflight_required'])
        self.assertEqual(result['mode'], 'read_only_no_retry')
        return result, output.getvalue()

    def test_missing_old_record_is_advisory_and_never_retried(self):
        client = Mock()
        client._graphql.side_effect = BufferAPIError('private-server-message')
        result, output = self.run_lookup(client)
        self.assertEqual(result['outcome'], 'historical_diagnostic_unavailable')
        self.assertEqual(result['reason'], 'BufferAPIError')
        self.assertNotIn('private-server-message', output)
        client._graphql.assert_called_once_with(QUERY, {'id': 'old-post'})

    def test_null_wrong_or_malformed_post_never_claims_success(self):
        for post in (None, {}, {'id': 'wrong'}, {'id': 'old-post', 'error': 'invalid'}):
            with self.subTest(post=post):
                client = Mock()
                client._graphql.return_value = {'post': post}
                result, _ = self.run_lookup(client)
                self.assertEqual(result['outcome'], 'historical_diagnostic_unavailable')
                client._graphql.assert_called_once()

    def test_real_historical_record_stays_separate_from_current_health(self):
        client = Mock()
        client._graphql.return_value = {'post': {'id': 'old-post', 'status': 'error',
                                               'error': {'message': 'Thread failed'}}}
        result, _ = self.run_lookup(client)
        self.assertEqual(result['outcome'], 'historical_record_available')
        self.assertEqual(result['detail']['category'], 'thread')
        self.assertEqual(result['scope'], 'historical_rejected_thread_only')

    def test_unavailable_destination_does_not_query_old_post(self):
        client = Mock()
        client.verify_destination.side_effect = BufferConfigurationError('secret-value')
        result, output = self.run_lookup(client)
        self.assertEqual(result['outcome'], 'historical_diagnostic_unavailable')
        self.assertNotIn('secret-value', output)
        client._graphql.assert_not_called()

    def test_unreadable_ledger_never_calls_buffer_or_rewrites_history(self):
        for text in ('broken-json', '[]', '{"entries": []}'):
            client = Mock()
            result, _ = self.run_lookup(client, text=text)
            self.assertEqual(result['outcome'], 'historical_diagnostic_unavailable')
            client.verify_destination.assert_not_called()
            client._graphql.assert_not_called()

    def test_empty_ledger_does_not_access_buffer(self):
        client = Mock()
        result, _ = self.run_lookup(client, state={'entries': {}})
        self.assertEqual(result['outcome'], 'no_failed_tips')
        client.verify_destination.assert_not_called()
        client._graphql.assert_not_called()
        self.assertNotIn('mutation', QUERY.lower())


if __name__ == '__main__':
    unittest.main()
