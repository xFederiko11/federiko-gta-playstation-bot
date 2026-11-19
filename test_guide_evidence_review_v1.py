"""Offline verification that source metadata cannot publish unverifiable GTA VI claims."""
from __future__ import annotations
from datetime import datetime, timezone
import unittest
from guide_evidence_review_v1 import make_report, markdown, topic, validate

STAMP="2026-11-19T08:00:00+00:00"
def lead(source,title,url):
    return {"source":source,"tier":"specialist","title":title,
            "url":url,"published_utc":STAMP}
def digest(items):
    return {"schema":"gta6-research-digest-v1","generated_utc":STAMP,"candidates":items}

class ReviewTests(unittest.TestCase):
    def test_topic_routes_and_claims_remain_unverified(self):
        r=make_report(digest([
            lead("PowerPyx","GTA 6 new money glitch guide","https://www.powerpyx.com/gta-6-glitch/"),
            lead("GTABase","GTA VI money glitch claimed","https://www.gtabase.com/news/gta-6-glitch"),
            lead("GTA Series Videos","GTA 6 vehicle preview","https://www.youtube.com/watch?v=ABCDE1234AB")
        ]))
        x=next(x for x in r["sections"] if x["topic"]=="glitch")
        self.assertEqual(x["source_count"],2)
        self.assertEqual(x["lead_count"],2)
        self.assertFalse(x["claim_verified"])
        self.assertFalse(x["trophy_safe_verified"])
        self.assertFalse(x["ready_to_publish"])
        self.assertFalse(x["platform_verified"])
        self.assertFalse(x["patch_verified"])
        self.assertIn("guide-e-tutorial/",x["target_page_candidates"])
        v=next(x for x in r["sections"] if x["topic"]=="veicoli")
        self.assertIn("guide-e-tutorial/",v["target_page_candidates"])
        self.assertNotIn("guide-e-tutorial/scansionare-veicoli/",v["target_page_candidates"])
        linked=make_report(digest([
            lead("PowerPyx","GTA VI WAiNK vehicle database scan guide",
                 "https://www.powerpyx.com/gta-6-vehicle-database/")
        ]))
        target=next(x for x in linked["sections"] if x["topic"]=="veicoli")
        self.assertIn("guide-e-tutorial/scansionare-veicoli/",target["target_page_candidates"])
        self.assertEqual(r["publication"],"review_only__no_site_or_buffer_changes")

    def test_no_trust_bypass_from_fake_external_links_or_dates(self):
        examples=[
            lead("PowerPyx","GTA 6 weapons", "https://evil.example/cheats"),
            lead("GTABase","GTA VI cheats", "https://gtabase.com.evil.example/cheats"),
            lead("GTA Series Videos","GTA VI secret", "https://user:pass@youtube.com/watch?v=1"),
            {**lead("PowerPyx","GTA 6 cheats", "https://powerpyx.com/cheats"),"published_utc":"yesterday"},
        ]
        for x in examples:
            with self.subTest(x=x):
                with self.assertRaises((ValueError,TypeError)):
                    validate(digest([x]))
        self.assertEqual(validate(digest([
            lead("untrusted", "GTA 6 things","https://evil.example/gta6")
        ])),[])

    def test_safe_markdown_and_no_auto_article_claims(self):
        r=make_report(digest([
            lead("PowerPyx","GTA VI <unsafe> [click](https://evil.example) cheat",
                 "https://www.powerpyx.com/gta-6-all-cheats/"),
        ]))
        s=markdown(r)
        self.assertIn("trucchi/",s)
        self.assertIn("safe",s)
        self.assertNotIn("[click](https://evil.example)",s)
        self.assertIn("Nessun testo di articoli copiato",s)
        self.assertIn("Nessun",s)
        self.assertIn("false",str(r).lower())
        self.assertEqual(topic("GTA 6 HDR OLED"),"hdr")
        with self.assertRaises(ValueError):
            markdown({"schema":"not-supported"})

    def test_empty_report_is_safe(self):
        out=make_report(digest([]))
        self.assertEqual(out["sections"],[])
        self.assertIn("Nessuna pista recente",markdown(out))
if __name__=="__main__":
    unittest.main()
