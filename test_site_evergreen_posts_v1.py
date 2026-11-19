"""Offline regression for original GTA VI site excerpts in editorial X queue."""
import unittest
from datetime import datetime,timedelta,timezone
from editorial_seo_v135 import x_weight
from site_evergreen_posts_v1 import (
    CONTENT, SOURCE, SPACING, DAY_BUDGET, candidate, validate
)

NOW=datetime(2026,11,19,10,0,tzinfo=timezone.utc)


class SiteEvergreenTests(unittest.TestCase):
    def setUp(self):
        self.state={"schema":"v13.7","entries":{},"signatures":{},"run_history":[]}

    def test_site_posts_are_original_distinct_and_not_spammy(self):
        self.assertTrue(validate())
        self.assertGreaterEqual(len(CONTENT),9)
        self.assertEqual(DAY_BUDGET,1)
        self.assertGreaterEqual(SPACING,timedelta(hours=18))
        self.assertEqual(len({x["id"] for x in CONTENT}),len(CONTENT))
        self.assertEqual(len({x["path"] for x in CONTENT}),len(CONTENT))
        for item in CONTENT:
            copy=item["text"]+"\nhttps://xfederiko11.github.io/gta-6"+item["path"]+"\n\n#GTAVI"
            self.assertLessEqual(x_weight(copy),280)
            self.assertGreaterEqual(x_weight(copy),80)
            self.assertEqual(copy.count("https://"),1)
            self.assertNotIn("@Rockstar",copy)
            self.assertTrue(item["path"].endswith("/"))

    def test_first_public_site_canonical_selected_only_if_200(self):
        calls=[]
        def live(url):
            calls.append(url)
            return url.endswith("/hdr-oled/")
        item=candidate(self.state,NOW,live_checker=live)
        self.assertIsNotNone(item)
        self.assertEqual(item["source"],SOURCE)
        self.assertIn("/hdr-oled/",item["url"])
        self.assertEqual(len(calls),1)
        self.assertIsNone(item.get("media_url"))
        self.assertIn("non è un preset universale",item["text"])
        self.assertEqual(len(item["key"]),24)

    def test_no_ghost_pages_and_one_unique_post_per_day(self):
        self.assertIsNone(candidate(self.state,NOW,live_checker=lambda url:False))
        first=candidate(self.state,NOW,live_checker=lambda url:True)
        self.state["entries"][first["key"]]={
            "source":SOURCE,"reserved_utc":NOW.isoformat(),"status":"uncertain"}
        self.assertIsNone(candidate(self.state,NOW+timedelta(hours=2),live_checker=lambda url:True))
        self.assertIsNone(candidate(self.state,NOW+timedelta(hours=19),live_checker=lambda url:True))
        tomorrow=NOW+timedelta(days=1)
        second=candidate(self.state,tomorrow,live_checker=lambda url:True)
        self.assertIsNotNone(second)
        self.assertNotEqual(second["key"],first["key"])
        self.assertNotEqual(second["url"],first["url"])

    def test_does_not_repeat_any_tip_after_every_site_evergreen_post(self):
        for index,item in enumerate(CONTENT):
            now=NOW+timedelta(days=index)
            post=candidate(self.state,now,live_checker=lambda url:True)
            self.assertIsNotNone(post,(index,item["id"]))
            self.state["entries"][post["key"]]={
                "source":SOURCE,"reserved_utc":now.isoformat(),"status":"sent"}
        self.assertIsNone(candidate(self.state,NOW+timedelta(days=len(CONTENT)),
                                    live_checker=lambda url:True))
        self.assertRaises(ValueError,candidate,self.state,datetime(2026,11,19),live_checker=lambda url:True)


if __name__=="__main__":
    unittest.main()
