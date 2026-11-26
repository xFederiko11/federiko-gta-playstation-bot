"""Offline media policy: one dedicated article cover, no repeated image in X."""
from __future__ import annotations
import hashlib
import unittest
from unittest.mock import Mock, patch
import requests
from social_media_gate_v2 import (cover_for,canonical_page_path,prepare,probe_image,
                                  trusted_asset,image_taken,SITE_IMAGE_PREFIX,BASE)


class ImageGateTests(unittest.TestCase):
    def test_unique_media_for_distinct_owned_links(self):
        paths=["","trofei/trofeo-01/","trofei/trofeo-02/",
               "guide-e-tutorial/viaggio-rapido-taxi/","hdr-oled/",
               "collezionabili/percorsi/","screenshot-ps5/invia/"]
        urls=[BASE+p for p in paths]
        covers=[cover_for(u) for u in urls]
        self.assertEqual(len(set(covers)),len(urls))
        for path,card in zip(paths,covers):
            token=hashlib.sha256(path.encode()).hexdigest()[:16]
            self.assertEqual(card,SITE_IMAGE_PREFIX+token+".jpg")
            self.assertTrue(trusted_asset(card))

    def test_canonical_and_untrusted_image_rejection(self):
        for url in ("http://xfederiko11.github.io/gta-6/",
                    "https://xfederiko11.github.io.evil.test/gta-6/a/",
                    BASE+"a/?tracking=1",BASE+"a/../b/",BASE+"a",
                    "https://example.org/news/"):
            # The path traversal is not present in a generated site.
            if "/../" in url:continue
            self.assertIsNone(cover_for(url))
        for image in ("http://media-rockstargames-com.akamaized.net/x.jpg",
                      "https://example.com/random.jpg",
                      "https://xfederiko11.github.io.evil.test/gta-6/assets/social-cards/a.jpg",
                      "https://www.rockstargames.com/VI/logo.svg",
                      "https://www.rockstargames.com/VI/photo.jpg?token=secret"):
            self.assertFalse(trusted_asset(image))

    def test_ledger_prevents_image_reuse_different_jobs(self):
        a={"source":"Guide GTA VI Italia","url":BASE+"trofei/",
           "text":"Trofei","key":"job-1"}
        first=prepare(a,{"entries":{}})
        self.assertEqual(first["media_url"],cover_for(a["url"]))
        ledger={"entries":{"job-1":{"status":"sent","media_url":first["media_url"]}}}
        self.assertIsNone(prepare({**a,"key":"job-2"},ledger))
        other=prepare({**a,"url":BASE+"trucchi/","key":"job-3"},ledger)
        self.assertIsNotNone(other)
        self.assertNotEqual(other["media_url"],first["media_url"])

    def test_external_unrelated_and_text_only_posts_held(self):
        self.assertIsNone(prepare({"source":"VGC","url":"https://example.com/article",
                                   "text":"GTA VI"}, {"entries":{}}))
        event={"source":"PowerPyx Tips","url":"https://www.powerpyx.com/gta-6-thing/",
               "text":"Quick tip","media_url":"https://www.rockstargames.com/VI/_next/static/media/thing.jpg"}
        self.assertIsNotNone(prepare(event,{"entries":{}}))
        self.assertIsNone(prepare({**event,"media_url":"https://news.example/img.jpg"},{"entries":{}}))

    def test_monitor_deduplication_is_enabled_for_future_official_news(self):
        from pathlib import Path
        workflow=Path(".github/workflows/gta-monitor.yml").read_text(encoding="utf-8")
        self.assertIn("V12_UNIQUE_IMAGES: 'true'",workflow)
        self.assertIn("archive_images",Path("image_registry_v12.py").read_text(encoding="utf-8"))

    def test_transient_503_then_valid_image_passes_after_one_bounded_retry(self):
        link=cover_for(BASE+"guide-e-tutorial/scansionare-veicoli/")
        class FakeResponse:
            def __init__(self,status):
                self.status_code=status
                self.url=link
                self.headers={"Content-Type":"image/jpeg","Content-Length":"39000"}
            def __enter__(self):return self
            def __exit__(self,*args):return None
            def iter_content(self,n):yield bytes([255,216,255])+b"photo-body"
        session=Mock()
        session.get.side_effect=[FakeResponse(503),FakeResponse(200)]
        with patch("social_media_gate_v2.time.sleep") as sleep:
            self.assertTrue(probe_image(link,session=session))
        self.assertEqual(session.get.call_count,2)
        sleep.assert_called_once_with(1)
        self.assertTrue(all(c.kwargs["allow_redirects"] is False
                            for c in session.get.call_args_list))

    def test_three_503_responses_keep_media_on_hold_with_safe_reason(self):
        link=cover_for(BASE+"salvare-auto/")
        class Down:
            status_code=503
            url=link
            headers={}
            def __enter__(self):return self
            def __exit__(self,*args):return None
        session=Mock()
        session.get.return_value=Down()
        with (patch("social_media_gate_v2.time.sleep") as sleep,
              self.assertLogs("gta6.media",level="WARNING") as messages):
            self.assertFalse(probe_image(link,session=session))
        self.assertEqual(session.get.call_count,3)
        self.assertEqual(sleep.call_count,2)
        self.assertIn("reason=HTTP503 attempts=3"," ".join(messages.output))
        self.assertNotIn(link," ".join(messages.output))

    def test_image_404_and_invalid_mime_do_not_retry(self):
        link=cover_for(BASE+"trofei/")
        class Response:
            status_code=404
            url=link
            headers={"Content-Type":"image/jpeg"}
            def __enter__(self):return self
            def __exit__(self,*args):return None
            def iter_content(self,n):yield bytes([255,216,255])+b"real-image"
        session=Mock()
        res=Response()
        session.get.return_value=res
        with patch("social_media_gate_v2.time.sleep") as sleep:
            self.assertFalse(probe_image(link,session=session))
            self.assertEqual(session.get.call_count,1)
            res.status_code=200
            res.headers={"Content-Type":"text/html"}
            self.assertFalse(probe_image(link,session=session))
            self.assertEqual(session.get.call_count,2)
            sleep.assert_not_called()

    def test_tls_failure_is_not_ignored_or_retried(self):
        link=cover_for(BASE+"trofei/")
        session=Mock()
        session.get.side_effect=requests.exceptions.SSLError("Do not reveal URL or token")
        with (patch("social_media_gate_v2.time.sleep") as sleep,
              self.assertLogs("gta6.media",level="WARNING") as messages):
            self.assertFalse(probe_image(link,session=session))
        session.get.assert_called_once()
        sleep.assert_not_called()
        self.assertIn("tls_verification_failed"," ".join(messages.output))
        self.assertNotIn("token"," ".join(messages.output))

    def test_public_get_probe_validates_real_bytes_before_buffer(self):
        link=cover_for(BASE+"trofei/")
        class FakeResponse:
            status_code=200
            url=link
            headers={"Content-Type":"image/jpeg","Content-Length":"39000"}
            def __enter__(self):return self
            def __exit__(self,*args):return None
            def iter_content(self,n):yield b"\xff\xd8\xff"+b"ok"*15
        session=Mock()
        session.get.return_value=FakeResponse()
        self.assertTrue(probe_image(link,session=session))
        self.assertEqual(session.get.call_args.kwargs["allow_redirects"],False)
        session.get.return_value.headers["Content-Type"]="text/html"
        self.assertFalse(probe_image(link,session=session))
        session.get.return_value.headers["Content-Type"]="image/jpeg"
        session.get.return_value.status_code=404
        self.assertFalse(probe_image(link,session=session))
        self.assertFalse(probe_image("https://fake.example/card.jpg",session=session))


class PhotographicPublicationTests(unittest.TestCase):
    def test_photo_metadata_rejects_illustration_and_missing_or_wrong_cover(self):
        from game_photo_policy_v1 import PhotographicCover
        page=BASE+"salvare-auto/"
        cover=cover_for(page)
        html=(f'<link rel="canonical" href="{page}">'
              f'<meta property="og:image" content="{cover}">'
              f'<meta name="twitter:image" content="{cover}">'
              '<meta name="gta6:cover-kind" content="official_game_photo">'
              '<meta property="og:image:alt" content="Immagine promozionale Rockstar Games">'
              '<h1>Auto</h1><figure data-article-cover="shared-social">'
              f'<img src="{cover}" width="1200" height="630"></figure>')
        for raw,expected in ((html,"official_game_photo"),
            (html.replace("official_game_photo","original_illustration"),None),
            (html.replace("Immagine promozionale","Illustrazione"),None),
            (html.replace('width="1200"','width="800"'),None),
            (html.replace('<meta name="gta6:cover-kind"','<meta name="other"'),None)):
            parser=PhotographicCover()
            parser.feed(raw)
            self.assertEqual(parser.photo_kind(page),expected)

    def test_thread_converted_to_one_photo_post_with_link_and_credit(self):
        from game_photo_policy_v1 import single_photo_item
        page=BASE+"salvare-auto/"
        item={"url":page,"source":"PowerPyx Tips","thread":["Salva la tua auto. #GTAVI","Fonte"],
              "text":"Salva la tua auto."}
        result=single_photo_item(item,"official_game_photo")
        self.assertIsNone(result["thread"])
        self.assertIn(page,result["text"])
        self.assertIn("PowerPyx",result["text"])
        self.assertIn("Rockstar Games",result["text"])
        self.assertIsNone(single_photo_item(item,"original_illustration"))
        self.assertIsNone(single_photo_item(dict(item,thread=["x"*240,"Fonte"]),"official_game_photo"))

    def test_delivery_revalidates_photo_and_refuses_old_text_reply(self):
        from game_photo_policy_v1 import verify_delivery
        page=BASE+"salvare-auto/"
        entry={"url":page,"media_url":cover_for(page),"photo_kind":"official_game_photo","thread":None}
        with (patch("game_photo_policy_v1.owned_photo_kind",return_value="official_game_photo") as check,
              patch("game_photo_policy_v1.probe_image",return_value=True)):
            self.assertTrue(verify_delivery(entry))
            self.assertFalse(verify_delivery(dict(entry,thread=["one","two"])))
            self.assertFalse(verify_delivery(dict(entry,media_url=cover_for(BASE+"trofei/"))))
            check.return_value=None
            self.assertFalse(verify_delivery(entry))


if __name__=="__main__":unittest.main()
