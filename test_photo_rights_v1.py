import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from photo_rights_v1 import load,reuse_documented
from game_photo_policy_v1 import scan_kind,prepare_photo,verify_delivery
from social_media_gate_v2 import cover_for
URL="https://xfederiko11.github.io/gta-6/articoli/test/"
DIGEST="a"*64
KIND="official_game_photo"

class RightsTests(unittest.TestCase):
    def test_empty_registry_and_exact_review_record(self):
        row={"url":URL,"sha256":DIGEST,"kind":KIND,"scope":"site_and_social",
             "evidence_url":"https://example.org/specific-grant/test","reviewed_on":"2026-11-26",
             "review_status":"documented_reuse_reviewed"}
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"rights.json"
            def put(records):
                file.write_text(json.dumps({"schema":"gta6-photo-rights-review-v1","records":records}))
                return load(file)
            self.assertEqual(put([]),{})
            data=put([row]);self.assertIn((URL,KIND,DIGEST),data)
            with patch("photo_rights_v1.load",return_value=data):
                self.assertTrue(reuse_documented(URL,KIND,DIGEST))
                self.assertFalse(reuse_documented(URL,KIND,"b"*64))
                self.assertFalse(reuse_documented(URL,"approved_gameplay",DIGEST))
            self.assertEqual(put([row,row]),{})
            self.assertEqual(put([dict(row,evidence_url="https://www.rockstargames.com/VI/media")]),{})
            self.assertEqual(put([dict(row,scope="site_only")]),{})
            self.assertEqual(put([dict(row,review_status="pending")]),{})
    def test_technical_photo_checks_do_not_grant_rights(self):
        item={"url":URL,"text":"Una guida verificata.","source":"GTA VI Italia",
              "photo_kind":KIND,"cover_sha256":DIGEST,"media_url":cover_for(URL)}
        with patch("game_photo_policy_v1.scan_details",return_value=(KIND,DIGEST)),patch("photo_rights_v1.reuse_documented",return_value=False),patch("game_photo_policy_v1.owned_photo_details",return_value=(KIND,DIGEST)),patch("game_photo_policy_v1.probe_cover_digest",return_value=True) as probe:
            self.assertIsNone(scan_kind(URL));self.assertIsNone(prepare_photo(item))
            self.assertFalse(verify_delivery(item));probe.assert_not_called()
        with patch("game_photo_policy_v1.scan_details",return_value=(KIND,DIGEST)),patch("photo_rights_v1.reuse_documented",return_value=True):
            self.assertEqual(scan_kind(URL),KIND)
            self.assertEqual(prepare_photo(item)["cover_sha256"],DIGEST)
    def test_scan_skips_unreviewed_pages_without_network(self):
        from game_photo_policy_v1 import scan_details
        scan_details.cache_clear()
        try:
            with patch("photo_rights_v1.load",return_value={}),patch("game_photo_policy_v1.owned_photo_details") as fetch:
                self.assertIsNone(scan_details(URL))
                fetch.assert_not_called()
            scan_details.cache_clear()
            with patch("photo_rights_v1.load",return_value={(URL,KIND,DIGEST):{}}),patch("game_photo_policy_v1.owned_photo_details",return_value=(KIND,DIGEST)) as fetch:
                self.assertEqual(scan_details(URL),(KIND,DIGEST))
                fetch.assert_called_once_with(URL)
        finally:
            scan_details.cache_clear()

    def test_attachment_and_copy_contract(self):
        from photo_rights_v1 import attachment_allowed,message_attachments_allowed
        cover=cover_for(URL)
        message={"text":"Guida "+URL,"assets":[{"image":{"url":cover}}]}
        with patch("photo_rights_v1.load",return_value={(URL,KIND,DIGEST):{}}),patch("game_photo_policy_v1.owned_photo_details",return_value=(KIND,DIGEST)),patch("game_photo_policy_v1.probe_cover_digest",return_value=True):
            self.assertTrue(attachment_allowed(cover,URL))
            self.assertTrue(message_attachments_allowed(message))
            self.assertTrue(message_attachments_allowed(dict(message,text="Guida "+URL+"?utm_source=x")))
            self.assertFalse(message_attachments_allowed(dict(message,text="Altra guida https://xfederiko11.github.io/gta-6/other/")))
            self.assertFalse(message_attachments_allowed(dict(message,assets=message["assets"]+[{"image":{"url":"https://www.rockstargames.com/photo.jpg"}}])))
            self.assertFalse(attachment_allowed("https://www.rockstargames.com/photo.jpg","https://www.rockstargames.com/VI/"))
        self.assertFalse(message_attachments_allowed(message))

    def test_missing_or_malformed_registry_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"missing.json";self.assertEqual(load(file),{})
            file.write_text("not-json");self.assertEqual(load(file),{})

if __name__=="__main__":unittest.main()
