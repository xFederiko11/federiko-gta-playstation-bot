"""Read-only diagnostics must never reserve or publish a post."""
import copy
import unittest
from datetime import datetime, timedelta, timezone
from editorial_autopilot_v137 import selection_diagnostics, similarity_key, identity

NOW = datetime(2026, 11, 24, 19, 0, tzinfo=timezone.utc)


def item(title, url, age_minutes):
    return {"title": title, "url": url, "source": "PowerPyx", "language": "it",
            "published": (NOW - timedelta(minutes=age_minutes)).isoformat()}


class EditorialSelectionFunnelTests(unittest.TestCase):
    def test_funnel_counts_and_does_not_mutate_state(self):
        fresh = item("GTA VI guida trofei platino PS5", "https://www.powerpyx.com/example-gta6-guide/", 10)
        stale = item("GTA VI guida veicoli", "https://www.powerpyx.com/old-gta6-guide/", 900)
        duplicate = item("GTA VI guida trofei gia pubblicata", "https://www.powerpyx.com/already-shared/", 10)
        unrelated = item("Nintendo Switch notizia", "https://www.powerpyx.com/unrelated/", 10)
        state = {"entries": {identity(duplicate["url"]): {"status": "reserved"}},
                 "signatures": {similarity_key(duplicate["title"]): "dummy"}}
        before = copy.deepcopy(state)
        result = selection_diagnostics([fresh, stale, duplicate, unrelated], state, NOW)
        self.assertEqual(result, {"feed_items": 4, "fresh": 3, "not_reserved": 2,
                                  "on_topic": 1, "quality_eligible": 1})
        self.assertEqual(state, before)

    def test_invalid_and_future_dates_do_not_crash(self):
        state = {"entries": {}, "signatures": {}}
        future = item("GTA VI guide", "https://www.powerpyx.com/future/", -30)
        invalid = {"published": "not-a-date", "title": "GTA VI guide",
                   "url": "https://www.powerpyx.com/invalid/"}
        result = selection_diagnostics([future, invalid], state, NOW)
        self.assertEqual(result["fresh"], 0)


if __name__ == "__main__":
    unittest.main()
