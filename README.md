# governant

**Policy as Code para el ciclo de vida de desarrollo en GitHub.**

governant permite a equipos de plataforma y seguridad definir, testear y aplicar reglas de deployment y pull request en sus repositorios de GitHub — todo como políticas Rego versionadas evaluadas por [Open Policy Agent](https://www.openpolicyagent.org/).

El nombre del proyecto viene de **repo[l]** → **governant**: gobernar repositorios mediante políticas declarativas.

[![OPA](https://img.shields.io/badge/OPA-v1.x-blue?logo=openpolicyagent)](https://www.openpolicyagent.org/)
[![Rego v1](https://img.shields.io/badge/Rego-v1-4a90e2)](https://www.openpolicyagent.org/docs/latest/policy-language/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Policies

| Policy | Package | Purpose |
|--------|---------|---------|
| **Deployment Protection** | `github.deploy` | Enforces rules when deploying to protected environments (approvals, allowed branches, tests, sign-off, rate limit) |
| **Pull Request** | `github.pullrequest` | Enforces rules on pull requests before merge (approvals, allowed branches, sign-off) |

Both policies share common helper functions in `policies/lib/helpers.rego`.

---

## How It Works

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────┐
│  GitHub webhook  │────▶│  Policy Server  │────▶│   OPA    │
│  (or CI action)  │     │  (FastAPI:8080) │     │  (:8181) │
└─────────────────┘     └────────┬────────┘     └──────────┘
                                 │
                         GitHub API callback
                         (approve / reject)
```

1. **Team configuration** — YAML files in `.repol/` declare per-environment rules: required approvals, allowed branches, sign-off, rate limits, etc.
2. **Schema validation** — JSON Schemas in `schemas/` validate the configuration structure.
3. **Rego evaluation** — The policy evaluates `input` against the configuration and produces `allow` (boolean) and `violations` (set of `{code, msg}` objects).
4. **GitHub callback** — For deployment protection rules, the server calls back to GitHub to approve or reject the deployment.

The server authenticates to GitHub as a **GitHub App** (JWT + installation token). No PAT required.

---

## Repository Layout

```
.devcontainer/               # Dev Container (recommended dev environment)
.github/
  actions/eval-policy/       # Composite action for CI
  workflows/                 # CI/CD workflows
.repol/                      # Policy YAML configs (teams edit these)
  pullrequest.yaml           # PR validation rules + branch naming
  deploy.yaml                # Deployment protection rules per environment
infra/
  local/                     # Local testing (Docker Compose: OPA + server)
  integration/               # Integration testing with real GitHub webhooks
  server/                    # Shared FastAPI server (OPA client, audit trail, GitHub auth)
  smee/                      # smee.io relay container (webhook tunnel)
policies/
  lib/helpers.rego           # Shared helper functions
  pullrequest.rego           # PR policy (Rego v1)
  deploy.rego                # Deploy policy (Rego v1)
  tests/                     # OPA unit tests
schemas/                     # JSON Schemas that validate .repol/ files
scripts/                     # Utility scripts (schema validation)
Makefile                     # All dev, test, and infra commands
pyproject.toml               # Python project metadata
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
make local-test     # run integration tests
make local-down     # stop services
```

### Build OPA Bundle

```bash
make build
```

---

## Infrastructure

### Local testing (`infra/local/`)

Runs OPA and the policy server in Docker for offline evaluation testing. See [infra/local/README.md](infra/local/README.md).

### Integration testing (`infra/integration/`)

End-to-end testing with real GitHub `deployment_protection_rule` webhooks via a smee.io tunnel. Requires a GitHub App. See [infra/integration/README.md](infra/integration/README.md).

### Policy server (`infra/server/`)

A modular FastAPI application shared by both environments:

- **Webhook dispatcher** — routes GitHub events to the right handler
- **OPA client** — evaluates policies against the OPA REST API
- **Audit trail** — records every evaluation in SQLite
- **GitHub auth** — GitHub App JWT authentication (no PAT)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full development guide, including devcontainer setup.

```bash
make lint test    # run all checks
```

---

MIT © 2025 Erasmo Domínguez
