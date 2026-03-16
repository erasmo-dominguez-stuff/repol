# Contributing to gitpoli

## Development environment (devcontainer)

The recommended way to develop is using the **Dev Container** included in the repository.
It provides a fully configured environment with all required tools pre-installed.

### What's included

| Tool | Version | Source |
|------|---------|--------|
| Python | 3.11 | devcontainer feature |
| OPA | latest | devcontainer feature |
| Docker + Compose v2 | latest | docker-in-docker feature |
| pre-commit | ≥ 3.5 | `pip install -e '.[dev]'` |
| VS Code extensions | OPA, Python, Pylance, Docker, YAML, GitHub Actions | auto-installed |

### Getting started with the devcontainer

1. Open the repo in VS Code
2. When prompted, click **Reopen in Container** (or run `Dev Containers: Reopen in Container` from the command palette)
3. Wait for the container to build — `postCreateCommand` will install dependencies and set up pre-commit hooks automatically
4. You're ready:

```bash
make lint test
```

> **Note:** Docker-in-Docker is enabled, so you can run `make local-up` and `make integration-up` directly from inside the devcontainer.

## Manual setup (without devcontainer)

If you prefer working outside the devcontainer, install the prerequisites manually:

| Tool | Install |
|------|---------|
| [OPA](https://www.openpolicyagent.org/) ≥ 1.9 | `brew install opa` or `make install-opa` |
| Python ≥ 3.11 | system / pyenv |
| Docker + Compose v2 | [Docker Desktop](https://www.docker.com/products/docker-desktop/) |
| [pre-commit](https://pre-commit.com/) | `pip install pre-commit` |

```bash
git clone https://github.com/erasmo-dominguez-stuff/gitpoli.git
cd gitpoli

pip install -e ".[dev]"
pre-commit install

make lint test
```

## Project layout

```
.devcontainer/           # Dev Container configuration
.github/
  actions/eval-policy/   # Composite action for CI
  workflows/             # CI/CD workflows
.repol/                  # Policy YAML configs (teams edit these)
  pullrequest.yaml       # PR validation rules + branch naming
  deploy.yaml            # Deployment protection rules per environment
infra/
  local/                 # Local testing (Docker Compose: OPA + server)
  integration/           # Integration testing with real GitHub webhooks
  server/                # Shared FastAPI server (used by local + integration)
    app/                 # Modular app package (routers, OPA client, audit, GitHub auth)
  smee/                  # smee.io relay container (webhook tunnel)
policies/
  lib/helpers.rego       # Shared helper functions
  pullrequest.rego       # PR policy (Rego)
  deploy.rego            # Deploy policy (Rego)
  tests/                 # OPA unit tests
schemas/                 # JSON Schemas that validate .repol/ files
scripts/                 # Utility scripts (schema validation)
```

## Development workflow

### 1. Write / edit policies

Policies live in `policies/` as Rego v1 files. Shared helpers go in `policies/lib/helpers.rego`.

### 2. Write tests

Tests live in `policies/tests/`. Run them with:

```bash
make test           # verbose
make test-coverage  # with coverage report
```

### 3. Edit policy configs

Team-facing YAML configurations live in `.repol/`. After editing, validate them against the JSON Schemas:

```bash
make validate-schemas
```

### 4. Run all checks

```bash
make lint    # opa check + opa fmt --fail + schema validation
```

### 5. Pre-commit hooks

Pre-commit runs automatically on `git commit`. To run manually:

```bash
pre-commit run --all-files
```

The hooks enforce:
- Rego syntax check (`opa check`)
- Rego formatting (`opa fmt`)
- YAML schema validation
- Trailing whitespace / EOF fixes
- YAML lint

## Testing with Docker

### Local testing

Run the policy server and OPA locally to test evaluations without GitHub:

```bash
make local-up       # Start OPA + policy server
make local-test     # Run integration tests against the local stack
make local-logs     # Tail logs
make local-down     # Stop services
```

### Integration testing (real GitHub webhooks)

Test end-to-end with actual GitHub `deployment_protection_rule` events via a smee.io tunnel:

```bash
make integration-setup   # Interactive setup (smee channel, GitHub App creds)
make integration-up      # Start OPA + server + smee tunnel
make integration-logs    # Tail logs
make integration-audit   # Query audit events
make integration-down    # Stop services
```

See [infra/integration/README.md](infra/integration/README.md) for full setup details.

## Commit conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add rate limit rule to deploy policy
fix: correct glob matching for nested branches
test: add branch naming edge cases
docs: update CONTRIBUTING with pre-commit setup
chore: bump OPA to 1.10
```

## Branch naming

Follow the branch rules defined in `.repol/pullrequest.yaml`:

| Source | Target |
|--------|--------|
| `feature/*` | `develop`, `main` |
| `bugfix/*` | `develop`, `main` |
| `hotfix/*` | `main`, `release/*` |
| `release/*` | `main` |
| `develop` | `main` |

## Adding a new policy

1. Create `policies/<name>.rego` with package `github.<name>`
2. Import `data.lib.helpers` for shared functions
3. Add tests in `policies/tests/<name>_test.rego`
4. If the policy needs a config file, create `.repol/<name>.yaml` and a matching schema in `schemas/`
5. Update `scripts/validate_schema.sh` with the new mapping
6. Run `make lint test` to verify
