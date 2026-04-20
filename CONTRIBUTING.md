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
# Contributing


## Development Guide & Extensibility

- Use devcontainer for consistent environment
- Run `make lint test` before pushing
- Policies live in `.repol/` and `policies/`
- API and webhook logic in `src/app/routers/`
- Policy evaluation logic in `src/app/handlers/` (each handler in its own module)
- **Adapters for all variable backends live in `src/app/adapters/` (e.g. `sqlite_audit_trail.py`, `cosmos_audit_trail.py`).**
- **All contracts/interfaces are in `src/app/core/` (e.g. `AuditTrail`, `Config`, `PolicyEvaluator`).**
- **Factories (e.g. `audit.py`) select the correct adapter based on environment variables.**

### Adapter/Factory Pattern

- `audit.py` is a pure factory, not an implementation. It injects the correct adapter everywhere.
- To add a new backend, create a new adapter in `adapters/` and update the factory to support it.
- All code uses the interface (`AuditTrail`), never the concrete class directly.

### How to Extend

**Add a new backend:**
1. Create a new adapter in `src/app/adapters/` implementing the relevant interface from `core/`.
2. Update the factory (e.g. `audit.py`) to select your adapter based on an environment variable.

**Add a new policy handler:**
1. Create a new handler in `src/app/handlers/` and register it in the handler registry.
2. See the extensibility section and example code below.

This pattern ensures the codebase is modular, testable, and easy to extend for new backends or policies.

## Adding a New Policy (SOLID/Hexagonal Architecture)

1. Create a handler module in `src/app/handlers/` (e.g. `my_policy.py`).
2. Implement a handler class or function:
   ```python
   from ..handlers import register_handler
   class MyPolicyHandler:
     async def __call__(self, request, event):
       # Normalize input, use PolicyEvaluator and AuditTrail
       policy_evaluator = request.app.state.policy_evaluator
       audit_trail = request.app.state.audit_trail
       result = await policy_evaluator.evaluate("my/policy", input_data)
       audit_id = audit_trail.record("my_policy", result, input_data, {"source": "webhook"})
       return {"allow": result.get("allow", False), "violations": result.get("violations", []), "audit_id": audit_id}
   handler = MyPolicyHandler()
   register_handler("my_policy_event", handler)
   ```
3. Register the handler explicitly in the registry.
4. Add your policy logic in `policies/` (Rego) and `.repol/` config if applicable.
5. Add tests in `tests/` for handler, registry, and adapters.

## Best Practices

- Use interfaces (core/) and adapters (adapters/) to decouple logic.
- Do not mix generic helpers in handlers; use dedicated classes or modules.
- Document your handler and register the event explicitly.
- Add unit tests for every critical component.
- If you need helpers, create modules/classes in `core/` or `adapters/` according to responsibility.

## Example: Adding a Policy for ADO

1. Create `handlers/ado_policy.py`.
2. Implement the handler class:
   ```python
   from ..handlers import register_handler
   class ADOHandler:
     async def __call__(self, request, event):
       # Normalization, evaluation, audit
       ...
   handler = ADOHandler()
   register_handler("ado_event", handler)
   ```
3. Add adapter for ADO integration in `adapters/` if needed.
4. Add tests in `tests/`.

---

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
