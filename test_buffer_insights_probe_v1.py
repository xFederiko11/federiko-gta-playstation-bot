"""Offline regressions for the optional read-only Buffer performance probe."""
import unittest
from datetime import datetime,timezone
from unittest.mock import Mock
import buffer_insights_probe_v1 as p

NOW=datetime(2026,11,20,16,0,tzinfo=timezone.utc)
CH="buffer-twitter-channel"
def payload(metrics=None,updated="2026-11-20T15:01:00Z",n=1):
    if metrics is None:
        metrics=[{"type":"reactions","value":14,"unit":"count"},
                 {"type":"impressions","value":220,"unit":"count"},
                 {"type":"comments","value":2,"unit":"count"}]
    return {"posts":{"edges":[{"node":{
        "id":"bufferid000123456", "status":"sent",
        "channelId":CH, "metricsUpdatedAt":updated,
        "metrics":metrics}} for i in range(n)]}}

class BufferMetricsTests(unittest.TestCase):
    def test_only_really_reported_metrics_count(self):
        result=p.parse(payload(),CH)
        self.assertEqual(result["status"],"available")
        self.assertEqual(result["sampled_posts"],1)
        self.assertEqual(result["totals_reported_subset"]["reactions"],14)
        self.assertEqual(result["totals_reported_subset"]["impressions"],220)
        self.assertNotIn("clicks",result["totals_reported_subset"])
        body=p.markdown(result,NOW)
        self.assertIn("Impression (Buffer): 220",body)
        self.assertNotIn("Follower: 220",body)
        self.assertIn("metriche mancanti NON valgono zero",body)
    def test_missing_metrics_does_not_become_zero(self):
        no=payload()
        no["posts"]["edges"][0]["node"]["metrics"]=None
        no["posts"]["edges"][0]["node"]["metricsUpdatedAt"]=None
        result=p.parse(no,CH)
        self.assertEqual(result["status"],"not_reported")
        self.assertEqual(result["totals_reported_subset"],{})
        self.assertIn("non disponibili",p.markdown(result,NOW))
    def test_spoofing_or_invalid_values_fail_closed(self):
        invalid=[
            {"channelId":"other-channel"},
            {"status":"scheduled"},
            {"metrics":[{"type":"impressions","value":float("inf"),"unit":"count"}]},
            {"metrics":[{"type":"impressions","value":-1,"unit":"count"}]},
            {"metrics":[{"type":"impressions","value":3.14,"unit":"count"}]},
            {"metrics":[{"type":"reactions","value":1,"unit":"count"},
                        {"type":"reactions","value":2,"unit":"count"}]},
            {"metricsUpdatedAt":"2030-01-01T00:00:00Z"},
        ]
        for patch in invalid:
            data=payload()
            data["posts"]["edges"][0]["node"].update(patch)
            with self.subTest(patch=patch):
                with self.assertRaises(ValueError):p.parse(data,CH)
    def test_whitelist_excludes_follower_attribution(self):
        d=payload([{"type":"follows","value":10000,"unit":"count"},
                   {"type":"reactions","value":3,"unit":"count"}])
        result=p.parse(d,CH)
        self.assertEqual(result["totals_reported_subset"],{"reactions":3})
        self.assertNotIn("10000",p.markdown(result,NOW))
    def test_nonblocking_when_metrics_scope_unavailable(self):
        client=Mock()
        client.channel_id=CH
        client.verify_destination.return_value={"service":"twitter"}
        client.list_channels.return_value=[{"id":CH,"service":"twitter",
                                            "organization_id":"owned-org"}]
        def graphql(query,vars):
            self.assertEqual(query,p.POST_METRICS)
            self.assertEqual(vars,{"orgId":"owned-org","channelId":CH})
            raise p.BufferAPIError("scope unavailable")
        client._graphql.side_effect=graphql
        result=p.snapshot(client=client)
        self.assertEqual(result["status"],"unavailable")
        self.assertEqual(result["reason"],"BufferAPIError")
        self.assertIn("non disponibili",p.markdown(result,NOW))
        self.assertIn("posts(first:10",p.POST_METRICS)
        self.assertNotIn("mutation",p.POST_METRICS.lower())
        self.assertNotIn("createPost",p.POST_METRICS)
    def test_successful_verified_destination_and_read_only_query(self):
        client=Mock()
        client.channel_id=CH
        client.verify_destination.return_value={"service":"twitter"}
        client.list_channels.return_value=[{"id":CH,"service":"twitter",
                                            "organization_id":"owned-org"}]
        client._graphql.return_value=payload()
        result=p.snapshot(client=client)
        self.assertEqual(result["status"],"available")
        client.verify_destination.assert_called_once()
        client.list_channels.assert_called_once()
        client._graphql.assert_called_once()
    def test_invalid_channel_does_not_call_insights(self):
        client=Mock()
        client.channel_id=CH
        client.verify_destination.return_value={"service":"facebook"}
        result=p.snapshot(client=client)
        self.assertEqual(result["status"],"unavailable")
        client._graphql.assert_not_called()

if __name__=="__main__":
    unittest.main()
