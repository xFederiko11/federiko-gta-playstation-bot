"""Offline regression tests for the source-specific Rockstar Support fallback.

No external websites, paid APIs, Buffer writes or posting actions are used.
"""
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, Mock, patch
import requests

from sources import _browser_html, get_html

SUPPORT_URL = "https://support.rockstargames.com/gta-online"
SUPPORT = {
    "id": "support-gta", "url": SUPPORT_URL,
    "selector": "a[href*='/articles/']",
    "browser_fallback_on_timeout": True,
}
READY_HTML = '<html><a href="/articles/abc">Patch notes ufficiali</a></html>'


class RockstarSupportTimeoutTests(unittest.TestCase):
    def test_source_configuration_enables_official_only_browser_fallback(self):
        source = next(x for x in json.loads(Path("sources.free.json").read_text())["sources"]
                      if x["id"] == "support-gta")
        self.assertEqual(source["url"], SUPPORT_URL)
        self.assertTrue(source["browser_fallback_on_timeout"])
        self.assertFalse(source["render_js"])

    def test_support_first_timeout_then_real_html_success(self):
        response = Mock(text=READY_HTML)
        response.raise_for_status.return_value = None
        with (patch("sources.requests.get",
                    side_effect=[requests.exceptions.ReadTimeout(), response]) as get,
              patch("sources.time.sleep") as sleep,
              patch("sources._browser_html") as browser):
            self.assertEqual(get_html(SUPPORT), READY_HTML)
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(1)
        browser.assert_not_called()
        self.assertTrue(all(call.kwargs["timeout"] == (5, 12)
                            for call in get.call_args_list))

    def test_support_two_timeouts_switch_to_same_official_browser_url(self):
        with (patch("sources.requests.get",
                    side_effect=requests.exceptions.ReadTimeout) as get,
              patch("sources.time.sleep") as sleep,
              patch("sources._browser_html", return_value=READY_HTML) as browser):
            self.assertEqual(get_html(SUPPORT), READY_HTML)
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(1)
        browser.assert_called_once_with(SUPPORT, SUPPORT_URL, None)

    def test_support_http_200_shell_without_articles_uses_browser(self):
        response = Mock(text="<html><body>Loading</body></html>")
        response.raise_for_status.return_value = None
        with (patch("sources.requests.get", return_value=response) as get,
              patch("sources._browser_html", return_value=READY_HTML) as browser):
            self.assertEqual(get_html(SUPPORT), READY_HTML)
        get.assert_called_once()
        browser.assert_called_once_with(SUPPORT, SUPPORT_URL, None)

    def test_browser_fallback_failure_does_not_turn_into_fabricated_success(self):
        with (patch("sources.requests.get",
                    side_effect=requests.exceptions.ReadTimeout) as get,
              patch("sources.time.sleep"),
              patch("sources._browser_html",
                    side_effect=ValueError("no official support article")) as browser):
            with self.assertRaisesRegex(ValueError, "no official support article"):
                get_html(SUPPORT)
        self.assertEqual(get.call_count, 2)
        browser.assert_called_once()

    def test_explicitly_disabled_browser_keeps_old_fail_closed_behavior(self):
        disabled = {**SUPPORT, "browser_fallback_on_timeout": False}
        with (patch("sources.requests.get",
                    side_effect=requests.exceptions.ReadTimeout) as get,
              patch("sources.time.sleep") as sleep,
              patch("sources._browser_html") as browser):
            with self.assertRaises(requests.exceptions.ReadTimeout):
                get_html(disabled)
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(1)
        browser.assert_not_called()

    def test_off_domain_url_cannot_trigger_official_support_browser(self):
        malicious = {**SUPPORT, "url": "https://example.net/loader"}
        with (patch("sources.requests.get",
                    side_effect=requests.exceptions.ReadTimeout) as get,
              patch("sources.time.sleep"),
              patch("sources._browser_html") as browser):
            with self.assertRaises(requests.exceptions.ReadTimeout):
                get_html(malicious)
        self.assertEqual(get.call_count, 2)
        browser.assert_not_called()

    def test_browser_redirect_off_official_host_fails_and_browser_closes(self):
        page = Mock()
        page.url = "https://not-rockstar.example.net/challenge"
        browser = Mock()
        browser.new_page.return_value = page
        pw = Mock()
        pw.chromium.launch.return_value = browser
        cm = MagicMock()
        cm.__enter__ = Mock(return_value=pw)
        cm.__exit__ = Mock(return_value=None)
        with patch("playwright.sync_api.sync_playwright", return_value=cm):
            with self.assertRaisesRegex(ValueError, "approved host"):
                _browser_html(SUPPORT, SUPPORT_URL)
        browser.close.assert_called_once()
        page.wait_for_selector.assert_not_called()

    def test_non_support_sources_keep_single_timeout_and_no_browser(self):
        with (patch("sources.requests.get",
                    side_effect=requests.exceptions.ReadTimeout) as get,
              patch("sources.time.sleep") as sleep,
              patch("sources._browser_html") as browser):
            with self.assertRaises(requests.exceptions.ReadTimeout):
                get_html({"id": "other", "url": "https://example.org/"})
        get.assert_called_once()
        self.assertEqual(get.call_args.kwargs["timeout"], 30)
        sleep.assert_not_called()
        browser.assert_not_called()


if __name__ == "__main__":
    unittest.main()
