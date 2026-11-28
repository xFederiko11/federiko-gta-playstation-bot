# BOT X — Control Room v1

The chat can inspect GitHub directly. The GitHub connector cannot directly create workflow dispatch events; this bridge accepts a strictly typed request in `.github/control-room/request.json` on main. No additional tokens, server, scheduled job, or paid runner.

| action | existing workflow | safety mode |
|---|---|---|
| grafica | gta6-photo-review-inbox-v1.yml | preview (no paid X API) |
| community | gta6-x-verified-social-radar-v1.yml | preview (no paid X API, manual drafts only) |
| pubblicazione | gta6-editorial-autopilot-v137.yml | preview (no Buffer calls or posting) |
| sito | site-editorial-integration-v1.yml | read-only site verification |

Only the repository's authenticated main-branch writers can send a command. No public comment, issue, arbitrary workflow, branch, shell, or input is accepted. A main-branch commit changing the mailbox triggers one bounded GitHub job. It uses GitHub's ephemeral token with actions:write only in the dispatch job. The PR validation job is read-only. The target workflows retain their normal safety and permissions.

## Operation

1. Read the latest mailbox and existing workflow runs. Reuse an active or recent result rather than creating a new request.
2. Update the mailbox using the current file SHA on main, with only the action and current UTC timestamp (seconds, ending Z). Submit only one command at a time; do not overwrite a command before its controller run has completed.
3. Inspect the controller workflow's result once. ACCEPTED means GitHub accepted the dispatch, not that the target finished. SKIPPED means no new target was started.
4. Inspect the target workflow once on a later check; do not poll or retry uncertain deliveries.

Requests older than the previous request, expired after 30 minutes, over 2 minutes in the future, superseded, already running, or with a target scheduled/manual run in the last 60 minutes are rejected/skipped. Reruns and force pushes cannot dispatch. An idle request is a no-op. No manual publication, Buffer writes, social replies, paid API scan, or changes to schedules are enabled by this bridge. It does not control ChatGPT WORK sessions.

The mailbox is public; do not put personal information, credentials, or article drafts in it. Never route around a failed authorization. If write permissions or branch rules prevent a request, use the existing GitHub Actions UI or the scheduled run. The controller's result is authoritative only for its own dispatch.
