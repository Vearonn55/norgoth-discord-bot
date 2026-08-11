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

- `DEPLOY_HOST` — VDS public IP/hostname
- `DEPLOY_USER` — `norbot`
- `DEPLOY_SSH_KEY` — private key for Actions → VDS (not the repo Deploy Key)

## Packages

Ensure GHCR is enabled for the repository and the `norbot` VDS user can `docker login ghcr.io` (PAT or `GITHUB_TOKEN` via deploy).
