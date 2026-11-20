# Verified publishing recovery - 20 November 2026

## Actual publication evidence

- Editorial run: https://github.com/xFederiko11/federiko-gta-playstation-bot/actions/runs/44653659495
- Job: 136014487622; 77 offline regression tests passed, destination preflight passed, one fresh item reserved and persisted before delivery.
- Title: GTA VI: quattro luoghi per fare soldi subito.
- Buffer post ID: `6affa1e27b0a126ceb99ab72`.
- Read-only Buffer receipt: status `sent`, sentAt `2026-11-20T01:26:58.878Z` (02:26:58 CET).
- Buffer returned externalLink: https://twitter.com/xFederiko11/status/2123588882885186002
- Receipt identity matched the requested post and the verified @xFederiko11 X channel. No replay of earlier failed or uncertain posts.
- This is a Buffer delivery receipt, NOT an independent public-X timeline or impressions check. Direct public-X retrieval was unavailable in the repair session.

## Failures repaired

1. The website build rejected the two approved Insider Gaming guides because its source assertion only admitted PowerPyx. Added exact HTTPS hostname validation, hostile-URL regression tests, and dynamic guide/page-count tests. Repair commit in xFederiko11/gta-6: `88afd43130ee73f96922aec278a88c3950357750`.
2. Editorial regression tests still expected four PowerPyx-only spotlights and the HDR page to be first. The new curated source and two priority guide pages invalidated those fixtures. Fixed the fixtures while retaining URL/source/layout, first-live-page, pacing and deduplication checks. Repair commit: `97e74cc0684d40288e13a5ff2da8ed4683340a7b`.
3. A caught Buffer delivery error could leave the workflow green. New `buffer_delivery_receipts_v1.py` independently re-reads one current post after persistence; missing/failed/pending current receipts do not count as successful publication. It never creates, retries or edits posts and never changes the deduplication ledger.
4. Publication checks now have a permanent `7,37 * * * *` fallback schedule and relevant content-change triggers. This is check cadence, not a promise to post every 30 minutes. Existing global and local publication limits remain enforced.
5. PR #53 merged: a paused Buffer queue stops new reservations instead of merely showing a warning.

## Website verification

- Successful build/deploy: https://github.com/xFederiko11/gta-6/actions/runs/44653074317
- Dedicated live-page check: https://github.com/xFederiko11/federiko-gta-playstation-bot/actions/runs/44654005861 (success, completed 2026-11-20T01:29:47Z).
- Both pages returned HTTP 200, with matching canonical URL, guide-step markup and Insider Gaming attribution:
  - https://xfederiko11.github.io/gta-6/guide-e-tutorial/soldi-facili-capitolo-1/
  - https://xfederiko11.github.io/gta-6/guide-e-tutorial/soldi-2500-three-sheets-liquor/
- The normal website deployment now includes the new source-validator tests.

## Recovery boundaries

- Fresh quick-tip recovery defaults were reviewed after the above real post-refresh receipt (`ede71172edf8a478c6ce4007617237cb98605c19`). An explicit repository variable `TIPS_REAUTH_CONFIRMED_V149=false` still wins. The old rejected WAiNK thread remains deduplicated; no fresh image-thread delivery is claimed by this note.
- Unit-test diagnostic output is excluded from the real GitHub Step Summary so simulated errors are not shown as production health.
- Temporary repair workflows were removed from both repositories after use; no public administrative publishing page or secret-bearing browser interface was added.
- No password, API key, Buffer subscription, account permission or historical reservation was reset or removed.
- Do not infer that every older design/social-scanner feature request is complete from this incident repair. Verified scope is publication recovery, guide deployment, receipt reporting and the guards described above.
