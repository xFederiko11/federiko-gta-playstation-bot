"""Regression tests: old indexed trophy URLs stay alive as safe redirects."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import legacy_pages_redirect_v149 as legacy
from portal_links_v148 import trophy_url

class LegacyRedirectTests(unittest.TestCase):
    def test_every_trophy_and_medals_redirect_to_new_portal(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(legacy,"OUT",Path(tmp)):
            legacy.main()
            targets=json.loads(Path("trophies-gta6-v142.json").read_text(encoding="utf-8"))["trophies"]
            self.assertEqual(len(list(Path(tmp).glob("*.html"))),57)
            for trophy in targets:
                src=(Path(tmp)/(trophy["id"]+".html")).read_text(encoding="utf-8")
                self.assertIn(trophy_url(trophy),src)
                self.assertIn('name="robots" content="noindex,follow"',src)
                self.assertIn('rel="canonical"',src)
                self.assertIn('http-equiv="refresh"',src)
                self.assertNotIn("PowerPyx",src)
            index=(Path(tmp)/"index.html").read_text(encoding="utf-8")
            self.assertIn("https://xfederiko11.github.io/gta-6/trofei/",index)
            self.assertNotIn("<meta property=\"og:image\"",index)
            self.assertTrue((Path(tmp)/".nojekyll").is_file())

    def test_no_open_redirects(self):
        with self.assertRaises(ValueError):
            legacy.render("https://evil.example/","Oops")
        with self.assertRaises(ValueError):
            legacy.render("http://xfederiko11.github.io/gta-6/","Oops")
        with self.assertRaises(ValueError):
            legacy.render("https://xfederiko11.github.io/gta-6.evil.example/","Oops")

if __name__=="__main__": unittest.main()
