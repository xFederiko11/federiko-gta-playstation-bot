"""Read-only, browser-rendered fallback for publicly accessible Rockstar pages.

Rockstar's Next.js Newswire can return an HTML shell to plain HTTP clients.
This module waits for PUBLIC browser DOM and extracts a bounded HTML summary
of elements actually shown on the page. It never logs in, posts or downloads media.
"""
from __future__ import annotations

from functools import lru_cache
from html import escape
from urllib.parse import urlsplit


_PUBLIC_HOSTS = frozenset(('rockstargames.com', 'www.rockstargames.com',
                           'support.rockstargames.com'))


def _safe_source(url: str) -> bool:
    try:
        p = urlsplit(url)
        if p.scheme != 'https' or p.hostname not in _PUBLIC_HOSTS or p.username or p.password:
            return False
        if p.port not in (None, 443):
            return False
        if p.hostname == 'support.rockstargames.com':
            return p.path.startswith('/articles/')
        return p.path.startswith(('/newswire', '/VI/media', '/gta-online'))
    except ValueError:
        return False


@lru_cache(maxsize=12)
def fetch_rendered(url: str, mode: str = 'snapshot') -> str:
    """Return a compact excerpt of *actual* rendered DOM (not invented news).

    mode: 'listing', 'article', or 'snapshot'. The cache lasts only one bot run.
    A browser timeout or a JS-only empty page fails closed with a safe reason.
    """
    if not _safe_source(url):
        raise ValueError('render_unsafe_url')
    if mode not in ('listing', 'article', 'snapshot'):
        raise ValueError('render_invalid_mode')
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout
    except ImportError:
        raise ValueError('render_browser_unavailable') from None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])
            try:
                ctx = browser.new_context(locale='en-US', timezone_id='America/New_York',
                                          service_workers='block')
                page = ctx.new_page()
                page.route('**/*', lambda route: route.abort() if
                           route.request.resource_type in ('image', 'media', 'font') else route.continue_())
                response = page.goto(url, wait_until='domcontentloaded', timeout=12000)
                if response is not None and response.status >= 400:
                    raise ValueError('render_http_error')
                if not _safe_source(page.url):
                    raise ValueError('render_redirect_not_allowed')
                selector = ('a[href*="/newswire/article/"]' if mode == 'listing' else
                            'h1' if mode == 'article' else 'h1, h2, h3')
                try:
                    page.wait_for_selector(selector, timeout=7000)
                except BrowserTimeout:
                    raise ValueError('render_content_missing') from None
                data = page.evaluate(r'''() => {
                    const root = document.querySelector('main') ||
                                 document.querySelector('[role="main"]') ||
                                 document.querySelector('article') || document.body;
                    const arr = (query, cap) => Array.from(root.querySelectorAll(query)).slice(0, cap);
                    const entries = arr('h1,h2,h3,p,li,time', 270).map(el => ({
                        tag: el.tagName.toLowerCase(),
                        text: (el.innerText || el.textContent || '').trim().slice(0, 1700),
                        datetime: el.getAttribute('datetime') || ''
                    })).filter(x => x.text);
                    const anchors = arr('a[href]', 450).map(el => ({
                        href: el.href, text: (el.innerText || el.getAttribute('aria-label') ||
                        el.querySelector('img')?.getAttribute('alt') || '').trim().slice(0, 220)
                    })).filter(x => x.href && x.text);
                    const firstParagraph = root.querySelector('p');
                    const dateRe = /^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2}$/i;
                    const dateLabels = Array.from(root.querySelectorAll('span,time')).filter(el => {
                        const t = (el.innerText || el.textContent || '').trim();
                        if (!dateRe.test(t) || !firstParagraph) return false;
                        return Boolean(el.compareDocumentPosition(firstParagraph) & Node.DOCUMENT_POSITION_FOLLOWING);
                    }).slice(0, 2).map(el => (el.innerText || el.textContent || '').trim());
                    const meta = Array.from(document.querySelectorAll('meta[property="article:published_time"],meta[name="date"],meta[name="pubdate"]')).slice(0, 4).map(el => ({
                        property: el.getAttribute('property') || '',
                        name: el.getAttribute('name') || '',
                        content: el.getAttribute('content') || ''
                    }));
                    return {title: document.title || '', entries, anchors, meta, dateLabels,
                            body_size: (root.innerText || '').length};
                }''')
            finally:
                browser.close()
    except ValueError:
        raise
    except BrowserTimeout:
        raise ValueError('render_timeout') from None
    except Exception:
        # Keep diagnostics safe: exceptions may include full URLs/query strings.
        raise ValueError('render_browser_error') from None

    if mode == 'listing' and not any('/newswire/article/' in a['href'] for a in data['anchors']):
        raise ValueError('render_content_missing')
    if mode == 'article' and not any(e['tag'] == 'h1' for e in data['entries']):
        raise ValueError('render_content_missing')
    if mode == 'snapshot' and (data['body_size'] < 60 or not data['entries']):
        raise ValueError('render_content_missing')

    parts = ['<html><head><title>', escape(data['title']), '</title>']
    for m in data['meta']:
        attrs = ' '.join(f'{k}="{escape(v, quote=True)}"' for k, v in m.items() if v)
        parts.extend(['<meta ', attrs, '>'])
    parts.append('</head><body><main>')
    # Date labels must exist in real DOM before the first paragraph; no date inference.
    for label in data.get('dateLabels', []):
        parts.extend(['<span>', escape(label), '</span>'])
    for entry in data['entries']:
        tag = entry['tag'] if entry['tag'] in ('h1','h2','h3','p','li','time') else 'p'
        dt = f' datetime="{escape(entry["datetime"], quote=True)}"' if tag == 'time' and entry['datetime'] else ''
        parts.extend([f'<{tag}{dt}>', escape(entry['text']), f'</{tag}>'])
    for a in data['anchors']:
        parts.extend(['<a href="', escape(a['href'], quote=True), '">', escape(a['text']), '</a>'])
    parts.append('</main></body></html>')
    result = ''.join(parts)
    if len(result) > 1_400_000:
        raise ValueError('render_excerpt_too_large')
    return result
