"""Offline X conversation scout tests. All outputs remain human-only."""
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from tempfile import TemporaryDirectory
import unittest

from x_community_review_v1 import (
    SCHEMA, SEARCHES, TARGETS, search_link, manual_candidates, plan, markdown
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

    def test_user_known_accounts_and_replies_are_context_specific(self):
        report=plan(NOW)
        self.assertEqual(len(TARGETS),7)
        targets=report["conversation_targets"]
        self.assertEqual(len(targets),4)
        self.assertEqual(len({item["handle"] for item in targets}),4)
        self.assertTrue(all(item["profile_url"]=="https://x.com/"+item["handle"]
                            for item in targets))
        self.assertTrue(all("from%3A" in item["search_url"] for item in targets))
        self.assertTrue(all(not item["specific_post_verified"] for item in targets))
        self.assertTrue(any(item["language"]=="it" for item in TARGETS))
        self.assertTrue(any(item["language"]=="en" for item in TARGETS))
        self.assertIn("colonna sonora",next(x for x in TARGETS
                        if x["handle"]=="RockstarINTEL")["when"])
        self.assertNotIn("troph",next(x for x in TARGETS
                        if x["handle"]=="RockstarINTEL")["reply"].lower())
        self.assertTrue(next(x for x in TARGETS if x["handle"]=="GTASeries")["observed_reply"])
        for target in TARGETS:
            self.assertLessEqual(len(target["reply"]),260)
            self.assertNotIn("http",target["reply"])
            self.assertNotIn("#GTAVI",target["reply"])
        body=markdown(report)
        self.assertIn("Account rilevanti e conversazioni da valutare",body)
        self.assertIn("bozza *condizionale*",body)
        self.assertIn("adatta la bozza e premi Invia personalmente",body)
        self.assertIn("Se hai già commentato, non replicare",body)

    def test_manually_reviewed_single_post_gets_one_click_reply_composer(self):
        report=with_file([context()],lambda p:plan(NOW,manual_path=p))
        reviewed=report["exact_posts"][0]
        self.assertTrue(reviewed["reply_intent_url"].startswith(
            "https://x.com/intent/tweet?"))
        parts=urlsplit(reviewed["reply_intent_url"])
        args=parse_qs(parts.query)
        self.assertEqual(args["in_reply_to"],["1234567890123456789"])
        self.assertEqual(args["text"],[context()["draft_reply_it"]])
        self.assertEqual(reviewed["approved_for_auto_reply"],False)
        body=markdown(report)
        self.assertIn("Apri bozza nella finestra Rispondi",body)
        self.assertIn("L'intent apre soltanto un composer",body)
        self.assertIn("nessun invio",body)
        no_draft={**context(),"draft_reply_it":""}
        other=with_file([no_draft],lambda p:plan(NOW,manual_path=p))
        self.assertIsNone(other["exact_posts"][0]["reply_intent_url"])

    def test_exact_tweet_accepted_only_after_human_review(self):
        report=with_file([context()],lambda path: plan(NOW,manual_path=path))
        self.assertEqual(len(report["exact_posts"]),1)
        self.assertEqual(report["exact_posts"][0]["author"],"@PlayStationIT")
        self.assertFalse(report["exact_posts"][0]["approved_for_auto_reply"])
        out=markdown(report)
        self.assertIn("https://x.com/PlayStationIT/status/1234567890123456789",out)
        self.assertIn("Qual è la fonte ufficiale",out)
        self.assertIn("nessun invio",out)

    def test_english_reply_requires_english_draft_and_still_manual_send(self):
        en={**context(),"language":"en"}
        en.pop("draft_reply_it")
        en["original_context"]="GTA Series Videos shares a walkthrough with a specific mission objective."
        en["editorial_note"]="Ask about an optional objective after reading the exact walkthrough."
        en["draft_reply_en"]="Is there an optional objective in this mission worth checking before moving on?"
        result=with_file([en],lambda path:plan(NOW,manual_path=path))
        item=result["exact_posts"][0]
        self.assertEqual(item["language"],"en")
        self.assertEqual(item["draft_reply_en"],en["draft_reply_en"])
        self.assertEqual(item["draft_reply"],en["draft_reply_en"])
        self.assertFalse(item["approved_for_auto_reply"])
        self.assertIn(en["draft_reply_en"],parse_qs(
            urlsplit(item["reply_intent_url"]).query)["text"])
        self.assertIn("Lingua: en",markdown(result))

    def test_no_fake_post_or_external_host_bypass(self):
        invalid=[
            {"post_url":"https://x.com.evil.example/PlayStationIT/status/123456789"},
            {"post_url":"https://twitter.com/PlayStationIT/status/123456789"},
            {"post_url":"https://x.com/search?q=PS5"},
            {"post_url":"https://x.com/PlayStationIT/status/123456789?ref=tracking"},
            {"post_url":"https://user:pass@x.com/PlayStationIT/status/123456789"},
            {"post_url":"https://x.com/PlayStationIT/status/no-id"},
            {"reviewed_original":False},
            {"language":"xx"},
            {"draft_reply_it":"Hey check https://xfederiko11.github.io/gta-6/"},
            {"draft_reply_it":"Nice!"},
            {"language":"en","draft_reply_it":"Questo va nel campo inglese, non italiano."},
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
