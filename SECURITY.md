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

## Private migration and recurring workload

The editorial workflow now runs full QA on code pushes/PRs without Buffer credentials; publication runs only on its independent schedule or explicit manual run, not when the monitor completes or a code push occurs. Ordinary UTC hours cover both CET and CEST reader windows. The urgent official-news monitor and launch watch remain independent; the local-time, dedupe, pacing, and receipt guards are unchanged. New owned editorial covers require an independently reviewed URL/kind/SHA-256 record with documented site/social reuse evidence. An empty registry intentionally holds posts instead of assuming copyright permission. Public feeds and existing archive entries are technical provenance, not a grant. Audit the separate official news media pathway and existing public derivatives before migrating them. No rights contacts or new licensed downloads are automatic.

See PRIVATE-ENGINE-MIGRATION.md for the staged no-cost migration plan. Keep private execution disabled until the billing owner has verified a zero-overage budget, compute and storage allowances, and secrets/state separation.

## Final Buffer attachment barrier

The project account and strict publishing workflows reject every createPost unless each attachment is tied to a reviewed owned page and exact live JPEG. External media remain held until an independently reviewed exact-asset rights contract is implemented; official hosts, YouTube thumbnails and galleries are not exemptions. The monitor holds these before image reservation and Buffer mutation; historical catchup pushes are QA only. Existing public website media still requires a separate audit and is not retroactively licensed by this change.
