# Buffer queue reset — 2026-11-20

User confirmed the Buffer queue was emptied (screenshot). This is NOT proof that the X timeline is empty, nor authorization to replay old pending entries.

## Recovery rules
- Never republish an old failed/pending Buffer entry automatically merely because Buffer is empty.
- Retain historical ledgers and identifiers; do not delete state or deduplication keys.
- Recheck each source URL, publication date and factual claim before a fresh post.
- Cross-check actual X publication where accessible; if inaccessible, treat delivery as unknown and do not auto-retry.
- Rewrite from verified source facts with new reader value, not superficial paraphrasing to bypass spam detection.
- Prefer Italian GTA VI trophy tips, short verified how-tos, PS5/PS5 Pro OLED guides and official news.
- Editorial baseline: 09:00, 14:00, 20:30 Europe/Rome, maximum three routine slots daily; urgent verified news requires spacing and dedupe.
- Replies and reposts of third-party X posts require relevance and human approval. No mass interactions.
- Queue-empty is not evidence that a publishing API connection is healthy. Verify an actual new Buffer->X delivery before bulk scheduling.

## Implementation status
Policy only. No workflow, scheduling, API token, Buffer queue or X post has been changed by this file.
