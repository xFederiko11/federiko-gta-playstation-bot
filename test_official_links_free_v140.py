"""Zero-API-X official video sharing tests. No network or Buffer writes."""
import json
import os
import time
import unittest
from unittest.mock import Mock, patch

import online
from buffer_publisher import Delivery
from video_cards_v12 import video_link, video_link_post, ROCKSTAR_CHANNEL
from official_media import OfficialMediaChoice

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

    def test_main_publisher_sends_official_link_with_verified_thumbnail(self):
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

            thumbnail='https://i.ytimg.com/vi/AbCdEfGhI12/hqdefault.jpg'
            choice=OfficialMediaChoice(thumbnail,'video_thumbnail',VIDEO)
            with (
                patch.dict(os.environ, {'OFFICIAL_LINKS_FREE_ENABLED':'true',
                                        'VIDEO_LINK_CARDS_V12':'false'}),
                patch.object(online,'italian_title',
                             side_effect=AssertionError('Do not translate Italian template')),
                patch.object(online,'official_media_for_event', return_value=choice) as photos,
                patch.object(online,'official_image_for_event',
                             side_effect=AssertionError('Wrong image resolver')),
            ):
                online.deliver(db,client,upload=Mock(side_effect=AssertionError('Do not upload media')),
                               directory='/tmp/unneeded-official-photos',
                               news_center_threads=True,require_official_media=True,
                               media_resolver=Mock(side_effect=AssertionError('Wrong resolver')))
            photos.assert_called_once_with(original)
            client.publish.assert_called_once()
            sent_text=client.publish.call_args.args[0]
            self.assertEqual(sent_text,video_link_post(original))
            self.assertEqual(client.publish.call_args.kwargs.get('media_url'),thumbnail)
            self.assertEqual(db.execute('SELECT status FROM publish_jobs').fetchone()[0], 'posted')
            # A second run cannot repeat a delivered post.
            online.deliver(db, client, upload=Mock(), directory='/tmp/unneeded')
            client.publish.assert_called_once()
        finally:
            db.close()

    def test_official_video_without_verified_thumbnail_goes_to_review_not_uncertain(self):
        db=online.open_db(':memory:')
        try:
            original=official_event()
            with db:
                db.execute('INSERT INTO publish_jobs(key,event_json,status,text,created_at) VALUES (?,?,?,?,?)',
                           ('video-unavailable',json.dumps(original),'draft','old',time.time()))
            client=Mock(destination={'id':'channel-1'})
            with (
                patch.dict(os.environ, {'OFFICIAL_LINKS_FREE_ENABLED':'true','VIDEO_LINK_CARDS_V12':'false'}),
                patch.object(online,'official_media_for_event',
                             return_value=OfficialMediaChoice('https://example.org/logo.jpg',
                                                              'official_logo','https://example.org/logo')),
            ):
                online.deliver(db,client,upload=Mock(side_effect=AssertionError('Do not upload')),
                               directory='/tmp/unneeded-official-photos',
                               news_center_threads=True,require_official_media=True)
            record=db.execute('SELECT status,last_error,attempted_at FROM publish_jobs').fetchone()
            self.assertEqual(record['status'],'review')
            self.assertEqual(record['last_error'],'video_thumbnail_unavailable')
            self.assertEqual(record['attempted_at'],0.0)
            client.publish.assert_not_called()
            client.publish_thread.assert_not_called()
        finally:
            db.close()

if __name__ == '__main__':
    unittest.main()
