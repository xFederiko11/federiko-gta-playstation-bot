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
    url=video_link(event)
    if not url: return None
    header='🎬 GTA VI | VIDEO UFFICIALE ROCKSTAR' if event['game']=='GTA VI' else '🎬 GTA ONLINE | VIDEO UFFICIALE ROCKSTAR'
    title=re.sub(r'\s+',' ',str(event.get('title') or 'Nuovo video Rockstar')).strip()
    from editorial_language_it import contains_english_prose, italian_title, TranslationUnavailable
    if contains_english_prose(title):
        try:
            title=italian_title(title, 'en')
        except TranslationUnavailable:
            return None
    if len(title)>100:
        title=title[:97].rsplit(' ',1)[0]+'…'
    tags='#GTAVI #GTA6' if event['game']=='GTA VI' else '#GTAOnline'
    text=f'{header}\n\n{title}\n\n🔗 Video ufficiale:\n{url}\n\n{tags}'
    return text if len(text)<=280 else None
