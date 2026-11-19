"""No-network regressions for useful X selection, pace and manual-only growth."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

import editorial_autopilot_v137 as bot
from organic_growth_v1 import (
    BIO, DRAFTS, ISSUE_TITLE, PINNED, PUBLIC, SCHEMA, make_plan,
    markdown, validate_drafts, load_profile_status, cadence_snapshot
)

NOW = datetime(2026, 11, 19, 14, 0, tzinfo=timezone.utc)


class OrganicXTests(unittest.TestCase):
    def test_all_drafts_are_usable_italian_and_original_site_links(self):
        validate_drafts()
        self.assertEqual(len(DRAFTS), 7)
        self.assertEqual(len({d["id"] for d in DRAFTS}), 7)
        self.assertLessEqual(bot.weight_x(PINNED), 280)
        self.assertLessEqual(bot.weight_x(BIO), 160)
        for d in DRAFTS:
            self.assertLessEqual(bot.weight_x(d["text"]), 280)
            self.assertIn("#GTAVI", d["text"])
            if d["url"]:
                self.assertTrue(d["url"].startswith(PUBLIC))
            else:
                self.assertNotIn("https://", d["text"])
        self.assertIn("Crescita organica", ISSUE_TITLE)
        self.assertIn("gta-6/", PINNED)

    def test_manual_plan_reports_missing_x_metrics_without_zero_inference(self):
        with TemporaryDirectory() as folder:
            p=Path(folder)
            result=make_plan(now=NOW, ledger_root=p, manual_path=p/"empty.csv")
        self.assertEqual(result["schema"],SCHEMA)
        self.assertFalse(result["actual_x_metrics_available"])
        self.assertEqual(result["x_metrics_count"],0)
        self.assertEqual(result["delivery_reservations"],0)
        self.assertEqual(len(result["drafts"]),3)
        output=markdown(result)
        self.assertIn("non disponibili",output)
        self.assertIn("manuale",output.lower())
        self.assertIn("Quick Tips Buffer restano sospesi",output)
        self.assertIn("nessuna modifica",output.lower())
        self.assertNotIn("nuovi follower: 0",output.lower())
        self.assertIn("post da fissare",output.lower())
        self.assertIn("Cecchino",output)
        with self.assertRaises(ValueError):
            markdown({"schema":"invalid"})

    def test_user_screenshots_are_snapshot_not_live_account_metrics(self):
        with TemporaryDirectory() as folder:
            p=Path(folder)
            plan=make_plan(now=NOW,ledger_root=p,manual_path=p/"missing.csv")
        snap=plan["profile_snapshot"]
        self.assertTrue(snap["website_link_visible"])
        self.assertTrue(snap["pinned_welcome_post_visible"])
        self.assertTrue(snap["authenticity_prompt_visible"])
        self.assertIsNone(snap["authenticity_verified"])
        self.assertIsNone(snap["followers_live"])
        output=markdown(plan)
        self.assertIn("- [x] Sito web visibile",output)
        self.assertIn("- [x] Post di presentazione fissato",output)
        self.assertIn("Post da fissare - archivio",output)
        self.assertIn("non significa automaticamente shadowban",output)
        self.assertIn("anteprima grigia",output)
        self.assertIn("non un controllo live",output)
        self.assertIn("Fan indipendente",plan["bio_suggestion"])
        self.assertNotIn("Nuovi follower: 0",output)

    def test_snapshot_cannot_certify_verification_or_live_followers(self):
        import json
        status=load_profile_status()
        for patch_state in (
            {**status,"authenticity_verified":True},
            {**status,"followers_live":0},
            {**status,"website_link_visible":"true"},
            {**status,"schema":"other"},
        ):
            with TemporaryDirectory() as folder:
                path=Path(folder)/"profile.json"
                path.write_text(json.dumps(patch_state),encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_profile_status(path)

    def test_high_ledger_volume_is_warning_not_restriction_assertion(self):
        with TemporaryDirectory() as folder:
            p=Path(folder)
            entries={
                "unique-"+str(i):{
                    "reserved_utc":(NOW-timedelta(hours=i)).isoformat(),
                    "status":"sent",
                } for i in range(9)
            }
            (p/"editorial-autopilot-v137.json").write_text(
                json.dumps({"schema":"v13.7","entries":entries}),encoding="utf-8")
            pace=cadence_snapshot(NOW,p)
            self.assertEqual(pace["sent_or_accepted_ledger_entries"],9)
            self.assertTrue(pace["review_high_volume"])
            plan=make_plan(now=NOW,ledger_root=p,manual_path=p/"no-x.csv")
            self.assertEqual(plan["cadence"]["sent_or_accepted_ledger_entries"],9)
            body=markdown(plan)
            self.assertIn("Volume elevato da riesaminare manualmente",body)
            self.assertIn("non prova shadowban",body)
            self.assertIn("non elimina post",body)
        with TemporaryDirectory() as folder:
            small=cadence_snapshot(NOW,Path(folder))
            self.assertFalse(small["review_high_volume"])
            self.assertEqual(small["sent_or_accepted_ledger_entries"],0)
        with self.assertRaises(ValueError):
            cadence_snapshot(datetime(2026,11,19),Path("."))

    def test_rotation_produces_new_copy_without_bot_publishing(self):
        with TemporaryDirectory() as folder:
            p=Path(folder)
            first=make_plan(now=NOW,ledger_root=p,manual_path=p/"none.csv")
            next_day=make_plan(now=NOW+timedelta(days=1),ledger_root=p,manual_path=p/"none.csv")
        self.assertEqual(first["mode"],"manual_review_only_no_buffer_no_x_api")
        self.assertNotEqual(first["drafts"][0]["id"],next_day["drafts"][0]["id"])
        self.assertTrue(all("text" in x and "id" in x for x in next_day["drafts"]))

    def test_low_value_creator_episode_is_not_broadcast_on_x(self):
        for title in (
            "GTA 6 Missione n. 8 - Ehi, Arnold! (Capitolo 1)",
            "GTA 6 Mission #9 Chapter 2 Gameplay",
            "GTA VI Full Playthrough",
            "GTA VI beautiful vehicles gameplay",
        ):
            with self.subTest(title=title):
                self.assertFalse(bot.x_quality_gate(
                    {"source":"GTA Series Videos","title":title})[0])
        for title in (
            "GTA VI How to get gold medals at shooting ranges",
            "GTA 6 All Collectibles locations guide",
            "GTA VI trophy guide PS5",
            "GTA 6 HDR OLED settings",
        ):
            with self.subTest(title=title):
                self.assertTrue(bot.x_quality_gate(
                    {"source":"GTA Series Videos","title":title})[0])
        # No blanket censorship of journalistic sources or official news.
        self.assertTrue(bot.x_quality_gate(
            {"source":"Rockstar Games","title":"GTA VI news"} )[0])

    def test_episodic_source_is_skipped_but_helpful_video_can_be_selected(self):
        bad={"source":"GTA Series Videos","title":"GTA 6 Missione n. 8 - Ehi Arnold! Capitolo 1",
             "url":"https://youtube.com/watch?v=ABCD1234567",
             "published":(NOW-timedelta(minutes=12)).isoformat(),"language":"it"}
        good={**bad, "title":"GTA VI trofeo Cecchino: medaglie oro PS5",
              "url":"https://youtube.com/watch?v=EFGH1234567"}
        empty={"schema":"v13.7","entries":{},"signatures":{},"run_history":[]}
        self.assertEqual(bot.select([bad],empty,NOW),[])
        selected=bot.select([bad,good],empty,NOW)
        self.assertEqual(len(selected),1)
        self.assertIn("Video community (non ufficiale)",selected[0]["text"])
        self.assertEqual(selected[0]["url"],good["url"])

    def test_quality_pacing_does_not_modify_official_news_monitor(self):
        self.assertLessEqual(bot.MAX_POSTS_DAY, 8)
        self.assertGreaterEqual(bot.MIN_SPACING_MIN, 30)
        self.assertEqual(bot.RUN_LIMIT,1)
        # This is a read-only growth planner: it has no publisher function.
        import organic_growth_v1
        self.assertFalse(hasattr(organic_growth_v1,"publish"))
        self.assertFalse(hasattr(organic_growth_v1,"follow"))
        self.assertFalse(hasattr(organic_growth_v1,"reply"))


if __name__=="__main__":
    unittest.main()
