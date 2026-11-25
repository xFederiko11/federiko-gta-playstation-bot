from datetime import datetime,timedelta,timezone
from unittest import TestCase
from tempfile import TemporaryDirectory
from pathlib import Path
import json
from site_article_rotation_v1 import (load,plans,BASE,SOURCE,measured_interest,
                                      ArticleCover,candidate,authorize,delivery_authorized)
from social_media_gate_v2 import cover_for

NOW=datetime(2026,12,30,12,tzinfo=timezone.utc)
URL=BASE+"guide-e-tutorial/scansionare-veicoli/"

class RotationTests(TestCase):
    def setUp(self):
        self.cfg=load()
        self.cfg["enabled"]=False
        self.cfg["articles"]=self.cfg["articles"][:1]
        self.state={"entries":{"old":{"url":URL,"status":"sent","text":"Old post",
                     "media_url":cover_for(URL),"reserved_utc":(NOW-timedelta(days=10)).isoformat()}}}
    def test_disabled_until_review(self):
        self.assertEqual(plans(self.state,NOW,config=self.cfg),[])
    def test_intervals_and_new_copy(self):
        self.cfg.update(enabled=True,released_utc=(NOW-timedelta(days=1)).isoformat())
        result=plans(self.state,NOW,config=self.cfg)[0]
        self.assertEqual(result["rotation_reason"],"updated")
        self.assertEqual(result["media_url"],cover_for(URL))
        self.assertEqual(plans({"entries":{}},NOW,config=self.cfg),[])
        self.cfg["released_utc"]=(NOW-timedelta(days=50)).isoformat()
        self.assertEqual(plans(self.state,NOW,config=self.cfg),[])
        self.state["entries"]["old"]["reserved_utc"]=(NOW-timedelta(days=15)).isoformat()
        self.assertEqual(plans(self.state,NOW,config=self.cfg,interest={URL:3})[0]["rotation_reason"],"measured_interest")
        self.state["entries"]["old"]["reserved_utc"]=(NOW-timedelta(days=31)).isoformat()
        item=plans(self.state,NOW,config=self.cfg)[0]
        self.assertEqual(item["rotation_reason"],"periodic")
        self.state["entries"][item["key"]]=dict(item,status="sent",reserved_utc=NOW.isoformat())
        self.assertEqual(plans(self.state,NOW,config=self.cfg),[])
        later=plans(self.state,NOW+timedelta(days=31),config=self.cfg)[0]
        self.assertNotEqual(later["key"],item["key"])
        self.assertNotEqual(later["text"],item["text"])
    def test_pending_blocks_rotation(self):
        self.cfg.update(enabled=True,released_utc=(NOW-timedelta(days=1)).isoformat())
        self.state["entries"]["uncertain"]={"url":URL,"status":"uncertain"}
        self.assertEqual(plans(self.state,NOW,config=self.cfg),[])

    def test_real_interest_requires_recent_verified_permalink(self):
        with TemporaryDirectory() as d:
            csv=Path(d)/"metrics.csv"
            receipts=Path(d)/"receipts.json"
            permalink="https://x.com/xFederiko11/status/123456789"
            receipt={"article_url":URL,"x_url":permalink,
                     "verified_by":"Buffer sent Post.externalLink on verified @xFederiko11 channel"}
            receipts.write_text(json.dumps({"schema":"verified-buffer-x-permalinks-v1","posts":[receipt]}))
            csv.write_text("post_url,date,impressions,replies,reposts\n"+permalink+",2026-12-29,10000,,\n")
            self.assertEqual(measured_interest(NOW,csv,receipts),{})
            csv.write_text("post_url,date,impressions,replies,reposts\n"+permalink+",2026-12-29,10000,3,1\n")
            self.assertEqual(measured_interest(NOW,csv,receipts),{URL:4})
            csv.write_text("post_url,date,impressions,replies,reposts\n"+permalink+",2026-12-15,10000,20,20\n")
            self.assertEqual(measured_interest(NOW,csv,receipts),{})
            receipt["verified_by"]="unverified"
            receipts.write_text(json.dumps({"schema":"verified-buffer-x-permalinks-v1","posts":[receipt]}))
            csv.write_text("post_url,date,impressions,replies,reposts\n"+permalink+",2026-12-29,10000,3,5\n")
            self.assertEqual(measured_interest(NOW,csv,receipts),{})

    def test_global_rotation_spacing_and_completed_time(self):
        self.cfg.update(enabled=True,released_utc=(NOW-timedelta(days=1)).isoformat())
        self.state["entries"]["old"]["completed_utc"]=(NOW-timedelta(days=2)).isoformat()
        self.assertEqual(plans(self.state,NOW,config=self.cfg),[])
        self.state["entries"]["old"]["completed_utc"]=(NOW-timedelta(days=10)).isoformat()
        self.assertTrue(plans(self.state,NOW,config=self.cfg))
        self.state["entries"]["another"]={"source":SOURCE,"url":BASE+"salvare-auto/",
                    "status":"sent","reserved_utc":(NOW-timedelta(hours=19)).isoformat()}
        self.assertEqual(plans(self.state,NOW,config=self.cfg),[])
        self.state["entries"]["another"]["reserved_utc"]=(NOW-timedelta(hours=21)).isoformat()
        self.assertTrue(plans(self.state,NOW,config=self.cfg))


    def test_live_shared_cover_exact(self):
        image=cover_for(URL)
        html=f'<html><head><link rel="canonical" href="{URL}"><meta property="og:image" content="{image}"><meta name="twitter:image" content="{image}"></head><body><h1>WAiNK</h1><figure data-article-cover="shared-social"><img src="{image}" width="1200" height="630"></figure></body></html>'
        p=ArticleCover();p.feed(html)
        self.assertTrue(p.valid(URL))
        for invalid in (html.replace('width="1200"','width="800"'),
                        html.replace('twitter:image','twitter:wrong'),
                        html.replace('<h1>WAiNK</h1>','<h1>WAiNK</h1><p>Other</p>'),
                        html.replace('shared-social','different')):
            p=ArticleCover();p.feed(invalid)
            self.assertFalse(p.valid(URL))

    def test_runtime_review_receipt_and_delivery_recheck(self):
        self.cfg.update(enabled=True,released_utc=(NOW-timedelta(days=1)).isoformat())
        self.cfg["articles"][0]["reviewed_utc"]=NOW.isoformat()
        self.state["entries"]["old"]["buffer_id"]="verified-receipt-id"
        receipts={(URL,"verified-receipt-id")}
        item=candidate(self.state,NOW,config=self.cfg,receipts=receipts,live_checker=lambda u:True)
        self.assertIsNotNone(item)
        self.assertTrue(authorize(item,self.state,NOW,config=self.cfg,receipts=receipts))
        self.assertIsNone(candidate(self.state,NOW,config=self.cfg,receipts=set(),live_checker=lambda u:True))
        self.assertIsNone(candidate(self.state,NOW,config=self.cfg,receipts=receipts,live_checker=lambda u:False))
        self.assertFalse(authorize(dict(item,text="different text"),self.state,NOW,config=self.cfg,receipts=receipts))
        self.state["entries"]["conflict"]={"url":BASE+"trucchi/","status":"sent","media_url":cover_for(URL)}
        self.assertFalse(authorize(item,self.state,NOW,config=self.cfg,receipts=receipts))
        del self.state["entries"]["conflict"]
        self.cfg["articles"][0]["reviewed_utc"]=None
        self.assertIsNone(candidate(self.state,NOW,config=self.cfg,receipts=receipts,live_checker=lambda u:True))
        self.cfg["articles"][0]["reviewed_utc"]=NOW.isoformat()
        entry=dict(item,status="reserved",reserved_utc=NOW.isoformat())
        self.state["entries"][item["key"]]=entry
        self.assertTrue(delivery_authorized(entry,self.state,NOW,config=self.cfg,receipts=receipts,live_checker=lambda u:True))
        self.assertFalse(delivery_authorized(entry,self.state,NOW,config=self.cfg,receipts=receipts,live_checker=lambda u:False))
        self.cfg["enabled"]=False
        self.assertFalse(delivery_authorized(entry,self.state,NOW,config=self.cfg,receipts=receipts,live_checker=lambda u:True))
