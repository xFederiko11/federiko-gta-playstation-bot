# GTA VI News Center — operations

This is a public production repository. It posts to X through existing Buffer credentials and runs on standard GitHub-hosted runners.

## Active workflows

- GTA Monitor gratuito: Rockstar, PlayStation and verified YouTube links.
- Breaking News Watch v13.4: official breaking news.
- Editorial Autopilot v13.7: press articles plus four curated PowerPyx launch spotlights.
- Special Campaign v13.9: short-lived official Rockstar image campaign, expiring 20 November 2026.

Keep workflow names stable: some automations depend on their names. Do not delete the .state directory, archived launch ledgers, bootstrap-gta6-v3-state.json or history-public.json.

## PowerPyx editorial coverage

Four original Italian posts from PowerPyx guides dated 18 November 2026: platinum roadmap, 70/80 challenges, missions/manual saves, and collectible database. Each carries an official link to the corresponding PowerPyx article. Spotlight window ends 24 November 2026 UTC; at least 120 minutes separate them. The existing editorial ledger controls deduplication. New posts must remain source-verified; PowerPyx estimates are attributed, not official Rockstar statements.

## X engagement

No new subscriptions. Buffer API does not provide the required X reply-reading/posting workflow for automatic public comment outreach. See OUTREACH-X-PLAYBOOK.md for manual draft responses to verified relevant videos; do not claim that comments were posted.

## Verify that a post was published

Check the GitHub run event, then the reserve step, then BUFFER_SENT (or BUFFER_PENDING). A green run with RESERVE count=0 or DELIVERY_NOT_ATTEMPTED means no new post. Confirm the post in Buffer Sent and on X where possible. Do not repeat uncertain deliveries: Buffer may have received the original mutation.

## Maintenance

Review logs and quotas weekly. Apply dependency updates only after tests and review. Keep GitHub Secrets private and prefer least-privilege workflow permissions. The previous Buffer Essentials through-date in workflow configuration is 15 December 2026; verify the plan before that date. No extra paid service is permitted.


## Watchdog autonomo v1

- Workflow: `.github/workflows/gta6-autonomous-health-v1.yml`, esecuzione prevista ogni 3 ore e su richiesta.
- Monitora i run di produzione di `gta-monitor.yml`, `gta6-editorial-autopilot-v137.yml`, `gta6-community-research-v1.yml` e il workflow del sito `deploy-site.yml`.
- Controlla nel ledger editoriale gli esiti recenti `rejected` o `uncertain` di Buffer, senza contattare Buffer e senza rimuovere o ritentare post.
- In caso di problemi apre/aggiorna un'unica issue `GTA VI - Stato automazioni`; la chiude soltanto quando lo stato torna regolare.
- I risultati sono conservati come artifact temporanei per 7 giorni. Il controllo è indipendente da ChatGPT e non ha accesso a segreti X/Buffer.
- Run falliti, API GitHub temporaneamente indisponibili e ledger malformato richiedono una verifica operativa; nessun meccanismo promette un servizio privo di manutenzione.

