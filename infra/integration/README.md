# Integration Environment

End-to-end testing with real GitHub webhooks. The policy server runs locally
and receives events from GitHub via [smee.io](https://smee.io). Covers **both**
deployment protection rules and pull request policy checks.

## Architecture

```
        GitHub webhook events
               │
   ┌───────────┴───────────────┐
   │ deployment_protection_rule │  pull_request / pull_request_review
   └───────────┬───────────────┘
               │
           smee.io
               │
               ▼
┌─────────────────┐     ┌─────────────────────┐     ┌──────────┐
│  smee-client    │────▶│   Policy Server      │────▶│   OPA    │
│  (alpine+node)  │     │   (FastAPI :8080)    │     │  :8181   │
└─────────────────┘     └──────────┬──────────┘     └──────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
           GitHub API callback           GitHub Checks API
           POST deployment_callback_url  POST /repos/.../check-runs
           (approve / reject deploy)     (gitpoli / PR Policy ✅/❌)
```

## Prerequisites

- Docker + Docker Compose v2
- GitHub App created and installed on the target repository
  - **Permissions required:** `Actions: write`, `Checks: write`,
    `Deployments: write`, `Environments: write`, `Pull requests: read`
  - **Events subscribed:** `deployment_protection_rule`, `deployment`,
    `pull_request`, `pull_request_review`, `check_run`
- `infra/integration/priv.pem` — private key downloaded from the GitHub App settings
- `infra/integration/.env` — credentials file (see below)

## Configuration

Edit `infra/integration/.env`:

```env
# Webhook tunnel — create a channel at https://smee.io/new
SMEE_URL=https://smee.io/<your-channel>

# GitHub App credentials
GITHUB_APP_ID=<your-app-id>
GITHUB_APP_PRIVATE_KEY_FILE=./priv.pem
```

The `SMEE_URL` must match the **Webhook URL** configured in the GitHub App settings.

## Start / Stop

```bash
make integration-up      # start OPA + policy server + smee tunnel
make integration-logs    # tail logs from all services
make integration-audit   # query the last 20 audit events
make integration-down    # stop and remove containers
```

## Testing Deployment Protection

### Setup (one-time)

1. Create environments in the repo: **Settings → Environments → New environment**
   - Create `production`, `staging`, and `development`
2. For each environment: **Deployment protection rules → Enable → select your App**

### Trigger a test deployment

Go to **Actions → Test Deployment (Integration) → Run workflow**, select an
environment, and click **Run workflow**. The job will pause waiting for the
protection rule response.

### What the server does

1. GitHub sends `deployment_protection_rule` webhook → smee → `POST /webhook`
2. Server loads `.repol/deploy.yaml` (environment rules)
3. Builds OPA input: `{environment, ref, approvers, tests_passed, signed_off, …}`
4. Queries OPA → `policies/deploy.rego` → `allow` + `violations`
5. Records audit event in SQLite
6. Calls back to `deployment_callback_url` → `approved` or `rejected`
7. Updates audit event with callback result (`meta.callback`)

### Verify

```bash
make integration-logs
# Look for:
#   Received event=deployment_protection_rule
#   policy=deploy decision=allow/deny
#   GitHub callback status=204 state=approved/rejected

curl -s "http://localhost:8080/audit?policy=deploy&limit=5" | jq .
```

---

## Testing Pull Request Policy

### Setup (one-time)

The GitHub App must have `Checks: write` and `Pull requests: read` permissions
and be subscribed to `pull_request` and `pull_request_review` events.

> If you updated permissions after the initial install, you must accept the new
> permissions: **Settings → Applications → Installed GitHub Apps → your app →
> Configure → Review request → Accept**.

### Trigger the check

Open a pull request in the repository (any branch → `main` or `develop`).
A `pull_request` webhook fires automatically.

### What the server does

1. GitHub sends `pull_request` (or `pull_request_review`) webhook → smee → `POST /webhook`
2. Server extracts `head_ref`, `base_ref`, `head_sha`, `pr_number`, `installation_id`
3. Fetches real approvers: `GET /repos/{owner}/{repo}/pulls/{n}/reviews` → logins with `APPROVED` state
4. Loads `.repol/pullrequest.yaml` (branch rules, approvals required, sign-off)
5. Queries OPA → `policies/pullrequest.rego` → `allow` + `violations`
6. Records audit event in SQLite
7. Posts Check Run: `POST /repos/{owner}/{repo}/check-runs`
   - Name: `gitpoli / PR Policy`
   - Conclusion: `success` (allow) or `failure` (deny)
   - Output: violation codes + audit ID

### Verify

```bash
make integration-logs
# Look for:
#   Received event=pull_request action=opened
#   GET .../pulls/{n}/reviews  HTTP/1.1 200
#   policy=pullrequest decision=allow/deny
#   Check run posted status=201 conclusion=success/failure

curl -s "http://localhost:8080/audit?policy=pullrequest&limit=5" | jq .
```

The Check Run also appears in the PR's **Checks** tab on GitHub.

To make it a required merge gate: **Settings → Branches → edit rule for `main` →
Require status checks → add `gitpoli / PR Policy`**.

---

## Services

| Service | Port | Description |
|---------|------|-------------|
| `opa`    | 8181 | OPA REST API — policies mounted from `policies/` |
| `server` | 8080 | gitpoli policy server (FastAPI) |
| `smee`   | —    | Webhook tunnel (smee.io → server) |

---

## Troubleshooting

**`smee` not forwarding events:**
Check that `SMEE_URL` in `.env` matches the channel URL in GitHub App settings.
Run `make integration-logs` and look for `POST http://server:8080/webhook - 200`.

**Check Run returns 403:**
The App installation doesn't have `Checks: write`. Update the permission in
GitHub App settings, then accept it in the installation. Verify with:
```bash
# The permissions block should show "checks": "write"
python3 infra/integration/scripts/check_env.py
```

**Deploy callback returns 422:**
The `deployment_callback_url` has expired (GitHub invalidates it after ~10 min).
Trigger a fresh deployment to get a new one.

**No events arriving (server logs empty after action):**
The App is not subscribed to the event type. Check **GitHub App → Edit →
Subscribe to events** and confirm the relevant events are checked, then
save + reinstall.

**smee auto-assigned a new channel URL:**
If `SMEE_URL` was empty on first start, smee created a fresh channel.
Copy the URL from `make integration-logs` and update `SMEE_URL` in `.env`
and the Webhook URL in GitHub App settings.

**Policy evaluation returning unexpected results:**
Test directly against the server:
```bash
# Deploy (uses payload file)
curl -s http://localhost:8080/evaluate/deploy \
  -H "Content-Type: application/json" \
  -d @infra/local/payloads/deploy_valid.json | jq .

# PR (inline input)
curl -s http://localhost:8080/evaluate/pullrequest \
  -H "Content-Type: application/json" \
  -d '{"head_ref":"feature/login","base_ref":"develop","workflow_meta":{"approvers":["alice"],"signed_off":false},"repo_policy":{}}' | jq .
```
