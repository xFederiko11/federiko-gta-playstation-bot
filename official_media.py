"""Immagini promozionali/autentiche prese solo da fonti ufficiali.

Nessuna generazione IA, nessun collage, nessuna immagine di terze parti.
Non confondere la data di prima osservazione con quella dello scatto.
Se non esiste un media sicuro, il bot NON pubblica (review manuale).
"""

import re
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


class OfficialMediaUnavailable(ValueError):
    """Non abbiamo prova che un'immagine reale pertinente sia pubblicabile."""


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


def approved_image_url(url, family):
    host = _host(url)
    if not host or not family:
        return False
    parsed = urlsplit(url)
    if any(k.casefold() in {'token', 'signature', 'expires', 'x-amz-signature', 'x-amz-expires', 'auth'}
           for k in parse_qs(parsed.query)):
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


def image_from_official_html(raw, source_url):
    """Legge solo i meta-tag immagine *della stessa fonte ufficiale*."""
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


def youtube_thumbnail(source_url, official_channel_id):
    if source_family(source_url, official_channel_id) != 'rockstar_youtube':
        return None
    parsed = urlsplit(source_url)
    video_id = (parse_qs(parsed.query).get('v') or [''])[0] if 'youtube.com' in parsed.hostname else parsed.path.strip('/')
    if not re.fullmatch('[A-Za-z0-9_-]{11}', video_id):
        return None
    return f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg'


def _probe_image(url, family, session=None):
    """Controllo senza scaricare tutto il media; niente redirect a host arbitrari."""
    if not approved_image_url(url, family):
        return False
    client = session or requests
    try:
        with client.get(url, stream=True, timeout=(5, 12), allow_redirects=False,
                        headers={'User-Agent': 'FederikoGTA-NewsCenter/4.0', 'Accept': 'image/avif,image/webp,image/png,image/jpeg'}) as response:
            if response.status_code != 200:
                return False
            if response.headers.get('Content-Type', '').split(';')[0].strip().lower() not in {'image/jpeg', 'image/png', 'image/webp'}:
                return False
            size = response.headers.get('Content-Length', '')
            if size.isdigit() and not 8_000 <= int(size) <= 12_000_000:
                return False
            part = next(response.iter_content(chunk_size=32), b'')
            return part.startswith(b'\xff\xd8\xff') or part.startswith(b'\x89PNG\r\n\x1a\n') or (part.startswith(b'RIFF') and b'WEBP' in part[8:16])
    except (requests.RequestException, OSError, StopIteration):
        return False


def official_image_for_event(event, *, session=None):
    """Risolve solo media derivanti dall'URL ufficiale della notizia stessa.

    Non cerca immagini online a tema (che potrebbero raffigurare eventi diversi).
    """
    if event.get('trust') != 'official' or event.get('demo'):
        raise OfficialMediaUnavailable('event_not_official')
    source = str(event.get('source_url') or '')
    family = source_family(source, event.get('official_channel_id'))
    if not family:
        raise OfficialMediaUnavailable('source_not_approved')
    candidate = event.get('official_image_url')
    if candidate and not approved_image_url(candidate, family):
        raise OfficialMediaUnavailable('image_domain_not_approved')
    if not candidate and family == 'rockstar_youtube':
        candidate = youtube_thumbnail(source, event.get('official_channel_id'))
    if not candidate and family in {'rockstar', 'sony'}:
        client = session or requests
        try:
            response = client.get(source, timeout=(5, 12), allow_redirects=False, headers={'User-Agent': 'FederikoGTA-NewsCenter/4.0'})
            if response.status_code == 200 and 'text/html' in response.headers.get('Content-Type', '').lower() and len(response.content) <= 2_000_000:
                candidate = image_from_official_html(response.text, source)
        except (requests.RequestException, OSError):
            pass
    if not candidate or not _probe_image(candidate, family, session):
        raise OfficialMediaUnavailable('no_verified_official_image')
    return candidate
