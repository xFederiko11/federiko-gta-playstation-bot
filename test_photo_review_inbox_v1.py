"""Offline X photo inbox tests: no paid API without opt-in, no automatic license."""
from __future__ import annotations
from datetime import datetime,timezone
import json
from pathlib import Path
import unittest

import photo_review_inbox_v1 as p

NOW=datetime(2026,11,21,14,0,tzinfo=timezone.utc)
TWEET=("Hello @xFederiko11 #GTA6Italia FOTO registrare-auto-personale "
       "step:2/5 PS5 Pro Credito:@sample. Sono autore e autorizzo GTA VI Italia "
       "a ripubblicare questa mia foto sul sito e sui social con credito. "
       "Allego screenshot originale.")

def fixture():
    return {"data":[{"id":"2026112111223344556","text":TWEET,"created_at":"2026-11-21T13:00:00Z",
                     "author_id":"11","attachments":{"media_keys":["3_abc"]}}],
            "includes":{"users":[{"id":"11","username":"sample"}],
                        "media":[{"media_key":"3_abc","type":"photo"}]}}


class PhotoInboxTests(unittest.TestCase):
    def test_offline_has_zero_cost_or_actions(self):
        self.assertEqual(len(p.GUIDES),11)
        called=[]
        def api(token):
            called.append(token);return fixture()
        res=p.collect(NOW,enabled=False,token="VALID_TOKEN_THAT_NEVER_GETS_USED",api=api)
        self.assertEqual(res["status"],"off_without_manual_links")
        self.assertEqual(called,[])
        self.assertEqual(res["requests"],0)
        self.assertEqual(res["candidates"],[])
        self.assertEqual(res["auto_approved"],0)
        self.assertEqual(res["images_downloaded"],0)
        self.assertEqual(res["posts_published"],0)
        self.assertIn("NON foto approvate",p.markdown(res))
        self.assertEqual(p.manual_links("data/photo-intake-known-status-v1.json"),[])

    def test_opt_in_single_request_source_only(self):
        calls=[]
        def fetch(token):
            calls.append(token);return fixture()
        report=p.collect(NOW,enabled=True,token="YOUR_EXISTING_LONG_BEARER_TOKEN",api=fetch)
        self.assertEqual(calls,["YOUR_EXISTING_LONG_BEARER_TOKEN"])
        self.assertEqual(report["requests"],1)
        self.assertEqual(len(report["candidates"]),1)
        row=report["candidates"][0]
        self.assertEqual(row["guide"],"registrare-auto-personale")
        self.assertEqual(row["role"],2)
        self.assertEqual(row["platform"],"PS5 Pro")
        self.assertEqual(row["review"],"HUMAN_REQUIRED")
        self.assertEqual(row["rights"],"unverified_public_claim_only")
        self.assertNotIn("media_url",row)
        self.assertNotIn("photo_bytes",row)
        self.assertIn(row["url"],p.markdown(report))
        self.assertNotIn("YOUR_EXISTING_LONG_BEARER_TOKEN",p.markdown(report))

    def test_missing_token_fails_closed(self):
        result=p.collect(NOW,enabled=True,token="short",api=lambda tok:fixture())
        self.assertEqual(result["candidates"],[])
        self.assertEqual(result["requests"],0)
        self.assertEqual(result["errors"],["missing_X_BEARER_TOKEN"])

    def test_require_photo_and_exact_creator_claim(self):
        d=fixture()
        self.assertEqual(len(p.from_api(d,NOW)),1)
        d["includes"]["media"][0]["type"]="video"
        self.assertEqual(p.from_api(d,NOW),[])
        d=fixture();d["data"][0]["text"]=TWEET.replace("Sono autore e autorizzo","Non autorizzo")
        self.assertEqual(p.from_api(d,NOW),[])
        d=fixture();d["data"][0]["text"]=TWEET.replace("registrare-auto-personale","invalid-guide")
        self.assertEqual(p.from_api(d,NOW),[])
        d=fixture();d["data"][0]["created_at"]="2026-11-01T13:00:00Z"
        self.assertEqual(p.from_api(d,NOW),[])
        d=fixture();d["data"][0]["text"]=TWEET.replace("step:2/5","step:9/5")
        self.assertEqual(p.from_api(d,NOW),[])

    def test_manual_permalinks_only_and_no_untrusted_redirects(self):
        for bad in ["http://x.com/s/status/1234567890","https://x.com.evil.test/u/status/1234567890",
                    "https://x.com/u/status/1234567890?token=x","https://x.com/u/status/1234567890#secret",
                    "https://x.com/a/status/abc12345"]:
            self.assertIsNone(p.canonical(bad))
        self.assertEqual(p.canonical("https://twitter.com/real/status/12345678901"),
                         "https://x.com/real/status/12345678901")
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            location=Path(tmp)/"manual.json"
            location.write_text(json.dumps({"schema":p.SEED_SCHEMA,"posts":[
                "https://x.com/real/status/12345678901","https://x.com/real/status/12345678901"]}))
            with self.assertRaises(ValueError):p.manual_links(location)

    def test_exact_public_post_not_sufficient_rights_proof(self):
        # Public X embed checks text and author; never validates pixels or rights.
        fake_time=int(NOW.timestamp()*1000)-p.AGE.days*0
        post_id=str((int(NOW.timestamp()*1000)-1288834974657)<<22)
        url="https://x.com/sample/status/"+post_id
        embed={"author_url":"https://x.com/sample",
               "html":"<blockquote><p>"+TWEET+"</p></blockquote>"}
        item=p.from_embed(url,embed,NOW)
        self.assertIsNotNone(item)
        self.assertEqual(item["evidence"],"PUBLIC_OEMBED_TEXT_ONLY_NO_IMAGE_VERIFICATION")
        self.assertEqual(item["review"],"HUMAN_REQUIRED")
        embed["author_url"]="https://x.com/attacker"
        self.assertIsNone(p.from_embed(url,embed,NOW))


if __name__=="__main__":unittest.main()
