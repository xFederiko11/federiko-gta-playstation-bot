"""Network-free regression tests for the v13.7 RSS editorial bot."""
import os
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import patch
import sys
import types

sys.path.insert(0, str(Path(__file__).parent))
import editorial_autopilot_v137 as bot
from editorial_language_it import TranslationUnavailable

NOW = datetime(2026, 11, 18, 14, 0, tzinfo=timezone.utc)

def article(title='GTA 6: nuovi dettagli sul mondo di gioco', url='https://www.videogameschronicle.com/news/novel-details/?utm_source=x', date=None):
    return {'source': 'VGC', 'title': title, 'url': bot.canonical(url),
            'published': (date or NOW - timedelta(minutes=15)).isoformat(), 'language': 'it'}

class EditorialV137Tests(unittest.TestCase):
    def setUp(self):
        self.state = {'schema': 'v13.7', 'entries': {}, 'signatures': {}, 'run_history': []}

    def test_topics_and_ps5_exclusion(self):
        self.assertEqual(bot.topic('GTA VI review from critics'), 'GTAVI')
        self.assertEqual(bot.topic('GTA Online new heists bonuses'), 'GTAOnline')
        self.assertEqual(bot.topic('GTA+ November perks updated'), 'GTAOnline')
        self.assertIsNone(bot.topic('PS5 update 2026'))

    def test_unverified_and_spoiler_titles_blocked(self):
        for text in ('GTA VI rumored ending', 'GTA 6 leaked gameplay', 'GTA 6 may be delayed',
                     'GTA Online gift card promotion', 'GTA VI ending spoilers'):
            self.assertIsNone(bot.topic(text), text)

    def test_url_validation_and_canonicalization(self):
        self.assertEqual(bot.canonical('https://www.ign.com/articles/gta6/?utm_medium=x&fbclid=a'),
                         'https://ign.com/articles/gta6')
        for url in ('http://example.com/a', 'https://x@y.com/a', 'https://x.com:8080/test'):
            with self.assertRaises(ValueError):
                bot.canonical(url)

    def test_rss_parsing_and_host_filter(self):
        src = {'name': 'VGC', 'domains': ['videogameschronicle.com']}
        stamp = format_datetime(NOW)
        good = f'<rss><channel><item><title>GTA VI review details</title><link>https://www.videogameschronicle.com/news/a</link><pubDate>{stamp}</pubDate></item></channel></rss>'
        bad = good.replace('www.videogameschronicle.com', 'evil.example')
        self.assertEqual(len(list(bot.parse_feed(good.encode(), src))), 1)
        self.assertEqual(len(list(bot.parse_feed(bad.encode(), src))), 0)

    def test_atom_feed(self):
        src = {'name': 'VGC', 'domains': ['videogameschronicle.com']}
        atom = f'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>GTA VI review details</title><link rel="alternate" href="https://www.videogameschronicle.com/news/a"/><published>{NOW.isoformat()}</published></entry></feed>'
        self.assertEqual(len(list(bot.parse_feed(atom.encode(), src))), 1)

    def test_freshness_and_day_limit(self):
        self.assertEqual(bot.select([article(date=NOW-timedelta(hours=13))], self.state, NOW), [])
        self.assertEqual(bot.select([article(date=NOW+timedelta(minutes=5))], self.state, NOW), [])
        for i in range(bot.MAX_POSTS_DAY):
            self.state['entries'][str(i)] = {'reserved_utc': NOW.isoformat()}
        self.assertEqual(bot.select([article()], self.state, NOW), [])

    def test_time_spacing(self):
        self.state['entries']['x'] = {'reserved_utc': (NOW-timedelta(minutes=5)).isoformat()}
        self.assertEqual(bot.select([article()], self.state, NOW), [])

    def test_duplicate_detection(self):
        candidate = article()
        self.assertEqual(len(bot.select([candidate, candidate], self.state, NOW, max_posts=5)), 1)
        self.state['entries'][bot.identity(candidate['url'])] = {'status': 'sent'}
        self.assertEqual(bot.select([candidate], self.state, NOW), [])

    def test_bridge_article_suppression(self):
        old = article(url='https://www.videogameschronicle.com/review/grand-theft-auto-6/')
        self.assertEqual(bot.select([old], self.state, NOW), [])

    def test_keywords_attribution_character_budget(self):
        text = bot.post_text(article())
        self.assertIn('Fonte: VGC\nhttps://', text)
        self.assertIn('#GTAVI', text)
        self.assertIn('VGC', text)
        self.assertLessEqual(bot.weight_x(text), 280)
        long_title = 'GTA VI ' + 'nuovi dettagli sul gioco e sulla città di Leonida ' * 10
        self.assertLessEqual(bot.weight_x(bot.post_text(article(title=long_title))), 280)

    def test_italian_paragraphs_source_and_hashtags(self):
        result = bot.post_text(article())
        self.assertIn('Novità\n\n', result)
        self.assertIn('\n\n🔗 Fonte: VGC\n', result)
        self.assertIn('\n\n#GTAVI #GTA6', result)
        self.assertNotIn('new world details', result)

    def test_fail_closed_on_english_title_translation_failure(self):
        event = article(title='GTA VI: New gameplay features revealed')
        event['language'] = 'en'
        with patch.object(bot, 'italian_title', side_effect=TranslationUnavailable('Offline')):
            with self.assertRaises(TranslationUnavailable):
                bot.post_text(event)

    def test_english_title_translation_is_used_in_output(self):
        event = article(title='GTA VI: New gameplay details')
        event['language'] = 'en'
        with patch.object(bot, 'italian_title', return_value='GTA VI: nuovi dettagli sul gameplay'):
            output = bot.post_text(event)
        self.assertIn('nuovi dettagli sul gameplay', output)
        self.assertNotIn('New gameplay details', output)

    def test_powerpyx_spotlights_verified_links_and_italian_format(self):
        now = datetime(2026, 11, 18, 20, 0, tzinfo=timezone.utc)
        self.assertEqual(len(bot.POWERPYX_SPOTLIGHTS), 4)
        for record in bot.POWERPYX_SPOTLIGHTS:
            self.assertTrue(record['url'].startswith('https://www.powerpyx.com/'))
            self.assertLessEqual(bot.weight_x(record['text']), 280)
            self.assertIn('PowerPyx', record['text'])
            self.assertGreaterEqual(record['text'].count(chr(10) + chr(10)), 2)
            self.assertIn('#GTAVI', record['text'])
        first = bot.powerpyx_spotlight(self.state, now)
        self.assertEqual(first['source'], 'PowerPyx')
        self.assertEqual(first['key'], bot.identity(first['url']))
        self.assertIn('🏆', first['text'])
        self.assertIsNone(bot.powerpyx_spotlight(self.state,
                         datetime(2026, 11, 24, tzinfo=timezone.utc)))

    def test_powerpyx_spotlights_use_shared_ledger_and_spacing(self):
        now = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
        first = bot.powerpyx_spotlight(self.state, now)
        self.state['entries'][first['key']] = {
            'source': 'PowerPyx', 'reserved_utc': now.isoformat(), 'status': 'sent'}
        self.assertIsNone(bot.powerpyx_spotlight(self.state, now + timedelta(minutes=90)))
        second = bot.powerpyx_spotlight(self.state, now + timedelta(minutes=121))
        self.assertIsNotNone(second)
        self.assertNotEqual(second['key'], first['key'])
        self.state['entries'][second['key']] = {
            'source': 'PowerPyx', 'reserved_utc': (now + timedelta(minutes=121)).isoformat(),
            'status': 'uncertain'}
        self.assertIsNone(bot.powerpyx_spotlight(self.state,
                          now + timedelta(minutes=123)))

    def test_reservation_and_repeated_delivery_never_double_posts(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as temp, patch.object(bot, 'STATE', Path(temp)/'ledger.json'), \
             patch.object(bot, 'read_feeds', return_value=([article(date=now)], [])), \
             patch.object(bot, 'load_sources', return_value=[]), \
             patch('quick_tips_v146.candidate', return_value=None), \
             patch.object(bot, 'powerpyx_spotlight', return_value=None), \
             patch('trophy_posts_v142.candidate', return_value=None), \
             patch.dict(os.environ, {'GITHUB_RUN_ID': '123456'}):
            bot.reserve()
            bot.reserve()
            self.assertEqual(len(bot.load_state()['entries']), 1)
            fake = types.ModuleType('buffer_publisher')
            fake.BufferAPIError = type('BufferAPIError', (Exception,), {'outcome_unknown': False, 'post_id': None})
            fake.BufferPending = type('BufferPending', (fake.BufferAPIError,), {})
            class Client:
                count = 0
                def __init__(self, **kwargs):
                    pass
                def verify_destination(self):
                    return True
                def publish(self, text):
                    self.__class__.count += 1
                    return 'buffer-test-1'
            fake.BufferClient = Client
            with patch.dict(sys.modules, {'buffer_publisher': fake}):
                bot.deliver()
                bot.deliver()
            self.assertEqual(Client.count, 1)
            self.assertEqual(next(iter(bot.load_state()['entries'].values()))['status'], 'sent')

if __name__ == '__main__':
    unittest.main()
