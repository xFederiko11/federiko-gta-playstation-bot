"""Offline regression tests for the source-specific Rockstar Support fallback.

No external websites, paid APIs, Buffer writes or posting actions are used.
"""
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, Mock, patch
import requests

from sources import _browser_html, get_html, SupportBrowserFailure

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

    def test_gta_vi_support_is_separate_official_source_with_same_safety(self):
        config = json.loads(Path("sources.free.json").read_text())
        online = next(x for x in config["sources"] if x["id"] == "support-gta")
        gta6 = next(x for x in config["sources"] if x["id"] == "support-gta6")
        self.assertNotEqual(online["id"], gta6["id"])
        self.assertEqual(gta6["url"], "https://support.rockstargames.com/VI")
        self.assertEqual(online["url"], SUPPORT_URL)
        self.assertEqual(gta6["trust"], "official")
        self.assertTrue(gta6["browser_fallback_on_timeout"])
        self.assertTrue(gta6["article_index_fallback"])
        self.assertNotIn("article_index_fallback", online)
        self.assertEqual(gta6["interval"], 1800)
        self.assertIn("patch-notes", gta6["watch_existing_pattern"])
        self.assertIn("grand.theft.auto.vi", gta6["include_link_pattern"])

    def test_gta_vi_support_uses_only_same_origin_chromium_fallback(self):
        gta6 = {
            "id": "support-gta6",
            "url": "https://support.rockstargames.com/VI",
            "selector": "a[href*='/articles/']",
            "browser_fallback_on_timeout": True,
        }
        html = '<main><a href="/articles/id">GTA VI patch notes</a></main>'
        with (patch("sources.requests.get",
                    side_effect=requests.exceptions.ReadTimeout) as requests_get,
              patch("sources.time.sleep") as sleep,
              patch("sources._browser_html", return_value=html) as browser):
            self.assertEqual(get_html(gta6), html)
        self.assertEqual(requests_get.call_count, 2)
        sleep.assert_called_once_with(1)
        browser.assert_called_once_with(gta6, gta6["url"], None)

    def test_gta_vi_baseline_collects_real_official_links_without_announcing_old_news(self):
        from sources import collect_links
        gta6 = next(x for x in json.loads(Path("sources.free.json").read_text())["sources"]
                    if x["id"] == "support-gta6")
        html = ('<main>'
                '<a href="/articles/123/grand-theft-auto-vi-installation-requirements">'
                'GTA VI installation requirements</a>'
                '<a href="/articles/456/account-recovery-help">'
                'Account security and recovery help</a>'
                '</main>')
        article = ('<article><h1 data-testid="page-title">GTA VI installation</h1>'
                   '<p>Verified Rockstar installation support information.</p></article>')
        with patch("sources.get_html", side_effect=[html, article]) as fetch:
            events, state = collect_links(gta6, previous={})
        self.assertEqual(events, [])
        self.assertEqual(len(state["links"]), 1)
        self.assertEqual(fetch.call_count, 2)
        self.assertFalse(any("account-recovery-help" in u for u in state["links"]))
        self.assertTrue(all(url.startswith("https://support.rockstargames.com/articles/")
                            for url in state["links"]))

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

    def test_chromium_launch_failure_has_safe_phase_not_playwright_message(self):
        pw = Mock()
        pw.chromium.launch.side_effect = RuntimeError("proxy-auth:confidential")
        cm = MagicMock()
        cm.__enter__.return_value = pw
        with (patch("playwright.sync_api.sync_playwright", return_value=cm),
              self.assertLogs("gta6.sources", level="WARNING") as captured):
            with self.assertRaises(SupportBrowserFailure) as failure:
                _browser_html(SUPPORT, SUPPORT_URL)
        self.assertEqual(failure.exception.phase, "launch")
        self.assertEqual(failure.exception.reason, "RuntimeError")
        self.assertNotIn("confidential", str(failure.exception))
        self.assertNotIn("confidential", "\\n".join(captured.output))
        self.assertIn("phase=launch", "\\n".join(captured.output))

    def test_selector_failure_is_distinguished_from_navigation_failure(self):
        page = Mock(url=SUPPORT_URL)
        page.wait_for_selector.side_effect = RuntimeError("response content sensitive")
        browser = Mock()
        browser.new_page.return_value = page
        pw = Mock()
        pw.chromium.launch.return_value = browser
        cm = MagicMock()
        cm.__enter__.return_value = pw
        with (patch("playwright.sync_api.sync_playwright", return_value=cm),
              self.assertLogs("gta6.sources", level="WARNING") as captured):
            with self.assertRaises(SupportBrowserFailure) as failure:
                _browser_html(SUPPORT, SUPPORT_URL)
        self.assertEqual(failure.exception.phase, "selector")
        self.assertIn("reason=RuntimeError", "\\n".join(captured.output))
        self.assertNotIn("sensitive", str(failure.exception))
        browser.close.assert_called_once()
        page.wait_for_function.assert_not_called()

    def test_browser_network_error_logs_allowlisted_code_only(self):
        page = Mock(url=SUPPORT_URL)
        page.goto.side_effect = RuntimeError(
            "Page.goto: net::ERR_TUNNEL_CONNECTION_FAILED at "
            "https://proxy.invalid/user/secret-password?token=abc")
        browser = Mock()
        browser.new_page.return_value = page
        pw = Mock()
        pw.chromium.launch.return_value = browser
        cm = MagicMock()
        cm.__enter__.return_value = pw
        with (patch("playwright.sync_api.sync_playwright", return_value=cm),
              self.assertLogs("gta6.sources", level="WARNING") as captured):
            with self.assertRaises(SupportBrowserFailure) as failure:
                _browser_html(SUPPORT, SUPPORT_URL)
        self.assertEqual(failure.exception.phase, "navigation")
        self.assertEqual(failure.exception.reason,
                         "RuntimeError_ERR_TUNNEL_CONNECTION_FAILED")
        self.assertIn("ERR_TUNNEL_CONNECTION_FAILED", " ".join(captured.output))
        self.assertNotIn("secret-password", " ".join(captured.output))
        self.assertNotIn("proxy.invalid", " ".join(captured.output))
        browser.close.assert_called_once()

    def test_unknown_navigation_code_is_not_logged(self):
        page = Mock(url=SUPPORT_URL)
        page.goto.side_effect = RuntimeError(
            "Page.goto: net::ERR_CUSTOM_SECRET_ACCOUNT_XYZ at https://secret.invalid")
        browser = Mock()
        browser.new_page.return_value = page
        pw = Mock()
        pw.chromium.launch.return_value = browser
        cm = MagicMock()
        cm.__enter__.return_value = pw
        with (patch("playwright.sync_api.sync_playwright", return_value=cm),
              self.assertLogs("gta6.sources", level="WARNING") as captured):
            with self.assertRaises(SupportBrowserFailure) as failure:
                _browser_html(SUPPORT, SUPPORT_URL)
        self.assertEqual(failure.exception.reason, "RuntimeError")
        self.assertNotIn("CUSTOM_SECRET", " ".join(captured.output))
        self.assertNotIn("secret.invalid", " ".join(captured.output))

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



class RockstarOfficialIndexTests(unittest.TestCase):
    URL = "https://support.rockstargames.com/articles/ABC123/grand-theft-auto-vi-launch-updates-ps5"
    NEXT = "https://support.rockstargames.com/articles/NEW123/grand-theft-auto-vi-title-update"
    HTML = '<a href="'+URL+'?ref=foo">Grand Theft Auto VI Launch Updates</a>'
    BODY = '<article><h1 data-testid="page-title">GTA VI Launch Updates</h1><p>Official notes, test fixture.</p></article>'

    def source(self):
        return next(x for x in json.loads(Path("sources.free.json").read_text())["sources"]
                    if x["id"] == "support-gta6")

    def test_filters_official_patch_links_deduplicates_article_ids(self):
        from sources import support_index_links
        html = (self.HTML+
                '<a href="'+self.URL+'#note">GTA VI Launch Updates</a>'
                '<a href="/articles/ABC123/grand-theft-auto-vi-patch-notes">GTA VI Patch Notes</a>'
                '<a href="/articles/V1/grand-theft-auto-v-title-update">GTA V Title Update</a>'
                '<a href="/articles/VI1/grand-theft-auto-vii-title-update">Grand Theft Auto VII Title Update</a>'
                '<a href="/articles/HELP/grand-theft-auto-vi-installation-support">GTA VI installation</a>'
                '<a href="https://example.invalid/articles/FAKE/grand-theft-auto-vi-patch-notes">GTA VI patch notes</a>'
                '<a href="http://support.rockstargames.com/articles/INSECURE/gta-vi-patch-notes">GTA VI patch notes</a>')
        self.assertEqual(support_index_links(html), {self.URL:"Grand Theft Auto VI Launch Updates"})
        old=self.URL+"?historic=1"
        self.assertEqual(list(support_index_links(html, {old:"previous"})), [old])

    def test_index_http_shell_uses_same_official_browser_and_rejects_empty(self):
        from sources import read_support_article_index, SUPPORT_ARTICLE_INDEX
        response=MagicMock(status_code=200,url=SUPPORT_ARTICLE_INDEX)
        response.__enter__.return_value=response
        response.iter_content.return_value=[b"<main>Knowledge Base</main>"]
        source=self.source()
        with (patch("sources.requests.get",return_value=response) as request,
              patch("sources._browser_html",return_value=self.HTML) as browser):
            self.assertEqual(list(read_support_article_index(source)), [self.URL])
            request.assert_called_once()
            self.assertFalse(request.call_args.kwargs["allow_redirects"])
            browser.assert_called_once_with(source,SUPPORT_ARTICLE_INDEX)
        with (patch("sources.requests.get",return_value=response),
              patch("sources._browser_html",return_value="<main>Loading</main>")):
            with self.assertRaisesRegex(ValueError,"no official GTA VI patch links"):
                read_support_article_index(source)

    def test_index_baselines_existing_news_then_reports_new_link_and_keeps_history(self):
        from sources import collect_links
        source=self.source()
        previous={"links":{"https://support.rockstargames.com/articles/OLD/old":"Prior"}}
        with (patch("sources.get_html",side_effect=[requests.ReadTimeout(),self.BODY]),
              patch("sources.read_support_article_index",return_value={self.URL:"GTA VI Launch Updates"})):
            events,state=collect_links(source,previous)
        self.assertEqual(events,[])
        self.assertTrue(state["article_index_baseline"])
        self.assertIn(self.URL,state["article_hashes"])
        self.assertEqual(len(state["links"]),2)
        with (patch("sources.get_html",side_effect=[requests.ReadTimeout(),self.BODY,self.BODY]),
              patch("sources.read_support_article_index",return_value={self.URL:"GTA VI Launch Updates",self.NEXT:"GTA VI Title Update"})):
            events,next_state=collect_links(source,state)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]["source_url"],self.NEXT)
        self.assertTrue(next_state["article_index_baseline"])

    def test_index_does_not_mask_errors_or_other_sources(self):
        from sources import collect_links
        with (patch("sources.get_html",side_effect=requests.ReadTimeout()),
              patch("sources.read_support_article_index",side_effect=ValueError("no verified links")) as index):
            with self.assertRaisesRegex(ValueError,"no verified links"):
                collect_links(self.source(),{})
            index.assert_called_once()
            with self.assertRaises(requests.ReadTimeout):
                collect_links(SUPPORT,{})
            self.assertEqual(index.call_count,1)

    def test_known_patch_revision_is_not_hidden_by_first_index_baseline(self):
        from sources import collect_links
        previous={"links":{self.URL:"GTA VI Launch Updates"},"article_hashes":{self.URL:"old-hash"}}
        with (patch("sources.get_html",side_effect=[requests.ReadTimeout(),self.BODY]),
              patch("sources.read_support_article_index",return_value={self.URL:"GTA VI Launch Updates"})):
            events,state=collect_links(self.source(),previous)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]["change_context"],"patch note aggiornata")
        self.assertTrue(state["article_index_baseline"])


if __name__ == "__main__":
    unittest.main()
