"""No-network tests: map rollout source, reader privacy and real follower counts."""
from __future__ import annotations
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from io import BytesIO
import json
import unittest
from map_growth_sync_v1 import SCHEMA,SOURCE,FIELDS,validate,fetch_public,metric_row,drafts,markdown


def example():
    return {"schema":SCHEMA,"guide_articles":11,"trophy_articles":55,
            "articles_with_map":66,"pages_with_interactive_map":68,
            "guide_location_descriptions":18,"collectible_descriptions":123,
            "exact_gameplay_coordinate_pairs_verified":0,
            "external_map_references_reviewed":4,
            "external_community_building_markers":1,
            "external_community_region_links":1,
            "external_location_detail_links":2,
            "individual_collectible_pins_verified":0,
            "external_link_verification":"indexed_public_source_not_in_game_or_live_api",
            "external_maps_loaded_automatically":False,
            "named_place_search_is_exact_pin":False,
            "providers":[{"embed":"https://vice-map.com/embed/map"},
                         {"embed":"https://gta6.city/embed/map"}]}


class MapGrowthTests(unittest.TestCase):
    def test_verify_public_map_without_invented_markers_or_autoload(self):
        self.assertTrue(validate(example()))
        rows=drafts()
        self.assertEqual(len(rows),3)
        self.assertEqual(len({r["url"] for r in rows}),3)
        self.assertEqual(len({r["text"] for r in rows}),3)
        self.assertTrue(all(r["compose"].startswith("https://x.com/intent/tweet?text=") for r in rows))
        self.assertTrue(all(r["published"] is False for r in rows))
        message=markdown(True,None)
        self.assertIn("68 pagine con mappa",message)
        self.assertIn("non disponibili, non zero",message)
        self.assertIn("game-map-load-intent",message)
        self.assertIn("game-map-follow-intent",message)
        self.assertIn("game-map-curated-link-open-intent",message)
        self.assertIn("Zero pin del singolo oggetto",message)
        self.assertIn("casa di Jason",message)
        self.assertIn("primi follower",message)
        self.assertIn("meditazioni",rows[2]["url"])
        self.assertTrue(all("marker preciso" not in r["text"] for r in rows))
        self.assertNotIn("follower ottenuti",message.lower())

    def test_fail_closed_if_public_page_claims_automated_embed_or_fake_exact_coordinates(self):
        for key,value in (("articles_with_map",65),("pages_with_interactive_map",0),
                          ("exact_gameplay_coordinate_pairs_verified",7),
                          ("external_map_references_reviewed",3),
                          ("external_community_building_markers",2),
                          ("individual_collectible_pins_verified",9),
                          ("external_maps_loaded_automatically",True),
                          ("named_place_search_is_exact_pin",True)):
            fake={**example(),key:value}
            with self.subTest(key=key),self.assertRaises(ValueError):
                validate(fake)
        fake=example();fake["external_link_verification"]="coordinates_100_percent_confirmed"
        with self.assertRaises(ValueError):validate(fake)
        fake=example();fake["providers"]=[{"embed":"https://bad.example/map"}]
        with self.assertRaises(ValueError):validate(fake)
        self.assertIn("non verificabile",markdown(False,None))
        self.assertNotIn("Tre bozze originali",markdown(False,None))

    def test_single_trusted_endpoint_rejects_redirect(self):
        payload=json.dumps(example()).encode()
        class Response:
            headers={"Content-Type":"application/json"}
            def __init__(self,url):self.url=url
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def geturl(self):return self.url
            def read(self,n):return payload[:n]
        def success(req,timeout):
            self.assertEqual(req.full_url,SOURCE)
            self.assertEqual(timeout,12)
            return Response(SOURCE)
        self.assertEqual(fetch_public(open_fn=success)["guide_articles"],11)
        with self.assertRaises(ValueError):
            fetch_public(open_fn=lambda req,timeout:Response("https://bad.example/"))

    def test_empty_unknown_metrics_not_faux_zero_and_manual_zero_preserved(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"map.csv"
            p.write_text(",".join(FIELDS)+"\n",encoding="utf-8")
            self.assertIsNone(metric_row(p))
            p.write_text(",".join(FIELDS)+"\n"
                "2026-11-21,12,4,2,5,10,0\n",encoding="utf-8")
            metrics=metric_row(p)
            self.assertEqual(metrics["x_new_followers"],0)
            self.assertEqual(metrics["map_follow_intents"],5)
            self.assertIn("x_new_followers: 0",markdown(True,metrics))
            self.assertNotIn("5 follower",markdown(True,metrics))
            p.write_text(",".join(FIELDS)+"\n"
                "2026-11-21,12,not_a_number,2,5,10,0\n",encoding="utf-8")
            with self.assertRaises(ValueError):metric_row(p)
            p.write_text(",".join(FIELDS)+"\n"
                "2026-11-21,12,4,2,5,10,0\n"
                "2026-11-21,10,4,2,5,10,0\n",encoding="utf-8")
            with self.assertRaises(ValueError):metric_row(p)

    def test_existing_issue_can_be_extended_without_broadcasting(self):
        import map_growth_sync_v1 as mod
        with TemporaryDirectory() as d:
            p=Path(d)
            issue=p/"existing.md"
            issue.write_text("# Crescita\n## Profilo: stato osservato dagli screenshot\nSalvato",encoding="utf-8")
            # Test insertion operation pure, without ever calling API or GitHub.
            original=issue.read_text(encoding="utf-8")
            appended=original.replace("## Profilo: stato osservato dagli screenshot",
                                      markdown(True,None)+"\n## Profilo: stato osservato dagli screenshot")
            self.assertIn("Salvato",appended)
            self.assertEqual(appended.count("## 🗺️ Mappe interattive"),1)
            self.assertNotIn("gh issue create",Path("map_growth_sync_v1.py").read_text(encoding="utf-8"))
            self.assertNotIn("publish_thread",Path("map_growth_sync_v1.py").read_text(encoding="utf-8"))


if __name__=="__main__":unittest.main()
