"""Offline regression checks for the research-only community source scanner."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import requests
from pathlib import Path
import unittest

from community_research_v1 import collect, fetch_candidates, load_registry, validate, parse_research_feed

NOW = datetime(2026, 11, 19, 8, 0, tzinfo=timezone.utc)


class Reply:
    status_code = 200
    def __init__(self, url, data):
        self.url = url
        self.data = data
        self.closed = False
    def raise_for_status(self):
        pass
    def iter_content(self, n):
        yield self.data
    def close(self):
        self.closed = True


class HTTP:
    def __init__(self, feed, data, actual=None):
        self.feed = feed
        self.data = data
        self.actual = actual
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append(url)
        if url != self.feed:
            raise requests.ConnectionError("Fixture only: this feed is intentionally unavailable")
        return Reply(self.actual or url, self.data)


class CommunityResearchTests(unittest.TestCase):
    def setUp(self):
        self.config = load_registry(Path("community-research-sources-v1.json"))

    def test_registry_attributions_and_no_automatic_publication(self):
        feeds = validate(self.config)
        self.assertFalse(self.config["policy"]["auto_publish"])
        self.assertIn("PowerPyx", [x["name"] for x in feeds])
        self.assertIn("GTAForums", [x["name"] for x in feeds])
        self.assertIn("GTA Wiki / Fandom", [x["name"] for x in feeds])
        for source in feeds:
            if source["collection"] != "read_only_feed":
                self.assertNotIn("feed", source)

    def test_untrusted_feeds_rejected_without_fetch(self):
        bad = json.loads(json.dumps(self.config))
        bad["sources"][1]["feed"] = "https://evil.example/content.xml"
        with self.assertRaises(ValueError):
            validate(bad)
        bad = json.loads(json.dumps(self.config))
        bad["policy"]["auto_publish"] = True
        with self.assertRaises(ValueError):
            validate(bad)

    def test_manual_sources_never_scraped(self):
        source = next(x for x in self.config["sources"] if x["name"] == "PowerPyx")
        date = (NOW - timedelta(hours=2)).isoformat()
        rss = (f'<rss><channel><item><title>GTA VI trophies and guide</title>'
               f'<link>https://www.powerpyx.com/gta-6-guide/</link><pubDate>{date}</pubDate>'
               '</item></channel></rss>').encode()
        session = HTTP(source["feed"], rss)
        result = collect(self.config, session=session, now=NOW)
        self.assertEqual(len(session.calls), 2)  # PowerPyx and YouTube; mock rejects the other.
        self.assertEqual(len(result["candidates"]), 1)
        self.assertFalse(result["candidates"][0]["official_rockstar"])
        self.assertIn("RICERCA", result["candidates"][0]["status"])
        self.assertEqual(result["publication"], "read_only__no_buffer_post__no_articles_auto_created")
        self.assertTrue(any(x["source"] == "GTA Series Videos" for x in result["errors"]))

    def test_reject_wrong_feed_redirect(self):
        src = next(x for x in self.config["sources"] if x["name"] == "GTA Series Videos")
        session = HTTP(src["feed"], b"", actual="https://spoof.example/updates.xml")
        with self.assertRaises(ValueError):
            fetch_candidates(src, session=session, now=NOW)

    def test_rss_age_topic_and_host_limit(self):
        source = next(x for x in self.config["sources"] if x["name"] == "PowerPyx")
        fresh = (NOW - timedelta(hours=3)).isoformat()
        old = (NOW - timedelta(days=6)).isoformat()
        rss = f'''<rss><channel>
        <item><title>GTA VI new collectibles guide</title><link>https://www.powerpyx.com/gta-6-guide</link><pubDate>{fresh}</pubDate></item>
        <item><title>GTA VI older collectibles guide</title><link>https://www.powerpyx.com/older</link><pubDate>{old}</pubDate></item>
        <item><title>GTA VI leaked endings</title><link>https://www.powerpyx.com/rumours</link><pubDate>{fresh}</pubDate></item>
        <item><title>GTA VI new settings</title><link>https://attacker.example/untrusted</link><pubDate>{fresh}</pubDate></item>
        <item><title>Cooking guide</title><link>https://www.powerpyx.com/cooking</link><pubDate>{fresh}</pubDate></item>
        </channel></rss>'''.encode()
        entries = fetch_candidates(source, session=HTTP(source["feed"], rss), now=NOW)
        self.assertEqual(len(entries), 2)
        self.assertTrue(any("leaked" in x["title"] for x in entries))
        self.assertEqual(entries[0]["source"], "PowerPyx")
        self.assertEqual(entries[0]["url"], "https://powerpyx.com/gta-6-guide")

    def test_rumors_survive_research_but_not_the_publishing_filter(self):
        src = next(x for x in self.config["sources"] if x["name"] == "PowerPyx")
        stamp = (NOW - timedelta(hours=1)).isoformat()
        rss = (f"<rss><channel><item><title>GTA VI rumored new property system</title>"
               f"<link>https://www.powerpyx.com/rumour/</link><pubDate>{stamp}</pubDate>"
               "</item></channel></rss>").encode()
        entries = list(parse_research_feed(rss, src))
        self.assertEqual(len(entries), 1)
        self.assertIn("rumored", entries[0]["title"])
        from editorial_autopilot_v137 import topic
        self.assertIsNone(topic(entries[0]["title"]))

    def test_atom_videos_are_not_rockstar_announcements(self):
        src = next(x for x in self.config["sources"] if x["name"] == "GTA Series Videos")
        stamp=(NOW-timedelta(hours=1)).isoformat()
        atom=(f'<feed xmlns="http://www.w3.org/2005/Atom">'
              f'<entry><title>GTA 6 - 100% Walkthrough Part 1</title>'
              f'<published>{stamp}</published>'
              f'<link rel="alternate" href="https://www.youtube.com/watch?v=ABCDEFGHIJK"/>'
              f'</entry></feed>').encode()
        entries = fetch_candidates(src, session=HTTP(src["feed"], atom), now=NOW)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["content_type"], "video")
        self.assertFalse(entries[0]["official_rockstar"])


if __name__ == "__main__":
    unittest.main()
