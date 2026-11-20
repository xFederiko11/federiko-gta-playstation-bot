"""Offline validation for real Buffer X permalinks. No API calls or post mutations."""
from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json,unittest
from x_permalink_bridge_v1 import (real_x_permalink,clean_article,parse_sent,
                                   ledger_map,records,merge,collect,SCHEMA)
NOW=datetime(2026,11,20,10,0,tzinfo=timezone.utc)
ARTICLE="https://xfederiko11.github.io/gta-6/guide-e-tutorial/studiare-animali/"
X="https://x.com/xFederiko11/status/2123588882885186002"
class FakeBuffer:
    channel_id="chan123"
    def __init__(self):self.queries=[]
    def verify_destination(self):return {"id":"chan123","service":"twitter"}
    def list_channels(self):return [{"id":"chan123","service":"twitter","organization_id":"orgA"}]
    def _graphql(self,q,v):
        self.queries.append(v)
        return {"posts":{"edges":[{"node":{
            "id":"buf1234567890abc","channelId":"chan123","channelService":"twitter",
            "status":"sent","sentAt":"2026-11-20T09:40:00Z",
            "externalLink":"https://twitter.com/xFederiko11/status/2123588882885186002",
            "text":"Studiare animali 100% rapido: usa il binocolo per osservare."}}],
            "pageInfo":{"hasNextPage":False,"endCursor":"xyz"}}}
class PermalinkTests(unittest.TestCase):
    def test_reject_ambiguous_and_fabricated_x_url(self):
        self.assertEqual(real_x_permalink("https://twitter.com/xFederiko11/status/2123588882885186002"),X)
        for url in ("https://x.com.evil.example/xFederiko11/status/2123588882885186002",
                    "http://x.com/xFederiko11/status/2123588882885186002",
                    "https://x.com/Fake/status/2123588882885186002",
                    "https://x.com/xFederiko11/status/6afdb98d7a1c17d8bbd36da1",
                    "https://x.com/xFederiko11/status/2123588882885186002?tracking=1"):
            self.assertIsNone(real_x_permalink(url))
        self.assertIsNone(clean_article("https://evil.test/gta-6/"))
    def test_only_sent_exact_channel_exact_first_post(self):
        ledger=ledger_map({"entries":{"one":{"status":"sent","url":ARTICLE,
                 "buffer_id":"buf1234567890abc",
                 "text":"Studiare animali 100% rapido: usa il binocolo per osservare."}}})
        client=FakeBuffer()
        result=collect({"entries":{"one":{"status":"sent","url":ARTICLE,
                 "buffer_id":"buf1234567890abc",
                 "text":"Studiare animali 100% rapido: usa il binocolo per osservare."}}},client=client,now=NOW)
        self.assertEqual(result["posts"][0]["article_url"],ARTICLE)
        self.assertEqual(result["posts"][0]["x_url"],X)
        self.assertEqual(result["matched_this_run"],1)
        self.assertEqual(len(client.queries),1)
        node=client._graphql(None,None)["posts"]["edges"][0]["node"]
        self.assertEqual(records([{**node,"channelId":"other"}],ledger,"chan123",now=NOW),[])
        self.assertEqual(records([{**node,"status":"scheduled"}],ledger,"chan123",now=NOW),[])
        self.assertEqual(records([{**node,"text":"Something completely different"}],ledger,"chan123",now=NOW),[])
        self.assertEqual(records([{**node,"externalLink":None}],ledger,"chan123",now=NOW),[])
    def test_preserve_previous_deduplicate_and_order(self):
        older={"article_url":ARTICLE,"x_url":X,"sent_at":"2026-11-19T09:40:00Z",
               "buffer_id":"older","excerpt":"Previous"}
        self.assertEqual(len(merge([older,older],[],now=NOW)),1)
        self.assertEqual(merge([older],[],now=NOW)[0]["x_url"],X)
        self.assertIsNone(parse_sent("no date",NOW))
        self.assertIsNone(parse_sent("2031-01-01T00:00:00Z",NOW))
    def test_no_private_token_or_fake_engagement_in_schema(self):
        client=FakeBuffer()
        state={"entries":{"one":{"status":"sent","url":ARTICLE,"buffer_id":"buf1234567890abc",
                                  "text":"Studiare animali 100% rapido: usa il binocolo per osservare."}}}
        rendered=json.dumps(collect(state,client=client,now=NOW))
        self.assertNotIn("BUFFER_API_KEY",rendered)
        self.assertNotIn("likes",rendered)
        self.assertNotIn("impressions",rendered)
        self.assertIn(SCHEMA,rendered)
if __name__=="__main__":unittest.main()
