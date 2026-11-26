"""Network-free regression tests for the v13.7 RSS editorial bot."""
import os
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import patch, Mock
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

    def test_gta_series_is_labeled_as_independent_not_official(self):
        item = {'source':'GTA Series Videos','title':'GTA 6 walkthrough part 1',
                'language':'it','url':'https://youtube.com/watch?v=ABCDEFGHIJK'}
        post = bot.post_text(item)
        self.assertIn('Video community (non ufficiale)', post)
        self.assertIn('Fonte: GTA Series Videos', post)
        self.assertNotIn('Rockstar conferma', post)
        self.assertLessEqual(bot.weight_x(post), 280)

    def test_well_formed_html_is_not_a_successful_empty_feed(self):
        src = {'name': 'PowerPyx', 'domains': ['powerpyx.com']}
        with self.assertRaises(ValueError):
            list(bot.parse_feed(b'<html><body>Access unavailable</body></html>', src))

    def test_powerpyx_xml_retry_recovers_and_is_bounded(self):
        src = {'name': 'PowerPyx', 'domains': ['powerpyx.com'],
               'feed': 'https://www.powerpyx.com/feed/', 'feed_domains': ['www.powerpyx.com']}
        valid = (f'<rss><channel><item><title>GTA VI review details</title>'
                 f'<link>https://www.powerpyx.com/gta-vi/</link><pubDate>{format_datetime(NOW)}</pubDate>'
                 f'</item></channel></rss>').encode()
        for responses, expected in (([b'<rss><channel>', valid], 1),
                                    ([b'<rss><channel>', b'<rss><channel>'], 0)):
            with (patch.object(bot, '_read_feed_once', side_effect=responses) as read,
                  patch.object(bot.time, 'sleep') as delay):
                items, errors = bot.read_feeds([src], session=Mock())
                self.assertEqual(len(items), expected)
                self.assertEqual(bool(errors), not bool(expected))
                self.assertEqual(read.call_count, 2)
                self.assertEqual(read.call_args_list[0], read.call_args_list[1])
                delay.assert_called_once_with(1)

    def test_powerpyx_access_page_and_other_sources_do_not_retry(self):
        for name, raw in (('PowerPyx', b'<html><broken'), ('VGC', b'<rss><channel>')):
            src = {'name': name, 'domains': ['powerpyx.com']}
            with (patch.object(bot, '_read_feed_once', return_value=raw) as read,
                  patch.object(bot.time, 'sleep') as delay):
                items, errors = bot.read_feeds([src], session=Mock())
                self.assertFalse(items)
                self.assertEqual(errors, [name + ': ParseError'])
                read.assert_called_once()
                delay.assert_not_called()

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

    def test_media_fallback_inspects_up_to_eight_stories_not_one_open_post_slot(self):
        now=datetime(2026,11,24,19,0,tzinfo=timezone.utc)
        entries={
            'prior-'+str(i):{
                'status':'sent',
                'reserved_utc':(now-timedelta(hours=2+i)).isoformat()
            }
            for i in range(5)
        }
        state={'entries':entries,'signatures':{}}
        titles=(
            'GTA VI: dove trovare i garage di Port Gellhorn',
            'GTA VI: nuovi dettagli sugli animali di Leonida',
            'GTA VI: guida pratica alle sfide di guida',
            'GTA VI: caratteristiche HDR per console PS5',
            'GTA VI: tutorial per raggiungere i motel',
            'GTA VI: posizione dei veicoli speciali',
            'GTA VI: catalogo delle armi nel gioco',
            'GTA VI: come usare il servizio taxi'
        )
        incoming=[
            article(title=t,
                    url='https://www.videogameschronicle.com/news/media-backup-'+str(i)+'/',
                    date=now-timedelta(minutes=12))
            for i,t in enumerate(titles)
        ]
        normal=bot.select(incoming,state,now,max_posts=8)
        pool=bot.select(incoming,state,now,max_posts=8,candidate_pool=True)
        self.assertEqual(len(normal),1,'Only one ordinary day slot remains')
        self.assertGreaterEqual(len(pool),3,'Inspect independent images before giving up')
        self.assertLessEqual(len(pool),bot.MAX_MEDIA_CANDIDATES)
        self.assertEqual(len({x['key'] for x in pool}),len(pool))
        self.assertEqual(len(state['entries']),5,'No reservation in read-only selection')
        state['entries']['last']={
            'reserved_utc':(now-timedelta(hours=2)).isoformat(),'status':'sent'
        }
        self.assertEqual(bot.select(incoming,state,now,max_posts=8,candidate_pool=True),[],
                         'Candidate pool must not bypass a completely full daily budget')

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
        from urllib.parse import urlsplit
        self.assertGreaterEqual(len(bot.POWERPYX_SPOTLIGHTS), 5)
        self.assertEqual(len({r["url"] for r in bot.POWERPYX_SPOTLIGHTS}), len(bot.POWERPYX_SPOTLIGHTS))
        for record in bot.POWERPYX_SPOTLIGHTS:
            parsed = urlsplit(record['url'])
            self.assertEqual(parsed.scheme, 'https')
            self.assertIn(parsed.hostname, ('www.powerpyx.com', 'insider-gaming.com'))
            self.assertIsNone(parsed.username)
            self.assertIsNone(parsed.password)
            source = 'Insider Gaming' if parsed.hostname == 'insider-gaming.com' else 'PowerPyx'
            self.assertLessEqual(bot.weight_x(record['text']), 280)
            self.assertIn(source, record['text'])
            self.assertGreaterEqual(record['text'].count(chr(10) + chr(10)), 2)
            self.assertIn('#GTAVI', record['text'])
        first = bot.powerpyx_spotlight(self.state, now)
        expected_source = 'Insider Gaming' if urlsplit(first['url']).hostname == 'insider-gaming.com' else 'PowerPyx'
        self.assertEqual(first['source'], expected_source)
        self.assertEqual(first['key'], bot.identity(first['url']))
        self.assertIn('GTA VI', first['text'])
        self.assertIn(expected_source, first['text'])
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

    def test_launch_editorial_slots_use_local_date_and_quality_cap(self):
        now=datetime(2026,11,20,10,0,tzinfo=timezone.utc)
        old={str(i):{'reserved_utc':(now-timedelta(days=1,minutes=i)).isoformat(),
                     'status':'sent'} for i in range(16)}
        self.assertEqual(bot.editorial_day_slots(old,now),(0,16))
        self.assertEqual(bot.select([article(date=now-timedelta(minutes=10))],
                         {'entries':old,'signatures':{}},now)[0]['source'],'VGC')
        for i in range(16):
            old['new-'+str(i)]={'reserved_utc':(now-timedelta(hours=2,minutes=i)).isoformat(),
                               'status':'reserved'}
        self.assertEqual(bot.editorial_day_slots(old,now),(16,16))
        self.assertEqual(bot.select([article(date=now-timedelta(minutes=10))],
                         {'entries':old,'signatures':{}},now),[])
        steady=datetime(2026,12,3,10,tzinfo=timezone.utc)
        self.assertEqual(bot.editorial_day_slots(old,steady)[1],bot.MAX_POSTS_DAY)

    def test_photo_media_budget_matches_buffer_gate_before_mutation(self):
        from editorial_seo_v135 import x_weight
        long="GTA VI | "+"Dettagli importanti per il pubblico. "*8+"\n\n#GTAVI"
        self.assertGreater(x_weight(long),235)
        base={'thread':[long,"📖 Guida e fonte:\nhttps://xfederiko11.github.io/gta-6/collezionabili/percorsi/"],
              'media_url':"https://xfederiko11.github.io/gta-6/assets/social-cards/b445047940facf4b.jpg"}
        self.assertFalse(bot.media_thread_preflight(base))
        self.assertTrue(bot.media_thread_preflight({**base,"thread":["📚 GTA VI | Guida e copertina unica\n\n#GTAVI",base["thread"][1]]}))
        self.assertFalse(bot.media_thread_preflight({**base,'thread':[long]}))
        self.assertFalse(bot.media_thread_preflight({**base,'thread':[None,base['thread'][1]]}))
        self.assertFalse(bot.media_thread_preflight({**base,'thread':[long]*3}))

    def test_image_failure_tries_next_real_story_without_loosening_media_gate(self):
        now = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return now if tz is None else now.astimezone(tz)
        stories=[
            article(title='GTA VI: come registrare una auto a Port Gellhorn',url='https://www.videogameschronicle.com/news/fallback-a/', date=now),
            article(title='GTA VI: collezionabili e mappa di Vice City',url='https://www.videogameschronicle.com/news/fallback-b/', date=now)
        ]
        attempted=[]
        def media(item, state):
            attempted.append(item['key'])
            if len(attempted)==1:
                return None
            return {**item, 'media_url':'https://xfederiko11.github.io/gta-6/assets/social-cards/test.jpg'}
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(bot,'datetime',Clock), \
             patch.object(bot,'STATE',Path(temp)/'ledger.json'), \
             patch.object(bot,'read_feeds',return_value=(stories,[])), \
             patch.object(bot,'load_sources',return_value=[]), \
             patch.object(bot,'powerpyx_spotlight',return_value=None), \
             patch('quick_tips_v146.candidate',return_value=None), \
             patch('site_evergreen_posts_v1.candidate',return_value=None), \
             patch('trophy_posts_v142.candidate',return_value=None), \
             patch('social_media_gate_v2.prepare',side_effect=media), \
             patch.dict(os.environ,{'GITHUB_RUN_ID':'backup-test','EDITORIAL_DIRECTOR_V142_ENABLED':'false'}):
            bot.reserve()
            saved=bot.load_state()['entries']
            self.assertEqual(len(saved),1)
            self.assertEqual(len(attempted),2)
            self.assertNotEqual(attempted[0],attempted[1])
            self.assertEqual(next(iter(saved)),attempted[1])
            self.assertEqual(next(iter(saved.values()))['status'],'reserved')
            bot.reserve()
            self.assertEqual(len(bot.load_state()['entries']),1)

    def test_reservation_and_repeated_delivery_never_double_posts(self):
        now = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return now if tz is None else now.astimezone(tz)
        with tempfile.TemporaryDirectory() as temp, patch.object(bot, 'datetime', Clock), patch.object(bot, 'STATE', Path(temp)/'ledger.json'), \
             patch.object(bot, 'read_feeds', return_value=([article(date=now)], [])), \
             patch.object(bot, 'load_sources', return_value=[]), \
             patch('quick_tips_v146.candidate', return_value=None), \
             patch.object(bot, 'powerpyx_spotlight', return_value=None), \
             patch('trophy_posts_v142.candidate', return_value=None), \
             patch('growth_conversion_v1.candidate', return_value=None), \
             patch('site_evergreen_posts_v1.candidate', return_value={
                 'key':'owned-sample-key','sig':'owned-sample-sig','source':'Guide GTA VI Italia',
                 'url':'https://xfederiko11.github.io/gta-6/salvare-auto/',
                 'title':'Salvare auto',
                 'text':'🚘 GTA VI: come salvare un auto? Leggi la guida originale, con requisiti e fonti.'
             }), \
             patch('social_media_gate_v2.probe_image', return_value=True), \
             patch.dict(os.environ, {'GITHUB_RUN_ID': '123456'}):
            bot.reserve()
            bot.reserve()
            self.assertEqual(len(bot.load_state()['entries']), 1)
            entry=next(iter(bot.load_state()['entries'].values()))
            self.assertIn('/assets/social-cards/', entry['media_url'])
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
                def publish_thread(self, parts, *, media_url=None):
                    assert len(parts)==2
                    self.__class__.count += 1
                    return 'buffer-test-thread-1'
            fake.BufferClient = Client
            with patch.dict(sys.modules, {'buffer_publisher': fake}):
                bot.deliver()
                bot.deliver()
            self.assertEqual(Client.count, 1)
            self.assertEqual(next(iter(bot.load_state()['entries'].values()))['status'], 'sent')

if __name__ == '__main__':
    unittest.main()
