# LASSY Control Worker

Cloudflare control plane for the outbound-only LASSY runner. A SQLite-backed
Durable Object serializes job claims and persists bounded results.

Set `LASSY_RUNNER_SECRET` and `LASSY_CONTROL_SECRET` with `wrangler secret put`.
The values must differ and must never be committed. Generate binding types with
`npm run types`, then run `npm run check` and `npm run deploy:dry` before deploy.

Human clients do not call `/control/*` directly. Wonderland Gateway holds the
control secret and exposes scoped MCP tools through its existing OAuth flow.
The PC holds only the runner secret and calls `/runner/*` over outbound HTTPS.
