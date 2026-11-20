"""Offline tests; no real Buffer or X operations."""
import copy
import os
import unittest
from unittest.mock import Mock, patch
from buffer_delivery_receipts_v1 import QUERY, collect, receipt, safe_x_url, safe_message


class ReceiptTests(unittest.TestCase):
    def post(self, **changes):
        return dict({'id': 'post-1', 'channelId': 'channel-1', 'channelService': 'twitter',
                     'status': 'sent', 'sentAt': '2026-11-20T01:00:00Z',
                     'externalLink': 'https://x.com/xFederiko11/status/1234567890123456789',
                     'error': None}, **changes)

    def test_complete_receipt_is_not_independent_x_verification(self):
        result = receipt(self.post(), channel_id='channel-1', post_id='post-1')
        self.assertEqual(result['outcome'], 'sent_receipt')
        self.assertFalse(result['public_x_independently_checked'])

    def test_no_false_success_for_pending_failed_or_missing_receipt(self):
        for status, outcome in [('sending', 'pending'), ('error', 'failed'), ('draft', 'pending')]:
            with self.subTest(status=status):
                result = receipt(self.post(status=status), channel_id='channel-1', post_id='post-1')
                self.assertEqual(result['outcome'], outcome)
        for changes in ({'externalLink': None}, {'sentAt': None}, {'sentAt': '2026-11-20T01:00:00'}):
            self.assertEqual(receipt(self.post(**changes), channel_id='channel-1', post_id='post-1')['outcome'], 'sent_incomplete_receipt')

    def test_wrong_destination_and_identity_fail_closed(self):
        for changes in ({'id': 'wrong'}, {'channelId': 'wrong'}, {'channelId': None}, {'channelService': 'facebook'}):
            with self.assertRaises(ValueError):
                receipt(self.post(**changes), channel_id='channel-1', post_id='post-1')

    def test_links_accept_numeric_service_ids_but_not_other_handles(self):
        self.assertIsNotNone(safe_x_url('https://twitter.com/1234567890/status/1234567890123456789'))
        self.assertIsNotNone(safe_x_url('https://x.com/i/web/status/1234567890123456789'))
        for url in ('http://x.com/xFederiko11/status/12345678',
                    'https://x.com.evil.test/xFederiko11/status/12345678',
                    'https://user@x.com/xFederiko11/status/12345678',
                    'https://x.com/OtherUser/status/12345678',
                    'https://x.com/xFederiko11/status/12345678?token=secret',
                    'https://x.com:444/xFederiko11/status/12345678'):
            self.assertIsNone(safe_x_url(url))

    def test_current_run_single_read_no_mutation_and_ledger_unchanged(self):
        client = Mock(channel_id='channel-1')
        client._graphql.return_value = {'post': self.post()}
        state = {'entries': {'one': {'run_id': '42', 'buffer_id': 'post-1', 'title': 'Guida'}}}
        before = copy.deepcopy(state)
        result = collect(state, run_id='42', client=client)
        self.assertTrue(result['current_run_attempted'])
        client._graphql.assert_called_once_with(QUERY, {'id': 'post-1'})
        client.publish.assert_not_called()
        self.assertEqual(state, before)
        self.assertNotIn('mutation', QUERY.lower())

    def test_historical_receipt_never_claimed_as_current_post(self):
        client = Mock(channel_id='channel-1')
        client._graphql.return_value = {'post': self.post()}
        result = collect({'entries': {'one': {'run_id': '41', 'buffer_id': 'post-1'}}}, run_id='42', client=client)
        self.assertFalse(result['current_run_attempted'])
        self.assertFalse(result['receipts'][0]['current_run'])

    def test_unknown_submission_never_retried(self):
        client = Mock(channel_id='channel-1')
        result = collect({'entries': {'one': {'run_id': '42', 'status': 'uncertain'}}}, run_id='42', client=client)
        self.assertEqual(result['receipts'][0]['outcome'], 'no_receipt')
        client._graphql.assert_not_called()
        client.publish.assert_not_called()

    def test_errors_redact_credentials(self):
        with patch.dict(os.environ, {'BUFFER_API_KEY': 'my-secret-token'}):
            self.assertNotIn('my-secret-token', safe_message('Problem my-secret-token'))
            self.assertNotIn('hidden-value', safe_message('Bearer hidden-value'))


if __name__ == '__main__':
    unittest.main()
