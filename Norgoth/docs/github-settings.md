# GitHub settings to apply manually

`gh` is not available in every environment. Apply these in the GitHub UI (or install `gh` and use the API).

## Branch protections

### `test`
- Require a pull request before merging
- Require status checks to pass: `Dashboard lint/test/build`, `API pytest`, `Bot pytest`, `Docker build (no push)`
- Restrict force pushes
- Restrict deletions

### `main`
- Require a pull request before merging (prefer from `test`)
- Require status checks (same CI jobs)
- Require review / dismiss stale reviews
- Restrict force pushes and deletions
- Optionally require linear history

## Environments

Create Environments:

| Name | Protection |
|------|------------|
| `test` | optional wait timer |
| `production` | **required reviewers** |

Secrets on both environments (or repo secrets if preferred):

- `DEPLOY_HOST` — VDS public IPv4 (hostname only if it has an A record).
  **Do not** use a Cloudflare-proxied hostname; SSH to Cloudflare IPs times out.
- `DEPLOY_PORT` — SSH listen port (historically **35342**, not 22)
- `DEPLOY_USER` — `norbot`
- `DEPLOY_SSH_KEY` — private key for Actions → VDS (not the repo Deploy Key)
- `DEPLOY_APPLY_SECRET` — HMAC secret for the HTTPS deploy fallback
  (`/opt/norbot/env/ci-apply.secret`). Required when GitHub-hosted runners
  cannot reach `DEPLOY_PORT`.
- `DEPLOY_APPLY_URL` — optional. Defaults to
  `https://api.norbot.io/__norbot/ci-apply` (production) or
  `https://api.test.norbot.io/__norbot/ci-apply` (test).

## Packages

Ensure GHCR is enabled for the repository. Actions deploy logs the VDS into
`ghcr.io` with the job `GITHUB_TOKEN` (`packages:write` includes pull) and
logs out after image pull. An optional host file
`/opt/norbot/env/ghcr.pull.token` is only needed for manual pulls/rollback.
