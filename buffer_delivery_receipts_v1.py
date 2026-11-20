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
  }
}"""
LEDGER = Path('.state/editorial-autopilot-v137.json')


def safe_x_url(value):
    if not isinstance(value, str) or any(ord(c) < 33 for c in value):
        return None
    try:
        u = urlsplit(value)
        if (u.scheme != 'https' or u.hostname not in
                {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'}
                or u.username or u.password or u.port not in (None, 443)
                or u.query or u.fragment):
            return None
        if not re.fullmatch(r'/(?:xFederiko11|[0-9]{8,25}|i/web)/status/[0-9]{8,25}/?', u.path, re.I):
            return None
        return value
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


def receipt(post, *, channel_id, post_id):
    if (not isinstance(post, dict) or post.get('id') != post_id
            or post.get('channelId') != channel_id or post.get('channelService') != 'twitter'):
        raise ValueError('Receipt identity or destination mismatch')
    status = post.get('status')
    if status not in {'sent', 'error', 'sending', 'scheduled', 'draft', 'needs_approval'}:
        raise ValueError('Unknown Buffer status')
    link = safe_x_url(post.get('externalLink'))
    stamp = post.get('sentAt')
    try:
        dt = datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
        valid_time = dt.tzinfo is not None
    except (ValueError, TypeError):
        valid_time = False
    result = {'buffer_id': post_id, 'buffer_status': status,
              'verified_by': 'Buffer API; expected X channel verified',
              'public_x_independently_checked': False,
              'sent_at': stamp if valid_time else None, 'external_url': link}
    result['outcome'] = ('sent_receipt' if status == 'sent' and link and valid_time
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
            item = receipt(data.get('post'), channel_id=client.channel_id, post_id=str(post_id))
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
