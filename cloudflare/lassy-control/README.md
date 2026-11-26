# LASSY Control Worker

Cloudflare control plane for the outbound-only LASSY runner. A SQLite-backed
Durable Object serializes job claims and persists bounded results.

Set `LASSY_RUNNER_SECRET` and `LASSY_CONTROL_SECRET` with `wrangler secret put`.

Per-runner secrets: give a runner its own secret with `wrangler secret put LASSY_RUNNER_SECRET__<ID>`, where `<ID>` is the runner id in upper case with `-` written as `_` (for example `bigg-legion` becomes `LASSY_RUNNER_SECRET__BIGG_LEGION`). The `runner_id` in the request body picks the secret. Once a runner has its own secret, the shared `LASSY_RUNNER_SECRET` no longer works for it, and its secret works for no other runner. Only lowercase ids of `a-z`, `0-9` and `-` can have their own secret, so two ids never share a binding. A runner without its own secret keeps using the shared one until it is migrated, and the shared one can be removed after the last runner moves. On the runner, `lassy runner-secret-set --data-dir <dir> --stdin` reads the secret from stdin, so a custodian such as Hermes can store it without a console prompt.
The values must differ and must never be committed. Generate binding types with
`npm run types`, then run `npm run check` and `npm run deploy:dry` before deploy.

Human clients do not call `/control/*` directly. Wonderland Gateway holds the
control secret and exposes scoped MCP tools through its existing OAuth flow.
The PC holds only the runner secret and calls `/runner/*` over outbound HTTPS.
