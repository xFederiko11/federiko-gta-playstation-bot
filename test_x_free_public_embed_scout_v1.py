"""Offline free, source-limited RSS -> official X oEmbed test suite."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse,parse_qs
import json
import unittest
import x_free_public_embed_scout_v1 as scout

NOW=datetime(2026,11,19,21,0,tzinfo=timezone.utc)

def snowflake(when):
    ms=int(when.timestamp()*1000)
    return str((ms-scout.TWITTER_EPOCH_MS)<<22)

POST_ID=snowflake(NOW-timedelta(hours=1))
URL="https://x.com/GTAHelper/status/"+POST_ID
TEXT="GTA VI PS5 trophy and platinum requirements are tricky: which optional missions matter for a clean completionist run?"

def fake_oembed():
    return {"author_url":"https://twitter.com/GTAHelper",
            "html":"<blockquote><p>"+TEXT+"</p>&mdash; GTAHelper (@GTAHelper)</blockquote>"}

def xml():
    return ('<rss><channel><item><title>GTA VI launch</title>'
            '<description><![CDATA[Source: '+URL+' - GTA VI]]></description>'
            '</item></channel></rss>').encode("utf-8")

class Response:
    def __init__(self,*,content=None,json_data=None,status=200):
        self.status_code=status
        self.content=content if content is not None else json.dumps(json_data).encode("utf-8")
        self.value=json_data
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False
    def iter_content(self,n):
        yield self.content
    def json(self):
        return self.value

class Session:
    def __init__(self):
        self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append(url)
        if url==scout.OEMBED:
            return Response(json_data=fake_oembed())
        return Response(content=xml())

class FreeEmbedTests(unittest.TestCase):
    def test_xml_extracts_exact_tweet_status_urls_only(self):
        self.assertEqual(scout.links_from_feed(xml()),[URL])
        self.assertEqual(scout.links_from_feed(xml().replace(
            URL.encode(),b"https://x.com/GTAHelper")),[])
        with self.assertRaises(ValueError):
            scout.links_from_feed(b"x"* (scout.MAX_BYTES+1))
        self.assertIsNone(scout.status_time("not-a-tweet"))

    def test_tweet_snowflake_matches_inferred_published_at(self):
        when=scout.status_time(POST_ID)
        self.assertLess(abs((when-(NOW-timedelta(hours=1))).total_seconds()),1)
        self.assertIsNotNone(scout.embed_to_candidate(URL,fake_oembed(),NOW))
        self.assertIsNone(scout.embed_to_candidate(URL,fake_oembed(),NOW+timedelta(days=5)))

    def test_author_and_embed_body_both_must_be_verifiable(self):
        p=fake_oembed()
        self.assertIsNone(scout.embed_to_candidate(URL,{**p,"author_url":"https://x.com.evil.test/GTAHelper"},NOW))
        self.assertIsNone(scout.embed_to_candidate(URL,{**p,"author_url":"https://twitter.com/Another"},NOW))
        self.assertIsNone(scout.embed_to_candidate(URL,{**p,"html":"<p>Hello world</p>"},NOW))
        self.assertIsNone(scout.embed_to_candidate(URL,{**p,"html":"<p>GTA VI giveaway crypto follow back and win free money today</p>"},NOW))
        got=scout.embed_to_candidate(URL,p,NOW)
        self.assertEqual(got["url"],URL)
        self.assertEqual(got["verified_via"],"public_x_oembed")
        self.assertTrue(got["human_send_only"])
        self.assertIn("platinum",got["excerpt"])
        self.assertIn("missable",got["reply"])

    def test_collect_from_real_feed_link_only_with_embedded_original(self):
        with TemporaryDirectory() as directory:
            feed=Path(directory)/"feeds.json"
            feed.write_text(json.dumps({"schema":"v13.7","sources":[
                {"name":"Example","feed":"https://www.powerpyx.com/feed/",
                 "feed_domains":["www.powerpyx.com"],"enabled":True}
            ]}),encoding="utf-8")
            session=Session()
            report=scout.collect(NOW,session=session,feeds=feed)
            self.assertEqual(report["status"],"ok")
            self.assertEqual(report["discovered_links"],1)
            self.assertEqual(report["oembed_checks"],1)
            self.assertEqual(len(report["posts"]),1)
            self.assertIn(URL,scout.section(report))
            self.assertEqual(len(session.calls),2)
            self.assertEqual(session.calls[-1],scout.OEMBED)
            self.assertEqual(scout.collect(NOW,session=Session(),
                                           feeds=feed,previous_ids={POST_ID})["posts"],[])

    def test_feed_with_no_status_links_has_no_fabricated_posts(self):
        with TemporaryDirectory() as directory:
            feed=Path(directory)/"feeds.json"
            feed.write_text(json.dumps({"schema":"v13.7","sources":[
                {"name":"Example","feed":"https://www.powerpyx.com/feed/",
                 "feed_domains":["www.powerpyx.com"],"enabled":True}
            ]}),encoding="utf-8")
            class NoLinks(Session):
                def get(self,url,**kwargs):
                    self.calls.append(url)
                    return Response(content=b"<rss><channel><item><title>GTA VI</title></item></channel></rss>")
            report=scout.collect(NOW,session=NoLinks(),feeds=feed)
            self.assertEqual(report["status"],"no_source_verified_tweets")
            self.assertEqual(report["posts"],[])
            self.assertIn("Nessun permalink",scout.section(report))

if __name__=="__main__":
    unittest.main()
