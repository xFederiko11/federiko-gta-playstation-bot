"""Offline tests for Reddit lead intake; no Reddit network access."""
from __future__ import annotations
import unittest
from datetime import datetime,timezone
from reddit_intake_v1 import canonical_url,parse_issue,select,markdown

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
    def test_untrusted_markdown_not_rendered_as_unsafe_links(self):
        candidate=issue(title="[REDDIT-LEAD] GTA VI PS5 garage [click](https://evil.test) help")
        report=markdown([candidate],NOW)
        self.assertNotIn("](https://evil.test)",report)
        self.assertEqual(len(select([candidate],NOW)),1)
if __name__=="__main__":unittest.main()
