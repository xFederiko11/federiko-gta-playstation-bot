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
            self.assertLessEqual(x_weight(copy),235)
            self.assertGreaterEqual(x_weight(copy),80)
            self.assertEqual(copy.count("https://"),1)
            self.assertNotIn("@Rockstar",copy)
            self.assertTrue(item["path"].endswith("/"))

    def test_photo_filter_skips_illustrated_entries_to_find_reviewed_article(self):
        target="https://xfederiko11.github.io/gta-6/articoli/gta-vi-leonida-sei-luoghi/"
        item=candidate(self.state,NOW,live_checker=lambda u:True,
                       photo_checker=lambda u:u==target)
        self.assertEqual(item["url"],target)
        self.assertFalse(self.state["entries"])

    def test_new_photo_editorial_is_available_after_prior_photo_story(self):
        old="https://xfederiko11.github.io/gta-6/articoli/gta-vi-leonida-sei-luoghi/"
        new="https://xfederiko11.github.io/gta-6/articoli/gta-vi-ultimate-edition-auto-garage/"
        self.state["entries"]["old"]={"source":SOURCE,"status":"sent","url":old,
                                       "reserved_utc":(NOW-timedelta(days=2)).isoformat()}
        selected=candidate(self.state,NOW,live_checker=lambda u:True,photo_checker=lambda u:u in (old,new))
        self.assertEqual(selected["url"],new)
        self.assertIn("Non sono istruzioni di sblocco",selected["text"])
        self.assertIsNone(candidate(self.state,NOW,live_checker=lambda u:False,photo_checker=lambda u:u==new))

    def test_original_creator_showcase_requires_live_page_and_unique_image(self):
        item=next(x for x in CONTENT if x["id"]=="creator-showcase-original")
        self.assertEqual(item["path"],"/video-tutorial/")
        self.assertIn("TGG, IGN e community",item["text"])
        self.assertIn(chr(10)*2,item["text"])
        self.assertNotIn("partnership",item["text"].lower())
        self.assertNotIn("sponsorizzato",item["text"].lower())
        self.assertNotIn("https://www.youtube.com",item["text"])
        self.assertEqual(DAY_BUDGET,1)
        self.assertIsNone(candidate(self.state,NOW,live_checker=lambda url:False))
        post=candidate(self.state,NOW,live_checker=lambda url:url.endswith("/video-tutorial/"))
        self.assertIsNotNone(post)
        self.assertEqual(post["url"],"https://xfederiko11.github.io/gta-6/video-tutorial/")
        self.assertLessEqual(x_weight(post["text"]),235)
        from social_media_gate_v2 import cover_for
        self.assertEqual(post["media_url"],cover_for(post["url"]))
        self.assertIn("/assets/social-cards/",post["media_url"])
        self.state["entries"][post["key"]]={
            "source":SOURCE,"reserved_utc":NOW.isoformat(),"status":"uncertain"}
        self.assertIsNone(candidate(self.state,NOW+timedelta(hours=2),
                                    live_checker=lambda url:True))

    def test_patch_archive_is_dated_not_breaking_and_requires_live_article(self):
        item=next(x for x in CONTENT if x["id"]=="patch-archive-20261123")
        self.assertIn("23 NOVEMBRE",item["text"])
        self.assertIn("7 correzioni",item["text"])
        self.assertNotIn("BREAKING",item["text"])
        self.assertIsNone(candidate(self.state,NOW,live_checker=lambda url:False))
        proposed=candidate(self.state,NOW,live_checker=lambda url:url.endswith(item["path"]))
        self.assertIsNotNone(proposed)
        self.assertEqual(proposed["url"],"https://xfederiko11.github.io/gta-6/patch/2026-11-23/")
        from social_media_gate_v2 import cover_for
        self.assertEqual(proposed["media_url"],cover_for(proposed["url"]))

    def test_ps5_first_person_glitch_copy_is_cautious_and_requires_live_guide(self):
        item=next(x for x in CONTENT if x["id"]=="ps5-first-person-glitch")
        self.assertEqual(item["path"],"/guide-e-tutorial/glitch-prima-persona-ps5/")
        self.assertIn("trofei NON verificati",item["text"])
        self.assertIn("Community:",item["text"])
        self.assertIn("patch 23/11",item["text"])
        self.assertIn("Salva prima",item["text"])
        self.assertNotIn("Trophy Safe",item["text"])
        self.assertNotIn("infinito",item["text"])
        self.assertNotIn("tutti i trofei",item["text"])
        self.assertEqual(DAY_BUDGET,1)
        self.assertIsNone(candidate(self.state,NOW,live_checker=lambda url:False))
        proposed=candidate(self.state,NOW,live_checker=lambda url:url.endswith(item["path"]))
        self.assertIsNotNone(proposed)
        self.assertEqual(proposed["url"],"https://xfederiko11.github.io/gta-6"+item["path"])
        self.assertLessEqual(x_weight(proposed["text"]),235)

    def test_final_guides_and_randy_locations_match_reviewed_pages(self):
        rows={x["id"]:x for x in CONTENT}
        for ident,phrases in (
            ("challenge-roadmap",("50 sfide","70 su 80")),
            ("range-focus",("5 GTA$","42 medaglie Oro")),
            ("randy-advanced-tracker",("Dale Mamba","16 consegne")),
            ("car-pegassi-vitello",("Waning Sands","garage destro","Non è uno spawn garantito")),
            ("car-pegassi-infernus",("Crosstown","settimo piano","Non è uno spawn garantito")),
            ("car-pegassi-tempesta",("Vespucci Island","Non è uno spawn garantito")),
            ("car-buckingham-windsor-drop",("Bayside","Non è uno spawn garantito")),
            ("car-pegassi-toros",("Southside","Non è uno spawn garantito")),
        ):
            for phrase in phrases:
                self.assertIn(phrase,rows[ident]["text"],ident)

    def test_animal_and_taxi_copy_matches_reviewed_tutorials(self):
        animals=next(x for x in CONTENT if x["id"]=="animal-guide")
        self.assertIn("100 specie su 255",animals["text"])
        self.assertIn("Caccia separata",animals["text"])
        taxi=next(x for x in CONTENT if x["id"]=="taxi-fast-travel")
        self.assertIn("Gone Fishing",taxi["text"])
        self.assertIn("100 GTA$ oltre alla tariffa",taxi["text"])

    def test_money_copy_matches_reviewed_tutorials(self):
        liquor=next(x for x in CONTENT if x["id"]=="money-liquor")
        self.assertIn("Consegna il rum",liquor["text"])
        self.assertIn("icona gialla",liquor["text"])
        self.assertNotIn("Durante l'incarico",liquor["text"])
        money=next(x for x in CONTENT if x["id"]=="money-early-four")
        self.assertIn("Prima di Recalibration",money["text"])
        self.assertIn("non passano al Capitolo 2",money["text"])

    def test_meditation_copy_reflects_current_source_without_claiming_personal_test(self):
        item=next(x for x in CONTENT if x["id"]=="meditation-risk")
        self.assertIn("PowerPyx",item["text"])
        self.assertIn("lezione alternativa dopo Coffee Break",item["text"])
        self.assertIn("15 sessioni su 18",item["text"])
        self.assertNotIn("incerto",item["text"])

    def test_legacy_article_url_is_not_a_new_evergreen_post(self):
        item=CONTENT[0]
        self.state["entries"]["old-key"]={
            "source":"legacy publisher",
            "url":"https://xfederiko11.github.io/gta-6"+item["path"].rstrip("/")+"?utm_source=x",
            "reserved_utc":(NOW-timedelta(days=40)).isoformat(),
            "status":"sent"}
        self.assertIsNone(candidate(self.state,NOW,live_checker=lambda u:u.endswith(item["path"])))
        # Uncertain historical delivery also prevents duplicate first posts.
        self.state["entries"]["old-key"]["status"]="attempted"
        self.assertIsNone(candidate(self.state,NOW,live_checker=lambda u:u.endswith(item["path"])))
        self.assertIsNotNone(candidate(self.state,NOW,live_checker=lambda u:u.endswith(CONTENT[1]["path"])))

    def test_first_public_site_canonical_selected_only_if_200(self):
        calls=[]
        def live(url):
            calls.append(url)
            return url.endswith("/hdr-oled/")
        item=candidate(self.state,NOW,live_checker=live)
        self.assertIsNotNone(item)
        self.assertEqual(item["source"],SOURCE)
        self.assertIn("/hdr-oled/",item["url"])
        expected = ["https://xfederiko11.github.io/gta-6" + x["path"] for x in CONTENT]
        first_live = expected.index(item["url"])
        self.assertEqual(calls,expected[:first_live+1])
        from social_media_gate_v2 import cover_for
        self.assertEqual(item["media_url"],cover_for(item["url"]))
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
