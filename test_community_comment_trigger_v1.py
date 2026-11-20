"""No-network first-comment X trigger regression: original post, no user quotes."""
from __future__ import annotations
import unittest
from copy import deepcopy
from datetime import datetime,timezone
from community_comment_trigger_v1 import allowed_issue,eligible_comment,candidate

NOW=datetime(2026,11,20,10,20,tzinfo=timezone.utc)
SITE="https://xfederiko11.github.io/gta-6/salvare-auto/"

def issue():
    return {"number":451,"html_url":"https://github.com/xFederiko11/gta-6/issues/451",
            "title":"💬 GTA VI | Salvare auto GTA VI — garage e tracker",
            "body":"<!-- gta6-discussion-v1 path=salvare-auto/ -->",
            "state":"open","labels":[{"name":"community-discussion"}],
            "comments":1,"updated_at":"2026-11-20T10:19:00Z"}
def comment():
    return {"user":{"type":"User","login":"giocatore-ps5"},
            "body":"Ho trovato un altro garage sulla mappa, come funziona la registrazione delle auto?",
            "created_at":"2026-11-20T10:10:00Z"}

class CommentTriggerTests(unittest.TestCase):
    def read(self,path):
        if path.startswith("/issues?"):return [issue()]
        if path.startswith("/issues/451/comments"):return [comment()]
        raise AssertionError(path)

    def test_one_sourced_original_two_message_thread(self):
        item=candidate({"entries":{}},NOW,read=self.read,live_checker=lambda u: u==SITE)
        self.assertIsNotNone(item)
        self.assertEqual(item["url"],SITE)
        self.assertEqual(len(item["thread"]),2)
        self.assertIn("Hai una conferma",item["thread"][0])
        self.assertIn(SITE,item["thread"][1])
        self.assertNotIn("giocatore-ps5",str(item))
        self.assertNotIn("Ho trovato un altro garage",str(item))
        self.assertEqual(candidate({"entries":{item["key"]:{"status":"sent","url":SITE,
                           "reserved_utc":NOW.isoformat(),"tip_id":item["tip_id"]}}},NOW,
                           read=self.read,live_checker=lambda _:True),None)

    def test_prior_post_or_unknown_attempt_must_not_duplicate(self):
        for status in ("sent","scheduled","reserved","attempted","uncertain","accepted_pending"):
            ledger={"entries":{"a":{"status":status,"url":SITE}}}
            self.assertIsNone(candidate(ledger,NOW,read=self.read,live_checker=lambda _:True))

    def test_forged_issues_and_spam_cannot_trigger(self):
        bad=issue()
        bad["html_url"]="https://github.com/attacker/repo/issues/451"
        self.assertIsNone(allowed_issue(bad))
        bad=issue()
        bad["labels"]=[]
        self.assertIsNone(allowed_issue(bad))
        for body in ("Ottimo!","Compra crypto subito su https://spam.example ora",
                     "free followers rispondi subito a questo messaggio"):
            comment_data={**comment(),"body":body}
            self.assertFalse(eligible_comment(comment_data,NOW))
        self.assertFalse(eligible_comment({**comment(),"user":{"type":"Bot","login":"gh[bot]"}},NOW))

    def test_no_network_failure_does_not_break_news_bot(self):
        import requests
        def down(path):raise requests.Timeout()
        self.assertIsNone(candidate({"entries":{}},NOW,read=down))
        self.assertIsNone(candidate({"entries":{}},NOW,read=self.read,
                                    live_checker=lambda _:False))

if __name__=="__main__":unittest.main()
