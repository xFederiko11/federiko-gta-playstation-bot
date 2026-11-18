"""Network-free validation of all 55 trophy pages, spoiler SEO and X cards."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock
from editorial_seo_v135 import x_weight
import trophy_posts_v142 as posts

DATA=json.loads(Path("trophies-gta6-v142.json").read_text(encoding="utf-8"))["trophies"]

class TrophySiteTests(unittest.TestCase):
    def test_verified_55_trophies_and_hidden_count(self):
        self.assertEqual(len(DATA),55)
        self.assertEqual(len({x['id'] for x in DATA}),55)
        self.assertEqual(sum(x['hidden'] for x in DATA),28)
        self.assertEqual({k:sum(t['tier']==k for t in DATA) for k in ('Platino','Oro','Argento','Bronzo')},
                         {'Platino':1,'Oro':2,'Argento':6,'Bronzo':46})
        self.assertEqual(DATA[6]['tier'],'Oro')
        self.assertEqual(DATA[13]['tier'],'Oro')

    def test_every_trophy_has_italian_caption_and_valid_length(self):
        for trophy in DATA:
            text=posts.formatted(trophy)
            self.assertLessEqual(x_weight(text),280,(trophy['number'],text))
            self.assertIn('🎯',text)
            self.assertIn(trophy['id']+'.html',text)
            self.assertIn('\n\n',text)
            self.assertIn('#GTAVI',text)

    def test_images_official_and_indicated_as_illustrative(self):
        for image in posts.PHOTOS:
            self.assertTrue(image.startswith('https://www.rockstargames.com/VI/_next/static/media/'))
        for t in DATA:
            self.assertIn(t['photo_group'],('city','landscapes','characters'))

    def test_pages_builder_creates_55_distinct_html_pages(self):
        with tempfile.TemporaryDirectory() as temp:
            env=dict(os.environ,TROPHY_OUTPUT_DIR=temp)
            result=subprocess.run([sys.executable,'build_trophy_site_v142.py'],
                                  env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(len(list(Path(temp).glob("trofeo-*.html"))),55)
            homepage=(Path(temp)/'index.html').read_text(encoding='utf-8')
            self.assertIn('tutti i 55 trofei',homepage)
            self.assertIn('<details>',homepage)
            self.assertIn('application/ld+json',homepage)
            golden=(Path(temp)/'trofeo-14.html').read_text(encoding='utf-8')
            self.assertIn('Oro',golden)
            self.assertIn('rel="canonical"',golden)
            self.assertIn('Screenshot',golden)
            hidden=(Path(temp)/'trofeo-07.html').read_text(encoding='utf-8')
            self.assertIn('noindex,follow',hidden)
            sitemap=(Path(temp)/'sitemap.xml').read_text(encoding='utf-8')
            self.assertEqual(sitemap.count('<url>'),29)
            gold=(Path(temp)/'guida-medaglie-oro.html').read_text(encoding='utf-8')
            self.assertIn('42 medaglie Oro',gold)
            self.assertIn('non prevede medaglie Oro per le missioni',gold)

    def test_only_two_trophy_posts_each_utc_day_and_no_old_duplication(self):
        from datetime import datetime, timezone, timedelta
        import trophy_posts_v142
        now=datetime(2026,11,21,21,0,tzinfo=timezone.utc)
        state={'entries':{}}
        first=trophy_posts_v142.candidate(state,now)
        self.assertIsNotNone(first)
        self.assertEqual(first['trophy_number'],14)
        state['entries'][first['key']]={'reserved_utc':now.isoformat(),
                                       'source':'Trofei GTA VI','status':'sent'}
        self.assertIsNone(trophy_posts_v142.candidate(state,now+timedelta(minutes=5)))
        next_item=trophy_posts_v142.candidate(state,now+timedelta(minutes=161))
        self.assertIsNotNone(next_item)
        self.assertNotEqual(first['key'],next_item['key'])
        next_time=now+timedelta(minutes=161)
        state['entries'][next_item['key']]={'reserved_utc':next_time.isoformat(),
                                            'source':'Trofei GTA VI','status':'uncertain'}
        self.assertIsNone(trophy_posts_v142.candidate(state,next_time+timedelta(hours=4)))

    def test_pages_health_cannot_invent_live_publication(self):
        fake=Mock()
        fake.get.side_effect=OSError('No network')
        self.assertFalse(posts.landing_live(session=fake))

if __name__=='__main__':
    unittest.main()
