"""Offline X conversation scout tests. All outputs remain human-only."""
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from x_community_review_v1 import (
    SCHEMA, SEARCHES, search_link, manual_candidates, plan, markdown
)

NOW=datetime(2026,11,19,15,0,tzinfo=timezone.utc)

def context():
    return {
        "post_url":"https://x.com/PlayStationIT/status/1234567890123456789",
        "language":"it",
        "reviewed_original":True,
        "reviewed_utc":NOW.isoformat(),
        "original_context":"Post di PlayStation Italia sulle novità e disponibilità del gioco su PS5.",
        "editorial_note":"Aggiungere una sola precisazione se verificata nella fonte ufficiale.",
        "draft_reply_it":"Qual è la fonte ufficiale del dettaglio tecnico specifico per PS5?",
    }


def with_file(items,fn):
    with TemporaryDirectory() as temp:
        path=Path(temp)/"manual.json"
        path.write_text(json.dumps({"schema":SCHEMA,"posts":items}),encoding="utf-8")
        return fn(path)


class ManualItalianDiscussionTests(unittest.TestCase):
    def test_rotating_searches_are_links_not_claimed_live_tweets(self):
        result=plan(NOW)
        self.assertTrue(result["manual_actions_only"])
        self.assertFalse(result["external_reply_automation_enabled"])
        self.assertEqual(result["live_x_posts_verified_by_bot"],0)
        self.assertEqual(result["buffer_actions"],0)
        self.assertEqual(result["exact_posts"],[])
        self.assertEqual(len(result["searches"]),5)
        self.assertEqual(len({x["id"] for x in result["searches"]}),5)
        self.assertTrue(all("https://x.com/search?q=" in x["url"] for x in result["searches"]))
        self.assertTrue(any("lang:it" in x["query"] for x in result["searches"]))
        self.assertIn("italia-domande",[x["id"] for x in result["searches"]])
        out=markdown(result)
        self.assertIn("non link a tweet verificati",out)
        self.assertIn("Nessun tweet specifico ancora verificato",out)
        self.assertIn("Non sono approvazione",out.replace("Una bozza non è approvazione","Non sono approvazione"))
        self.assertIn("no",out.lower())
        self.assertNotIn("Segui ora 50",out)

    def test_exact_tweet_accepted_only_after_human_review(self):
        report=with_file([context()],lambda path: plan(NOW,manual_path=path))
        self.assertEqual(len(report["exact_posts"]),1)
        self.assertEqual(report["exact_posts"][0]["author"],"@PlayStationIT")
        self.assertFalse(report["exact_posts"][0]["approved_for_auto_reply"])
        out=markdown(report)
        self.assertIn("https://x.com/PlayStationIT/status/1234567890123456789",out)
        self.assertIn("Qual è la fonte ufficiale",out)
        self.assertIn("nessun invio",out)

    def test_no_fake_post_or_external_host_bypass(self):
        invalid=[
            {"post_url":"https://x.com.evil.example/PlayStationIT/status/123456789"},
            {"post_url":"https://twitter.com/PlayStationIT/status/123456789"},
            {"post_url":"https://x.com/search?q=PS5"},
            {"post_url":"https://x.com/PlayStationIT/status/123456789?ref=tracking"},
            {"post_url":"https://user:pass@x.com/PlayStationIT/status/123456789"},
            {"post_url":"https://x.com/PlayStationIT/status/no-id"},
            {"reviewed_original":False},
            {"language":"en"},
            {"draft_reply_it":"Hey check https://xfederiko11.github.io/gta-6/"},
            {"draft_reply_it":"Nice!"},
            {"reviewed_utc":"yesterday"},
        ]
        for diff in invalid:
            with self.subTest(diff=diff),self.assertRaises(ValueError):
                with_file([{**context(),**diff}],manual_candidates)
        with self.assertRaises(ValueError):
            with_file([context(),context()],manual_candidates)
        with self.assertRaises(ValueError):
            with_file([context()]*9,manual_candidates)

    def test_scope_narrow_and_schema_strict(self):
        self.assertLessEqual(len(SEARCHES),8)
        self.assertTrue(all(x["title"] and x["tip"] and x["look_for"] for x in SEARCHES))
        self.assertNotIn("API",str(search_link('GTA VI lang:it')))
        with self.assertRaises(ValueError):
            plan(NOW,limit=6)
        with self.assertRaises(ValueError):
            plan(datetime(2026,11,19,15))
        with self.assertRaises(ValueError):
            markdown({"schema":"invalid"})


if __name__=="__main__":
    unittest.main()
