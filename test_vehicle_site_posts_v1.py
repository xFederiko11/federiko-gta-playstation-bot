"""Safe vehicle article rotation: one existing site item/day, no phantom posts."""
import unittest
from datetime import datetime, timezone
from site_evergreen_posts_v1 import (
    VEHICLE_CONTENT, ORIGINAL_CONTENT, CONTENT, DAY_BUDGET,
    SPACING, candidate, validate
)
from editorial_seo_v135 import x_weight
from social_media_gate_v2 import cover_for

NOW=datetime(2026,11,24,10,0,tzinfo=timezone.utc)
SITE="https://xfederiko11.github.io/gta-6"

class VehicleSitePostsTests(unittest.TestCase):
    def test_sixteen_verified_nonspoiler_cars_one_per_url(self):
        self.assertTrue(validate())
        self.assertEqual(len(VEHICLE_CONTENT),16)
        self.assertEqual(len(CONTENT),len(VEHICLE_CONTENT)+len(ORIGINAL_CONTENT))
        self.assertEqual(DAY_BUDGET,1)
        self.assertGreaterEqual(SPACING.total_seconds(),18*3600)
        paths=[x["path"] for x in VEHICLE_CONTENT]
        self.assertEqual(len(set(paths)),len(paths))
        self.assertTrue(all(p.startswith("/veicoli/") and p.endswith("/") for p in paths))
        self.assertNotIn("/veicoli/moses-sultan/",paths)
        self.assertNotIn("/veicoli/invetero-coquette-d10/",paths)
        for entry in VEHICLE_CONTENT:
            self.assertIn("📍 ",entry["text"])
            self.assertIn("Non è uno spawn garantito",entry["text"])
            self.assertNotIn("https://",entry["text"])
            self.assertNotIn("@",entry["text"])
            self.assertLessEqual(x_weight(entry["text"]+"\n"+SITE+entry["path"]+"\n\n#GTAVI"),235)

    def test_only_published_link_can_become_candidate(self):
        state={"schema":"v13.7","entries":{},"signatures":{},"run_history":[]}
        tested=VEHICLE_CONTENT[0]
        target=SITE+tested["path"]
        self.assertIsNone(candidate(state,NOW,live_checker=lambda u:False))
        selected=candidate(state,NOW,live_checker=lambda u:u==target)
        self.assertIsNotNone(selected)
        self.assertEqual(selected["url"],target)
        self.assertEqual(selected["media_url"],cover_for(target))
        self.assertEqual(selected["source"],"Guide GTA VI Italia")
        self.assertIn("📍 ",selected["text"])
        self.assertEqual(state["entries"],{})
        self.assertTrue(selected["media_url"].endswith(".jpg"))

if __name__=="__main__":
    unittest.main()
