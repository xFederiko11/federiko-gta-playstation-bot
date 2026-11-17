"""Regressioni SEO: pertinenza, leggibilita', limiti e nuove/vecchie bozze."""

import json
import re
import tempfile
import time
import unittest
from unittest.mock import Mock

from news_center import thread_for_event
from presentation import format_post, _post_weight
from seo_policy import hashtags_for, relevant_tags, search_label, search_context
from test_news_center import playstation_event


def gta_event(**updates):
    return {
        **playstation_event(),
        "game": "GTA VI", "category": "PATCH", "platforms": ["PS5"],
        "title": "Rockstar Games: dettagli ufficiali GTA VI",
        "source_url": "https://www.rockstargames.com/newswire/article/test",
        **updates,
    }


class SearchDiscoveryTests(unittest.TestCase):
    def test_gtavi_uses_searchable_synonym_and_relevant_tags(self):
        event = gta_event()
        post = format_post(event)
        self.assertIn("GTA VI (GTA 6)", post)
        self.assertIn("#GTAVI #PS5", post)
        self.assertLessEqual(_post_weight(post), 280)

    def test_gta_vi_without_specific_console_has_two_topic_tags(self):
        self.assertEqual(hashtags_for(gta_event(platforms=[])), ("#GTAVI", "#GTA6"))

    def test_ps5_firmware_never_tags_gtavi(self):
        event = playstation_event()
        post = format_post(event)
        self.assertIn("Firmware PS5", post)
        self.assertIn("#PS5 #PlayStation", post)
        self.assertNotIn("#GTAVI", post)
        self.assertNotIn("GTA 6", post)
        self.assertIn(event["source_url"], post)
        thread = thread_for_event(event)
        self.assertIn("#PS5 #PlayStation", thread[0])
        self.assertTrue(all(_post_weight(chunk) <= 280 for chunk in thread))

    def test_ps5_pro_only_if_explicit(self):
        self.assertNotIn("#PS5Pro", format_post(gta_event()))
        event = gta_event(platforms=["PS5 Pro"])
        self.assertEqual(hashtags_for(event), ("#GTAVI", "#PS5Pro"))
        self.assertIn("#PS5Pro", format_post(event))

    def test_ps4_firmware_is_not_ps5(self):
        event = playstation_event()
        event["platforms"] = ["PS4"]
        event["source_url"] = "https://www.playstation.com/it-it/support/hardware/ps4/system-software/"
        post = format_post(event)
        self.assertIn("Firmware PS4", post)
        self.assertIn("#PS4", post)
        self.assertNotIn("#PS5", post)

    def test_unofficial_and_demo_do_not_get_organic_optimized_tags(self):
        event = gta_event(trust="community")
        self.assertEqual(hashtags_for(event), ())
        self.assertEqual(search_label(event), "GTA VI")
        self.assertNotIn("#GTAVI", format_post(event))
        event["demo"] = True
        self.assertNotIn("#GTAVI", format_post(event))

    def test_no_duplicate_tags_or_more_than_two(self):
        event = gta_event(title="Nuovo trailer #GTAVI per GTA 6")
        post = format_post(event)
        tags = re.findall(r"(?<!\w)#[A-Za-z0-9_]+", post)
        self.assertLessEqual(len(tags), 2)
        self.assertEqual(len({tag.lower() for tag in tags}), len(tags))

    def test_long_titles_preserve_source_and_fit_tweet(self):
        event = gta_event(title="Grande annuncio ufficiale Rockstar " * 40)
        post = format_post(event)
        self.assertIn(event["source_url"], post)
        self.assertIn("FONTE UFFICIALE", post)
        self.assertLessEqual(_post_weight(post), 280)

    def test_thread_has_tags_only_on_first_part_and_never_claims_date(self):
        event = gta_event(observed_at="2026-11-17T21:00:00Z")
        parts = thread_for_event(event)
        self.assertIsNotNone(parts)
        self.assertIn("GTA 6", parts[0])
        self.assertIn("#GTAVI", parts[0])
        self.assertNotIn("#GTAVI", " ".join(parts[1:]))
        self.assertNotIn("uscito oggi", " ".join(parts))
        self.assertTrue(all(_post_weight(part) <= 280 for part in parts))

    def test_existing_draft_is_reformatted_before_single_post_publish(self):
        import online
        with tempfile.TemporaryDirectory() as td:
            db = online.open_db(td + "/db.sqlite")
            event = gta_event(facts=[])
            db.execute("INSERT INTO publish_jobs(key,event_json,status,text,created_at) VALUES (?,?,?,?,?)",
                       ("old-draft", json.dumps(event), "draft", "OLD post without tags", time.time()))
            db.commit()
            client = Mock(destination={"id": "channel-1"})
            client.publish.return_value = "buffer-post-1"
            client.last_delivery.external_url = "https://x.com/xFederiko11/status/123"
            online.deliver(db, client, lambda path: "https://example.org/card.png", td, render=Mock())
            sent_text = client.publish.call_args.args[0]
            self.assertIn("#GTAVI", sent_text)
            self.assertNotIn("OLD post without tags", sent_text)
            self.assertEqual(db.execute("SELECT text FROM publish_jobs").fetchone()[0], sent_text)
            client.publish_thread.assert_not_called()
            db.close()


if __name__ == "__main__":
    unittest.main()
