"""GitHub API client — authenticates as a GitHub App (JWT).

The server authenticates as a GitHub App and generates short-lived
installation access tokens on demand.  The installation_id that GitHub
includes in every webhook payload is what ties a request to a specific
repository, so no static token per-repo is needed.

Flow:
  1. Generate a signed JWT using the App's RSA private key.
  2. Exchange the JWT for an installation token (valid 1 hour).
  3. Use the installation token for all GitHub API calls in that request.

Private key sources (in order of preference):
  GITHUB_APP_PRIVATE_KEY_PATH — path to a .pem file (local / Docker mount)
  GITHUB_APP_PRIVATE_KEY      — raw PEM content (cloud envs, e.g. Azure secrets)
"""

#TODO if this is a Github client and if I want to follow a Hexagonal architecture, should be stored in a separate folder like clients or any other terminology used for hex

import time
from typing import Optional

import httpx
import jwt

from . import audit
from .config import GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, GITHUB_APP_PRIVATE_KEY_PATH

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_COMMON_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# The private key is loaded once and cached.  It never changes at runtime,
# so there is no need to reload it between requests.
