"""Application settings from environment variables."""

import os
from pathlib import Path

OPA_URL = os.getenv("OPA_URL", "http://localhost:8181")
REPOL_DIR = Path(os.getenv("REPOL_DIR", ".repol"))

# ── GitHub authentication ─────────────────────────────────────────────────────
# Option A (recommended): GitHub App — set APP_ID + PRIVATE_KEY_PATH.
#   The installation_id is extracted from each webhook payload automatically.
# Option B (fallback):    Personal access token — set GITHUB_TOKEN.

GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "")
GITHUB_APP_PRIVATE_KEY_PATH = os.getenv("GITHUB_APP_PRIVATE_KEY_PATH", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
