"""Opt-in video-link previews for verified Rockstar YouTube posts.

An X link preview may render in-feed, but is NOT a native video upload.
Never downloads or re-uploads third-party media. Uses the official Rockstar
channel context established in sources.free.json, not arbitrary URL claims.
"""
import re
from urllib.parse import urlsplit,parse_qs

ROCKSTAR_CHANNEL='UC6VcWc1rAoWdBCM0JxrRQ3A'


def video_link(event):
    if event.get('trust') != 'official' or event.get('game') not in ('GTA VI','GTA Online'):
        return None
    if event.get('official_channel_id') != ROCKSTAR_CHANNEL:
        return None
    raw=event.get('source_url','')
    try:
        p=urlsplit(str(raw))
        if (p.scheme!='https' or p.hostname not in ('www.youtube.com','youtube.com','youtu.be')
                or p.username or p.password or p.port not in (None,443)):
            return None
        if p.hostname in ('youtube.com','www.youtube.com'):
            if p.path!='/watch': return None
            video_id=(parse_qs(p.query).get('v') or [''])[0]
        else:
            video_id=p.path.strip('/')
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}',video_id): return None
    except ValueError:
        return None
    return 'https://www.youtube.com/watch?v='+video_id


def video_link_post(event):
    """Italian-only official-link share, not a native X retweet or video upload.

    Intentional conservative templates: Rockstar's source title can be English,
    but the public post always contains fully Italian wording. We do not rely
    on an external translation service for urgent official videos.
    """
    url = video_link(event)
    if not url:
        return None
    title = re.sub(r'\s+', ' ', str(event.get('title') or '')).lower()
    if event['game'] == 'GTA VI':
        header = '🎬 GTA VI | Video ufficiale Rockstar'
        if re.search(r'\btrailer\b', title):
            message = 'Rockstar Games ha pubblicato un trailer ufficiale di GTA VI.'
        elif re.search(r'\bpre[\s-]?load\b', title):
            message = 'Rockstar Games presenta il precaricamento di GTA VI.'
        elif re.search(r'\bgameplay\b', title):
            message = 'Nuovo video ufficiale dedicato al gameplay di GTA VI.'
        else:
            message = 'Rockstar Games ha pubblicato un video dedicato a GTA VI.'
        tags = '#GTAVI #GTA6'
    else:
        header = '🎬 GTA Online | Video ufficiale Rockstar'
        message = 'Rockstar Games ha pubblicato un video dedicato a GTA Online.'
        tags = '#GTAOnline'

    text = f'{header}\n\n{message}\n\n▶️ Guarda il video originale:\n{url}\n\n{tags}'
    from editorial_seo_v135 import x_weight
    return text if x_weight(text) <= 280 else None
