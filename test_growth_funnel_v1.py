"""Offline tests: no fabricated tweet links/metrics and no social actions."""
import unittest,json
from pathlib import Path
from tempfile import TemporaryDirectory
from growth_funnel_v1 import valid,choose,markdown

URL="https://xfederiko11.github.io/gta-6/salvare-auto/"
LINK="https://x.com/xFederiko11/status/2123741902625218841"
def post():
    return {"article_url":URL,"x_url":LINK,
            "excerpt":"🚘 GTA VI: controlla il tracker e registra le auto nella guida.",
            "sent_at":"2026-11-20T11:35:01.834Z",
            "verified_by":"Buffer sent Post.externalLink on verified @xFederiko11 channel"}
class GrowthFunnelTests(unittest.TestCase):
    def test_only_owned_verified_sent_posts(self):
        self.assertIsNotNone(valid(post()))
        for change in ({"article_url":"https://bad.example/gta-6/"},
                       {"x_url":"https://x.com/other/status/2123741902625218841"},
                       {"x_url":"https://x.com.evil.test/xFederiko11/status/2123741902625218841"},
                       {"verified_by":"claimed"}):
            self.assertIsNone(valid({**post(),**change}))
    def test_deduplicate_and_no_social_mutations(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"feed.json"
            p.write_text(json.dumps({"schema":"verified-buffer-x-permalinks-v1",
                                     "posts":[post(),post()]}))
            found=choose(p)
            self.assertEqual(len(found),1)
            text=markdown(p)
            self.assertIn(LINK,text)
            self.assertIn("Mentions",text)
            self.assertNotIn("1000 follower",text)
            self.assertIn("SOLO",text)
            self.assertNotIn("Pubblica automaticamente",text)
    def test_malformed_feed_fails_closed(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"feed.json"
            p.write_text(json.dumps({"schema":"fake","posts":[post()]}))
            with self.assertRaises(ValueError):choose(p)
        self.assertEqual(choose("missing-feed-mock.json"),[])
if __name__=="__main__":unittest.main()
