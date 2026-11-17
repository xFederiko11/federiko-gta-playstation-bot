import copy
import unittest

from presentation import (_post_weight, demo_events, format_post, group_platform_events,
                          render_card_html)


def event(platform="PS5", **extra):
    base = {"event_key": "update-1", "game": "GTA VI", "category": "PATCH",
            "data_kind": "package_update", "region": "EU", "platforms": [platform],
            "title": "Aggiornamento disponibile", "trust": "observation",
            "version_namespace": "publisher_shared_build",
            "facts": [{"label": "Versione", "value": "1.0"},
                      {"label": "Download", "value": 1234567, "unit": "byte"}],
            "source_name": "Store PS", "source_url": "https://example.org/ps",
            "observed_at": "2026-11-17T14:00:00Z"}
    return {**base, **extra}


class GroupingTests(unittest.TestCase):
    def test_identical_values_merge_platforms_preserve_sources_and_input(self):
        first = event()
        other = event("Xbox Series X|S", source_name="Store Xbox", source_url="https://example.org/xbox",
                      observed_at="2026-11-17T14:05:00Z")
        original = copy.deepcopy([first, other])
        groups = group_platform_events([first, other])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["platforms"], ["PS5", "Xbox Series X|S"])
        self.assertEqual(len(groups[0]["sources"]), 2)
        self.assertEqual([first, other], original)

    def test_different_download_sizes_are_separate(self):
        other = event("Xbox Series X|S")
        other["facts"][1]["value"] = 2234567
        self.assertEqual(len(group_platform_events([event(), other])), 2)

    def test_region_and_measurement_kind_are_significant(self):
        for other in (event("Xbox", region="US"), event("Xbox", data_kind="installed_size")):
            self.assertEqual(len(group_platform_events([event(), other])), 2)

    def test_missing_fields_never_imply_equality(self):
        for field in ("region", "event_key", "data_kind"):
            first, other = event(), event("Xbox")
            first.pop(field)
            other.pop(field)
            self.assertEqual(len(group_platform_events([first, other])), 2)
        first, other = event(), event("Xbox")
        first["facts"][1]["value"] = None
        other["facts"][1]["value"] = None
        self.assertEqual(len(group_platform_events([first, other])), 2)

    def test_version_namespaces_are_not_cross_console_versions(self):
        for namespaces in ((None, None), ("sony_package", "xbox_package")):
            first, other = event(), event("Xbox Series X|S")
            first["version_namespace"], other["version_namespace"] = namespaces
            self.assertEqual(len(group_platform_events([first, other])), 2)

    def test_news_can_merge_without_package_version(self):
        facts = [{"label": "Evento", "value": "Bonus doppio"}]
        events = [event(facts=facts, version_namespace=None, data_kind="event"),
                  event("Xbox Series X|S", facts=facts, version_namespace=None, data_kind="event")]
        self.assertEqual(len(group_platform_events(events)), 1)

    def test_bytes_are_not_install_or_patch_size_and_units_stay_distinct(self):
        for other in (event("Xbox", install_bytes=123), event("Xbox", patch_bytes=123)):
            self.assertEqual(len(group_platform_events([event(), other])), 2)
        other = event("Xbox")
        other["facts"][1]["unit"] = "GiB"
        self.assertEqual(len(group_platform_events([event(), other])), 2)

    def test_zero_is_a_real_value_not_missing(self):
        facts = [{"label": "File rimossi", "value": 0}]
        self.assertEqual(len(group_platform_events([event(facts=facts, version_namespace=None),
                          event("Xbox", facts=facts, version_namespace=None)])), 1)

    def test_claim_provenance_is_preserved(self):
        self.assertEqual(len(group_platform_events([event(), event("Xbox", trust="community")])), 2)

    def test_facts_order_does_not_create_fake_console_difference(self):
        other = event("Xbox")
        other["facts"].reverse()
        self.assertEqual(len(group_platform_events([event(), other])), 1)

    def test_different_console_headlines_get_a_shared_neutral_title(self):
        grouped = group_platform_events([event(title="Download su PS5"),
                                         event("Xbox", title="Download su Xbox")])[0]
        self.assertEqual(grouped["title"], "Aggiornamento per più piattaforme")


class PresentationTests(unittest.TestCase):
    def test_html_displays_actual_numbers_missing_values_and_demo_label(self):
        shared, console = demo_events()
        first, second = render_card_html(shared), render_card_html(console)
        for text in ("DEMO · DATI FITTIZI", "1.25 GiB", "Non disponibile", "PS5", "Xbox Series X|S"):
            self.assertIn(text, first)
        for text in ("1.60 GiB", "+0.35 GiB", "DEMO 0.2"):
            self.assertIn(text, second)

    def test_html_is_self_contained_and_escapes_content(self):
        content = render_card_html(event(title="<script>alert(1)</script>"))
        self.assertNotIn("<script>", content)
        self.assertIn("&lt;script&gt;", content)
        self.assertNotIn("<link", content)
        self.assertNotIn("<img", content)

    def test_community_cannot_appear_as_official(self):
        content = render_card_html(event(trust="community"))
        self.assertIn("SEGNALAZIONE COMMUNITY", content)
        self.assertNotIn("FONTE UFFICIALE", content)

    def test_unknown_platform_and_dates_are_not_invented(self):
        value = event(platforms=[], observed_at=None, source_name=None, source_url=None)
        content = render_card_html(value)
        for missing in ("Piattaforma non disponibile", "Data non disponibile", "Fonte non disponibile"):
            self.assertIn(missing, content)

    def test_text_stays_within_standard_x_limit(self):
        for value in (event(), event(title="Titolo " * 80), *demo_events()):
            text = format_post(value)
            self.assertLessEqual(_post_weight(text), 280)
            self.assertIn("GTA VI", text)

    def test_grouped_text_lists_all_platforms(self):
        grouped = group_platform_events([event(), event("Xbox Series X|S")])[0]
        text = format_post(grouped)
        self.assertIn("PS5 + Xbox Series X|S", text)
        self.assertIn("1234567 byte", text)

    def test_spoiler_and_demo_are_visible_in_text(self):
        value = event(spoiler=True, demo=True)
        self.assertIn("SPOILER", format_post(value))
        self.assertIn("DEMO · DATI FITTIZI", format_post(value))
        self.assertIn("SPOILER", render_card_html(value))


if __name__ == "__main__":
    unittest.main()
