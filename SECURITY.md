# Security policy

Report vulnerabilities privately to the repository maintainer. Never publish passwords, tokens, decrypted state, or account data in an issue.

## Credentials and state

GitHub Actions Secrets must hold BUFFER_API_KEY, BUFFER_CHANNEL_ID and STATE_PASSWORD. No X API key or new subscriptions are required. Do not put secrets in repository files or workflow logs. The public repository contains encrypted state and public publication ledgers; do not delete or decrypt them. Encrypted state still depends on secrecy of the encryption key.

## Supply-chain and GitHub Actions

GitHub Actions are pinned to full commit hashes checked against upstream release tags. Pull-request test jobs have read-only repository permissions and receive no Buffer secrets. Publishing jobs receive write permissions only when required to record reservations and delivery results. Review Dependabot PRs and run tests before merging. Do not automatically merge unreviewed dependency or workflow changes.

## Publishing safety

Every public news post must be in Italian, with clear source attribution and no fabricated claims. PowerPyx guides are linked and summarized in original words; no copied articles or images. Reserve in persistent ledgers before calling Buffer, and never automatically retry an uncertain write. Viral-video responses and native X reposts are not auto-published. Do not introduce paid API dependencies or spammy engagement automation.

## Source visibility and operational reports

The public repository and its Actions logs/artifacts remain publicly accessible subject to GitHub access rules. They are not a private operator workspace. Do not add new internal review details to public issues. The discovery job reads only fixed JSON inputs from a single observed public site revision; it never exports the excluded site build backlog. Scheduled X intake uses no paid X search. Private-engine migration requires verified plan/runner quotas, tested cross-repository credentials, a public static publishing target, and an explicit rollback plan. Obfuscation is not access control. Changing visibility alone does not remove historical public copies or forks.

## Cross-repository reader feed

Use a public, reader-only JSON feed of explicitly reviewed article summaries and image hashes. The bot consumes it as data, never executes code from the site, and independently checks the rendered article and exact JPEG before reserving and sending. This removes cross-repository write tokens and makes a future private-engine migration simpler. Do not move internal ledgers, candidates, secrets or report artifacts into the public feed. Keep public static delivery separate from private execution. The new integration workflow is read-only and does not call Buffer.
