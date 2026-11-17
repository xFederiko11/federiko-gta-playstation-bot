"""Official-logo last resort: test ranking, provenance and safety offline."""
import unittest
from unittest.mock import Mock

from official_media import (
    GTA_VI_LOGO, PLAYSTATION_LOGO, OfficialMediaUnavailable,
    approved_logo_url, official_media_for_event,
)


class Response:
    def __init__(self, content, status=200, content_type='text/html'):
        self.status_code = status
        self.content = content
        self.text = content.decode('utf-8', 'replace')
        self.headers = {'Content-Type': content_type, 'Content-Length': str(len(content))}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def iter_content(self, chunk_size):
        yield self.content[:chunk_size]


LOGO_DATA = b'\x89PNG\r\n\x1a\n' + (b'x' * 2048)
PHOTO_DATA = b'\xff\xd8\xff' + (b'x' * 20000)


class LogoFallbackTests(unittest.TestCase):
    def event(self, game='GTA VI', source='https://www.rockstargames.com/newswire/article/123', **kwargs):
        return dict(trust='official', game=game, source_url=source, **kwargs)

    def test_priority_editorial_image_beats_brand_logo(self):
        photo = 'https://media-rockstargames-com.akamaized.net/abc.jpg'
        session = Mock()
        session.get.return_value = Response(PHOTO_DATA, content_type='image/jpeg')
        choice = official_media_for_event(self.event(official_image_url=photo), session=session)
        self.assertEqual((choice.url, choice.kind), (photo, 'editorial_image'))
        self.assertEqual(session.get.call_count, 1)

    def test_social_photo_on_article_beats_logo(self):
        url = 'https://www.rockstargames.com/newswire/article/123'
        photo = 'https://media-rockstargames-com.akamaized.net/news/official-image.jpg'
        html = f'<meta property="og:image" content="{photo}">'.encode()
        session = Mock()
        session.get.side_effect = [Response(html), Response(PHOTO_DATA, content_type='image/jpeg')]
        choice = official_media_for_event(self.event(source=url), session=session)
        self.assertEqual((choice.url, choice.kind), (photo, 'editorial_image'))

    def test_article_photo_is_checked_before_fallback_logo(self):
        photo = 'https://media-rockstargames-com.akamaized.net/article/photo.jpg'
        html = f'<article><img alt="Vice City" width="1024" height="768" src="{photo}"></article>'.encode()
        session = Mock()
        session.get.side_effect = [Response(html), Response(PHOTO_DATA, content_type='image/jpeg')]
        choice = official_media_for_event(self.event(), session=session)
        self.assertEqual(choice.url, photo)
        self.assertEqual(choice.kind, 'editorial_image')

    def test_gta_vi_logo_only_as_last_resort(self):
        session = Mock()
        session.get.side_effect = [Response(b'<html><body>No photo</body></html>'), Response(LOGO_DATA, content_type='image/png')]
        choice = official_media_for_event(self.event(), session=session)
        self.assertEqual(choice.kind, 'official_logo')
        self.assertEqual(choice.url, GTA_VI_LOGO)
        self.assertIn('rockstargames.com', choice.credit_url)
        self.assertEqual(session.get.call_count, 2)

    def test_sony_logo_last_for_ps5_but_not_gta_logo(self):
        session = Mock()
        session.get.side_effect = [Response(b'<html>No photo</html>'), Response(LOGO_DATA, content_type='image/png')]
        choice = official_media_for_event(self.event(game='PlayStation', source='https://www.playstation.com/it-it/support/hardware/ps5/system-software-info/'), session=session)
        self.assertEqual(choice.kind, 'official_logo')
        self.assertEqual(choice.url, PLAYSTATION_LOGO)

    def test_no_gta_vi_logo_for_gta_online(self):
        session = Mock()
        session.get.return_value = Response(b'<html>No photo</html>')
        with self.assertRaisesRegex(OfficialMediaUnavailable, 'no_verified_official_image_or_logo'):
            official_media_for_event(self.event(game='GTA Online', title='GTA+ bonuses'), session=session)
        self.assertEqual(session.get.call_count, 1)

    def test_non_official_event_cannot_receive_logo(self):
        event = dict(self.event(), trust='community')
        with self.assertRaisesRegex(OfficialMediaUnavailable, 'event_not_official'):
            official_media_for_event(event, session=Mock())

    def test_logo_host_is_strict_allowlist(self):
        self.assertTrue(approved_logo_url(GTA_VI_LOGO, 'rockstar'))
        self.assertTrue(approved_logo_url(PLAYSTATION_LOGO, 'sony'))
        self.assertFalse(approved_logo_url('https://blog.playstation.com/fake_logo.png', 'sony'))
        self.assertFalse(approved_logo_url(GTA_VI_LOGO, 'sony'))
        self.assertFalse(approved_logo_url(PLAYSTATION_LOGO, 'rockstar'))

    def test_no_publication_when_logo_fails_validation(self):
        session = Mock()
        session.get.side_effect = [Response(b'<html>No photo</html>'), Response(b'<!doctype html>', content_type='text/html')]
        with self.assertRaises(OfficialMediaUnavailable):
            official_media_for_event(self.event(), session=session)

    def test_no_redirect_accepted_as_logo(self):
        session = Mock()
        session.get.side_effect = [Response(b'<html>No photo</html>'), Response(LOGO_DATA, status=302, content_type='image/png')]
        with self.assertRaises(OfficialMediaUnavailable):
            official_media_for_event(self.event(), session=session)


if __name__ == '__main__':
    unittest.main()
