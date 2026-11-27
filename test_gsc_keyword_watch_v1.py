import json,unittest
from datetime import datetime,date
from zoneinfo import ZoneInfo
from gsc_keyword_watch_v1 import SITE,SCOPE,TOKEN_URL,QUERY_URL,access_token,periods,fetch_rows,collect,review

class GscTests(unittest.TestCase):
    def test_final_windows(self):
        self.assertEqual(periods(datetime(2026,11,27,12,tzinfo=ZoneInfo("America/Los_Angeles"))),
            [(date(2026,11,18),date(2026,11,24)),(date(2026,11,11),date(2026,11,17))])
    def test_oauth_scope_and_fixed_endpoint(self):
        def fake(url,body,headers):
            self.assertEqual(url,TOKEN_URL)
            self.assertIn(b"grant_type=refresh_token",body)
            return {"access_token":"fake","scope":SCOPE}
        env={"GSC_CLIENT_ID":"i","GSC_CLIENT_SECRET":"s","GSC_REFRESH_TOKEN":"r"}
        self.assertEqual(access_token(env,fake),"fake")
        with self.assertRaises(ValueError):access_token({},fake)
        with self.assertRaises(ValueError):access_token(env,lambda *a:{"access_token":"fake","scope":"other"})
    def test_read_only_italy_query_page_and_canonical_review(self):
        def fake(url,body,headers):
            self.assertEqual(url,QUERY_URL)
            q=json.loads(body)
            self.assertEqual(q["dataState"],"final")
            self.assertEqual(q["dimensionFilterGroups"][0]["filters"][0]["expression"],"ita")
            keys=["come salvare auto gta 6",SITE] if q["dimensions"]==["query","page"] else [SITE]
            return {"rows":[{"keys":keys,"impressions":10,"clicks":0,"ctr":0,"position":6.1}]}
        data=collect("fake",datetime(2026,11,27,12,tzinfo=ZoneInfo("America/Los_Angeles")),fake)
        self.assertEqual(len(data["windows"]),2)
        self.assertEqual(data["windows"][0]["review"][0]["canonical_target"],SITE+"salvare-auto/")
        self.assertEqual(data["windows"][0]["page"]["rows"][0]["impressions"],10)
    def test_empty_and_malformed(self):
        self.assertEqual(fetch_rows("fake",date(2026,11,18),date(2026,11,24),["page"],lambda *a:{}),{"rows":[],"local_cap_reached":False})
        with self.assertRaises(ValueError):fetch_rows("fake",date(2026,11,18),date(2026,11,24),["page"],lambda *a:{"rows":[{"keys":[SITE],"clicks":-1}]})
        self.assertEqual(review([{"keys":["glitch gta 6",SITE],"impressions":5,"position":3}]),[])
