# Verified publishing recovery - 20 November 2026

## Actual publication evidence

- Editorial publication run: https://github.com/xFederiko11/federiko-gta-playstation-bot/actions/runs/44653659495
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
6. A push-only lookup of an old rejected Buffer thread raised a GraphQL error and prevented the mandatory live preflight from running. Historical diagnostics now report unavailability without retrying, exposing response details, changing history or claiming current health. Current destination preflight and new-publication receipt checks remain mandatory. Fix: `2087414d022db52550013b932bc03f34e63180ae`; six added regression cases: `68002bd901d5a1bcd6a77ff2ac9796f051cdc867`.

## Final production verification

- Final push-triggered run: https://github.com/xFederiko11/federiko-gta-playstation-bot/actions/runs/44654529939
- Job 136017384012 completed successfully; logs end at 2026-11-20T01:34:08Z.
- 83 offline regression tests passed; X safety audit passed.
- The unavailable old rejected-thread lookup was handled as advisory with no mutation.
- Real live preflight: `BUFFER_PREFLIGHT_OK account=@xFederiko11`.
- Real tip state: `QUICK_TIPS_READY`, `TIPS_REAUTH_CONFIRMED_V149=true`; history and deduplication unchanged.
- Eight feeds succeeded: 110 qualifying items, zero feed errors.
- The director correctly held another publication for `editorial_local_spacing`; no second post was attempted seven minutes after the first.
- A separate read-only check at 01:34:07Z reconfirmed the same Buffer post as sent with the original sentAt. Buffer then returned https://x.com/2122776704191995904/status/2123588882885186002 for the same post ID and verified channel.
- `current_run_attempted=false` correctly distinguished this verification-only run from the earlier actual publication.

## Website verification

- Successful build/deploy: https://github.com/xFederiko11/gta-6/actions/runs/44653074317
- Dedicated live-page check: https://github.com/xFederiko11/federiko-gta-playstation-bot/actions/runs/44654005861 (success, completed 2026-11-20T01:29:47Z).
- Both pages returned HTTP 200, with matching canonical URL, guide-step markup and Insider Gaming attribution:
  - https://xfederiko11.github.io/gta-6/guide-e-tutorial/soldi-facili-capitolo-1/
  - https://xfederiko11.github.io/gta-6/guide-e-tutorial/soldi-2500-three-sheets-liquor/
- The normal website deployment now includes the new source-validator tests.

## Recovery boundaries

- Fresh quick-tip recovery defaults were reviewed after the real post-refresh receipt (`ede71172edf8a478c6ce4007617237cb98605c19`) and their readiness was observed in the final run. An explicit repository variable `TIPS_REAUTH_CONFIRMED_V149=false` still wins. The old rejected WAiNK thread remains deduplicated; no fresh image-thread delivery is claimed by this note.
- Unit-test diagnostic output is excluded from the real GitHub Step Summary so simulated errors are not shown as production health.
- Temporary repair workflows were removed from both repositories after use; no public administrative publishing page or secret-bearing browser interface was added.
- No password, API key, Buffer subscription, account permission or historical reservation was reset or removed.
- Do not infer that every older design/social-scanner feature request is complete from this incident repair. Verified scope is publication recovery, guide deployment, receipt reporting and the guards described above.
