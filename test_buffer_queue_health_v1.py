"""Network-free Buffer queue health audit tests."""
from datetime import datetime,timezone
from unittest.mock import Mock
import unittest
import buffer_queue_health_v1 as h

NOW=datetime(2026,11,19,20,0,tzinfo=timezone.utc)


def payload(sent=1,scheduled=2,errors=0):
    def records(state,n):
        return {"edges":[{"node":{"id":"buffer-"+str(i),
                   "status":state,
                   "dueAt":"2026-11-19T20:00:00Z",
                   "externalLink":"https://x.com/xFederiko11/status/1234567890"
                                  if state=="sent" else None}} for i in range(n)]}
    return {"sent":records("sent",sent),
            "scheduled":records("scheduled",scheduled),
            "error":records("error",errors)}


class BufferQueueAuditTests(unittest.TestCase):
    def test_graphql_query_is_read_only_and_status_specific(self):
        self.assertIn("sent:posts(",h.POST_QUERY)
        self.assertIn("scheduled:posts(",h.POST_QUERY)
        self.assertIn("error:posts(",h.POST_QUERY)
        self.assertIn("organizationId:$orgId",h.POST_QUERY)
        self.assertNotIn("mutation",h.POST_QUERY.lower())
        self.assertNotIn("createPost",h.POST_QUERY)

    def test_summary_and_report_are_about_real_buffer_state(self):
        report=h.summarize(payload(),paused=True)
        self.assertEqual(len(report["sent"]),1)
        self.assertEqual(len(report["scheduled"]),2)
        self.assertEqual(len(report["error"]),0)
        self.assertTrue(report["is_queue_paused"])
        body=h.render(report,NOW)
        self.assertIn("Sent: 1",body)
        self.assertIn("Scheduled: 2",body)
        self.assertIn("Coda sospesa: sì",body)
        self.assertIn("Apri collegamento Buffer al post su X",body)
        self.assertIn("non invia, ritenta o rischedula post",body)
        self.assertNotIn("Buffer: 0 follower",body)

    def test_numeric_account_id_is_not_misrepresented_as_verified_public_x_link(self):
        data=h.summarize(payload(),paused=False)
        data["sent"][0]["externalLink"]="https://x.com/2122776704191995904/status/2123425658265104635"
        body=h.render(data,NOW)
        self.assertIn("handle non verificabile",body)
        self.assertNotIn("[Apri collegamento Buffer al post su X]",body)
        self.assertIsNone(h.verified_account_post_link(data["sent"][0]["externalLink"]))
        self.assertIsNone(h.verified_account_post_link("https://x.com.evil.test/xFederiko11/status/1234567890"))
        self.assertIsNone(h.verified_account_post_link("https://x.com/xFederiko11/status/1234567890?redirect=yes"))
        self.assertIsNone(h.verified_account_post_link("https://x.com/@xFederiko11/status/1234567890"))
        self.assertEqual(h.verified_account_post_link(
            "https://x.com/xFederiko11/status/1234567890"),
            "https://x.com/xFederiko11/status/1234567890")

    def test_api_diagnostic_has_no_post_mutations(self):
        fake=Mock()
        fake.channel_id="real_channel_id"
        fake.verify_destination.return_value={"isQueuePaused":False}
        def graphql(query,params):
            if query == h.ORGANIZATIONS_QUERY:
                return {"account":{"organizations":[{"id":"org1"}]}}
            self.assertEqual(query,h.POST_QUERY)
            self.assertEqual(params,{"orgId":"org1","channelId":"real_channel_id"})
            return payload(sent=4,scheduled=3,errors=1)
        fake._graphql.side_effect=graphql
        data=h.snapshot(client=fake)
        self.assertEqual(data["status"],"ok")
        self.assertEqual(len(data["sent"]),4)
        self.assertEqual(len(data["scheduled"]),3)
        self.assertEqual(len(data["error"]),1)
        fake.verify_destination.assert_called_once()
        self.assertEqual(fake._graphql.call_count,2)

    def test_fail_closed_on_ambiguous_org_or_graphql_error(self):
        fake=Mock()
        fake.channel_id="real_channel_id"
        fake.verify_destination.return_value={}
        fake._graphql.return_value={"account":{"organizations":[]}}
        self.assertEqual(h.snapshot(client=fake)["status"],"unavailable")
        fake._graphql.return_value={"account":{"organizations":[{"id":"1"},{"id":"2"}]}}
        self.assertEqual(h.snapshot(client=fake)["status"],"unavailable")
        for bad in ({"sent":{"edges":[]}},{"sent":{"edges":[{"node":{"status":"wrong"}}]},
                   "scheduled":{"edges":[]},"error":{"edges":[]}}):
            with self.assertRaises(ValueError):
                h.summarize(bad)
        self.assertIn("Dati Buffer non disponibili",h.render(
            {"status":"unavailable","reason":"BufferConfigurationError"},NOW))

if __name__=="__main__":
    unittest.main()
