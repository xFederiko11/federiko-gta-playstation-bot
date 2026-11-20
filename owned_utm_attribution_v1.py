"""Attributable first-party links for GTA VI Italia posts on our own X account.

This is URL labeling, not analytics data fetching or publication. The canonical
article URL stays unchanged in the editorial journal and Buffer receipt bridge.
Umami automatically parses UTM parameters on visits to the tagged destination.
No personal data, X visitor identification, or claimed follower conversions.
"""
from __future__ import annotations

from urllib.parse import urlencode
import re

OWNED = re.compile(r"^https://xfederiko11\.github\.io/gta-6/(?:[a-z0-9-]+/)*$")
SOURCE = "x"
MEDIUM = "social"
CAMPAIGN = "gta_vi_italia_organic_2026"
PLACEMENTS = frozenset(("guide_reply", "community_question", "trophy_reply", "quick_tip"))


def tagged_site_url(canonical: str, *, placement: str) -> str:
    """Tag only an exact canonical owned landing page; never tag sources.

    The caller retains `canonical` for deduplication and permalink receipts;
    this is solely the user-facing URL in the reply to our own X post.
    """
    if not isinstance(canonical, str) or not OWNED.fullmatch(canonical):
        raise ValueError("UTM target must be an exact canonical GTA VI Italia URL")
    if placement not in PLACEMENTS:
        raise ValueError("Unknown editorial UTM placement")
    return canonical + "?" + urlencode((
        ("utm_source", SOURCE),
        ("utm_medium", MEDIUM),
        ("utm_campaign", CAMPAIGN),
        ("utm_content", placement),
    ))
