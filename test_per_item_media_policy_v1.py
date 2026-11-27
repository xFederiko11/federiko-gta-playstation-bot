import unittest
from datetime import datetime, timezone

from per_item_media_policy_v1 import (
    VIDEO_KEY, VIDEO_URL, SOURCE_URL, launch_video_candidate,
    link_only_message_allowed, verify_link_only_entry,
)


class PerItemMediaPolicyTests(unittest.TestCase):
    def test_exact_official_video_link_is_not_an_image_license(self):
        message = {
            "text": "GTA VI su PS5 e Xbox Series X|S.\nVideo ufficiale Rockstar Games:\n" + VIDEO_URL,
            "assets": [],
        }
        self.assertTrue(link_only_message_allowed(message))
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
            "text": "La mappa di Leonida è scaricabile.\nFonte: Rockstar Games\n" + SOURCE_URL,
            "assets": [],
        }
        self.assertTrue(link_only_message_allowed(message))
        self.assertFalse(link_only_message_allowed({
            **message, "text": message["text"].replace("grand-theft-auto-vi-now-available",
                                                       "grand-theft-auto-vi-now-available?utm=other")
        }))

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
