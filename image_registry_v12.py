"""Persistent one-image-per-story guard across GTA VI archive and newer posts.

Opt-in via V12_UNIQUE_IMAGES=true. On collision return False and hold the
article for review; never silently re-use a logo or download press imagery.
"""
from pathlib import Path
from urllib.parse import unquote, urlsplit
import json


def identity(url):
    try:
        parts = urlsplit(str(url))
        if parts.scheme != 'https' or not parts.hostname:
            return ''
        return (parts.hostname.lower() + unquote(parts.path).lower())
    except ValueError:
        return ''


def archive_images(path):
    """Use the existing bootstrap journal; never clear, rewrite, or recreate it."""
    path = Path(path)
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError):
        raise RuntimeError('Bootstrap journal invalid: cannot verify image history') from None
    items = data.get('items') if isinstance(data, dict) else None
    if not isinstance(items, dict):
        raise RuntimeError('Bootstrap journal missing items: cannot verify image history')
    return {identity(record.get('image_url')) for record in items.values()
            if isinstance(record, dict) and record.get('status') in {'scheduled', 'sending', 'review', 'sent'}
            and identity(record.get('image_url'))}


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS image_use_v12 (
        media_key TEXT PRIMARY KEY, job_key TEXT NOT NULL, image_url TEXT NOT NULL,
        first_attempt_at REAL NOT NULL DEFAULT (strftime('%s','now'))
    )''')


def reserve_image(db, url, job_key, *, archive_path):
    """Reserve image before a network mutation. Never auto-release on timeout."""
    initialize(db)
    key = identity(url)
    if not key:
        return False
    if key in archive_images(archive_path):
        return False
    # Accept idempotent calls for same job, not two distinct jobs.
    row = db.execute('SELECT job_key FROM image_use_v12 WHERE media_key=?', (key,)).fetchone()
    if row:
        return row[0] == job_key
    with db:
        cursor = db.execute('INSERT OR IGNORE INTO image_use_v12(media_key,job_key,image_url) VALUES (?,?,?)',
                            (key, job_key, url))
    return cursor.rowcount == 1
