"""Fail-closed Italian title translation for the public GTA VI editorial feeds.

Only already-public news headlines are sent to the free translation endpoint.
If unavailable or suspicious, the article is skipped. No English fallback.
"""
from __future__ import annotations

from html import unescape
import re
import unicodedata
import requests

API_URL = "https://api.mymemory.translated.net/get"
TAGS = re.compile(r"<[^>]*>")
SPACE = re.compile(r"\s+")
ENGLISH_MARKERS = re.compile(
    r"\b(?:the|and|with|from|gets|getting|releasing|released|announces|announced|"
    r"reveals|revealed|new|latest|first|this|that|about|here|when|where|"
    r"why|what|how|guide|review|details|ahead|available|coming|launches|"
    r"launching|players|gameplay\s+features)\b", re.I
)
BRAND_TERMS = (
    "rockstar", "ps5", "ps5 pro", "gta+", "metacritic",
    "xbox", "vice city", "lucia", "jason", "leonida",
)


class TranslationUnavailable(ValueError):
    """Safe-to-skip machine translation error, not permission to post English."""


def plain(value: str) -> str:
    return SPACE.sub(" ", unescape(TAGS.sub(" ", str(value)))).strip()


def numerals(value: str) -> list[str]:
    # Preserve figures, dates, FPS values, percentages and prices.
    # Normalise thousand separators from English to Italian punctuation.
    return sorted(re.sub(r"[,\.]", "", n) for n in re.findall(r"(?<!\w)\d[\d,.]*", value))


def contains_english_prose(value: str) -> bool:
    """Conservative send-time guard for obviously untranslated English wording.

    Links, hashtags and proper channel names are not prose.
    """
    text = re.sub(r"https?://\\S+", " ", plain(value))
    text = re.sub(r"#[A-Za-z0-9_]+", " ", text)
    return bool(ENGLISH_MARKERS.search(text))


def italian_title(headline: str, language: str, *, session=None) -> str:
    original = plain(headline)
    if language == "it":
        if not original:
            raise TranslationUnavailable("Titolo italiano vuoto")
        return original
    if language != "en" or not original or len(original.encode("utf-8")) > 500:
        raise TranslationUnavailable("Lingua sconosciuta o titolo troppo lungo")
    try:
        r = (session or requests).get(
            API_URL, params={"q": original, "langpair": "en|it", "mt": "1"},
            headers={"Accept": "application/json", "User-Agent": "GTAVINewsCenter/1.0"},
            timeout=(3, 8),
        )
        r.raise_for_status()
        payload = r.json()
        if int(payload.get("responseStatus", 0)) != 200:
            raise TranslationUnavailable("Il servizio di traduzione ha rifiutato la richiesta")
        translated = plain((payload.get("responseData") or {}).get("translatedText") or "")
    except (requests.RequestException, ValueError, TypeError, AttributeError, KeyError) as exc:
        raise TranslationUnavailable("Traduzione non disponibile") from exc

    if not translated or len(translated) > 420:
        raise TranslationUnavailable("Traduzione vuota o anomala")
    if translated.casefold() == original.casefold() or ENGLISH_MARKERS.search(translated):
        raise TranslationUnavailable("Testo non tradotto integralmente in italiano")
    if re.search(r"https?://|[@#]|my\s*memory|warning|quota|translation\s+limit|<", translated, re.I):
        raise TranslationUnavailable("Traduzione contiene testo estraneo")
    if numerals(original) != numerals(translated):
        raise TranslationUnavailable("Cifre o valori numerici modificati dalla traduzione")
    for term in BRAND_TERMS:
        if term in original.casefold() and term not in translated.casefold():
            raise TranslationUnavailable("Nome proprio o piattaforma persi durante la traduzione")
    return translated
