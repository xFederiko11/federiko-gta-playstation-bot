"""Bounded read-only delivery receipts. Never creates, retries or edits posts.

Uses documented Post.sentAt, externalLink, error and verified channel ownership.
A Buffer receipt is not an independent public X timeline or impressions check.
https://developers.buffer.com/reference.html
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

QUERY = """query Receipt($id: PostId!) {
  post(input: {id: $id}) {
    id channelId channelService status sentAt externalLink
    error { message }
    assets { mimeType source }
    metadata {
      ... on TwitterPostMetadata {
        thread { assets { mimeType source } }
      }
    }
  }
}"""
LEDGER = Path('.state/editorial-autopilot-v137.json')
EXPECTED_X_HANDLE = 'xFederiko11'


def safe_x_url(value, expected_handle=EXPECTED_X_HANDLE):
    """Return a canonical link only for this verified Buffer channel.

    Buffer may return a numeric account ID as the owner segment of
    externalLink. The tweet ID remains the public permalink key; after
    verify_destination and channelId checks, bind that link to the expected
    handle rather than emitting an unusable numeric-owner URL.
    """
    if not isinstance(value, str) or any(ord(c) < 33 for c in value):
        return None
    handle = str(expected_handle or '').strip().lstrip('@')
    if not re.fullmatch(r'[A-Za-z0-9_]{1,15}', handle):
        return None
    try:
        u = urlsplit(value)
        if (u.scheme != 'https' or u.hostname not in
                {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'}
                or u.username or u.password or u.port not in (None, 443)
                or u.query or u.fragment):
            return None
        web_status = re.fullmatch(r'/i/web/status/([0-9]{8,25})/?', u.path, re.I)
        if web_status:
            return 'https://x.com/i/web/status/' + web_status.group(1)
        match = re.fullmatch(r'/([^/]+)/status/([0-9]{8,25})/?', u.path, re.I)
        if not match:
            return None
        owner, post_id = match.groups()
        if (owner.casefold() != handle.casefold()
                and not re.fullmatch(r'[0-9]{8,25}', owner)):
            return None
        return f'https://x.com/{handle}/status/{post_id}'
    except ValueError:
        return None


def safe_message(value):
    text = str(value or '')
    for name in ('BUFFER_API_KEY', 'BUFFER_CHANNEL_ID', 'GH_TOKEN', 'GITHUB_TOKEN'):
        secret = os.getenv(name)
        if secret:
            text = text.replace(secret, '[redacted]')
    text = re.sub(r'(?i)bearer\s+\S+', 'Bearer [redacted]', text)
    return ' '.join(text.split())[:240]



def _has_image(assets):
    """Only actual image assets count: links, video and document previews do not."""
    if not isinstance(assets, list):
        return False
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        mime = str(asset.get('mimeType') or '').lower().strip()
        source = asset.get('source')
        if mime not in {'image/jpeg', 'image/png', 'image/webp', 'image/avif'}:
            continue
        if not isinstance(source, str):
            continue
        try:
            u = urlsplit(source)
        except ValueError:
            continue
        if u.scheme == 'https' and u.hostname and not u.username and not u.password:
            return True
    return False


def _post_image_attached(post):
    """A Buffer X thread stores the first photo under metadata.twitter.thread[0]."""
    if _has_image(post.get('assets')):
        return True
    metadata = post.get('metadata')
    thread = metadata.get('thread') if isinstance(metadata, dict) else None
    return bool(isinstance(thread, list) and thread and isinstance(thread[0], dict)
                and _has_image(thread[0].get('assets')))


def receipt(post, *, channel_id, post_id, require_image=False):
    if (not isinstance(post, dict) or post.get('id') != post_id
            or post.get('channelId') != channel_id or post.get('channelService') != 'twitter'):
        raise ValueError('Receipt identity or destination mismatch')
    status = post.get('status')
    if status not in {'sent', 'error', 'sending', 'scheduled', 'draft', 'needs_approval'}:
        raise ValueError('Unknown Buffer status')
    link = safe_x_url(post.get('externalLink'), expected_handle=EXPECTED_X_HANDLE)
    stamp = post.get('sentAt')
    try:
        dt = datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
        valid_time = dt.tzinfo is not None
    except (ValueError, TypeError):
        valid_time = False
    image_attached = _post_image_attached(post)
    result = {'buffer_id': post_id, 'buffer_status': status,
              'verified_by': 'Buffer API; expected X channel verified',
              'public_x_independently_checked': False,
              # This proves the image is attached to Buffer's post model, NOT
              # that a public X photo was independently viewed.
              'buffer_image_asset_confirmed': image_attached,
              'buffer_image_required': bool(require_image),
              'sent_at': stamp if valid_time else None, 'external_url': link}
    result['outcome'] = ('sent_without_confirmed_image' if
                         status == 'sent' and link and valid_time
                         and require_image and not image_attached else
                         'sent_receipt' if status == 'sent' and link and valid_time
                         else 'sent_incomplete_receipt' if status == 'sent'
                         else 'failed' if status == 'error' else 'pending')
    if status == 'error':
        result['error_message'] = safe_message((post.get('error') or {}).get('message'))
    return result


def collect(state, *, run_id, client):
    entries = state.get('entries')
    if not isinstance(entries, dict):
        raise ValueError('Unreadable editorial ledger')
    current = [e for e in entries.values() if isinstance(e, dict) and e.get('run_id') == run_id]
    if len(current) > 1:
        raise ValueError('Unexpected multiple current reservations')
    recent = sorted((e for e in entries.values() if isinstance(e, dict) and e.get('buffer_id')),
                    key=lambda e: e.get('reserved_utc', ''), reverse=True)
    targets = current or recent[:1]
    # Read-only: no retry, no mutations, no external X timeline assumptions.
    result = {'checked_utc': datetime.now(timezone.utc).isoformat(),
              'current_run_attempted': bool(current), 'receipts': [],
              'mode': 'read_only_no_retry'}
    if targets:
        client.verify_destination()
    for entry in targets:
        post_id = entry.get('buffer_id')
        if not post_id:
            item = {'outcome': 'no_receipt', 'ledger_status': entry.get('status')}
        else:
            data = client._graphql(QUERY, {'id': str(post_id)})
            # Link-only fallbacks are an explicit per-item exception;
            # unknown current modes still fail closed.
            no_image_mode = entry.get('media_mode') in {
                'source_link_only', 'official_video_link'}
            item = receipt(data.get('post'), channel_id=client.channel_id,
                           post_id=str(post_id),
                           require_image=(
                               bool(entry.get('media_url')) or
                               (bool(current) and not no_image_mode)))
        item['title'] = str(entry.get('title') or '')
        item['current_run'] = bool(current)
        result['receipts'].append(item)
    return result


def main():
    from buffer_publisher import BufferClient
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('previews/buffer-delivery-receipt-v1.json'))
    args = parser.parse_args()
    try:
        state = json.loads(LEDGER.read_text(encoding='utf-8'))
        result = collect(state, run_id=os.environ.get('GITHUB_RUN_ID', ''),
                         client=BufferClient(expected_username='xFederiko11'))
        code = 0
        if result['current_run_attempted'] and any(r['outcome'] != 'sent_receipt' for r in result['receipts']):
            code = 2
    except Exception as exc:
        result = {'outcome': 'verification_unavailable', 'reason': type(exc).__name__,
                  'mode': 'read_only_no_retry'}
        code = 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    args.output.write_text(content, encoding='utf-8')
    print('BUFFER_DELIVERY_RECEIPT\n' + content)
    summary = os.getenv('GITHUB_STEP_SUMMARY')
    if summary:
        with Path(summary).open('a', encoding='utf-8') as stream:
            stream.write('\n## Buffer delivery receipt (read only)\n```json\n' + content + '```\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
