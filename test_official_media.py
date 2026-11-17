"""Security/content and Buffer GraphQL tests for authentic publisher media."""
import json
import unittest
from unittest.mock import Mock

import online
from buffer_publisher import BufferClient
from official_media import (OfficialMediaUnavailable, approved_image_url,
                            image_from_official_html, official_image_for_event,
                            youtube_thumbnail)


class ResponseImage:
    def __init__(self, content=b'\xff\xd8\xff' + b'a' * 32, status=200, kind='image/jpeg', length='200000'):
        self.status_code = status
        self.headers = {'Content-Type': kind, 'Content-Length': length}
        self.content = content
        self.text = content.decode('latin-1')
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def iter_content(self, chunk_size):
        yield self.content[:chunk_size]


class OfficialMediaTests(unittest.TestCase):
    def test_extracts_only_genuine_official_image_from_rockstar(self):
        article = 'https://www.rockstargames.com/newswire/article/123'
        html = '<meta property="og:image" content="https://media-rockstargames-com.akamaized.net/news/photo.jpg">'
        self.assertEqual(image_from_official_html(html, article),
                         'https://media-rockstargames-com.akamaized.net/news/photo.jpg')
        self.assertIsNone(image_from_official_html('<meta property="og:image" content="https://fakesite.example/photo.jpg">', article))

    def test_unapproved_or_unstable_urls_rejected(self):
        for image in ('http://media-rockstargames-com.akamaized.net/a.jpg',
                      'https://media-rockstargames-com.akamaized.net.evil.test/a.jpg',
                      'https://cdn.playstation.com/branding/logo.png',
                      'https://cdn.playstation.com/a.jpg?token=secret',
                      'https://localhost/private.png'):
            self.assertFalse(approved_image_url(image, 'sony' if 'playstation.com' in image else 'rockstar'), image)

    def test_youtube_thumbnail_only_for_official_channel(self):
        source = 'https://www.youtube.com/watch?v=ABCDEFGHIjk'
        self.assertEqual(youtube_thumbnail(source, 'UC6VcWc1rAoWdBCM0JxrRQ3A'),
                         'https://i.ytimg.com/vi/ABCDEFGHIjk/hqdefault.jpg')
        self.assertIsNone(youtube_thumbnail(source, 'fake-channel'))

    def test_verifies_authentic_jpeg_and_rejects_html(self):
        event = {'trust': 'official', 'source_url': 'https://www.rockstargames.com/newswire/article/123',
                 'official_image_url': 'https://media-rockstargames-com.akamaized.net/news/photo.jpg'}
        sess = Mock()
        sess.get.return_value = ResponseImage()
        self.assertEqual(official_image_for_event(event, session=sess), event['official_image_url'])
        sess.get.return_value = ResponseImage(content=b'<html>fake</html>', kind='text/html')
        with self.assertRaises(OfficialMediaUnavailable):
            official_image_for_event(event, session=sess)

    def test_missing_media_prevents_any_publication(self):
        db = online.open_db(':memory:')
        try:
            event = {'event_key': 'missing-media', 'game': 'GTA VI', 'category': 'NEWS',
                     'data_kind': 'announcement', 'region': 'EU', 'platforms': ['PS5'],
                     'title': 'Official', 'facts': [{'label': 'Dato', 'value': 'Sì'}],
                     'trust': 'official', 'source_url': 'https://www.rockstargames.com/newswire/article/1'}
            with db:
                db.execute('INSERT INTO posts(key,source_id,source_json) VALUES (?,?,?)',
                           ('missing-media', 'missing-media', json.dumps({'key':'missing-media', 'presentation': event, 'trust':'official'})))
            online.prepare_jobs(db, {'scope': 'gta', 'sources': []})
            publisher, uploader, renderer = Mock(), Mock(), Mock()
            def missing(_): raise OfficialMediaUnavailable('no_verified_official_image')
            online.deliver(db, publisher, uploader, '/tmp', render=renderer,
                           require_official_media=True, media_resolver=missing)
            row = db.execute('SELECT status,last_error FROM publish_jobs').fetchone()
            self.assertEqual(tuple(row), ('review', 'no_verified_official_image'))
            publisher.publish.assert_not_called()
            publisher.publish_thread.assert_not_called()
            renderer.assert_not_called()
            uploader.assert_not_called()
        finally:
            db.close()

    def test_official_image_passed_directly_on_single_post_without_generated_card(self):
        db = online.open_db(':memory:')
        try:
            event = {'event_key': 'official-1', 'game': 'GTA Online', 'category': 'NEWS',
                     'data_kind': 'announcement', 'region': 'EU', 'platforms': ['PS5'],
                     'title': 'Official', 'facts': [{'label':'Dato', 'value':'Sì'}],
                     'trust': 'official', 'source_url': 'https://www.rockstargames.com/newswire/article/1'}
            with db:
                db.execute('INSERT INTO posts(key,source_id,source_json) VALUES (?,?,?)',
                           ('official-1','official-1',json.dumps({'key':'official-1','presentation':event,'trust':'official'})))
            online.prepare_jobs(db, {'scope':'gta','sources':[]})
            client, upload, render = Mock(), Mock(), Mock()
            client.publish.return_value = 'buffer1'
            client.last_delivery = Mock(external_url='https://x.com/test/1')
            link = 'https://media-rockstargames-com.akamaized.net/news/photo.jpg'
            online.deliver(db, client, upload, '/tmp', render=render, require_official_media=True,
                           media_resolver=lambda ev: link)
            self.assertEqual(client.publish.call_args.kwargs['media_url'], link)
            render.assert_not_called()
            upload.assert_not_called()
            self.assertEqual(db.execute('SELECT status FROM publish_jobs').fetchone()[0], 'posted')
        finally:
            db.close()

    def test_first_post_of_thread_has_image_not_top_level(self):
        session = Mock()
        session.post.side_effect = [Mock(status_code=200, headers={}, json=lambda: {'data': {'channel': {
            'id':'ch', 'name':'myfan','service':'twitter','isDisconnected':False,'isLocked':False,
            'isQueuePaused':False,'externalLink':'https://x.com/myfan'}}}),
            Mock(status_code=200, headers={}, json=lambda: {'data': {'createPost': {'post': {
                'id':'buf1','status':'sent','channelId':'ch','externalLink':'https://x.com/myfan/status/1'}}}})]
        client = BufferClient('fake', 'ch', 'myfan', session=session)
        image = 'https://media-rockstargames-com.akamaized.net/news/photo.jpg'
        client.publish_thread(['First', 'Second'], media_url=image)
        value = session.post.call_args.kwargs['json']['variables']['input']
        self.assertEqual(value['assets'], [])
        self.assertEqual(value['metadata']['twitter']['thread'][0]['assets'], [{'image':{'url':image}}])
        self.assertEqual(value['metadata']['twitter']['thread'][1]['assets'], [])

if __name__ == '__main__':
    unittest.main()
