# Contributing to LASSY

LASSY is built task-by-task from the implementation plan. Each task produces
one reviewable pull request. The rules below apply to every contribution,
human or agent.

## One task per pull request

- Each pull request corresponds to exactly one task from the implementation
  plan and uses the branch name specified for that task
  (e.g. `devin/01-repo-contracts`).
- Do not combine multiple tasks in a single pull request.
- Do not begin Task N+1 until the pull request for Task N has been reviewed and
  the owner explicitly says to continue.

## Tests before review

- Use test-driven development: write the failing test first, confirm the
  expected failure, then implement until the test passes.
- A pull request is not ready for review until every stated verification
  command exits 0.
- Run the full unit suite and lint before requesting review:

  ```bash
  uv sync --all-extras --dev
  uv run ruff check .
  uv run pytest -q
  ```

- Dependencies must stay pinned. Commit `uv.lock` and use `uv sync --locked`
  in CI.

## No committed host data

The repository must remain portable and public-safe. Do not commit:

- Secrets, tokens, or credentials (use environment-variable names and
  `.example` templates only).
- Model weights, browser profiles, conversation stores, or screenshots.
- Machine-specific absolute paths (`C:\Users\...`, `/Users/...`, drive letters,
  or machine-specific usernames).
- Private machine reports containing usernames or host-identifying data.

Runtime data uses platform-native user-data directories and is gitignored.

## No merge by an agent

- Agents may push branches and open pull requests.
- Agents must **not** merge pull requests, force-push protected branches,
  alter repository visibility, add billable infrastructure, publish
  packages/releases, or add/change a license without explicit owner approval.
- The `main` branch is protected: pull requests and at least one approving
  review are required; force pushes and deletions are disabled.

## Review checkpoints

At each pull request, the author provides:

1. A one-paragraph outcome summary.
2. Exact tests run and their exit status.
3. Files added/changed.
4. A security-impact statement.
5. Assumptions that still require physical-machine verification.
6. Rollback instructions.
7. A direct question asking whether the next task may begin.

## Architecture authority

Read [`docs/design-contract.md`](docs/design-contract.md) before changing
interfaces or dependencies. Do not reinterpret the architecture mid-task.
