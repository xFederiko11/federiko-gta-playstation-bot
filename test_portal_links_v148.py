"""No-network safety tests for staged GTA 6 portal permalink migration."""
import os
from unittest.mock import Mock,patch
import unittest

import portal_links_v148 as portal
from editorial_seo_v135 import x_weight
import quick_tips_v146 as tips

class PortalLinksV148Tests(unittest.TestCase):
    def test_all_six_quicktips_have_permalink(self):
        self.assertEqual(len(portal.TIPS),len(tips.TIPS))
        for item in tips.TIPS:
            url=portal.guide_url(item["id"])
            self.assertTrue(url.startswith("https://xfederiko11.github.io/gta-6/guide-e-tutorial/"))
            self.assertTrue(url.endswith("/"))

    def test_portal_enabled_only_with_opt_in(self):
        with patch.dict(os.environ,{"GTA6_PORTAL_LINKS_ENABLED":"false"}):
            self.assertFalse(portal.page_live(portal.guide_url(tips.TIPS[0]["id"])))
        with patch.dict(os.environ,{"GTA6_PORTAL_LINKS_ENABLED":"true"}),patch.object(portal,"page_live",return_value=False):
            self.assertIsNone(portal.guide_if_live(tips.TIPS[0]["id"]))

    def test_valid_live_response_and_canonical(self):
        link=portal.guide_url(tips.TIPS[0]["id"])
        body='<html lang="it"><head><link rel="canonical" href="'+link+'"></head></html>'
        class Response:
            status_code=200
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def iter_content(self,n):yield body.encode("utf-8")
        session=Mock()
        session.get.return_value=Response()
        with patch.dict(os.environ,{"GTA6_PORTAL_LINKS_ENABLED":"true"}):
            self.assertTrue(portal.page_live(link,session=session))
            self.assertFalse(portal.page_live("https://attacker.example/redirect",session=session))
        session.get.assert_called_once()

    def test_pending_pages_never_replace_old_links(self):
        with patch.dict(os.environ,{"GTA6_PORTAL_LINKS_ENABLED":"true"}),patch.object(portal,"page_live",return_value=False):
            self.assertIsNone(portal.guide_if_live("waink-vehicles-ps5"))
        self.assertIn(tips.TIPS[0]["source_url"],tips.reply(tips.TIPS[0]))

    def test_live_guide_thread_has_local_article_in_reply_only(self):
        item=tips.TIPS[0]
        link=portal.guide_url(item["id"])
        reply=tips.reply(item,portal_link=link)
        self.assertIn(link,reply)
        self.assertNotIn(link,item["main"])
        self.assertIn("Fonte PowerPyx",reply)
        self.assertLessEqual(x_weight(reply),280)
        with patch.dict(os.environ,{"GTA6_PORTAL_LINKS_ENABLED":"true"}),patch.object(portal,"guide_if_live",return_value=link):
            from datetime import datetime,timezone
            record=tips.candidate({"entries":{}},datetime(2026,11,19,9,0,tzinfo=timezone.utc))
        self.assertEqual(record["url"],link)
        self.assertEqual(record["thread"][1],reply)

    def test_old_trophy_dedupe_key_is_preserved_when_link_switches(self):
        from datetime import datetime,timezone
        import json
        import trophy_posts_v142 as trophies
        from editorial_autopilot_v137 import identity
        item=json.loads(trophies.SOURCE.read_text())["trophies"][13]
        legacy=trophies.BASE+"/"+item["id"]+".html"
        target=portal.trophy_url(item)
        with patch.dict(os.environ,{"GTA6_PORTAL_LINKS_ENABLED":"true"}),patch.object(portal,"trophy_if_live",return_value=target):
            result=trophies.candidate({"entries":{}},datetime(2026,11,19,8,tzinfo=timezone.utc))
        self.assertEqual(result["url"],target)
        self.assertEqual(result["key"],identity(legacy))
        self.assertIn(target,result["text"])
        self.assertLessEqual(x_weight(result["text"]),280)
        with patch.dict(os.environ,{"GTA6_PORTAL_LINKS_ENABLED":"true"}),patch.object(portal,"trophy_if_live",return_value=target):
            again=trophies.candidate({"entries":{identity(legacy):{"source":"Trofei GTA VI"}}},datetime(2026,11,19,9,tzinfo=timezone.utc))
        self.assertNotEqual(again["trophy_number"],item["number"])

if __name__=="__main__":unittest.main()
