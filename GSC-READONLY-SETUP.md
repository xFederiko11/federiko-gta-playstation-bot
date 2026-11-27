# Search Console — private, read-only, zero additional service spend

Status: code prepared for an authorized private engine. The existing public bot does NOT receive OAuth credentials or publish private search analytics. The OpenSEO connection is separate and cannot be exported to GitHub Actions.

Official API: https://developers.google.com/webmaster-tools/v1/searchanalytics/query
OAuth scope: https://www.googleapis.com/auth/webmasters.readonly
Property: https://xfederiko11.github.io/gta-6/ (URL-prefix property, verified access required).

1. Complete private engine migration and verify the included runner/storage budget with paid overage blocked. Do not add a paid service.
2. In an owner-controlled Google Cloud project enable Search Console API; authorize a dedicated OAuth client and refresh token with only the readonly scope. Store GSC_CLIENT_ID, GSC_CLIENT_SECRET, GSC_REFRESH_TOKEN as secrets in the private repo, never in source, logs or messages.
3. After read-only access and zero paid overage are confirmed, set private repository variables GSC_READONLY_ENABLED=true and BOTX_PRIVATE_BUDGET_VERIFIED=true. Public repos always skip the secret-bearing steps.
4. Existing source workflow runs a daily report during 00:00–03:59 UTC, or explicitly on manual dispatch, without a new cron. Report contains the last two complete seven-day windows for Italy, query/page and page rows, clicks, impressions, CTR, average position, canonical review suggestions. It stays in a private Actions artifact (14 days); no issue, Pages, Buffer or X export. No title rewrite or posting.
5. Verify GSC_PRIVATE_REPORT_OK, then inspect the private artifact and monitor access/revocation, local caps, and quota. If credentials are absent, it skips; if API fails, it reports failure without logging response or secrets. Search Analytics gives top returned rows rather than exact national keyword volume. Existing Trends RSS remains separate.

Until the private repository, budget and authorization exist, use the already connected Search Console interface for read-only reviews. Do not label the scheduled GSC collector operational.
