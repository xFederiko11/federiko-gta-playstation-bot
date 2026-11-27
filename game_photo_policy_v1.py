"""Require a genuinely photographic, topic-reviewed published article cover.

The public article is the source of truth; internal build audits stay private.
No generic logos, unrelated official images, or text-only reply fallbacks.
"""
from datetime import date
from functools import lru_cache
import hashlib
import re
import requests
from social_media_gate_v2 import canonical_page_path, cover_for, trusted_asset
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
        self.digests = []
        self.summaries = []

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        a = dict(attrs)
        if tag == "meta" and a.get("name") == "gta6:cover-kind":
            self.kinds.append(a.get("content"))
        if tag == "meta" and a.get("name") == "gta6:share-summary":
            self.summaries.append(a.get("content") or "")
        if tag == "meta" and a.get("name") == "gta6:cover-sha256":
            self.digests.append(a.get("content") or "")
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


    def photo_details(self, url):
        kind = self.photo_kind(url)
        if not kind or len(self.digests) != 1 or not re.fullmatch(r"[a-f0-9]{64}", self.digests[0]):
            return None
        return kind, self.digests[0]


def _owned_photo_page(url, session=None):
    if not canonical_page_path(url):
        return None
    try:
        with (session or requests).get(url, timeout=(3, 7), stream=True,
                  allow_redirects=False, headers={"User-Agent": "GTA6Italia-PhotoCheck/1.0",
                                                 "Cache-Control": "no-cache"}) as r:
            if r.status_code != 200 or r.url != url:
                return None
            data = bytearray()
            for chunk in r.iter_content(16384):
                data.extend(chunk)
                if len(data) > 1_500_000:
                    return None
            parser = PhotographicCover()
            parser.feed(data.decode("utf-8", errors="replace"))
            return parser
    except (requests.RequestException, OSError, ValueError):
        return None


def owned_photo_details(url, session=None):
    page=_owned_photo_page(url,session)
    return page.photo_details(url) if page else None


def owned_photo_contract(url, session=None):
    page=_owned_photo_page(url,session)
    details=page.photo_details(url) if page else None
    if not details or len(page.summaries)!=1:
        return None
    return (*details,page.summaries[0])


def probe_cover_digest(url, digest, session=None):
    """Compare every byte of the exact public JPEG with its reviewed page.

    A stale CDN object, partial file, missing digest or unrelated redirect holds
    publication. No query-string replacement, upload, or Buffer mutation.
    """
    if (not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)
            or not trusted_asset(url) or not url.startswith("https://xfederiko11.github.io/gta-6/assets/social-cards/")):
        return False
    try:
        with (session or requests).get(url, timeout=(4, 10), stream=True,
                  allow_redirects=False, headers={"User-Agent":"GTA6Italia-ExactPhoto/1.0",
                                                  "Accept":"image/jpeg","Cache-Control":"no-cache"}) as r:
            if r.status_code != 200 or r.url != url:
                return False
            if r.headers.get("Content-Type","").split(";")[0].strip().lower() != "image/jpeg":
                return False
            data=bytearray()
            for chunk in r.iter_content(16384):
                data.extend(chunk)
                if len(data)>1_600_000:
                    return False
            return (8_000<=len(data)<=1_600_000 and data.startswith(bytes.fromhex("ffd8ff"))
                    and data.endswith(bytes.fromhex("ffd9"))
                    and hashlib.sha256(data).hexdigest()==digest)
    except (requests.RequestException, OSError, ValueError):
        return False


@lru_cache(maxsize=64)
def scan_details(url):
    """Skip unreviewed URLs before network I/O; live hash checks remain mandatory."""
    from photo_rights_v1 import load
    if not canonical_page_path(url) or not any(page==url for page,_,_ in load()):
        return None
    return owned_photo_details(url)


def scan_kind(url):
    from photo_rights_v1 import reuse_documented
    details=scan_details(url)
    if not details:return None
    if not reuse_documented(url,*details):
        print("PHOTO_RIGHTS_HOLD: no reviewed reuse evidence for this cover")
        return None
    return details[0]


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
    details = scan_details(item.get("url"))
    if not details:
        return None
    from photo_rights_v1 import reuse_documented
    if not reuse_documented(item.get('url'),*details):
        return None
    if item.get('feed_summary'):
        from live_editorial_feed_v1 import matching
        if details!=(item.get('feed_kind'),item.get('feed_digest')) or not matching(item):
            return None
    prepared = single_photo_item(item, details[0])
    if prepared is None:
        return None
    return dict(prepared, cover_sha256=details[1])


def verify_delivery(entry):
    """Recheck live article and the exact attachment, not a Buffer URL preview."""
    if entry.get("feed_summary"):
        from live_editorial_feed_v1 import matching
        if not matching(entry):return False
    kind=entry.get("photo_kind")
    digest=entry.get("cover_sha256")
    from photo_rights_v1 import reuse_documented
    return (kind in KINDS and isinstance(digest,str)
            and reuse_documented(entry.get("url"),kind,digest)
            and not entry.get("thread")
            and entry.get("media_url") == cover_for(entry.get("url"))
            and owned_photo_details(entry.get("url")) == (kind,digest)
            and probe_cover_digest(entry.get("media_url"),digest))
