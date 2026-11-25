from datetime import datetime,timedelta,timezone
from unittest import TestCase
from site_article_rotation_v1 import load,plans,BASE,SOURCE
from social_media_gate_v2 import cover_for

NOW=datetime(2026,12,30,12,tzinfo=timezone.utc)
URL=BASE+"guide-e-tutorial/scansionare-veicoli/"

class RotationTests(TestCase):
    def setUp(self):
        self.cfg=load()
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
