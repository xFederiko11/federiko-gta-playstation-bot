"""Offline Umami X attribution checks: only real owned Pages and no fake followers."""
from __future__ import annotations

from urllib.parse import urlsplit, parse_qs
import unittest

from editorial_double_threads_v1 import double
from editorial_seo_v135 import x_weight
from owned_utm_attribution_v1 import tagged_site_url, is_owned_site_url, CAMPAIGN
from quick_tips_v146 import TIPS, reply
from x_permalink_bridge_v1 import ledger_map

SITE = "https://xfederiko11.github.io/gta-6/"
GUIDE = SITE + "guide-e-tutorial/scansionare-veicoli/"
TROPHY = SITE + "trofei/"
OLD = "https://xfederiko11.github.io/federiko-gta-playstation-bot/trophy-1.html"


class OwnedUmamiAttributionTests(unittest.TestCase):
    def test_strict_first_party_origin_and_canonical_paths_only(self):
        self.assertTrue(is_owned_site_url(SITE))
        self.assertTrue(is_owned_site_url(GUIDE))
        self.assertFalse(is_owned_site_url(OLD))
        bad = (
            "http://xfederiko11.github.io/gta-6/",
            "https://other.github.io/gta-6/",
            "https://xfederiko11.github.io.evil.test/gta-6/",
            "https://xfederiko11.github.io/gta-6/foo/?utm_source=spam",
            "https://xfederiko11.github.io/gta-6/foo/#fragment",
            "https://xfederiko11.github.io/gta-6/foo",
            "https://xfederiko11.github.io/gta-6/../other/",
            "https://a@xfederiko11.github.io/gta-6/",
            "https://xfederiko11.github.io/gta-6/%2e%2e/",
            "https://www.powerpyx.com/gta-6-guide/",
        )
        for url in bad:
            with self.subTest(url=url):
                self.assertFalse(is_owned_site_url(url))
                with self.assertRaises(ValueError):
                    tagged_site_url(url, placement="guide_reply")
        with self.assertRaises(ValueError):
            tagged_site_url(GUIDE, placement="unverified")
        with self.assertRaises(ValueError):
            tagged_site_url(GUIDE, placement="123&user=personal")

    def test_umami_utms_are_consistent_and_privacy_safe(self):
        for placement in ("guide_reply","community_question","trophy_reply","quick_tip"):
            with self.subTest(placement=placement):
                link=tagged_site_url(GUIDE,placement=placement)
                parts=urlsplit(link)
                self.assertEqual(parts.scheme,"https")
                self.assertEqual(parts.hostname,"xfederiko11.github.io")
                self.assertEqual(parts.path,"/gta-6/guide-e-tutorial/scansionare-veicoli/")
                query=parse_qs(parts.query)
                self.assertEqual(query,{
                    "utm_source":["x"],"utm_medium":["social"],
                    "utm_campaign":[CAMPAIGN],"utm_content":[placement]
                })
                self.assertEqual(parts.fragment,"")
                self.assertNotIn("visitor_id",link)
                self.assertNotIn("utm_term",link)
                self.assertEqual(len(link.split("?")),2)

    def test_owned_guide_reply_tagged_but_ledger_article_remains_canonical(self):
        item={"key":"example","source":"Guide GTA VI Italia","title":"Scansionare auto",
              "url":GUIDE,"text":"🚗 Scansiona le auto per il tracker GTA VI"}
        result=double(item)
        self.assertEqual(result["url"],GUIDE)
        self.assertEqual(len(result["thread"]),2)
        self.assertNotIn("utm_source=",result["thread"][0])
        self.assertIn(tagged_site_url(GUIDE,placement="guide_reply"),result["thread"][1])
        self.assertLessEqual(x_weight(result["thread"][1]),280)
        record={"entries":{"key":{
            "source":result["source"],"url":result["url"],
            "buffer_id":"6b000a860f5eda1a57d61243","thread":result["thread"]
        }}}
        self.assertEqual(ledger_map(record)["6b000a860f5eda1a57d61243"]["article_url"],GUIDE)

    def test_growth_question_placement_is_distinguishable(self):
        item={"source":"Guide GTA VI Italia","title":"Cosa preferisci?",
              "url":GUIDE,"text":"Quale guida GTA VI ti serve? Scrivicelo qui.",
              "tip_id":"growth-question-tracker"}
        result=double(item)
        self.assertIn(tagged_site_url(GUIDE,placement="community_question"),
                      result["thread"][1])
        self.assertEqual(result["url"],GUIDE)

    def test_trophy_legacy_fallback_survives_without_utm(self):
        item={"source":"Trofei GTA VI","url":OLD,"title":"Vecchia pagina",
              "text":"🏆 Trofei della storia GTA VI: verifica i requisiti."}
        result=double(item)
        self.assertEqual(result["url"],OLD)
        self.assertIn(OLD,result["thread"][1])
        self.assertNotIn("utm_",result["thread"][1])
        owned=double({**item,"url":TROPHY})
        self.assertEqual(owned["url"],TROPHY)
        self.assertIn(tagged_site_url(TROPHY,placement="trophy_reply"),owned["thread"][1])

    def test_curated_tip_tag_only_when_guide_live_and_keep_source_credit(self):
        tip=TIPS[0]
        fallback=reply(tip)
        self.assertIn(tip["source_url"],fallback)
        self.assertNotIn("utm_",fallback)
        localized=reply(tip,portal_link=GUIDE)
        self.assertIn(tagged_site_url(GUIDE,placement="quick_tip"),localized)
        self.assertIn("PowerPyx",localized)
        self.assertLessEqual(x_weight(localized),280)
        self.assertEqual(tip["source_url"],TIPS[0]["source_url"])


if __name__=="__main__":
    unittest.main()
