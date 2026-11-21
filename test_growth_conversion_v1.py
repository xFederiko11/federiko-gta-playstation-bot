"""Offline tests: original community posts and manual-only mobile social desk."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote
import unittest
from growth_conversion_v1 import PROMPTS,validate,candidate
from growth_social_desk_v2 import parse_verified,render,render_file

NOW=datetime(2026,11,20,9,15,tzinfo=timezone.utc)
POST_ID="2123704147768246272"

class GrowthConversionTests(unittest.TestCase):
    def test_12_unique_sourced_questions_with_exactly_one_question(self):
        self.assertTrue(validate())
        self.assertEqual(len(PROMPTS),12)
        self.assertEqual(len({p['path'] for p in PROMPTS}),12)
        self.assertTrue(all(p['text'].count('?')==1 for p in PROMPTS))
        from editorial_double_threads_v1 import double
        from editorial_seo_v135 import x_weight
        from editorial_autopilot_v137 import media_thread_preflight
        first=candidate({'entries':{}},datetime(2026,11,21,13,tzinfo=timezone.utc),
                        live_checker=lambda _:True)
        packaged=double(first)
        photo={**packaged,'media_url':'https://xfederiko11.github.io/gta-6/assets/social-cards/b445047940facf4b.jpg'}
        self.assertLessEqual(x_weight(photo['thread'][0]),235)
        self.assertTrue(media_thread_preflight(photo))

    def test_one_original_question_in_existing_launch_slots(self):
        now=datetime(2026,11,21,13,0,tzinfo=timezone.utc)
        ledger={'entries':{}}
        calls=[]
        item=candidate(ledger,now,live_checker=lambda url:calls.append(url) or True)
        self.assertIsNotNone(item)
        self.assertTrue(item['tip_id'].startswith('growth-question-'))
        self.assertEqual(item['source'],'Guide GTA VI Italia')
        self.assertEqual(len(calls),1)
        ledger['entries'][item['key']]={'reserved_utc':now.isoformat(),'url':item['url'],
                                      'status':'sent','tip_id':item['tip_id']}
        self.assertIsNone(candidate(ledger,now+timedelta(minutes=20),live_checker=lambda url:True))
        self.assertIsNone(candidate({'entries':{}},datetime(2026,11,21,8,tzinfo=timezone.utc),
                                    live_checker=lambda url:True))
        self.assertIsNone(candidate({'entries':{}},datetime(2026,12,3,13,tzinfo=timezone.utc),
                                    live_checker=lambda url:True))
        self.assertIsNone(candidate({'entries':{}},now,live_checker=lambda url:False))

    def test_verified_ps5_photo_hub_replaces_existing_launch_slot_without_extra_posts(self):
        from growth_conversion_v1 import FIRST_DAY
        from editorial_double_threads_v1 import double
        from owned_utm_attribution_v1 import tagged_site_url
        from editorial_seo_v135 import x_weight
        self.assertEqual(FIRST_DAY.isoformat(),"2026-11-21")
        self.assertEqual(len(PROMPTS),12)
        prompt=PROMPTS[1]
        self.assertEqual(prompt["id"],"ps5-original-screenshots")
        self.assertEqual(prompt["path"],"/screenshot-ps5/")
        self.assertIn("55 richieste fotografiche",prompt["text"])
        self.assertNotIn("già ricevute",prompt["text"])
        self.assertNotIn("foto già inviate",prompt["text"])
        self.assertEqual(prompt["text"].count("?"),1)
        now=datetime(2026,11,22,13,0,tzinfo=timezone.utc)
        examined=[]
        item=candidate({"entries":{}},now,
                       live_checker=lambda url: examined.append(url) or True)
        expected="https://xfederiko11.github.io/gta-6/screenshot-ps5/"
        self.assertIsNotNone(item)
        self.assertEqual(examined,[expected])
        self.assertEqual(item["url"],expected)
        self.assertEqual(item["source"],"Guide GTA VI Italia")
        self.assertEqual(item["tip_id"],"growth-question-ps5-original-screenshots")
        result=double(item)
        self.assertEqual(result["url"],expected)
        self.assertEqual(len(result["thread"]),2)
        self.assertLessEqual(x_weight(result["thread"][0]),280)
        self.assertLessEqual(x_weight(result["thread"][1]),280)
        self.assertIn(tagged_site_url(expected,placement="community_question"),result["thread"][1])
        self.assertNotIn("utm_",result["thread"][0])
        self.assertIsNone(candidate({"entries":{}},now,live_checker=lambda url:False))
        state={"entries":{item["key"]:{
            "url":item["url"],"reserved_utc":now.isoformat(),
            "status":"sent","tip_id":item["tip_id"]}}}
        self.assertIsNone(candidate(state,now+timedelta(minutes=30),
                                    live_checker=lambda url:True))

    def test_real_world_ledger_with_null_tip_id_does_not_crash_reservation(self):
        # Production 21 Nov 2026: None was persisted for a non-growth entry.
        now=datetime(2026,11,21,13,0,tzinfo=timezone.utc)
        state={"entries":{
            "previous-guide":{"tip_id":None,"url":None,"reserved_utc":now.isoformat(),
                              "status":"sent","source":"Guide GTA VI Italia"},
            "previous-news":{"tip_id":None,"url":"https://example.org/news/",
                             "reserved_utc":(now-timedelta(days=2)).isoformat(),
                             "status":"sent"}
        }}
        row=candidate(state,now,live_checker=lambda _:True)
        self.assertIsNotNone(row)
        self.assertTrue(row["tip_id"].startswith("growth-question-"))
        state["entries"]["past"]={"tip_id":row["tip_id"],"url":row["url"],
                                   "reserved_utc":now.isoformat(),"status":"sent"}
        self.assertIsNone(candidate(state,now,live_checker=lambda _:True))

    def test_map_widget_campaign_uses_existing_editorial_slot_on_november_23(self):
        from editorial_double_threads_v1 import double
        from editorial_seo_v135 import x_weight
        now=datetime(2026,11,23,13,0,tzinfo=timezone.utc)
        item=candidate({'entries':{}},now,live_checker=lambda url:True)
        self.assertIsNotNone(item)
        self.assertEqual(item['tip_id'],'growth-question-mappe-interattive-ps5')
        self.assertEqual(item['url'],'https://xfederiko11.github.io/gta-6/mappe-guide/')
        thread=double(item)
        self.assertLessEqual(x_weight(thread['thread'][0]),235)
        self.assertIn('mappe-guide/',thread['thread'][1])
        self.assertIn('Non è il pin esatto',thread['thread'][0])
        self.assertEqual(len(thread['thread']),2)

    def test_dedup_same_guide_even_if_previous_workflow(self):
        now=datetime(2026,11,21,14,0,tzinfo=timezone.utc)
        initial=candidate({'entries':{}},now,live_checker=lambda url:True)
        ledger={'entries':{'from-news':{'status':'scheduled','url':initial['url'],
                                       'reserved_utc':(now-timedelta(hours=3)).isoformat()}}}
        self.assertIsNone(candidate(ledger,now,live_checker=lambda url:True))

class SocialDeskTests(unittest.TestCase):
    def test_verified_real_x_post_with_exact_matching_reply_id(self):
        url='https://x.com/GTAhelper/status/'+POST_ID
        reply='For the platino, verify the required mission before advancing.'
        intent='https://x.com/intent/tweet?in_reply_to='+POST_ID+'&text='+quote(reply,safe='')
        md='[Apri tweet / metti cuore]('+url+') | [Apri risposta precompilata]('+intent+')'
        found=parse_verified(md,NOW)
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]['url'],url)
        self.assertEqual(found[0]['reply'],reply)
        self.assertIn('Rispondi con bozza',render(md,NOW))
        self.assertIn('Tweet reali da valutare',render(md,NOW))
        self.assertNotIn('Buffer Scheduled',render(md,NOW))
        self.assertEqual(parse_verified(md, NOW+timedelta(days=4)),[])
        self.assertEqual(parse_verified(md.replace('in_reply_to='+POST_ID,'in_reply_to=9876543210000000000'), NOW),[])

    def test_invalid_sources_and_repetitions_fall_back_to_searches(self):
        url='https://x.com/GTAhelper/status/'+POST_ID
        md='[Apri tweet / metti cuore]('+url+') | [Apri risposta precompilata](https://evil.test/intent/tweet?in_reply_to='+POST_ID+'&text=spam)'
        self.assertEqual(parse_verified(md,NOW),[])
        self.assertIn('Nessun tweet specifico verificabile',render(md,NOW))
        self.assertIn('Soldi iniziali',render(md,NOW))
        self.assertIn('Auto rare e garage',render(md,NOW))
        self.assertNotIn('https://evil.test',render(md,NOW))
        with TemporaryDirectory() as d:
            self.assertIn('non confermati' if False else 'non tweet confermati',
                render_file(Path(d)/'missing.md',NOW))
        with self.assertRaises(ValueError):
            parse_verified('',datetime(2026,11,20,9))

if __name__=='__main__':
    unittest.main()
