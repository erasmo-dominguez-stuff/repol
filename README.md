# gitpoli

**Policy as Code for the GitHub software development lifecycle.**

gitpoli lets platform and security teams define, test, and enforce deployment and pull-request rules across their GitHub repositories — all as versioned [Rego](https://www.openpolicyagent.org/docs/latest/policy-language/) policies evaluated by [Open Policy Agent](https://www.openpolicyagent.org/).

> The `.repol/` configuration directory stands for **repo policies** — the per-repo rules that teams own and edit.

[![OPA](https://img.shields.io/badge/OPA-v1.x-blue?logo=openpolicyagent)](https://www.openpolicyagent.org/)
[![Rego v1](https://img.shields.io/badge/Rego-v1-4a90e2)](https://www.openpolicyagent.org/docs/latest/policy-language/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Table of Contents

- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Policies](#policies)
- [Repository Layout](#repository-layout)
- [Quick Start](#quick-start)
- [Creating the GitHub App](#creating-the-github-app)
- [Configuring Deployment Protection Rules](#configuring-deployment-protection-rules)
- [Integration Testing (Real Webhooks)](#integration-testing-real-webhooks)
- [Audit Trail](#audit-trail)
- [API Reference](#api-reference)
- [Contributing](#contributing)

---

## How It Works

Each policy follows the same pattern:

1. **Team configuration** — YAML files in `.repol/` declare per-environment rules: required approvals, allowed branches, sign-off, rate limits, etc.
2. **Schema validation** — JSON Schemas in `schemas/` validate the configuration structure.
3. **Rego evaluation** — The policy evaluates `input` against the configuration and produces `allow` (boolean) and `violations` (set of `{code, msg}` objects).

### Two modes of operation

| Mode | When | How |
|------|------|-----|
| **CI/CD** | Every push and PR | GitHub Actions composite action (`.github/actions/eval-policy/`) evaluates policies with the OPA CLI. No server required. |
| **Webhook** | Deployment to a protected environment | A FastAPI server receives `deployment_protection_rule` events, evaluates the policy via OPA, records an audit trail, and calls back to GitHub to approve or reject. Authenticated as a GitHub App (JWT + installation token, no PAT). |

---

## Architecture

### Webhook flow (deployment protection)

```
 Developer pushes / triggers deploy
           │
           ▼
 ┌─────────────────────┐
 │  GitHub Repository   │
 │  (environment rule)  │
 └────────┬────────────┘
          │  deployment_protection_rule event
          ▼
 ┌─────────────────┐
 │   smee.io       │  (webhook tunnel — dev/integration only)
 └────────┬────────┘
          │  POST /webhook
          ▼
 ┌─────────────────────────────────────────────────┐
 │              gitpoli Policy Server               │
 │                 (FastAPI :8080)                   │
 │                                                   │
 │  1. Parse event (environment, ref, deployment)    │
 │  2. Load .repol/deploy.yaml (team config)         │
 │  3. Build OPA input                               │
 │  4. Query OPA ──────────────────────────┐         │
 │  5. Record audit event (SQLite)         │         │
 │  6. Callback to GitHub ──────────┐      │         │
 │                                  │      │         │
 └──────────────────────────────────┼──────┼─────────┘
                                    │      │
                    ┌───────────────┘      └──────────────┐
                    ▼                                      ▼
          ┌──────────────────┐                   ┌──────────────┐
          │   GitHub API     │                   │   OPA :8181  │
          │  (approve/reject)│                   │  (Rego v1)   │
          └──────────────────┘                   └──────────────┘
```

### CI/CD flow (pull request checks)

```
 Developer opens / updates PR
           │
           ▼
 ┌──────────────────────────────┐
 │  GitHub Actions              │
 │  ├─ policy-check.yml         │   opa check + opa test + schema validate
 │  └─ reusable-pr-check.yml    │   eval-policy action → allow/deny
 └──────────────────────────────┘
           │
           ▼
       OPA CLI (no server)
```

---

## Policies

| Policy | Package | Purpose |
|--------|---------|---------|
| **Deployment Protection** | `github.deploy` | Enforces rules when deploying to protected environments |
| **Pull Request** | `github.pullrequest` | Enforces rules on pull requests before merge |

Both policies share common helper functions in `policies/lib/helpers.rego`.

### Deployment Protection checks

- Input and policy schema validation
- Environment exists and is enabled
- Branch is in the allowed list for the target environment
- Minimum approvals met
- CI tests passed
- DCO sign-off present
- Daily deployment rate limit

### Pull Request checks

- Policy configuration present and valid
- Branch naming convention matches (source → target mapping)
- Target branch is in the allowed list
- Minimum approvals met
- DCO sign-off present

---

## Repository Layout

```
.devcontainer/               # Dev Container (recommended dev environment)
.github/
  actions/eval-policy/       # Composite action for CI (OPA eval + summary)
  workflows/
    policy-check.yml         # CI: lint + test on push/PR
    policy-docker-ci.yml     # CI: build Docker image for server
    reusable-pr-check.yml    # Reusable: evaluate PR policy
    reusable-deploy-check.yml# Reusable: evaluate deploy policy
    test-deploy.yml          # Manual: trigger test deployment
    policy-release.yml       # Release: publish OPA bundle
.repol/                      # Repo policies — YAML configs teams edit
  pullrequest.yaml           # PR rules: branch naming, approvals, sign-off
  deploy.yaml                # Deploy rules per environment (prod, staging, dev)
infra/
  local/                     # Local testing (Docker Compose: OPA + server)
  integration/               # Integration testing with real GitHub webhooks
  server/                    # Shared FastAPI server
  smee/                      # smee.io relay container (webhook tunnel)
policies/
  lib/helpers.rego           # Shared helper functions
  pullrequest.rego           # PR policy (Rego v1)
  deploy.rego                # Deploy policy (Rego v1)
  tests/                     # OPA unit tests
schemas/                     # JSON Schemas that validate .repol/ files
scripts/                     # Utility scripts (schema validation)
Makefile                     # All dev, test, and infra commands
```

---

## Quick Start

### Prerequisites

- [OPA CLI](https://www.openpolicyagent.org/docs/latest/#running-opa) ≥ 1.9
- Docker + Compose v2 (for local/integration testing)

### Validate & Test

```bash
make lint    # opa check + opa fmt + schema validation
make test    # run all OPA unit tests
```

### Evaluate Policies Locally

```bash
make eval-deploy    # evaluate deploy policy with sample input
make eval-pr        # evaluate PR policy with sample input
```

### Run the Full Stack Locally

```bash
make local-up       # start OPA + policy server
make local-test     # run integration tests against it
make local-down     # stop services
```

### Build OPA Bundle

```bash
make build
```

---

## Creating the GitHub App

To use gitpoli as a **deployment protection rule**, you need a GitHub App that receives `deployment_protection_rule` webhook events and calls back to approve or reject deployments.

### Step 1: Register the App

1. Go to **GitHub → Settings → Developer settings → GitHub Apps → New GitHub App**
2. Fill in the following:

| Field | Value |
|-------|-------|
| **App name** | `gitpoli` (or any name you choose) |
| **Homepage URL** | Your repo URL or `https://github.com` |
| **Webhook URL** | Your smee.io channel URL (see [Integration Testing](#integration-testing-real-webhooks)) |
| **Webhook secret** | _(leave blank or set one)_ |

3. Under **Permissions**:
   - **Repository permissions:**
     - `Deployments` → **Read and write**
     - `Actions` → **Read-only** (optional, for workflow visibility)
   - **Subscribe to events:**
     - ☑ **Deployment protection rules**

4. Click **Create GitHub App**.

### Step 2: Generate a Private Key

1. After creating the App, scroll to **Private keys** → **Generate a private key**
2. Download the `.pem` file
3. Place it at `infra/integration/app.pem`
4. Note the **App ID** from the App's General page

### Step 3: Install the App on Your Repository

1. Go to **GitHub → Settings → Developer settings → GitHub Apps → your app → Install App**
2. Select the organization / account that owns your target repository
3. Choose **Only select repositories** → select the target repo
4. Click **Install**

---

## Configuring Deployment Protection Rules

After installing the GitHub App, you need to create environments and enable the custom deployment protection rule.

### Step 1: Create Environments

1. Go to your **target repository → Settings → Environments**
2. Click **New environment** and create:
   - `production`
   - `staging`
   - `development`

### Step 2: Enable the Custom Protection Rule

1. Go to **Settings → Environments → production → Deployment protection rules**
2. Under **Enable custom deployment protection rules**, find your GitHub App (`gitpoli`) and enable it
3. Repeat for `staging` if desired

> **Tip:** You can also enable the protection rule programmatically:
> ```bash
> # From within the integration stack container:
> docker compose -f infra/integration/docker-compose.yml exec server \
>   python -m scripts.enable_protection_rule
> ```

### Step 3: Configure `.repol/deploy.yaml`

Each repository that adopts gitpoli needs a `.repol/deploy.yaml` defining the rules per environment:

```yaml
# .repol/deploy.yaml
policy:
  version: "1.0.0"
  environments:
    production:
      enabled: true
      rules:
        approvals_required: 2       # require 2 PR approvers
        allowed_branches: [main]    # only deploy from main
        tests_passed: true          # CI tests must pass
        signed_off: true            # DCO sign-off required
        max_deployments_per_day: 5  # rate limit

    staging:
      enabled: true
      rules:
        approvals_required: 0
        allowed_branches: [main, develop]
        tests_passed: false
        signed_off: false
        max_deployments_per_day: 20

    development:
      enabled: true
      rules:
        approvals_required: 0
        allowed_branches: null      # any branch
        tests_passed: false
        signed_off: false
        max_deployments_per_day: 50
```

### Step 4: Test with a Deployment

1. Go to **Actions → Test Deployment (Integration) → Run workflow**
2. Select an environment and click **Run workflow**
3. The job will wait for the deployment protection rule to approve/reject
4. Check the audit trail: `curl -s http://localhost:8080/audit | jq .`

---

## Integration Testing (Real Webhooks)

End-to-end testing with real GitHub `deployment_protection_rule` webhooks via [smee.io](https://smee.io).

### Setup

```bash
# Interactive setup — creates smee channel, validates credentials
make integration-setup
```

Or manually:

1. Create a smee.io channel at https://smee.io/new
2. Copy `infra/integration/.env.example` → `infra/integration/.env`
3. Set `SMEE_URL`, `GITHUB_APP_ID`, and place the `.pem` key at `infra/integration/app.pem`

### Run

```bash
make integration-up      # start OPA + server + smee tunnel
make integration-logs    # tail all service logs
make integration-audit   # query audit events
make integration-down    # stop everything
```

### What happens

1. You trigger a deployment in your GitHub repository (manually or via `test-deploy.yml`)
2. GitHub sends a `deployment_protection_rule` event to the smee.io channel
3. `smee-client` forwards it to `POST /webhook` on the policy server
4. The server loads `.repol/deploy.yaml`, builds the OPA input, and queries OPA
5. OPA evaluates `policies/deploy.rego` and returns allow/deny + violations
6. The server records an audit event and calls back to GitHub to approve/reject
7. The audit event is updated with the callback result (HTTP status, state)

### Services

| Service | Port | Description |
|---------|------|-------------|
| `opa`    | 8181 | OPA REST API with policies mounted |
| `server` | 8080 | Policy evaluation server (FastAPI) |
| `smee`   | —    | Webhook tunnel (smee.io → server) |

---

## Audit Trail

Every policy evaluation is recorded in an SQLite database for traceability.

### Audit schema

Each event includes:

| Field | Description |
|-------|-------------|
| `id` | Unique UUID |
| `timestamp` | ISO 8601 UTC |
| `policy` | `deploy` or `pullrequest` |
| `decision` | `allow` or `deny` |
| `violations` | Array of `{code, msg}` objects |
| `input_hash` | SHA-256 hash prefix of the input (for deduplication) |
| `actor` | Who triggered the evaluation (from `X-Actor` header) |
| `source` | `webhook`, `evaluate`, or `api` |
| `environment` | Target environment (deploy only) |
| `ref` | Git ref being evaluated |
| `meta` | Extra context: approvers, head_ref, callback result |

### Callback tracking

When the server calls the GitHub API to approve/reject, the result is recorded inside the audit event's `meta.callback`:

```json
{
  "meta": {
    "callback": {
      "status_code": 204,
      "state": "approved",
      "timestamp": "2026-03-16T08:00:00+00:00"
    }
  }
}
```

---

## API Reference

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Server + OPA health check |

### Policy evaluation (direct)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/evaluate/deploy` | Evaluate deploy policy (full OPA input JSON) |
| `POST` | `/evaluate/pullrequest` | Evaluate PR policy (full OPA input JSON) |

### Webhook

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/webhook` | Single entrypoint — routes by `X-GitHub-Event` header |
| `POST` | `/webhook/deployment_protection_rule` | Direct deploy handler |
| `POST` | `/webhook/pull_request` | Direct PR handler |

### Audit

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/audit` | Query events. Params: `limit`, `policy`, `decision`, `since`, `environment` |
| `GET` | `/audit/summary` | Aggregate stats: totals by decision, policy, environment |
| `GET` | `/audit/{id}` | Single event by ID |

**Example:**

```bash
# List recent audit events
curl -s http://localhost:8080/audit?limit=5 | jq .

# Get summary stats
curl -s http://localhost:8080/audit/summary | jq .
# → {"total": 8, "by_decision": {"allow": 4, "deny": 4}, "by_policy": {"deploy": 4, "pullrequest": 4}, ...}

# Filter by environment and decision
curl -s "http://localhost:8080/audit?environment=production&decision=deny" | jq .
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full development guide, including devcontainer setup.

```bash
make lint test    # run all checks
```







---

MIT © 2026 Erasmo Domínguez
