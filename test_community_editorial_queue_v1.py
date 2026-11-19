"""No-network checks for autonomous GitHub editorial intake."""
import unittest
import base64
import json
import re

from community_editorial_queue_v1 import classify, valid_candidate, markdown, ISSUE_MARKER


def item(title, source="PowerPyx", tier="specialist", url="https://powerpyx.com/gta-6-guide/"):
    return {"title": title, "source":source, "tier":tier, "url":url,
            "published_utc":"2026-11-19T07:00:00+00:00"}


class QueueTests(unittest.TestCase):
    def test_labels_are_explicit_and_not_rockstar_announcements(self):
        self.assertIn("DATAMINING", classify(item("GTA 6 datamined police files"))[0])
        self.assertIn("RUMOR", classify(item("GTA VI leaked map rumor"))[0])
        self.assertIn("COMMUNITY", classify(item("GTA VI community challenge"))[0])
        self.assertIn("GUIDA INDIPENDENTE", classify(item("GTA VI guide"))[0])
        self.assertIn("GUIDA INDIPENDENTE",
                      classify(item("GTA 6 walkthrough",tier="specialist_video"))[0])

    def test_topic_and_https_filter(self):
        self.assertTrue(valid_candidate(item("GTA VI vehicles")))
        self.assertFalse(valid_candidate(item("Cooking with friends", source="IGN")))
        self.assertFalse(valid_candidate(item("GTA 6 hack",url="javascript:alert(1)")))
        self.assertFalse(valid_candidate(item("GTA 6 patch",url="https://user:pw@fake.test/a")))
        self.assertFalse(valid_candidate(item("GTA 6 " + "x" * 350)))

    def test_markdown_contains_attribution_and_safety(self):
        digest={"schema":"gta6-research-digest-v1","generated_utc":"2026-11-19T08:00:00Z",
                "candidates":[item("GTA VI leaked garage feature"),
                              item("Cooking advice",source="Other")],
                "errors":[{"source":"GTA Series Videos","error":"RequestException"}],
                "manual_sources":[{"name":"GTAForums"}]}
        result=markdown(digest)
        self.assertIn(ISSUE_MARKER,result)
        encoded=re.search(r"<!-- gta6-verified-source-feed-b64:([A-Za-z0-9_=-]+) -->",result)
        self.assertIsNotNone(encoded)
        payload=json.loads(base64.urlsafe_b64decode(encoded.group(1)).decode("utf-8"))
        self.assertEqual(payload["schema"],"gta6-community-feed-v1")
        self.assertEqual(len(payload["items"]),1)
        self.assertFalse(payload["items"][0]["verified"])
        self.assertIn("RUMOR",payload["items"][0]["status"])
        self.assertIn("RUMOR",result)
        self.assertIn("da controllare",result)
        self.assertIn("PowerPyx",result)
        self.assertIn("Nessun controllo trophy-safe",result)
        self.assertIn("GTAForums",result)
        self.assertIn("GTA Series Videos",result)
        self.assertNotIn("Cooking advice",result)
        self.assertNotIn("Buffer: invio",result)

    def test_unknown_schema_fails_closed(self):
        with self.assertRaises(ValueError):
            markdown({"schema":"different"})
        blank=markdown({"schema":"gta6-research-digest-v1","candidates":[]})
        self.assertIn("Nessun nuovo titolo",blank)

if __name__=="__main__":
    unittest.main()
