"""Build native Buffer retweet metadata from an explicitly verified official X URL.

This is a read-only helper, not a bot that scrapes X or submits mutations.
Live retweet automation remains DISABLED pending platform/API tests.
"""
from urllib.parse import urlsplit
import re

OFFICIAL_X_HANDLES = {'rockstargames', 'playstation'}


def verified_official_status(url):
    """Only direct x.com official status URLs; no query strings, redirects or usernames."""
    try:
        parts = urlsplit(str(url))
    except ValueError:
        return None
    if (parts.scheme != 'https' or parts.hostname not in {'x.com', 'www.x.com'} or
            parts.port not in {None, 443} or parts.query or parts.fragment or parts.username or parts.password):
        return None
    match = re.fullmatch(r'/([A-Za-z0-9_]{1,15})/status/(\d{10,22})/?', parts.path)
    if not match or match.group(1).casefold() not in OFFICIAL_X_HANDLES:
        return None
    return {'handle': match.group(1), 'id': match.group(2),
            'url': 'https://x.com/'+match.group(1)+'/status/'+match.group(2)}


def draft_input_for_verified_repost(url, channel_id, comment=''):
    """Return draft-only Buffer GraphQL variables; caller must separately test API.

    Buffer RetweetMetadataInput fields: id (required), comment (optional).
    This function never sends network requests. Do not infer native repost from a URL share.
    """
    value = verified_official_status(url)
    if not value or not str(channel_id).strip():
        raise ValueError('Verified official X status and channel id required')
    if not isinstance(comment, str) or len(comment) > 180:
        raise ValueError('Repost comment too long')
    retweet = {'id': value['id']}
    if comment.strip():
        retweet['comment'] = comment.strip()
    return {'input': {'channelId': str(channel_id), 'text': comment.strip() or value['url'],
                      'schedulingType': 'automatic', 'mode': 'addToQueue',
                      'saveToDraft': True, 'assets': [],
                      'metadata': {'twitter': {'retweet': retweet}}}}
