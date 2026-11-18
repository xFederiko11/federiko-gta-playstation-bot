"""Offline Italian-only editorial and layout tests."""
import unittest
from unittest.mock import Mock
from editorial_language_it import (
    italian_title, TranslationUnavailable, contains_english_prose,
)

class TranslationTests(unittest.TestCase):
    def client(self, translation, status=200):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            'responseStatus': status,
            'responseData': {'translatedText': translation},
        }
        http = Mock()
        http.get.return_value = response
        return http

    def test_italian_titles_bypass_external_service(self):
        self.assertEqual(
            italian_title('GTA VI: nuove missioni e ricompense', 'it'),
            'GTA VI: nuove missioni e ricompense'
        )

    def test_english_title_translated_and_preserves_numbers(self):
        translated = italian_title(
            'GTA 6: 60 FPS on PS5 Pro',
            'en',
            session=self.client('GTA 6: 60 FPS su PS5 Pro'),
        )
        self.assertEqual(translated, 'GTA 6: 60 FPS su PS5 Pro')

    def test_machine_translation_failure_blocks_post(self):
        for reply in ('GTA VI: New gameplay features', '', 'MyMemory quota exceeded'):
            with self.assertRaises(TranslationUnavailable):
                italian_title('GTA VI: New gameplay features', 'en', session=self.client(reply))

    def test_numbers_may_not_change(self):
        with self.assertRaises(TranslationUnavailable):
            italian_title('GTA 6: 60 FPS on PS5 Pro', 'en',
                          session=self.client('GTA 6: 30 FPS su PS5 Pro'))

    def test_proper_names_may_not_disappear(self):
        with self.assertRaises(TranslationUnavailable):
            italian_title('Rockstar announces GTA 6', 'en',
                          session=self.client('Annunciato GTA 6'))

    def test_invalid_language_fails_closed(self):
        with self.assertRaises(TranslationUnavailable):
            italian_title('GTA 6: New gameplay', 'de')

    def test_english_checker_skips_links_and_hashtags(self):
        self.assertFalse(contains_english_prose(
            '📰 GTA VI | Ultime novità\n\nNuove missioni da completare.\n\n'
            'Fonte: https://example.org/new-players-launch\n\n#GTAVI'
        ))
        self.assertTrue(contains_english_prose('GTA VI: New gameplay features revealed'))

if __name__ == '__main__':
    unittest.main()
