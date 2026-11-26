"""Official, real media for X posts, with brand logos strictly as last resort.

Priority: event image -> official page social image -> article image ->
verified official brand logo. No AI assets, random unrelated media or redirects.
"""

from dataclasses import dataclass
import re
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


class OfficialMediaUnavailable(ValueError):
    """There is no verified, relevant, official image safe for automatic posting."""


@dataclass(frozen=True)
class OfficialMediaChoice:
    url: str
    kind: str  # editorial_image, video_thumbnail, official_logo
    credit_url: str


# These assets were located on the publishers' official sites on 17 Nov 2026.
# A live content check is still mandatory on every posting attempt.
GTA_VI_LOGO = (
    'https://media-rockstargames-com.akamaized.net/tina-uploads/posts/'
    '3928aaa9471o3a/7ff0c4b640e5979c692e869a2c01781c596d30bd.png'
)
PLAYSTATION_LOGO = (
    'https://blog.playstation.com/tachyon/2026/09/'
    '8d4a1fdac2d9ea1bcce9566dc292d2971ffbad46.png?fit=512%2C512'
)
LOGO_CREDITS = {
    GTA_VI_LOGO: 'https://www.rockstargames.com/newswire/article/3928aaa9471o3a/grand-theft-auto-vi-watch-trailer-2-now',
    PLAYSTATION_LOGO: 'https://blog.playstation.com/2026/0/',
}


def _on(host, domains):
    return bool(host) and any(host == domain or host.endswith('.' + domain) for domain in domains)


def _host(url):
    try:
        parsed = urlsplit(str(url))
    except ValueError:
        return ''
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        return ''
    return parsed.hostname.lower()


def source_family(source_url, channel_id=None):
    host = _host(source_url)
    if _on(host, ('rockstargames.com',)):
        return 'rockstar'
    if _on(host, ('playstation.com',)):
        return 'sony'
    if host in {'youtube.com', 'www.youtube.com', 'youtu.be', 'www.youtu.be'} and channel_id == 'UC6VcWc1rAoWdBCM0JxrRQ3A':
        return 'rockstar_youtube'
    return None


def _unsigned(url):
    try:
        return not any(k.casefold() in {'token', 'signature', 'expires', 'x-amz-signature', 'x-amz-expires', 'auth'}
                       for k in parse_qs(urlsplit(url).query))
    except ValueError:
        return False


def approved_image_url(url, family):
    host = _host(url)
    if not host or not family or not _unsigned(url):
        return False
    parsed = urlsplit(url)
    if any(parsed.path == urlsplit(logo).path for logo in LOGO_CREDITS):
        return False
    if re.search(r'(?:favicon|logo|placeholder|default-avatar|site-icon|\.svg(?:$|\?))', parsed.path, re.I):
        return False
    if family == 'rockstar':
        return _on(host, ('rockstargames.com', 'rockstargamescdn.com')) or host == 'media-rockstargames-com.akamaized.net'
    if family == 'sony':
        return _on(host, ('playstation.com', 'playstation.net'))
    if family == 'rockstar_youtube':
        return host in {'i.ytimg.com', 'img.youtube.com'}
    return False


def approved_logo_url(url, family):
    """Never treat arbitrary event-provided 'logo' URLs as trusted logos."""
    return bool(url in LOGO_CREDITS and _unsigned(url) and (
        (url == GTA_VI_LOGO and family in {'rockstar', 'rockstar_youtube'}) or
        (url == PLAYSTATION_LOGO and family == 'sony')
    ))


def image_from_official_html(raw, source_url):
    """Read social-photo tags solely from the official source page."""
    family = source_family(source_url)
    if family not in {'rockstar', 'sony'}:
        return None
    soup = BeautifulSoup(raw, 'html.parser')
    for attributes in ({'property': 'og:image:secure_url'}, {'property': 'og:image'},
                       {'name': 'twitter:image'}, {'property': 'twitter:image'}):
        meta = soup.find('meta', attrs=attributes)
        if not meta or not meta.get('content'):
            continue
        url = urljoin(source_url, meta['content'].strip())
        if approved_image_url(url, family):
            return url
    return None


def article_image_from_official_html(raw, source_url):
    """Only inline imagery in the actual article, never sidebar/advertising/logo."""
    family = source_family(source_url)
    if family not in {'rockstar', 'sony'}:
        return None
    soup = BeautifulSoup(raw, 'html.parser')
    article = soup.find('article')
    if article is None:
        return None
    for img in article.find_all('img', limit=24):
        if img.find_parent(['nav', 'aside', 'footer']):
            continue
        alt = (img.get('alt') or '').lower()
        if any(bad in alt for bad in ('logo', 'icon', 'avatar', 'profilo', 'social')):
            continue
        width = str(img.get('width') or '')
        height = str(img.get('height') or '')
        if width.isdigit() and int(width) < 400:
            continue
        if height.isdigit() and int(height) < 250:
            continue
        for attr in ('src', 'data-src'):
            raw_url = img.get(attr)
            if raw_url:
                url = urljoin(source_url, raw_url.strip())
                if approved_image_url(url, family):
                    return url
    return None


def youtube_thumbnail(source_url, official_channel_id):
    if source_family(source_url, official_channel_id) != 'rockstar_youtube':
        return None
    parsed = urlsplit(source_url)
    video_id = (parse_qs(parsed.query).get('v') or [''])[0] if 'youtube.com' in parsed.hostname else parsed.path.strip('/')
    if not re.fullmatch('[A-Za-z0-9_-]{11}', video_id):
        return None
    return f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg'


def _probe_image(url, family, session=None, *, logo=False):
    """Verify response content without following redirects to unrelated domains."""
    if not (approved_logo_url(url, family) if logo else approved_image_url(url, family)):
        return False
    client = session or requests
    try:
        with client.get(url, stream=True, timeout=(5, 12), allow_redirects=False,
                        headers={'User-Agent': 'FederikoGTA-NewsCenter/5.0',
                                 'Accept': 'image/avif,image/webp,image/png,image/jpeg'}) as response:
            if response.status_code != 200:
                return False
            if response.headers.get('Content-Type', '').split(';')[0].strip().lower() not in {'image/jpeg', 'image/png', 'image/webp'}:
                return False
            size = response.headers.get('Content-Length', '')
            if size.isdigit() and not (1_000 if logo else 8_000) <= int(size) <= 12_000_000:
                return False
            part = next(response.iter_content(chunk_size=32), b'')
            return part.startswith(b'\xff\xd8\xff') or part.startswith(b'\x89PNG\r\n\x1a\n') or (part.startswith(b'RIFF') and b'WEBP' in part[8:16])
    except (requests.RequestException, OSError, StopIteration):
        return False


def _official_logo_for_event(event, family):
    # A GTA VI logo must never illustrate unrelated GTA Online/Rockstar articles.
    name = ' '.join(str(event.get(key) or '') for key in ('game', 'title')).casefold()
    if family == 'sony':
        return PLAYSTATION_LOGO
    if family in {'rockstar', 'rockstar_youtube'} and re.search(r'\b(?:gta\s*(?:vi|6)|grand\s*theft\s*auto\s*(?:vi|6))\b', name):
        return GTA_VI_LOGO
    return None


def official_media_for_event(event, *, session=None, allow_logo=True):
    """Rank legitimate photos first; use only a product-correct official logo last."""
    if event.get('trust') != 'official' or event.get('demo'):
        raise OfficialMediaUnavailable('event_not_official')
    source = str(event.get('source_url') or '')
    family = source_family(source, event.get('official_channel_id'))
    if not family:
        raise OfficialMediaUnavailable('source_not_approved')
    client = session or requests
    candidate = event.get('official_image_url')
    if candidate and not approved_image_url(candidate, family):
        raise OfficialMediaUnavailable('image_domain_not_approved')
    if candidate and _probe_image(candidate, family, session):
        return OfficialMediaChoice(candidate, 'editorial_image', source)
    if family == 'rockstar_youtube':
        thumb = youtube_thumbnail(source, event.get('official_channel_id'))
        if thumb and _probe_image(thumb, family, session):
            return OfficialMediaChoice(thumb, 'video_thumbnail', source)
    if family in {'rockstar', 'sony'}:
        try:
            response = client.get(source, timeout=(5, 12), allow_redirects=False,
                                  headers={'User-Agent': 'FederikoGTA-NewsCenter/5.0'})
            if response.status_code == 200 and 'text/html' in response.headers.get('Content-Type', '').lower() and len(response.content) <= 2_000_000:
                for photo in (image_from_official_html(response.text, source),
                              article_image_from_official_html(response.text, source)):
                    if photo and _probe_image(photo, family, session):
                        return OfficialMediaChoice(photo, 'editorial_image', source)
        except (requests.RequestException, OSError):
            pass
    fallback = _official_logo_for_event(event, family) if allow_logo else None
    if fallback and _probe_image(fallback, family, session, logo=True):
        return OfficialMediaChoice(fallback, 'official_logo', LOGO_CREDITS[fallback])
    raise OfficialMediaUnavailable('no_verified_official_image_or_logo')


def official_image_for_event(event, *, session=None):
    """Backward-compatible URL-only resolver used by the publication runner."""
    return official_media_for_event(event, session=session).url
