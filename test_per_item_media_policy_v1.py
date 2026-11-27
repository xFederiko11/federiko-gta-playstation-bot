import unittest
from datetime import datetime, timezone

from per_item_media_policy_v1 import (
    VIDEO_KEY, VIDEO_URL, SOURCE_URL, VIDEO_TEXT, SOURCE_TEXT, launch_video_candidate,
    link_only_message_allowed, source_link_candidate, source_link_message_allowed,
    verify_link_only_entry, verify_source_link_entry,
)


class PerItemMediaPolicyTests(unittest.TestCase):
    def test_exact_official_video_link_is_not_an_image_license(self):
        message = {
            "text": VIDEO_TEXT,
            "assets": [],
        }
        self.assertTrue(link_only_message_allowed(message))
        self.assertFalse(link_only_message_allowed({**message, "text": message["text"].replace("è disponibile", "include una missione segreta")}))
        self.assertFalse(link_only_message_allowed({**message, "assets": [{"image": {"url": "https://example.org/x.jpg"}}]}))
        self.assertFalse(link_only_message_allowed({
            **message, "text": message["text"].replace("T95WGWkx7P0", "aaaaaaaaaaa")
        }))
        self.assertFalse(link_only_message_allowed({
            **message, "text": message["text"] + "\nhttps://example.org/photo.jpg"
        }))
        self.assertFalse(link_only_message_allowed({
            **message, "text": message["text"].replace("Video ufficiale Rockstar Games", "Notizia")
        }))

    def test_exact_official_source_url_is_reviewed_for_link_sharing_only(self):
        message = {
            "text": SOURCE_TEXT,
            "assets": [],
        }
        self.assertTrue(link_only_message_allowed(message))
        self.assertFalse(link_only_message_allowed(message, allow_thread=False))
        self.assertFalse(link_only_message_allowed({
            **message, "text": message["text"].replace("grand-theft-auto-vi-now-available",
                                                       "grand-theft-auto-vi-now-available?utm=other")
        }))

    def test_verified_feed_article_falls_back_to_source_link_without_media(self):
        url = "https://www.videogameschronicle.com/news/example-story/"
        text = ("📰 GTA VI | Novità\\n\\nDettaglio confermato dalla fonte.\\n\\n"
                "🔗 Fonte: VGC\\n" + url + "\\n\\n#GTAVI #GTA6")
        item = {"key": "vgc-story", "sig": "gta vi story", "title": "GTA VI: dettagli",
                "source": "VGC", "url": url, "text": text}
        candidate = source_link_candidate(item)
        self.assertEqual(candidate["media_mode"], "source_link_only")
        self.assertIsNone(candidate["media_url"])
        self.assertTrue(verify_source_link_entry(candidate))
        self.assertFalse(source_link_message_allowed(
            {"text": text.replace("videogameschronicle.com", "evil.example"), "assets": []}))
        self.assertFalse(source_link_message_allowed(
            {"text": text + "\\nhttps://example.org/image.jpg", "assets": []}))
        self.assertFalse(verify_source_link_entry({**candidate, "url": "https://evil.example/"}))

    def test_fallback_is_one_time_and_has_no_image_attachment(self):
        now = datetime(2026, 11, 27, 12, tzinfo=timezone.utc)
        candidate = launch_video_candidate({"entries": {}}, now, launch=True)
        self.assertEqual(candidate["media_mode"], "official_video_link")
        self.assertIsNone(candidate["media_url"])
        self.assertEqual(candidate["url"], VIDEO_URL)
        self.assertEqual(len(candidate["thread"]), 2)
        self.assertTrue(verify_link_only_entry(candidate))
        self.assertIsNone(launch_video_candidate({"entries": {VIDEO_KEY: {"status": "sent"}}}, now))
        self.assertIsNone(launch_video_candidate(
            {"entries": {"other": {"url": VIDEO_URL, "status": "sent"}}}, now
        ))

    def test_non_launch_link_post_is_single_message(self):
        now = datetime(2026, 11, 27, 12, tzinfo=timezone.utc)
        candidate = launch_video_candidate({"entries": {}}, now)
        self.assertIsNone(candidate["thread"])
        self.assertTrue(verify_link_only_entry(candidate))


if __name__ == "__main__":
    unittest.main()
