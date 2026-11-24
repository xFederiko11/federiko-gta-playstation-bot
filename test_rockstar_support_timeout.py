"""Regression tests for the source-specific Rockstar Support timeout fallback."""
import unittest
from unittest.mock import Mock, patch
import requests
from sources import get_html


class RockstarSupportTimeoutTests(unittest.TestCase):
    def test_support_timeout_once_then_success(self):
        result = Mock()
        result.text = "<html>ok</html>"
        result.raise_for_status.return_value = None
        with patch("sources.requests.get", side_effect=[requests.exceptions.ReadTimeout(), result]) as get, patch("sources.time.sleep") as sleep:
            self.assertEqual(get_html({"id": "support-gta", "url": "https://support.rockstargames.com/gta-online"}), result.text)
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(1)
        self.assertTrue(all(call.kwargs["timeout"] == 45 for call in get.call_args_list))

    def test_support_second_timeout_propagates(self):
        with patch("sources.requests.get", side_effect=requests.exceptions.ReadTimeout) as get, patch("sources.time.sleep") as sleep:
            with self.assertRaises(requests.exceptions.ReadTimeout):
                get_html({"id": "support-gta", "url": "https://support.rockstargames.com/gta-online"})
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_other_sources_do_not_retry(self):
        with patch("sources.requests.get", side_effect=requests.exceptions.ReadTimeout) as get, patch("sources.time.sleep") as sleep:
            with self.assertRaises(requests.exceptions.ReadTimeout):
                get_html({"id": "other", "url": "https://example.org/"})
        self.assertEqual(get.call_count, 1)
        sleep.assert_not_called()
        self.assertEqual(get.call_args.kwargs["timeout"], 30)


if __name__ == "__main__":
    unittest.main()
