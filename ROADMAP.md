# 🗺️ Strategic Technical Roadmap: `gitpoli` - Governance Control Plane

**Product Vision:** To build an agnostic, open-source "Policy-as-Code" platform that enforces enterprise compliance frameworks (SOC2, PCI-DSS) across any Git ecosystem (GitHub, GitLab, Azure DevOps), prioritizing a frictionless "Shift-Left" developer experience.

---

## 🏗️ Phase 1: Foundation & Shift-Left Developer Experience (CLI)
*As agreed, we prioritize the local developer experience and the metadata standardization to make `gitpoli` a daily-use tool before scaling the backend abstractions.*

### Feature 1.1: Standardized Repository Metadata (`project.yaml`)
*   **Description:** A canonical file acting as the source of truth for the repository's identity, criticality, and compliance requirements.
*   **Implementation Steps:**
    1.  Create `schemas/gitpoli_project_schema.json` using JSON Schema Draft-07. Include required fields: `metadata` (name, owner), `classification` (tier: 1-4, data_sensitivity: high/medium/low), and `compliance` (frameworks array).
    2.  Update `scripts/validate_schema.sh` to validate `.repol/project.yaml` against this new schema.
    3.  Update the FastAPI backend (`src/app/handlers/pull_request.py` and `deploy.py`) to parse `.repol/project.yaml` using `yaml.safe_load()` and inject it into the `opa_input["project_meta"]` payload.
    4.  Update Rego policies (`policies/pullrequest.rego`) to read `input.project_meta.classification.tier` to enforce dynamic rules (e.g., Tier 1 requires 2 approvers).

### Feature 1.2: `gitpoli-cli` Scaffolding & Initialization
*   **Description:** A standalone Python CLI tool for developers to interact with the framework locally.
*   **Implementation Steps:**
    1.  Create a `cli/` directory with a `pyproject.toml` configuring `typer`, `rich`, and `pyyaml` as dependencies. Set the entry point to `gitpoli = "gitpoli_cli.main:app"`.
    2.  Implement the `gitpoli init` command: Checks for the `.repol/` directory. If missing, it scaffolds it and generates a boilerplate `project.yaml` and `pullrequest.yaml` based on interactive prompts.

### Feature 1.3: Local Policy Evaluation (`check-pr`)
*   **Description:** Simulates the server-side PR evaluation directly on the developer's machine without making network calls.
*   **Implementation Steps:**
    1.  Implement the `gitpoli check-pr --base <branch>` command.
    2.  Use Python's `subprocess` to execute `git rev-parse --abbrev-ref HEAD` to extract the current local branch.
    3.  Build a mock JSON payload in memory that matches the structure expected by OPA, injecting the local `.repol/project.yaml` and branch data.
    4.  Use `subprocess` to execute the local OPA binary: `opa eval --data <path-to-policies> --input <mock-json> "data.github.pullrequest"`.
    5.  Parse the OPA JSON output and render violations using a `rich.table.Table`. If blocking violations exist, exit with code `1`.

---

## 🔌 Phase 2: Platform Agnosticism (The Core Abstraction)
*Once the CLI and metadata are solid, decouple the FastAPI backend from GitHub-specific webhook payloads to support GitLab and Azure DevOps.*

### Feature 2.1: Standardized Internal Event Schema
*   **Description:** A canonical internal data model that represents Git events regardless of their origin.
*   **Implementation Steps:**
    1.  Use `pydantic` in `src/app/core/models.py` to define `NormalizedPREvent` and `NormalizedDeployEvent`.
    2.  Define universal attributes: `repository_id`, `actor` (username), `source_ref`, `target_ref`, and `approval_status`.
    3.  Refactor all Rego policies to evaluate this normalized Pydantic JSON dump instead of the raw GitHub webhook payload.

### Feature 2.2: Inbound Webhook Adapters (Gateway Pattern)
*   **Description:** Translation layers converting provider-specific webhooks into the normalized schema.
*   **Implementation Steps:**
    1.  Define an abstract base class `InboundAdapter` in `src/app/adapters/inbound/base.py`.
    2.  Move current GitHub logic into `src/app/adapters/inbound/github.py`.
    3.  Develop `src/app/adapters/inbound/gitlab.py` to parse GitLab Merge Request and Pipeline webhooks.
    4.  Update FastAPI routing: Create endpoints like `/webhook/{provider}`. A factory pattern will instantiate the correct adapter based on the path parameter, parse the payload, and pass the normalized data to the `PolicyEvaluator`.

### Feature 2.3: Outbound Action Dispatchers
*   **Description:** An abstract interface to communicate decisions (Block, Approve, Comment) back to the origin platform.
*   **Implementation Steps:**
    1.  Create an interface `PlatformEnforcer` in `src/app/adapters/outbound/base.py`.
    2.  Implement methods: `post_status_check()`, `block_deployment()`, and `add_pr_comment()`.
    3.  Implement the `GitHubEnforcer` (wrapping the GitHub Apps API) and prepare the skeleton for `GitLabEnforcer` (wrapping GitLab's Commit Status API).

---

## 🧠 Phase 3: Context Providers (External Enrichment)
*Allow policies to make decisions based on data that does not live inside the Git repository (e.g., Jira, Active Directory).*

### Feature 3.1: Extensible Fetcher Architecture
*   **Description:** A middleware layer intercepting the normalized payload to enrich it before it reaches OPA.
*   **Implementation Steps:**
    1.  Create a `ContextHydrator` pipeline in `src/app/core/context.py`.
    2.  Define an interface where multiple "Fetchers" can asynchronously append data to the payload under a `context` key before invoking OPA.

### Feature 3.2: ITSM Integration (Jira / ServiceNow)
*   **Description:** Tie code deployments to approved change management tickets.
*   **Implementation Steps:**
    1.  Write a Jira Fetcher that uses RegEx to extract a Jira Ticket ID from the PR branch name (e.g., `feature/PROJ-123`).
    2.  Perform an authenticated HTTP GET to the Jira REST API to retrieve the ticket status.
    3.  Inject `{"jira": {"status": "Approved", "id": "PROJ-123"}}` into the OPA input.
    4.  Write Rego rules to block deployments if `input.context.jira.status != "Approved"`.

---

## 📊 Phase 4: Visibility & Audit (The Control Panel)
*Provide actionable insights and compliance evidence for Security and Audit teams.*

### Feature 4.1: Advanced Audit API
*   **Description:** Expose the audit trail data (SQLite/CosmosDB) for external consumption.
*   **Implementation Steps:**
    1.  Create `src/app/routers/audit_api.py`.
    2.  Implement GET endpoints with filtering capabilities (by timeframe, repository, framework, and outcome).
    3.  Create an aggregation endpoint `/api/v1/metrics/compliance-score` to calculate the percentage of successful policy evaluations per repository.

### Feature 4.2: Exception Management Workflow
*   **Description:** Allow administrators to temporarily bypass a rule (Risk Acceptance) with a strict audit trail.
*   **Implementation Steps:**
    1.  Create a database table `policy_exceptions` tracking `repo_id`, `rule_code`, `approved_by`, `reason`, and `expires_at`.
    2.  Modify the FastAPI `PolicyEvaluator` to check this table. If an OPA violation matches an active exception, suppress the violation and allow the action, but log it as "Conditionally Approved via Exception".

---

## 📦 Phase 5: Policy Registry ("Batteries Included")
*Lower the barrier to entry by providing pre-written, auditor-approved compliance policies.*

### Feature 5.1: Centralized Rules Repository
*   **Description:** A public standard library of Rego policies.
*   **Implementation Steps:**
    1.  Create a new GitHub repository: `gitpoli-rules-registry`.
    2.  Structure policies by framework: `frameworks/soc2/`, `frameworks/pci-dss/`, and `best-practices/gitflow/`.
    3.  Set up GitHub Actions in the registry repo to compile the `.rego` files into OPA bundles (`.tar.gz`) on every release.

### Feature 5.2: Dynamic Bundle Resolution
*   **Description:** Auto-download policies based on the `project.yaml` declarations.
*   **Implementation Steps:**
    1.  If a `.repol/project.yaml` declares `compliance: frameworks: ["soc2"]`, the `gitpoli` server will utilize OPA's native **Bundle API** to dynamically download the compiled bundle from the registry.
    2.  Update the CLI so `gitpoli check-pr` can also fetch remote bundles and cache them locally in `~/.gitpoli/cache/` before evaluating.

---

## 🚀 Phase 6: Active Pipeline Enforcement (The "GitLab" Mode)
*Replicate GitLab's ability to force the execution of security pipelines, preventing developers from bypassing required CI jobs.*

### Feature 6.1: Passive Workflow Auditing
*   **Description:** Validate that the developer hasn't tampered with required security checks.
*   **Implementation Steps:**
    1.  Write a Rego policy that fetches the `.github/workflows/security.yml` file content via the platform's API during a PR event.
    2.  Parse the YAML within Rego and assert that the mandatory `sast_scan` job exists and hasn't been modified. Reject the PR if tampered with.

### Feature 6.2: Active CI Injection (Remote Triggering)
*   **Description:** Launch centralized security pipelines controlled by the Security Team from the `gitpoli` server.
*   **Implementation Steps:**
    1.  Upon receiving a webhook for a new commit, `gitpoli` uses the platform API (e.g., GitHub Actions `workflow_dispatch`) to trigger a pipeline in a central, locked-down repository (e.g., `org-security/compliance-scans`).
    2.  `gitpoli` passes the target repository's URL and Git SHA as inputs to this central pipeline.
    3.  `gitpoli` posts a "Pending" status check on the developer's PR. The PR cannot be merged until the central pipeline finishes and sends a success webhook back to `gitpoli`.