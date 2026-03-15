# Local Testing Infrastructure

Run the policy server and OPA locally to test Pull Request and Deployment Protection policies.

## Architecture

```
┌──────────┐     ┌─────────────────┐     ┌──────────┐
│  curl /  │────▶│  Policy Server  │────▶│   OPA    │
│  GitHub  │     │  (FastAPI:8080) │     │  (:8181) │
└──────────┘     └─────────────────┘     └──────────┘
                        │                      │
                   .repol/*.yaml          policies/*.rego
```

## Server Structure

The policy server is a modular FastAPI app shared at `infra/server/app/`:

```
infra/server/app/
├── __init__.py          # App assembly (creates FastAPI, includes routers)
├── config.py            # Settings (OPA_URL, REPOL_DIR, GitHub App credentials)
├── opa.py               # OPA REST client
├── github.py            # GitHub deployment callback client
├── audit.py             # SQLite audit trail storage
├── helpers.py           # Shared request helpers (format, record audit)
└── routers/
    ├── health.py        # GET  /health
    ├── evaluate.py      # POST /evaluate/deploy, /evaluate/pullrequest
    ├── webhook.py       # POST /webhook (dispatch), /webhook/deployment_protection_rule, /webhook/pull_request
    └── audit_api.py     # GET  /audit, /audit/{id}
```

## Quick Start

From the repository root:

```bash
# Start services
make local-up

# Run tests
make local-test

# View logs
make local-logs

# Stop services
make local-down
```

## Manual Testing

```bash
# Evaluate a PR policy (direct OPA input)
curl -s http://localhost:8080/evaluate/pullrequest \
  -H "Content-Type: application/json" \
  -d @infra/local/payloads/pr_valid.json | jq .

# Evaluate a deploy policy
curl -s http://localhost:8080/evaluate/deploy \
  -H "Content-Type: application/json" \
  -d @infra/local/payloads/deploy_valid.json | jq .

# Simulate a GitHub deployment_protection_rule webhook
curl -s http://localhost:8080/webhook/deployment_protection_rule \
  -H "Content-Type: application/json" \
  -H "X-Approvers: alice,bob" \
  -H "X-Tests-Passed: true" \
  -H "X-Signed-Off: true" \
  -d '{"environment":"production","deployment":{"ref":"main"}}' | jq .
```

## Docker Runner Image

Standalone OPA image with policies baked in — no Python, no server.
Useful for CI runners and quick evaluations.

```bash
# Build
make local-build-runner

# Run OPA unit tests
docker run --rm policy-opa test /policies -v --ignore "*.json"

# Evaluate a policy from stdin
cat infra/local/payloads/deploy_valid.json | \
  docker run --rm -i policy-opa eval \
    --data /policies --input /dev/stdin --format json \
    "data.github.deploy"

# Serve OPA REST API stand-alone
docker run -d -p 8181:8181 policy-opa run --server --addr :8181 /policies
```

## Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check (verifies OPA connectivity) |
| `/evaluate/deploy` | POST | Evaluate deploy policy — body = full OPA input |
| `/evaluate/pullrequest` | POST | Evaluate PR policy — body = full OPA input |
| `/webhook` | POST | GitHub webhook dispatcher (routes by X-GitHub-Event header) |
| `/webhook/deployment_protection_rule` | POST | GitHub deployment protection webhook |
| `/webhook/pull_request` | POST | GitHub pull request webhook |
| `/audit` | GET | Query audit events (with optional filters) |
| `/audit/{id}` | GET | Retrieve a single audit event |

### Webhook Headers

The `/webhook/*` endpoints accept optional headers to inject workflow metadata
that GitHub doesn't include in the raw webhook payload:

| Header | Type | Default | Description |
|---|---|---|---|
| `X-Approvers` | string | `""` | Comma-separated approver logins |
| `X-Tests-Passed` | bool | `false` | CI tests passed |
| `X-Signed-Off` | bool | `false` | DCO sign-off |
| `X-Deployments-Today` | int | `0` | Deployments already done today |

## Test Payloads

| File | Policy | Expected |
|---|---|---|
| `pr_valid.json` | pullrequest | `allow = true` |
| `pr_denied.json` | pullrequest | `allow = false` (branch naming + target) |
| `deploy_valid.json` | deploy | `allow = true` |
| `deploy_denied.json` | deploy | `allow = false` (branch denied) |
