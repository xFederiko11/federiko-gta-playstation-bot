"""One dedicated verified image per published GTA VI X link.

The bot NEVER publishes a link-bearing post without a distinct image. It
derives official site cover URL from the exact canonical article path; the
site builds that JPEG with matching SHA-256. Other media must already be
official Rockstar/PlayStation and distinct in the persistent delivery ledger.
This doesn't download third-party article thumbnails or bypass Buffer safety.
"""
from __future__ import annotations
import hashlib
import logging
import time
from urllib.parse import urlsplit
import requests

BASE="https://xfederiko11.github.io/gta-6/"
SITE_IMAGE_PREFIX=BASE+"assets/social-cards/"
OFFICIAL=("www.rockstargames.com","media-rockstargames-com.akamaized.net",
          "blog.playstation.com","www.playstation.com")
ACTIVE_STATUSES={"reserved","attempted","sent","accepted_pending","scheduled","uncertain","review"}
LOG=logging.getLogger("gta6.media")
TRANSIENT_IMAGE_HTTP=frozenset({429,500,502,503,504})
MAX_IMAGE_READS=3


def canonical_page_path(target):
    if not isinstance(target,str) or not target.startswith(BASE):
        return None
    try:u=urlsplit(target)
    except ValueError:return None
    if (u.scheme!="https" or u.hostname!="xfederiko11.github.io" or
        u.username or u.password or u.port not in (None,443) or
        u.query or u.fragment or not u.path.startswith("/gta-6/")):
        return None
    path=u.path.removeprefix("/gta-6/")
    if path and (not path.endswith("/") or any(not p.isascii() or not p.replace("-","").isalnum() for p in path.strip("/").split("/"))):
        return None
    return path


def cover_for(target):
    path=canonical_page_path(target)
    if path is None:return None
    return SITE_IMAGE_PREFIX+hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]+".jpg"


def trusted_asset(url):
    if not isinstance(url,str):return False
    try:u=urlsplit(url)
    except ValueError:return False
    if (u.scheme!="https" or not u.hostname or u.username or u.password or
        u.port not in (None,443)):
        return False
    if url.startswith(SITE_IMAGE_PREFIX):
        return u.query=="" and u.fragment=="" and u.path.endswith(".jpg")
    return u.hostname.lower() in OFFICIAL and u.path.lower().endswith((".jpg",".jpeg",".png",".webp")) and not any(x in u.query.lower() for x in ("token=","expires=","signature="))


def image_taken(image,ledger):
    """No repeat for a different post in the durable editorial state."""
    if not image:return True
    from image_registry_v12 import identity
    current=identity(image)
    for row in ledger.get("entries",{}).values():
        if row.get("status") in ACTIVE_STATUSES:
            if identity(row.get("media_url"))==current:
                return True
    return False


def prepare(item,ledger):
    """Pure reserve-time gate: hold unsupported or reused images before Buffer."""
    target=str(item.get("url") or "")
    own=canonical_page_path(target) is not None
    current=item.get("media_url")
    if own:
        # Always use own per-article card over a generic repeated trophy photo.
        current=cover_for(target)
    if not trusted_asset(current):
        return None
    if image_taken(current,ledger):
        return None
    result=dict(item,media_url=current)
    if not result.get("media_url"):
        raise AssertionError("Text-only Buffer post escaped the media gate")
    return result


def probe_image(url, session=None):
    """Check the real public image bytes; retry only short-lived CDN outages.

    The same canonical trusted URL is retried, never a guessed replacement.
    A 404, redirect, invalid MIME, HTML, tiny blob, corrupt JPEG/PNG/WebP,
    untrusted host or bad TLS certificate still fails closed immediately.
    """
    if not trusted_asset(url):
        return False
    http=session or requests
    provider="owned-site" if url.startswith(SITE_IMAGE_PREFIX) else "official"
    for attempt in range(MAX_IMAGE_READS):
        try:
            with http.get(url,stream=True,timeout=(4,10),allow_redirects=False,
                          headers={"User-Agent":"GTA6Italia-ImageDelivery/1.0",
                                   "Accept":"image/jpeg,image/png,image/webp"}) as res:
                status=res.status_code
                if status in TRANSIENT_IMAGE_HTTP:
                    if attempt+1<MAX_IMAGE_READS:
                        time.sleep(attempt+1)
                        continue
                    LOG.warning("MEDIA_IMAGE_PROBE_HOLD source=%s reason=HTTP%s attempts=%s",
                                provider,status,MAX_IMAGE_READS)
                    return False
                if status!=200:
                    LOG.warning("MEDIA_IMAGE_PROBE_HOLD source=%s reason=HTTP%s",
                                provider,status)
                    return False
                target=urlsplit(res.url)
                if target.scheme!="https" or not trusted_asset(res.url):
                    LOG.warning("MEDIA_IMAGE_PROBE_HOLD source=%s reason=unexpected_media_url",provider)
                    return False
                kind=res.headers.get("Content-Type","").split(";")[0].strip().lower()
                if kind not in {"image/jpeg","image/png","image/webp"}:
                    LOG.warning("MEDIA_IMAGE_PROBE_HOLD source=%s reason=invalid_content_type",provider)
                    return False
                length=res.headers.get("Content-Length","")
                if length.isdigit() and not 8000<=int(length)<=12000000:
                    LOG.warning("MEDIA_IMAGE_PROBE_HOLD source=%s reason=invalid_content_length",provider)
                    return False
                start=next(res.iter_content(32),b"")
                valid=(start.startswith(b"\\xff\\xd8\\xff")
                       or start.startswith(b"\\x89PNG\\r\\n\\x1a\\n")
                       or (start.startswith(b"RIFF") and start[8:12]==b"WEBP"))
                if not valid:
                    LOG.warning("MEDIA_IMAGE_PROBE_HOLD source=%s reason=invalid_image_magic",provider)
                return valid
        except requests.exceptions.SSLError:
            LOG.warning("MEDIA_IMAGE_PROBE_HOLD source=%s reason=tls_verification_failed",provider)
            return False
        except (requests.exceptions.Timeout,requests.exceptions.ConnectionError) as exc:
            if attempt+1<MAX_IMAGE_READS:
                time.sleep(attempt+1)
                continue
            LOG.warning("MEDIA_IMAGE_PROBE_HOLD source=%s reason=%s attempts=%s",
                        provider,type(exc).__name__,MAX_IMAGE_READS)
            return False
        except (requests.RequestException,OSError,StopIteration,ValueError) as exc:
            LOG.warning("MEDIA_IMAGE_PROBE_HOLD source=%s reason=%s",
                        provider,type(exc).__name__)
            return False
    return False
