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

| Mode | Event | How | Requires server? |
|------|-------|-----|------------------|
| **CI/CD** | Push / PR | GitHub Actions composite action evaluates policies with the OPA CLI. | No |
| **App webhook — Deploy** | `deployment_protection_rule` | FastAPI server receives the event, evaluates the deploy policy via OPA, and calls back to GitHub to approve or reject. | Yes |
| **App webhook — PR** | `pull_request`, `pull_request_review` | FastAPI server receives the event, fetches real approvers from the GitHub API, evaluates the PR policy via OPA, and posts a Check Run (`gitpoli / PR Policy`) on the PR. | Yes |

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

### Webhook flow (pull request policy)

```
 Developer opens / updates PR  ─── or ───  Reviewer submits approval
           │                                         │
           └─────────────────┬───────────────────────┘
                             │  pull_request / pull_request_review event
                             ▼
                      ┌─────────────┐
                      │  smee.io    │  (webhook tunnel — dev/integration only)
                      └──────┬──────┘
                             │  POST /webhook
                             ▼
             ┌───────────────────────────────────────────┐
             │          gitpoli Policy Server             │
             │             (FastAPI :8080)                │
             │                                           │
             │  1. Parse event (head_ref, base_ref, sha) │
             │  2. GET /pulls/{n}/reviews → approvers    │
             │  3. Load .repol/pullrequest.yaml           │
             │  4. Build OPA input                       │
             │  5. Query OPA ──────────────────────┐     │
             │  6. Record audit event (SQLite)     │     │
             │  7. POST /check-runs ─────────────┐ │     │
             └───────────────────────────────────┼─┼─────┘
                                                 │ │
                           ┌─────────────────────┘ └──────────────┐
                           ▼                                       ▼
                 ┌──────────────────┐                   ┌──────────────┐
                 │   GitHub API     │                   │   OPA :8181  │
                 │  (Check Run      │                   │  (Rego v1)   │
                 │  gitpoli/PR      │                   └──────────────┘
                 │  Policy ✅/❌)   │
                 └──────────────────┘
```

### CI/CD flow (pull request checks — Actions only)

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


## Repository Layout & Extensibility

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
    app/
      handlers/              # Modular policy handlers (extensible registry)
        __init__.py          # Handler registry (explicit)
        pull_request.py      # PR policy handler
        deploy.py            # Deploy policy handler
      routers/               # API routers (webhook, audit, health)
      ...                    # Core modules (github, opa, audit, helpers)
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

### Extensible Handler Registry

Policy evaluation logic is now fully modular and extensible:

- Each event type (e.g. `pull_request`, `deployment_protection_rule`) has a dedicated handler module in `infra/server/app/handlers/`.
- The handler registry in `handlers/__init__.py` allows explicit registration and dispatch.
- To add a new policy, create a handler module and register it in the registry.
- The main webhook dispatcher (`routers/webhook.py`) routes events to the registry, making it easy to evolve and extend.

**Example: Adding a new policy handler**

1. Create `handlers/my_policy.py` with your handler function:
   ```python
   from ..handlers import register_handler
   async def handle_my_policy(request, event):
       # normalization, evaluation, response
       ...
   register_handler("my_policy_event", handle_my_policy)
   ```
2. The dispatcher will automatically route matching events to your handler.

---

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

gitpoli uses a **single GitHub App** for both deployment protection and pull request policy. The App authenticates with a JWT + installation token (no PAT required).

### Step 1: Register the App

1. Go to **GitHub → Settings → Developer settings → GitHub Apps → New GitHub App**
2. Fill in the following:

| Field | Value |
|-------|-------|
| **App name** | `gitpoli` (or any name you choose) |
| **Homepage URL** | Your repo URL or `https://github.com` |
| **Webhook URL** | Your smee.io channel URL (see [Integration Testing](#integration-testing-real-webhooks)) |
| **Webhook secret** | _(leave blank or set one)_ |

3. Under **Repository permissions** set:

| Permission | Level | Required for |
|------------|-------|--------------|
| `Actions` | Read and write | Workflow control |
| `Checks` | **Read and write** | Posting PR Check Runs |
| `Deployments` | **Read and write** | Deployment approval/rejection |
| `Environments` | Read and write | Reading environment config |
| `Pull requests` | **Read-only** (minimum) | Fetching PR approver reviews |

4. Under **Subscribe to events** enable:
   - ☑ **Deployment protection rule**
   - ☑ **Deployment** / **Deployment status**
   - ☑ **Pull request**
   - ☑ **Pull request review**
   - ☑ **Check run**

5. Click **Create GitHub App**.

### Step 2: Generate a Private Key

1. After creating the App, scroll to **Private keys** → **Generate a private key**
2. Download the `.pem` file
3. Place it at `infra/integration/priv.pem`
4. Note the **App ID** from the App's General page

### Step 3: Configure Credentials

Edit `infra/integration/.env`:

```env
SMEE_URL=https://smee.io/<your-channel>
GITHUB_APP_ID=<your-app-id>
GITHUB_APP_PRIVATE_KEY_FILE=./priv.pem
```

### Step 4: Install the App on Your Repository

1. Go to **GitHub → Settings → Developer settings → GitHub Apps → your app → Install App**
2. Select the account/organization that owns your target repo
3. Choose **Only select repositories** → select the target repo
4. Click **Install**

> **Important:** Every time you change permissions in the App settings you must **accept the new permissions** on the installation page. Without this step, the new permissions won't be active. Go to **Settings → Applications → Installed GitHub Apps → your app → Configure** and click **Review request**.

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

### Step 4: Test a Deployment

1. Make sure the integration stack is running: `make integration-up`
2. Go to **Actions → Test Deployment (Integration) → Run workflow**
3. Select an environment and click **Run workflow**
4. The job will pause waiting for the protection rule to approve/reject
5. Watch the server logs: `make integration-logs`
6. Check the audit trail: `curl -s http://localhost:8080/audit | jq .`

---

## Integration Testing (Real Webhooks)

End-to-end testing with real GitHub webhooks via [smee.io](https://smee.io). Covers **both** deployment protection and pull request policy.

### Prerequisites

- GitHub App created and installed on the repo ([Creating the GitHub App](#creating-the-github-app))
- `infra/integration/priv.pem` — downloaded private key
- `infra/integration/.env` — configured with `SMEE_URL` and `GITHUB_APP_ID`
- The smee.io channel URL set as the **Webhook URL** in the GitHub App settings

### Start the stack

```bash
make integration-up      # start OPA + policy server + smee tunnel
make integration-logs    # tail all service logs (server + smee + opa)
make integration-audit   # query audit events
make integration-down    # stop everything
```

### Testing deployment protection

1. Ensure the environments (`production`, `staging`, `development`) exist in the repo and the GitHub App is enabled as a protection rule for each
2. Trigger a deployment via **Actions → Test Deployment (Integration) → Run workflow** or any workflow that deploys to a protected environment
3. GitHub sends a `deployment_protection_rule` webhook → smee → server
4. The server loads `.repol/deploy.yaml`, evaluates via OPA, and calls back to approve or reject
5. Check the result:

```bash
make integration-logs    # look for: decision=allow/deny  callback state=approved/rejected
curl -s http://localhost:8080/audit?policy=deploy | jq .
```

### Testing pull request policy

1. Open a pull request in the repository (any branch → `main` or `develop`)
2. GitHub sends a `pull_request` webhook → smee → server
3. The server fetches real approvers via `GET /repos/{owner}/{repo}/pulls/{n}/reviews`
4. OPA evaluates `.repol/pullrequest.yaml` rules (branch naming, approvals, target branch)
5. The server posts a **Check Run** (`gitpoli / PR Policy`) on the PR with `success` or `failure`
6. Check the result:

```bash
make integration-logs    # look for: decision=allow/deny  check_run posted status=201
curl -s http://localhost:8080/audit?policy=pullrequest | jq .
```

The Check Run will appear in the PR's **Checks** tab on GitHub:
- ✅ `gitpoli / PR Policy — Policy passed`
- ❌ `gitpoli / PR Policy — Policy violations found` (with violation codes listed)

> **Tip:** To also trigger on review approvals, the App must have the `pull_request_review` event subscribed. When a reviewer approves, a new `pull_request_review` webhook fires and the check run is updated automatically.

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


---

## Deployment Proposal for Production

This section describes how to deploy gitpoli in a production Azure environment, mapping each component to recommended Azure services:

### Component Mapping

| Component         | Azure Service / Strategy                | Notes                                  |
|-------------------|----------------------------------------|----------------------------------------|
| Policy Server     | Azure Container Apps / App Service     | FastAPI app, scalable, managed         |
| OPA Engine        | Azure Container Apps (sidecar) / AKS   | OPA as a container, sidecar or AKS pod |
| Audit Trail       | Azure Cosmos DB (production)           | Replace SQLite with Cosmos DB          |
| Webhook Relay     | Azure Event Grid / API Management      | smee.io for dev, Event Grid for prod   |
| Policy Configs    | Azure Blob Storage / Repo mount         | Store YAML configs in Blob Storage     |

### Deployment Steps

1. **Policy Server (FastAPI):**
  - Deploy as an Azure Container App for managed scaling and easy integration with OPA.
  - Alternatively, use Azure App Service for simple web hosting.

2. **OPA Engine:**
  - Run OPA as a sidecar container in Azure Container Apps, or as a pod in Azure Kubernetes Service (AKS).
  - Mount policies from Blob Storage or use GitHub Actions to publish bundles.

3. **Audit Trail:**
  - Use Azure Cosmos DB for production-grade audit storage (global distribution, scalability).
  - Update the audit adapter to use Cosmos DB instead of SQLite.

4. **Webhook Relay:**
  - For production, use Azure Event Grid or Azure API Management to securely relay GitHub webhooks to the policy server.
  - For development/integration, smee.io remains supported.

5. **Policy Configs:**
  - Store `.repol/*.yaml` configs in Azure Blob Storage for centralized, versioned access.
  - Mount Blob Storage as a volume or fetch configs at runtime.

### Integration

- All components communicate via HTTP APIs.
- Use Azure Managed Identity for secure access between services (e.g., policy server → Cosmos DB).
- Configure environment variables for service endpoints and credentials.

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

## Simulating Azure Stack Locally

To test the Azure production architecture locally, use Docker Compose in `infra/integration/`:

1. **Run the full stack:**
   - OPA (policy engine)
   - Policy Server (FastAPI app)
   - smee (webhook relay, simulates Azure Event Grid)

2. **How to start:**

```bash
cd infra/integration
cp .env.example .env   # Edit with your GitHub App credentials
docker compose up -d   # Starts opa, server, smee
```

- smee forwards GitHub webhooks to your local server, simulating Azure Event Grid.
- Policy Server and OPA run as containers, simulating Azure Container Apps/App Service and OPA sidecar.
- Audit data is stored in a local volume, simulating Cosmos DB.
- Policy configs are mounted from `.repol/`, simulating Blob Storage.

3. **Test end-to-end:**
- Trigger GitHub Actions or deployments in your repo.
- Webhooks are relayed via smee to your local stack.
- Policy evaluation, audit, and callbacks are handled as in Azure.

---

## Azure-like Integration Stack (az-integration)

You can simulate the full Azure production stack locally using Docker Compose in `infra/az-integration/`:

- Cosmos DB Emulator (or Mongo as fallback)
- Azure Functions (Core Tools, Python)
- OPA (Open Policy Agent)
- smee (webhook relay, simulates Event Grid)

### Usage

```bash
make az-integration-up      # Start Azure-like stack
make az-integration-logs    # Tail logs from all services
make az-integration-down    # Stop everything
```

- The backend Python runs as an Azure Function (HTTP trigger) using Core Tools.
- Audit events are stored in Cosmos DB (emulator) if `AUDIT_BACKEND=cosmos`, or SQLite if `AUDIT_BACKEND=sqlite`.
- All components are selected via environment variables and inyectable contracts (see below).


### Extensibility & Clean Architecture (Adapter/Factory Pattern)

All variable components (audit, config, OPA client, etc.) implement a contract (interface/abstract class) in `core/`, with adapters in `adapters/`:

- `AuditTrail`: `SQLiteAuditTrail`, `CosmosAuditTrail`
- `Config`: `EnvConfig`, ...
- (You can extend this pattern to OPA client, storage, etc.)

The factory (e.g. `audit.py`) selects the correct implementation based on environment variables (e.g. `AUDIT_BACKEND`). This means:

- **`audit.py` is NOT an adapter or implementation.** It is a pure factory that injects the correct adapter everywhere.
- To add a new backend, create a new adapter in `adapters/` and update the factory to support it.
- All code uses the interface (`AuditTrail`), never the concrete class directly.

**How to extend:**

1. **Add a new backend:**
  - Create a new adapter in `src/app/adapters/` implementing the relevant interface from `core/`.
  - Update the factory (e.g. `audit.py`) to select your adapter based on an environment variable.
2. **Add a new policy handler:**
  - Create a new handler in `src/app/handlers/` and register it in the handler registry.
  - See the extensibility section and CONTRIBUTING.md for details.

**This pattern ensures:**
- All logic is decoupled and testable.
- Adding new backends or policies is easy and does not require changing core logic.
- The codebase is clean, DRY, and ready for production or further extension.

---
