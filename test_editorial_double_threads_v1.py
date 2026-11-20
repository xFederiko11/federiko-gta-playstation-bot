"""Safe, attributed two-message thread conversion regression."""
import unittest
from editorial_double_threads_v1 import double,clean_headline,reply_for
from editorial_seo_v135 import x_weight

class DoubleThreadTests(unittest.TestCase):
    def test_feed_moves_url_to_first_reply_without_inventing_steps(self):
        item={'source':'VGC','title':'GTA VI nuova notizia','url':'https://www.videogameschronicle.com/news/test',
              'text':'📰 GTA VI | Novità\n\nNovità sul mondo di gioco\n\n🔗 Fonte: VGC\nhttps://www.videogameschronicle.com/news/test\n\n#GTAVI #GTA6'}
        result=double(item)
        self.assertEqual(len(result['thread']),2)
        self.assertIn('Novità sul mondo di gioco',result['thread'][0])
        self.assertIn(item['url'],result['thread'][1])
        self.assertNotIn('https://',result['thread'][0])
        self.assertNotIn('mappa',result['thread'][0].lower())
        self.assertEqual(result['source'],item['source'])
        self.assertLessEqual(max(map(x_weight,result['thread'])),280)

    def test_curated_photo_thread_is_preserved_unchanged(self):
        item={'source':'PowerPyx Tips','url':'https://www.powerpyx.com/gta-6-test/',
              'title':'PS5', 'text':'Source',
              'thread':['📍 Azione verificata\n#GTAVI','📖 Fonte: PowerPyx\nhttps://www.powerpyx.com/gta-6-test/'],
              'media_url':'https://www.rockstargames.com/VI/test.jpg'}
        self.assertEqual(double(item),item)

    def test_real_evergreen_moves_guide_to_reply(self):
        item={'source':'Guide GTA VI Italia','url':'https://xfederiko11.github.io/gta-6/salvare-auto/',
              'title':'Salvare auto','text':'🚙 GTA VI | AUTO\n\nControlla tracker e garage.\n\n📍 Passaggi e fonte:\nhttps://xfederiko11.github.io/gta-6/salvare-auto/\n\n#GTAVI'}
        result=double(item)
        self.assertIn('tracker',result['thread'][0])
        self.assertIn('spoiler',result['thread'][1])
        self.assertIn('https://xfederiko11',result['thread'][1])

    def test_invalid_or_over_budget_fails_closed(self):
        item={'source':'VGC','url':'https://user@example.org/private','title':'Error','text':'Test'}
        with self.assertRaises(ValueError):double(item)
        item['url']='https://example.org/valid'
        item['text']='Un titolo completo molto lungo ' * 40
        with self.assertRaises(ValueError):double(item)
        with self.assertRaises(ValueError):double({**item,'thread':['Solo uno']})

    def test_facts_not_truncated_for_decorative_images(self):
        item={'source':'VGC','url':'https://www.videogameschronicle.com/news/a',
              'title':'Specifiche','text':('Fatti verificati nelle note ufficiali. '*8).strip(),
              'media_url':'https://www.rockstargames.com/VI/test.jpg'}
        result=double(item)
        self.assertEqual(len(result['thread']),2)
        self.assertIsNone(result['media_url'])

if __name__=='__main__':
    unittest.main()
