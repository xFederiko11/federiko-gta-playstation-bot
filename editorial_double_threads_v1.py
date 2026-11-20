"""Turn *verified existing* editorial candidates into atomic two-post X threads.

The first message keeps the original factual source headline or editorial tip.
The reply supplies the source / Italian guide and a useful next action.
Never invent a map, location, timing, reward, or alleged screenshot.
"""
from __future__ import annotations
import re
from urllib.parse import urlsplit
from editorial_seo_v135 import x_weight

TRAILING_CTA=re.compile(r'(?i)^(?:[📍🔗🔎📖💾🎯✅⚠️🏆📸]\s*)?(?:fonte|guida completa|guida in italiano|procedura illustrata|dettagli|requisiti|passaggi e fonte|consulta|approfondimento|apri la guida|leggi i passaggi|checklist|verifica prima|prosegui|mappa e dettagli|source)\s*:?\s*$')
TAG_LINE=re.compile(r'^\s*(?:#\w+\s*)+$')


def clean_headline(text: str) -> str:
    """Preserve sourced information, only move URLs/CTAs into reply."""
    lines=[]
    for line in text.splitlines():
        stripped=line.strip()
        if 'https://' in stripped or 'http://' in stripped:
            continue
        if TAG_LINE.fullmatch(stripped):
            continue
        if stripped.startswith('🔗 Fonte:') or TRAILING_CTA.fullmatch(stripped):
            continue
        lines.append(line.rstrip())
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def verify_link(value: str) -> str:
    p=urlsplit(value)
    if (p.scheme!='https' or not p.hostname or p.username or p.password
        or p.port not in (None,443) or any(ord(x)<33 for x in value)):
        raise ValueError('Untrusted source URL in double-post candidate')
    return value


def reply_for(item: dict) -> str:
    url=verify_link(str(item['url']))
    source=str(item.get('source') or 'Fonte originale').strip()
    if source=='Guide GTA VI Italia':
        text='🗺️ Guida italiana con passaggi, immagini e fonti (spoiler a scelta):\n'+url
    elif source=='Trofei GTA VI':
        text='🏆 Requisiti, consigli e avvisi sul platino nella checklist:\n'+url
    elif source=='PowerPyx Tips':
        text='📍 Procedura di riferimento con controlli PS5 e fonte:\n'+url
    elif source in {'PowerPyx','Insider Gaming'}:
        text='📖 Passaggi e posizioni documentati nella fonte originale:\n'+url+'\n\n🔎 Fonte: '+source
    else:
        text='📰 Dettagli e verifiche nella fonte originale:\n'+url+'\n\n🔎 Fonte: '+source
    if x_weight(text)>280:
        raise ValueError('Reply exceeds X character budget')
    return text


def double(item: dict) -> dict:
    """Return a new candidate; reject unsupported material rather than filler."""
    if isinstance(item.get('thread'),list):
        if len(item['thread'])!=2 or any(not x.strip() or x_weight(x)>280 for x in item['thread']):
            raise ValueError('Expected verified two-message source thread')
        if item.get('media_url') and x_weight(item['thread'][0])>235:
            raise ValueError('Photo thread exceeds first-message limit')
        return dict(item)
    main=clean_headline(str(item['text']))
    if not main or x_weight(main)>280:
        raise ValueError('Cannot convert source text to a complete X post')
    if '#GTAVI' not in main:
        proposed=main+'\n\n#GTAVI'
        if x_weight(proposed)<=280:
            main=proposed
    media=item.get('media_url')
    if media and x_weight(main)>235:
        # Never amputate verified facts to force a decorative attachment.
        media=None
    output=dict(item,thread=[main,reply_for(item)],media_url=media)
    assert len(output['thread'])==2
    return output
