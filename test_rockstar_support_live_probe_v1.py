"""Network-free contracts for the public, read-only Rockstar Support probe."""
from __future__ import annotations
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
import json
import unittest

from sources import SupportBrowserFailure
from rockstar_support_live_probe_v1 import OFFICIAL_SOURCES, probe


GOOD = ('<nav><a href="/articles/a">Release notes GTA VI</a></nav>'
        '<article><a href="https://support.rockstargames.com/articles/b">'
        'Official installation notes</a></article>')


class RockstarSupportLiveProbeTests(unittest.TestCase):
    def test_live_chromium_install_and_probe_share_the_same_browser_directory(self):
        workflow = Path(".github/workflows/rockstar-support-qa.yml").read_text(
            encoding="utf-8")
        value = "PLAYWRIGHT_BROWSERS_PATH: ${{ github.workspace }}/.browsers"
        self.assertEqual(workflow.count(value), 2)
        self.assertIn("timeout 210s python rockstar_support_live_probe_v1.py", workflow)
        self.assertNotIn("BUFFER_API_KEY:", workflow)
        self.assertNotIn("STATE_PASSWORD:", workflow)

    def test_strict_source_list_is_official_and_only_two_sources(self):
        self.assertEqual(set(OFFICIAL_SOURCES), {"support-gta6", "support-gta"})
        self.assertTrue(all(url.startswith("https://support.rockstargames.com/")
                            for url in OFFICIAL_SOURCES.values()))

    def test_authentic_article_links_are_observed_without_media_or_state_writes(self):
        reader = Mock(return_value=GOOD)
        messages = []
        outcomes = probe(fetcher=reader, report=messages.append)
        self.assertEqual(outcomes, {
            "support-gta6": "listing_present", "support-gta": "listing_present"})
        self.assertEqual(reader.call_count, 2)
        self.assertTrue(all("status=listing_present links=2" in msg for msg in messages))
        self.assertFalse(any("Release notes" in msg for msg in messages))

    def test_timeout_phase_is_reported_with_only_the_sanitized_reason(self):
        reader = Mock(side_effect=SupportBrowserFailure("navigation", "TimeoutError"))
        messages = []
        outcomes = probe(fetcher=reader, report=messages.append)
        self.assertEqual(outcomes["support-gta6"], "browser_navigation")
        self.assertTrue(all("phase=navigation reason=TimeoutError" in m for m in messages))
        self.assertEqual(reader.call_count, 2)

    def test_unexpected_exception_cannot_log_proxy_secret(self):
        reader = Mock(side_effect=RuntimeError("user:super-secret@proxy"))
        messages = []
        outcomes = probe(fetcher=reader, report=messages.append)
        self.assertEqual(outcomes["support-gta6"], "source_RuntimeError")
        self.assertTrue(all("reason=RuntimeError" in msg for msg in messages))
        self.assertFalse(any("super-secret" in msg for msg in messages))

    def test_no_links_is_not_a_source_success(self):
        reader = Mock(return_value='<main><a href="/accounts/account-security">Account</a>'
                                    '<a href="https://evil.invalid/articles/123">Fake</a></main>')
        messages = []
        outcomes = probe(fetcher=reader, report=messages.append)
        self.assertEqual(outcomes["support-gta6"], "empty_listing")
        self.assertTrue(all("phase=content reason=no_article_links" in m for m in messages))

    def test_url_modified_off_official_is_not_fetched(self):
        original = json.loads(Path("sources.free.json").read_text(encoding="utf-8"))
        source = next(x for x in original["sources"] if x["id"] == "support-gta6")
        source["url"] = "https://fake.invalid/VI"
        with TemporaryDirectory() as temp:
            file = Path(temp) / "source.json"
            file.write_text(json.dumps(original), encoding="utf-8")
            reader = Mock(return_value=GOOD)
            messages = []
            outcomes = probe(file, fetcher=reader, report=messages.append)
        self.assertEqual(outcomes["support-gta6"], "unsafe_configuration")
        self.assertEqual(outcomes["support-gta"], "listing_present")
        reader.assert_called_once()
        self.assertIn("phase=config reason=invalid_official_source", messages[0])


if __name__ == "__main__":
    unittest.main()
