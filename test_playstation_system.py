import unittest
import requests
from unittest.mock import Mock, patch

from playstation_system import parse_system_page, fetch_system_update, URLS


def page(current="DEMO", historical="99.99"):
    return f"<main><div><h3>Versione: {current}</h3><ul><li>Correzioni di sicurezza di esempio.</li></ul></div><span>Aggiornamenti precedenti del software di sistema</span><h3>Versione: {historical}</h3></main>"


class SystemTests(unittest.TestCase):
    def test_current_version_is_not_highest_historical_version(self):
        event = parse_system_page(page("14.02", "99.99"), "PS4", observed_at="2026-11-17T00:00:00Z")
        self.assertEqual(event["version"], "14.02")
        self.assertIsNone(event["release_at"])
        self.assertEqual(event["platforms"], ["PS4"])
        self.assertEqual(event["trust"], "official")

    def test_ps5_punctuation_is_preserved(self):
        event = parse_system_page(page("26.07-14.23.00", "99.99-99.99.99"), "PS5")
        self.assertEqual(event["facts"][0]["value"], "26.07-14.23.00")

    def test_two_possible_current_versions_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_system_page("<h3>Versione: 14.01</h3>" + page("14.02"), "PS4")

    def test_missing_history_boundary_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_system_page("<h3>Versione: 14.02</h3>", "PS4")

    def test_script_and_old_versions_cannot_become_current(self):
        raw = "<script><h3>Versione: 99.99</h3></script>" + page("14.02")
        self.assertEqual(parse_system_page(raw, "PS4")["version"], "14.02")

    def test_unofficial_source_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_system_page(page("14.02"), "PS4", source_url="https://playstation.com.example.org/updates")

    def test_absent_notes_do_not_create_fake_patch_notes(self):
        value = parse_system_page("<div><h3>Versione: 14.02</h3></div><span>Aggiornamenti precedenti del software</span>", "PS4")
        self.assertIsNone(value["facts"][1]["value"])

    def test_transient_http_retries_same_page_once(self):
        error = requests.HTTPError("private upstream details", response=Mock(status_code=503))
        with (patch("playstation_system._fetch_system_page", side_effect=[error, {"version": "test"}]) as fetch,
              patch("playstation_system.time.sleep") as delay,
              self.assertLogs("gta6.playstation", level="WARNING") as logs):
            self.assertEqual(fetch_system_update("PS5"), {"version": "test"})
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(fetch.call_args_list[0], fetch.call_args_list[1])
        delay.assert_called_once_with(1)
        self.assertIn("HTTP_503", " ".join(logs.output))
        self.assertNotIn("private upstream details", " ".join(logs.output))

    def test_rate_limit_and_access_denial_do_not_retry(self):
        for status in (401, 403, 404, 429):
            with self.subTest(status=status):
                error = requests.HTTPError("do not print", response=Mock(status_code=status))
                with (patch("playstation_system._fetch_system_page", side_effect=error) as fetch,
                      patch("playstation_system.time.sleep") as delay):
                    with self.assertRaises(requests.HTTPError):
                        fetch_system_update("PS5")
                fetch.assert_called_once()
                delay.assert_not_called()

    def test_timeout_retry_is_bounded_and_parse_failure_never_retries(self):
        for error, count in ((requests.ReadTimeout(), 2), (ValueError("ambiguous page"), 1),
                             (requests.exceptions.SSLError(), 1), (requests.exceptions.ProxyError(), 1)):
            with (patch("playstation_system._fetch_system_page", side_effect=error) as fetch,
                  patch("playstation_system.time.sleep")):
                with self.assertRaises(type(error)):
                    fetch_system_update("PS5")
                self.assertEqual(fetch.call_count, count)

    @patch("playstation_system.requests.get")
    def test_binary_redirect_is_not_downloaded(self, get):
        response = Mock(url=URLS["PS5"], headers={"Content-Type": "application/octet-stream"})
        get.return_value.__enter__.return_value = response
        with self.assertRaises(ValueError):
            fetch_system_update("PS5")
        response.iter_content.assert_not_called()
        self.assertTrue(get.call_args.kwargs["stream"])

    @patch("playstation_system.requests.get")
    def test_live_client_parses_only_html_response(self, get):
        response = Mock(url=URLS["PS4"], headers={"Content-Type": "text/html; charset=utf-8"})
        response.iter_content.return_value = [page("14.02").encode()]
        get.return_value.__enter__.return_value = response
        self.assertEqual(fetch_system_update("PS4")["version"], "14.02")


if __name__ == "__main__":
    unittest.main()
