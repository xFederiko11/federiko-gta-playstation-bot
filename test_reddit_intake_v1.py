"""Offline tests for Reddit lead intake; no Reddit network access."""
from __future__ import annotations
import unittest
from datetime import datetime,timezone
from unittest.mock import Mock,patch
from urllib.error import HTTPError
from reddit_intake_v1 import expand_ift_link
from reddit_intake_v1 import canonical_url,parse_issue,select,markdown,expand_short_links

NOW=datetime(2026,11,20,14,0,tzinfo=timezone.utc)
URL="https://www.reddit.com/r/GTA6/comments/abc123/"
def issue(**changes):
    return {**{"author":{"login":"xFederiko11"},
      "title":"[REDDIT-LEAD] GTA 6 PS5 where to save rare cars in garage",
      "body":"Reddit source: https://www.reddit.com/r/GTA6/comments/abc123/garage_location/",
      "url":"https://github.com/xFederiko11/federiko-gta-playstation-bot/issues/999",
      "createdAt":"2026-11-20T13:00:00Z"},**changes}

class RedditIntakeTests(unittest.TestCase):
    def test_owned_permalinks_only(self):
        self.assertEqual(canonical_url("https://www.reddit.com/r/GTA6/comments/abc123/garage_location/"),URL)
        for link in ("https://old.reddit.com/r/GTA6/comments/abc123/",
                     "https://reddit.com.evil.test/r/GTA6/comments/abc123/",
                     "http://www.reddit.com/r/GTA6/comments/abc123/",
                     "https://www.reddit.com/r/Other/comments/abc123/",
                     "https://www.reddit.com/r/GTA6/comments/abc123/?ref=spam",
                     "https://www.reddit.com/r/GTA6/comments/abc123/%2fsecret"):
            self.assertIsNone(canonical_url(link),link)
    def test_owner_marker_and_title_required(self):
        self.assertEqual(parse_issue(issue(),NOW)["reddit_url"],URL)
        self.assertIsNone(parse_issue(issue(author={"login":"untrusted-user"}),NOW))
        self.assertIsNone(parse_issue(issue(title="A normal issue about GTA VI"),NOW))
        self.assertIsNone(parse_issue(issue(body="No reliable permalink"),NOW))
        self.assertIsNone(parse_issue(issue(body="https://www.reddit.com/r/GTA6/comments/abc123/ https://www.reddit.com/r/GTAVI/comments/def123/"),NOW))
        self.assertIsNone(parse_issue(issue(createdAt="2026-10-01T10:00:00Z"),NOW))
        self.assertIsNone(parse_issue(issue(title="[REDDIT-LEAD] Buy crypto immediately"),NOW))
    def test_dedupe_and_no_publishing_or_metrics(self):
        self.assertEqual(len(select([issue(),issue()],NOW)),1)
        report=markdown([issue()],NOW)
        self.assertIn("https://www.reddit.com/r/GTA6/comments/abc123/",report)
        self.assertIn("revisione necessaria",report.lower())
        self.assertIn("non pubblica",report.lower())
        self.assertNotIn("1000 follower",report)
        self.assertIn("senza link promozionali",report)
    def test_ifttt_short_link_only_expands_from_owner_issue_to_verified_reddit_url(self):
        shortened=issue(body="Reddit source: https://ift.tt/bMAG9Kx")
        clean=expand_short_links([shortened],resolve=lambda value:
            "https://www.reddit.com/r/GTA6/comments/abc123/garage_location/")
        self.assertEqual(select(clean,NOW)[0]["reddit_url"],URL)
        self.assertIn("Eventi Reddit ricevuti: 1",markdown(clean,NOW))
        self.assertIn("non pertinenti dal titolo: 0",markdown(clean,NOW))
        self.assertIn("pertinenti e con URL verificato: 1",markdown(clean,NOW))
        spoof=issue(author={"login":"other"},body=shortened["body"])
        called=[]
        def dangerous(_):
            called.append(1)
            return "https://www.reddit.com/r/GTA6/comments/abc123/"
        self.assertEqual(expand_short_links([spoof],resolve=dangerous)[0]["body"],spoof["body"])
        self.assertEqual(called,[])
        other=expand_short_links([shortened],resolve=lambda value:"https://intranet.example/secret")
        self.assertEqual(select(other,NOW),[])
        self.assertEqual(len(select(expand_short_links([shortened],resolve=lambda value:None),NOW)),0)
        report=markdown([shortened],NOW)
        self.assertIn("Eventi Reddit ricevuti: 1",report)
        self.assertIn("link IFTTT pertinenti ancora da risolvere: 1",report)
    def test_real_ift_url_does_not_mean_relevant_gta_tip(self):
        irrelevant=issue(title="[REDDIT-LEAD] I feel sorry for streamers without any music",
                         body="Reddit source: https://ift.tt/bMAG9Kx")
        clean=expand_short_links([irrelevant],resolve=lambda value:
            "https://www.reddit.com/r/GTA6/comments/abc123/streaming_music/")
        self.assertEqual(select(clean,NOW),[])
        self.assertIn("Eventi Reddit ricevuti: 1",markdown(clean,NOW))
        self.assertIn("non pertinenti dal titolo: 1",markdown(clean,NOW))
    def test_ift_tt_relevant_title_only_and_hard_request_limit(self):
        relevant=issue(title="[REDDIT-LEAD] GTA VI money glitch PS5 update",
                       body="Reddit source: https://ift.tt/abcde123")
        irrelevant=issue(title="[REDDIT-LEAD] People complain about background music",
                         body="Reddit source: https://ift.tt/bMAG9Kx")
        calls=[]
        def resolve(link):
            calls.append(link)
            return "https://www.reddit.com/r/GTA6/comments/abc123/"
        rows=expand_short_links([irrelevant, relevant, relevant], resolve=resolve, max_lookups=1)
        self.assertEqual(calls,["https://ift.tt/abcde123"])
        self.assertEqual(select(rows,NOW)[0]["title"],"GTA VI money glitch PS5 update")
        self.assertIn("non pertinenti dal titolo: 1", markdown(rows,NOW))
        self.assertIn("link IFTTT pertinenti ancora da risolvere: 0",markdown(rows,NOW))

    def test_newest_relevant_issue_wins_tie(self):
        first=issue(title="[REDDIT-LEAD] GTA VI money farming glitch",
                    body="Reddit source: https://www.reddit.com/r/GTA6/comments/abc123/",
                    createdAt="2026-11-20T10:00:00Z")
        second=issue(title="[REDDIT-LEAD] GTA VI save car garage advice",
                     body="Reddit source: https://www.reddit.com/r/GTA6/comments/xyz789/",
                     createdAt="2026-11-20T13:45:00Z")
        items=select([first,second],NOW)
        self.assertEqual(len(items),2)
        self.assertEqual(items[0]["title"],"GTA VI save car garage advice")

    def test_head_unsupported_falls_back_to_bounded_get_without_following(self):
        calls=[]
        opener=Mock()
        def fake_open(req,timeout):
            calls.append((req.full_url, req.get_method(), timeout))
            if req.get_method()=="HEAD":
                raise HTTPError(req.full_url,405,"not supported",{},None)
            raise HTTPError(req.full_url,302,"redirect",
                            {"Location":"https://www.reddit.com/r/GTA6/comments/abc123/"},
                            None)
        opener.open.side_effect=fake_open
        with patch("reddit_intake_v1.build_opener",return_value=opener):
            expanded=expand_ift_link("https://ift.tt/abcde123")
        self.assertEqual(expanded,URL)
        self.assertEqual(calls,[("https://ift.tt/abcde123","HEAD",6),
                                ("https://ift.tt/abcde123","GET",6)])
        with patch("reddit_intake_v1.build_opener",return_value=opener):
            self.assertIsNone(expand_ift_link("https://evil.example/x"))
        self.assertEqual(len(calls),2)
        # It never accesses the address inside the Location header.

    def test_untrusted_markdown_not_rendered_as_unsafe_links(self):
        candidate=issue(title="[REDDIT-LEAD] GTA VI PS5 garage [click](https://evil.test) help")
        report=markdown([candidate],NOW)
        self.assertNotIn("](https://evil.test)",report)
        self.assertEqual(len(select([candidate],NOW)),1)
if __name__=="__main__":unittest.main()
