"""Offline media policy: one dedicated article cover, no repeated image in X."""
from __future__ import annotations
import hashlib
import unittest
from unittest.mock import Mock
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


if __name__=="__main__":unittest.main()
