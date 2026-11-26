"""Require a genuinely photographic, topic-reviewed published article cover.

The public article is the source of truth; internal build audits stay private.
No generic logos, unrelated official images, or text-only reply fallbacks.
"""
from datetime import date
from functools import lru_cache
import requests
from social_media_gate_v2 import canonical_page_path, cover_for, probe_image
from site_article_rotation_v1 import ArticleCover
from editorial_seo_v135 import x_weight
from quality_publish_policy_v1 import local

START = date(2026, 11, 26)
KINDS = {"official_game_photo", "approved_gameplay"}


def active(now):
    return local(now).date() >= START


class PhotographicCover(ArticleCover):
    def __init__(self):
        super().__init__()
        self.kinds = []
        self.alts = []

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        a = dict(attrs)
        if tag == "meta" and a.get("name") == "gta6:cover-kind":
            self.kinds.append(a.get("content"))
        if tag == "meta" and a.get("property") == "og:image:alt":
            self.alts.append(a.get("content") or "")

    def photo_kind(self, url):
        if not self.valid(url) or len(self.kinds) != 1 or len(self.alts) != 1:
            return None
        kind, alt = self.kinds[0], self.alts[0]
        if kind == "official_game_photo" and alt.startswith("Immagine promozionale"):
            return kind
        if kind == "approved_gameplay" and alt.startswith("Screenshot di gameplay autorizzato:"):
            return kind
        return None


def owned_photo_kind(url, session=None):
    if not canonical_page_path(url):
        return None
    try:
        with (session or requests).get(url, timeout=(3, 7), stream=True,
                  allow_redirects=False, headers={"User-Agent": "GTA6Italia-PhotoCheck/1.0"}) as r:
            if r.status_code != 200 or r.url != url:
                return None
            data = bytearray()
            for chunk in r.iter_content(16384):
                data.extend(chunk)
                if len(data) > 1_500_000:
                    return None
            parser = PhotographicCover()
            parser.feed(data.decode("utf-8", errors="replace"))
            return parser.photo_kind(url)
    except (requests.RequestException, OSError, ValueError):
        return None


@lru_cache(maxsize=64)
def scan_kind(url):
    """One bounded read per candidate in this scan; delivery checks again."""
    return owned_photo_kind(url)


def single_photo_item(item, kind):
    """Keep the factual main copy and link in ONE photo-bearing X message.

    Do not split into a photo parent and text-only source reply.
    Hold rather than cut a gameplay instruction to fit.
    """
    if kind not in KINDS:
        return None
    url = item.get("url")
    if not canonical_page_path(url):
        return None
    thread = item.get("thread")
    text = thread[0] if isinstance(thread, list) and len(thread) == 2 else item.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    lines = [line for line in text.splitlines()
             if not (line.strip().startswith("#") and all(w.startswith("#") for w in line.split()))]
    text = "\n".join(lines).strip()
    if url not in text:
        text += "\n\n" + url
    credit = "Foto promozionale: Rockstar Games." if kind == "official_game_photo" else "Foto autorizzata: credito nella guida."
    if item.get("source") == "PowerPyx Tips":
        credit = "Fonte: PowerPyx. " + credit
    text += "\n\n" + credit
    if x_weight(text) > 235:
        return None
    return dict(item, text=text, thread=None, photo_kind=kind)


def prepare_photo(item):
    """Owned article covers are individually reviewed; unrelated source photos wait."""
    kind = scan_kind(item.get("url"))
    if not kind:
        return None
    return single_photo_item(item, kind)


def verify_delivery(entry):
    """Recheck live article and the exact attachment, not a Buffer URL preview."""
    return (entry.get("photo_kind") in KINDS
            and not entry.get("thread")
            and entry.get("media_url") == cover_for(entry.get("url"))
            and owned_photo_kind(entry.get("url")) == entry.get("photo_kind")
            and probe_image(entry.get("media_url")))
