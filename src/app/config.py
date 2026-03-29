"""Application settings — all configuration is read from environment variables.

Every public symbol is typed. Defaults are chosen so the server starts in a
local development setup (OPA on localhost, no GitHub App, no DB path).
For production, every setting without a safe default is left as an empty string
so that missing config fails loudly at the first call site rather than silently.
"""
#TODO what is the best way to manage configuration in a hexagonal architecture? Should I have a separate config for each adapter (e.g. github_config, opa_config, audit_config) or is it acceptable to have a single config file with all settings?

import os
from pathlib import Path

# ── OPA sidecar ───────────────────────────────────────────────────────────────
# URL of the OPA REST API.  In Docker Compose this is the OPA service name;
# in a single-container setup you can run OPA as a sidecar on the same host.
OPA_URL: str = os.getenv("OPA_URL", "http://localhost:8181")

# ── Repo-level policy YAML files ─────────────────────────────────────────────
# Directory that holds deploy.yaml and pullrequest.yaml.  These are the policy
# configuration files that teams commit to their repository and mount into the
# container at runtime.
REPOL_DIR: Path = Path(os.getenv("REPOL_DIR", ".repol"))

# ── GitHub App authentication ─────────────────────────────────────────────────
# The server authenticates as a GitHub App to post Check Runs and call back
# deployment protection rules.  Supply GITHUB_APP_ID plus the private key in
# one of two forms:
#   GITHUB_APP_PRIVATE_KEY_PATH — path to a PEM file (local / Docker secret mount)
#   GITHUB_APP_PRIVATE_KEY      — raw PEM content as a single env var (cloud envs
#                                  where mounting files is inconvenient, e.g. Azure
#                                  Container Apps secrets)
# When both are set, GITHUB_APP_PRIVATE_KEY_PATH takes precedence.
GITHUB_APP_ID: str = os.getenv("GITHUB_APP_ID", "")
GITHUB_APP_PRIVATE_KEY_PATH: str = os.getenv("GITHUB_APP_PRIVATE_KEY_PATH", "")
GITHUB_APP_PRIVATE_KEY: str = os.getenv("GITHUB_APP_PRIVATE_KEY", "")

# ── Webhook signature verification ───────────────────────────────────────────
# GitHub signs every webhook payload with HMAC-SHA256 using this shared secret.
# Set the exact same value in your GitHub App → Webhook → Secret field.
# When left empty the server skips verification and logs a warning — acceptable
# for local development but MUST be set in production.
WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")

# ── Audit database ────────────────────────────────────────────────────────────
# SQLite file path.  Mount a persistent volume at this location so audit events
# survive container restarts.  Defaults to an in-memory path for local testing.
AUDIT_DB: str = os.getenv("AUDIT_DB", "/data/audit.db")

# ── Integration testing ───────────────────────────────────────────────────────
# Comma-separated GitHub logins to inject as extra approvers during integration
# testing.  GitHub prevents users from approving their own PRs, so this lets
# the repo owner bypass that restriction in a controlled test environment.
# Has absolutely no effect when empty — do not set in production.
_raw: str = os.getenv("PR_FORCE_APPROVERS", "")
PR_FORCE_APPROVERS: list[str] = [u.strip() for u in _raw.split(",") if u.strip()]
