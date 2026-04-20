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

import logging
import time
from pathlib import Path
from typing import Optional

import httpx
import jwt

from .config import GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, GITHUB_APP_PRIVATE_KEY_PATH

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_COMMON_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# The private key is loaded once and cached.  It never changes at runtime,
# so there is no need to reload it between requests.
_PRIVATE_KEY_CACHE: Optional[str] = None


def _load_private_key() -> str:
    global _PRIVATE_KEY_CACHE
    if _PRIVATE_KEY_CACHE:
        return _PRIVATE_KEY_CACHE

    if GITHUB_APP_PRIVATE_KEY_PATH:
        key_path = Path(GITHUB_APP_PRIVATE_KEY_PATH)
        if key_path.is_file():
            _PRIVATE_KEY_CACHE = key_path.read_text(encoding="utf-8")
            return _PRIVATE_KEY_CACHE
        raise RuntimeError(f"GITHUB_APP_PRIVATE_KEY_PATH does not exist: {key_path}")

    if GITHUB_APP_PRIVATE_KEY:
        _PRIVATE_KEY_CACHE = GITHUB_APP_PRIVATE_KEY
        return _PRIVATE_KEY_CACHE

    raise RuntimeError(
        "GitHub App private key not configured. "
        "Set GITHUB_APP_PRIVATE_KEY_PATH or GITHUB_APP_PRIVATE_KEY."
    )


def _app_jwt() -> str:
    if not GITHUB_APP_ID:
        raise RuntimeError("GITHUB_APP_ID is required for GitHub App API calls.")

    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 540, "iss": str(GITHUB_APP_ID)}
    return jwt.encode(payload, _load_private_key(), algorithm="RS256")


async def _installation_token(installation_id: Optional[int]) -> str:
    if not installation_id:
        raise RuntimeError("installation_id is required for GitHub App API calls.")

    token_url = f"{_GITHUB_API}/app/installations/{installation_id}/access_tokens"
    headers = {**_COMMON_HEADERS, "Authorization": f"Bearer {_app_jwt()}"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(token_url, headers=headers)

    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Unable to mint installation token for {installation_id}: "
            f"{resp.status_code} {resp.text}"
        )
    return resp.json()["token"]


def _check_run_payload(allow: bool, violations: list, audit_id: str, head_sha: str) -> dict:
    conclusion = "success" if allow else "failure"
    title = "Policy passed" if allow else "Policy violations found"
    if violations:
        summary = "\n".join(f"- `{v.get('code', 'unknown')}`: {v.get('msg', '')}" for v in violations)
    else:
        summary = "No violations."
    summary = f"{summary}\n\nAudit ID: `{audit_id}`"

    return {
        "name": "gitpoli / PR Policy",
        "head_sha": head_sha,
        "status": "completed",
        "conclusion": conclusion,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "output": {"title": title, "summary": summary},
    }


async def get_pr_approvers(repo_full_name: str, pr_number: int, installation_id: int) -> list[str]:
    """Return unique GitHub logins that approved a pull request."""
    token = await _installation_token(installation_id)
    url = f"{_GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}/reviews"
    headers = {**_COMMON_HEADERS, "Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url, headers=headers)

    if resp.status_code != 200:
        logger.warning(
            "Could not fetch PR reviews for %s#%s: %s %s",
            repo_full_name,
            pr_number,
            resp.status_code,
            resp.text,
        )
        return []

    approvers: set[str] = set()
    for review in resp.json():
        if review.get("state") == "APPROVED":
            login = (review.get("user") or {}).get("login")
            if login:
                approvers.add(login)
    return sorted(approvers)


async def github_callback(
    callback_url: str,
    allow: bool,
    violations: list,
    audit_id: str,
    environment_name: str = "",
    installation_id: Optional[int] = None,
) -> None:
    """Send deployment protection callback result to GitHub."""
    state = "approved" if allow else "rejected"
    desc = "Policy passed"
    if violations:
        first = violations[0]
        desc = f"{first.get('code', 'policy_violation')}: {first.get('msg', '')}"[:140]

    payload = {
        "state": state,
        "comment": f"{desc} (audit: {audit_id})",
        "environment_name": environment_name or None,
    }
    headers = dict(_COMMON_HEADERS)

    if installation_id:
        token = await _installation_token(installation_id)
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(callback_url, headers=headers, json=payload)

    if resp.status_code not in (200, 204):
        logger.warning(
            "GitHub callback failed: %s %s %s",
            resp.status_code,
            callback_url,
            resp.text,
        )


async def github_check_run(
    repo_full_name: str,
    head_sha: str,
    allow: bool,
    violations: list,
    audit_id: str,
    installation_id: Optional[int] = None,
) -> None:
    """Create a completed Check Run on a pull request commit."""
    if not installation_id:
        logger.warning("Missing installation_id: cannot post check run.")
        return

    token = await _installation_token(installation_id)
    url = f"{_GITHUB_API}/repos/{repo_full_name}/check-runs"
    headers = {**_COMMON_HEADERS, "Authorization": f"Bearer {token}"}
    payload = _check_run_payload(allow=allow, violations=violations, audit_id=audit_id, head_sha=head_sha)

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, headers=headers, json=payload)

    if resp.status_code not in (200, 201):
        logger.warning(
            "GitHub check-run failed for %s@%s: %s %s",
            repo_full_name,
            head_sha,
            resp.status_code,
            resp.text,
        )
