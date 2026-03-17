.DEFAULT_GOAL := help
SHELL         := /usr/bin/env bash
POLICIES_DIR  := policies
SCHEMAS_DIR   := schemas
BUNDLE_NAME   := gitpoli-policies.tar.gz

.PHONY: help check fmt test build clean validate-schemas

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' | sort

# ── Policy development ────────────────────────────────────────────────────────

check: ## Syntax-check all Rego files
	opa check $(POLICIES_DIR)/

fmt: ## Auto-format Rego files in-place
	opa fmt -w $(POLICIES_DIR)/

fmt-check: ## Check Rego formatting without modifying (CI mode)
	opa fmt --fail $(POLICIES_DIR)/

test: ## Run all OPA unit tests
	opa test $(POLICIES_DIR)/ --ignore "*.json" -v

test-coverage: ## Run tests with coverage
	opa test $(POLICIES_DIR)/ --ignore "*.json" --coverage -v

validate-schemas: ## Validate all policy JSON configs against their schemas
	./scripts/validate_schema.sh

lint: check fmt-check validate-schemas ## Run all linting checks (check + fmt + schema)

# ── Build ─────────────────────────────────────────────────────────────────────

build: test ## Build OPA bundle (runs tests first)
	opa build --bundle $(POLICIES_DIR)/ --output $(BUNDLE_NAME)
	@echo "Built $(BUNDLE_NAME)"
	@ls -lh $(BUNDLE_NAME)

clean: ## Remove build artifacts
	rm -f $(BUNDLE_NAME)
	find . -name "*.tar.gz" -not -path "./.git/*" -delete

# ── Evaluation helpers ────────────────────────────────────────────────────────

eval-deploy: ## Evaluate deploy policy with sample input
	@echo '{"environment":"production","ref":"refs/heads/main","repo_environments":["production","staging"],"workflow_meta":{"approvers":["alice","bob"],"checks":{"tests":true},"signed_off":true,"deployments_today":1},"repo_policy":{"policy":{"version":"1.0.0","environments":{"production":{"enabled":true,"rules":{"approvals_required":2,"allowed_branches":["main"],"tests_passed":true,"signed_off":true,"max_deployments_per_day":5}}}}}}' | \
	opa eval --data $(POLICIES_DIR)/ --input /dev/stdin --format pretty "data.github.deploy.allow"

eval-pr: ## Evaluate PR policy with sample input
	@echo '{"head_ref":"feature/login","base_ref":"develop","repo_policy":{"policy":{"version":"1.0","branch_rules":[{"source":"feature/*","target":"develop"},{"source":"feature/*","target":"main"}],"rules":{"allowed_target_branches":["main","develop"],"approvals_required":1,"signed_off":false}}},"workflow_meta":{"approvers":["erasmo"],"signed_off":false}}' | \
	opa eval --data $(POLICIES_DIR)/ --input /dev/stdin --format pretty "data.github.pullrequest.allow"

# ── Dev setup ─────────────────────────────────────────────────────────────────

install-opa: ## Install OPA CLI (macOS)
	brew install opa

install-check-jsonschema: ## Install check-jsonschema for full schema validation
	pip install check-jsonschema

# ── Local infrastructure ──────────────────────────────────────────────────────

local-up: ## Start local OPA + policy server (docker compose)
	docker compose -f infra/local/docker-compose.yml up -d --build

local-down: ## Stop local infrastructure
	docker compose -f infra/local/docker-compose.yml down

local-logs: ## Tail logs from local infrastructure
	docker compose -f infra/local/docker-compose.yml logs -f

local-test: ## Run integration tests against local infrastructure
	./infra/local/scripts/test.sh

local-build-runner: ## Build standalone OPA runner image with policies baked in
	docker build -t policy-opa -f infra/local/Dockerfile.opa .

# ── Integration environment (GitHub webhook testing) ──────────────────────────

integration-setup: ## Run interactive integration setup (smee channel, .env)
	bash infra/integration/scripts/setup.sh

integration-up: ## Start integration stack (OPA + server + smee tunnel)
	docker compose -f infra/integration/docker-compose.yml up -d --build

integration-down: ## Stop integration stack
	docker compose -f infra/integration/docker-compose.yml down

integration-logs: ## Tail logs from integration stack
	docker compose -f infra/integration/docker-compose.yml logs -f

integration-audit: ## Query audit events from integration server
	@curl -sf http://localhost:8080/audit | python3 -m json.tool

# ── Azure-like integration environment ───────────────────────────────────────

az-integration-up: ## Start Azure-like integration stack (Cosmos, OPA, Functions, smee)
	docker compose -f infra/az-integration/docker-compose.yml up -d --build

az-integration-down: ## Stop Azure-like integration stack
	docker compose -f infra/az-integration/docker-compose.yml down

az-integration-logs: ## Tail logs from Azure-like integration stack
	docker compose -f infra/az-integration/docker-compose.yml logs -f

az-integration-test: ## Run integration tests against Azure-like stack
	bash infra/az-integration/scripts/test.sh
