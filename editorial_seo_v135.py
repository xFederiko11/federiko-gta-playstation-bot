"""GTA News Center v13.5: trustworthy X discovery, one consistent policy.

This is not a growth hack. Uses descriptive words and up to two contextual tags,
with official provenance and link priority. Does not scrape X trends or add
unrelated tags to increase reach. Posts with unverified claims are never fixed
by changing hashtags; source verification is a separate mandatory gate.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit
from editorial_language_it import italian_title, TranslationUnavailable

URL = re.compile(r'https?://[^\s<>]+', re.I)
TAG = re.compile(r'(?<!\w)#[A-Za-z0-9_]+')
GTA_VI = re.compile(r'\b(?:grand\s+theft\s+auto\s+vi|gta\s*(?:vi|6))\b', re.I)
GTA_ONLINE = re.compile(r'\b(?:gta\s*online|grand\s+theft\s+auto\s+online)\b', re.I)
PS5_PRO = re.compile(r'\b(?:ps5\s*pro|playstation\s*5\s*pro)\b', re.I)
PS5 = re.compile(r'\b(?:ps5|playstation\s*5)\b', re.I)


def x_weight(value: str) -> int:
    """Conservative X 280-character approximation, 23 per HTTP(S) URL.

    Astral symbols count twice. Avoid filling the limit exactly: X's complex
    emoji/Unicode parser can yield slightly different weights.
    """
    total = 0
    end = 0
    for match in URL.finditer(value):
        total += sum(1 if ord(c) <= 0x10FF or 0x2000 <= ord(c) <= 0x2037 else 2 for c in value[end:match.start()])
        total += 23
        end = match.end()
    return total + sum(1 if ord(c) <= 0x10FF or 0x2000 <= ord(c) <= 0x2037 else 2 for c in value[end:])


def category_from_title(title: str) -> str:
    """Classify *only* clear official headlines; generic 'GTA' is not GTA VI."""
    if GTA_ONLINE.search(title):
        return 'online'
    if GTA_VI.search(title):
        return 'vi'
    return 'rockstar'


def contextual_tags(category: str, *, official_title: str = '',
                    explicit_gta_plus: bool = False) -> tuple[str, ...]:
    if category == 'vi':
        return ('#GTAVI', '#PS5Pro') if PS5_PRO.search(official_title) else ('#GTAVI', '#GTA6')
    if category == 'online':
        return ('#GTAOnline', '#GTAPlus') if explicit_gta_plus else ('#GTAOnline',)
    if category == 'ps5':
        return ('#PS5', '#PlayStation')
    return ()


def finish(text: str, *, category: str, official_title: str = '',
           gta_plus: bool = False, limit: int = 280) -> str:
    """Append at most two relevant tags, without altering evidence or source.

    When room is scarce, drop optional hashtags rather than truncating facts.
    No duplicate tag, no third tag. Invalid existing copy must be rejected
    by the caller instead of being silently truncated.
    """
    if x_weight(text) > limit:
        raise ValueError('source_copy_too_long')
    found = TAG.findall(text)
    if len(found) > 2 or len({v.casefold() for v in found}) != len(found):
        raise ValueError('source_copy_bad_hashtags')
    current = {v.casefold() for v in found}
    output = text
    extra = []
    for tag in contextual_tags(category, official_title=official_title,
                               explicit_gta_plus=gta_plus):
        if len(current) >= 2:
            break
        if tag.casefold() in current:
            continue
        next_tags = extra + [tag]
        suffix = '\n' + ' '.join(next_tags)
        if x_weight(text + suffix) <= limit:
            extra = next_tags
            current.add(tag.casefold())
    if extra:
        output += '\n' + ' '.join(extra)
    return output


def compose_official_alert(headline: str, url: str) -> str | None:
    """Safe breaking post, preserving actual headline and original Rockstar URL.

    This function does NOT validate publication date, ownership or article body:
    those checks are mandatory upstream, before calling it.
    """
    parts = urlsplit(url)
    if (parts.scheme != 'https' or parts.hostname not in
            ('rockstargames.com', 'www.rockstargames.com')
            or not parts.path.startswith('/newswire/article/') or parts.username or parts.password):
        return None
    try:
        title = italian_title(headline, 'en')
    except TranslationUnavailable:
        return None
    if not title or len(title) < 10:
        return None
    # The category is determined from the original headline, not the translation.
    category = category_from_title(headline)
    if category != 'vi':
        return None
    prefix = '🚨 GTA VI | Rockstar Games\n\n📰 '
    suffix = '\n\n🔗 Fonte ufficiale:\n' + url
    # Keep separate paragraphs for readability. Do not sacrifice the source URL.
    for max_title in range(min(190, len(title)), 19, -1):
        clipped = title if len(title) <= max_title else title[:max_title - 1].rstrip() + '…'
        post = prefix + clipped + suffix
        if x_weight(post) > 257:
            continue
        try:
            result = finish(post, category=category, official_title=headline)
        except ValueError:
            continue
        # Separate SEO tags from the original source.
        result = result.replace('\n#GTAVI', '\n\n#GTAVI')
        if x_weight(result) <= 280:
            return result
    return None
