# Private engine migration — staged, no spend by default

## Current boundary
- Keep the existing public site URL and GitHub Pages deployment. The public reader feed contains only reader-facing data, never runtime state or a write credential.
- Public repositories, branches and their history remain copyable; obfuscation is not access control. Do not describe old public commits, forks or artifacts as confidential after migration.
- Both existing repositories remain public until the owner has verified the private environment. The current production workflows explicitly guard public execution; do not remove those guards in place.

## Quota and cost gate
GitHub standard public runners are free; private runner use draws from the owner's monthly included compute amount and shared storage allowances. GitHub's current billing guide: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- GitHub Free: included compute equivalent to $12 per month (about 2,000 standard Linux minutes at $0.006/min) and 500 MB artifact storage; the actual account plan and use must be verified in Billing.
- Set the account's Actions budget to zero paid overage with stop-usage enabled, and verify the configuration before enabling any private schedules. No new cost is authorized.
- Sample measured job durations and count, including failed jobs, retries and artifact retention, over a representative week. Project monthly usage conservatively, leave margin for emergencies, and keep standard public static QA/deploy where possible. Elapsed workflow time alone is not billable usage.
- This rollout reduces redundant ordinary editorial triggers; urgent news remains unchanged. It does NOT yet make the total private workload fit the free allowance.

## Reversible migration
1. Create a new private engine repository (administration access required, not available through the current connector). Copy only reviewed source and lockfiles; scan files and history, exclude archive originals and sensitive logs. Do not transfer plaintext tokens; use repository/environment secrets and encrypted state with a tested restore.
2. Set up a private dry-run workflow without Buffer mutations. Reuse the public reader feed for incoming content. Keep private source, review records and runtime logs on the private side. Do not expose draft queues or internal issue reports.
3. If private generation needs to update public Pages, first test a static-only output handoff to a public staging branch, with an explicitly scoped short-lived installation credential and a static allowlist. Avoid broad PATs, public administrative endpoints or committed credentials. Do not publish the bot engine in generated artifacts.
4. Run parity tests and compare the private read-only candidate set to the public production system. Verify budget, restore, deduplication, actual publisher account, and exactly one active writer. Never run both writers with the same live account.
5. At cutover, stop the old writer first, take a consistent ledger checkpoint, confirm no uncertain/reserved Buffer writes, migrate secrets and state, and activate the new writer only after tests and budget approval. Keep a rollback checkpoint; if activation fails, stop the new writer before resuming the old one. Do not replay uncertain submissions.
6. Remove public operational source from current trees only after a separate review and successful cutover. Historical copies cannot be recalled by deleting the repository. Rotate any credentials if audit finds exposure.

## Completion criteria
Private execution, real cost ceiling, stable public URL, identical quality and publication checks, successful rollback rehearsal. Until then no visibility or account settings are changed.

## Runtime sample 2026-11-26

Eight recent scheduled jobs (IDs 45863498026, 45863299975, 45859495213, 45858531119, 45856181506, 45855539128, 45853536667, 45849361842) took 274 seconds in total from individual GitHub job start/end timestamps. Sum of per-job ceilings to minutes: 9. This is an illustrative short sample, not invoiced usage or a representative monthly projection. The existing health job now measures up to 12 recent scheduled runs read-only, no extra scheduled workflow. Missing timestamps or API failures are not treated as zero. Account budget and storage still require verification before cutover.
