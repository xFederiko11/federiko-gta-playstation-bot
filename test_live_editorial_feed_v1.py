import unittest,hashlib
from datetime import datetime,timezone
from unittest.mock import patch
from live_editorial_feed_v1 import BASE,SCHEMA,validate,matching,candidates
from social_media_gate_v2 import cover_for

def row(path="articoli/test/"):
    url=BASE+path
    return {"url":url,"title":"GTA VI: fotografia di prova","summary":"Una sintesi originale del gioco con fotografie autentiche e pertinenti.",
            "published":"2026-11-26","image":cover_for(url),"sha256":"a"*64,"kind":"official_game_photo"}

class ReaderFeedTests(unittest.TestCase):
    def tearDown(self):candidates.cache_clear()
    def test_validate_exact_schema_no_external_url_or_illustration(self):
        r=row();self.assertEqual(validate({"schema":SCHEMA,"items":[r]}),[r])
        for bad in (dict(r,url="https://example.org/articoli/test/"),dict(r,kind="original_illustration"),dict(r,summary="@other "+r["summary"]),dict(r,private_queue="x")):
            with self.assertRaises(ValueError):validate({"schema":SCHEMA,"items":[bad]})
        with self.assertRaises(ValueError):validate({"schema":SCHEMA,"items":[r,r]})
    def test_new_article_auto_import_with_matching_public_contract_and_dedupe(self):
        from site_evergreen_posts_v1 import candidate
        r=row();now=datetime(2026,11,26,18,tzinfo=timezone.utc)
        state={"entries":{}}
        with patch("live_editorial_feed_v1.fetch",return_value=[r]),patch("live_editorial_feed_v1.matching",return_value=True):
            selected=candidate(state,now,live_checker=lambda u:u==r["url"],photo_checker=lambda u:"official_game_photo" if u==r["url"] else None,include_feed=True)
            self.assertEqual(selected["url"],r["url"]);self.assertEqual(selected["feed_digest"],r["sha256"])
            state["entries"]["old"]={"url":r["url"]+"?utm_source=x","status":"uncertain","source":"other"}
            self.assertIsNone(candidate(state,now,live_checker=lambda u:u==r["url"],photo_checker=lambda u:"official_game_photo" if u==r["url"] else None,include_feed=True))
    def test_stale_summary_or_photo_cannot_pass(self):
        r=row();entry={"url":r["url"],"feed_kind":r["kind"],"feed_digest":r["sha256"],"feed_summary":r["summary"]}
        self.assertTrue(matching(entry,lambda u:(r["kind"],r["sha256"],r["summary"])))
        self.assertFalse(matching(entry,lambda u:(r["kind"],"b"*64,r["summary"])))
        self.assertFalse(matching(entry,lambda u:(r["kind"],r["sha256"],"stale")))
        self.assertFalse(matching(entry,lambda u:None))
    def test_network_failure_is_empty(self):
        with patch("live_editorial_feed_v1.fetch",side_effect=ValueError("bad")):
            self.assertEqual(candidates(),())

if __name__=="__main__":unittest.main()
