"""Zero-API-X official video sharing tests. No network or Buffer writes."""
import json
import os
import time
import unittest
from unittest.mock import Mock, patch

import online
from buffer_publisher import Delivery
from video_cards_v12 import video_link, video_link_post, ROCKSTAR_CHANNEL

VIDEO = 'https://www.youtube.com/watch?v=AbCdEfGhI12'


def official_event(title='GTA 6 Official Trailer 3'):
    return {
        'event_key': VIDEO, 'game': 'GTA VI', 'category': 'NEWS',
        'data_kind': 'announcement', 'region': None, 'platforms': ['PS5'],
        'title': title, 'facts': [{'label': 'Titolo dalla fonte', 'value': title}],
        'trust': 'official', 'source_name': 'Rockstar Games',
        'official_channel_id': ROCKSTAR_CHANNEL, 'source_url': VIDEO,
    }


class OfficialLinksFreeTests(unittest.TestCase):
    def test_rockstar_only_and_italian_paragraphs(self):
        text = video_link_post(official_event())
        self.assertIsNotNone(text)
        self.assertIn('🎬 GTA VI | Video ufficiale Rockstar\n\n', text)
        self.assertIn('\n\n▶️ Guarda il video originale:\n'+VIDEO, text)
        self.assertIn('\n\n#GTAVI #GTA6', text)
        self.assertNotIn('Official Trailer 3', text)

    def test_reject_unverified_channel_and_fake_link(self):
        event = official_event()
        self.assertEqual(video_link(event), VIDEO)
        self.assertIsNone(video_link_post({**event, 'official_channel_id': 'attacker-channel'}))
        self.assertIsNone(video_link_post({**event, 'trust': 'community'}))
        self.assertIsNone(video_link_post({**event, 'source_url': 'https://example.net/watch?v=AbCdEfGhI12'}))
        self.assertIsNone(video_link_post({**event, 'source_url': 'https://www.youtube.com/watch?v=ABCD'}))

    def test_main_publisher_sends_official_link_without_translation_api_or_image_upload(self):
        db = online.open_db(':memory:')
        try:
            original = official_event()
            with db:
                db.execute(
                    'INSERT INTO publish_jobs(key,event_json,status,text,created_at) VALUES (?,?,?,?,?)',
                    ('official-video-test', json.dumps(original), 'draft',
                     'OLD PLACEHOLDER ENGLISH TITLE', time.time())
                )
            client = Mock(destination={'id': 'channel-1'})
            client.publish.return_value = 'buffer-verified-id'
            client.last_delivery = Delivery('buffer-verified-id', 'sent',
                                            'https://x.com/xFederiko11/status/1234567890')
            with patch.dict(os.environ, {'OFFICIAL_LINKS_FREE_ENABLED': 'true',
                                          'VIDEO_LINK_CARDS_V12': 'false'}), \
                 patch.object(online, 'italian_title', side_effect=AssertionError('Should not translate already safe Italian template')), \
                 patch.object(online, 'official_image_for_event', side_effect=AssertionError('Images not needed')):
                online.deliver(db, client, upload=Mock(side_effect=AssertionError('Should not upload')),
                               directory='/tmp/unneeded-official-photos', news_center_threads=True,
                               require_official_media=True,
                               media_resolver=Mock(side_effect=AssertionError('Should not probe images')))
            client.publish.assert_called_once()
            sent_text = client.publish.call_args.args[0]
            self.assertEqual(sent_text, video_link_post(original))
            self.assertIsNone(client.publish.call_args.kwargs.get('media_url'))
            self.assertEqual(db.execute('SELECT status FROM publish_jobs').fetchone()[0], 'posted')
            # A second run cannot repeat a delivered post.
            online.deliver(db, client, upload=Mock(), directory='/tmp/unneeded')
            client.publish.assert_called_once()
        finally:
            db.close()

if __name__ == '__main__':
    unittest.main()
