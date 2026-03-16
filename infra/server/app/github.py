"""GitHub API client — authenticates as a GitHub App (JWT).

Requires GITHUB_APP_ID + GITHUB_APP_PRIVATE_KEY_PATH.  The server
generates short-lived installation tokens from the installation_id
present in every webhook payload.
"""

import logging
import time
from typing import Optional

import httpx
import jwt

from .config import GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY_PATH
from . import audit

logger = logging.getLogger("policy-server")

_GITHUB_API = "https://api.github.com"
_COMMON_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


# ── GitHub App JWT ────────────────────────────────────────────────────────────

_private_key: Optional[str] = None


def _load_private_key() -> str:
    """Read the PEM private key from disk (cached after first call)."""
    global _private_key
    if _private_key is None:
        with open(GITHUB_APP_PRIVATE_KEY_PATH) as f:
            _private_key = f.read()
    return _private_key


def _generate_jwt() -> str:
    """Create a short-lived JWT signed with the App's private key."""
    now = int(time.time())
    payload = {
        "iat": now - 60,  # clock drift margin
        "exp": now + (10 * 60),  # 10 min max
        "iss": GITHUB_APP_ID,
    }
    return jwt.encode(payload, _load_private_key(), algorithm="RS256")


async def _get_installation_token(installation_id: int) -> str:
    """Exchange the App JWT for a scoped installation access token."""
    url = f"{_GITHUB_API}/app/installations/{installation_id}/access_tokens"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            url,
            headers={**_COMMON_HEADERS, "Authorization": f"Bearer {_generate_jwt()}"},
        )
    resp.raise_for_status()
    return resp.json()["token"]


def is_app_configured() -> bool:
    """True when GitHub App credentials are available."""
    return bool(GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY_PATH)


# ── Resolve auth header ──────────────────────────────────────────────────────


async def _auth_header(installation_id: Optional[int]) -> dict:
    """Return the Authorization header for a GitHub API call."""
    if not is_app_configured():
        logger.error("GitHub App not configured (GITHUB_APP_ID / GITHUB_APP_PRIVATE_KEY_PATH)")
        return {}
    if not installation_id:
        logger.error("No installation_id in webhook payload — cannot authenticate")
        return {}
    token = await _get_installation_token(installation_id)
    return {"Authorization": f"token {token}"}


# ── Callback ──────────────────────────────────────────────────────────────────


async def github_callback(
    callback_url: str,
    allow: bool,
    violations: list,
    audit_id: str,
    *,
    environment_name: str = "",
    installation_id: Optional[int] = None,
):
    """POST back to GitHub deployment_callback_url to approve/reject.

    GitHub custom deployment protection rules require the app to call
    back asynchronously to signal the decision.

    Args:
        callback_url: The deployment_callback_url from the webhook payload.
        allow: Whether the policy allows the deployment.
        violations: List of violation dicts.
        audit_id: ID of the audit event for traceability.
        environment_name: GitHub environment name (required by the API).
        installation_id: GitHub App installation ID (from webhook payload).
    """
    if not callback_url:
        logger.debug("No callback URL — skipping GitHub callback")
        return

    auth = await _auth_header(installation_id)
    if not auth:
        logger.warning("No GitHub credentials configured — cannot call back")
        return

    state = "approved" if allow else "rejected"
    comment_parts = [f"Policy decision: **{state}** (audit_id: `{audit_id}`)"]
    if violations:
        codes = ", ".join(v.get("code", "?") for v in violations)
        comment_parts.append(f"Violations: {codes}")

    payload = {
        "environment_name": environment_name,
        "state": state,
        "comment": ". ".join(comment_parts),
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                callback_url,
                json=payload,
                headers={**_COMMON_HEADERS, **auth},
            )
        if resp.status_code >= 400:
            logger.warning(
                "GitHub callback error status=%d body=%s",
                resp.status_code,
                resp.text[:500],
            )
        logger.info(
            "GitHub callback status=%d state=%s env=%s auth=%s",
            resp.status_code,
            state,
            environment_name,
            "app" if installation_id else "none",
        )
        audit.update_callback(audit_id, status_code=resp.status_code, state=state)
    except Exception as exc:
        logger.error("GitHub callback failed: %s", exc)
        audit.update_callback(audit_id, status_code=0, state=f"error: {exc}")


# ── Check Run (PR policy result) ──────────────────────────────────────────────


async def github_check_run(
    *,
    repo_full_name: str,
    head_sha: str,
    allow: bool,
    violations: list,
    audit_id: str,
    installation_id: Optional[int],
):
    """Create or update a GitHub Check Run with the PR policy result.

    The check run name 'gitpoli / PR Policy' must be added as a required
    status check in branch protection rules to block merging on deny.
    """
    auth = await _auth_header(installation_id)
    if not auth:
        logger.warning("No GitHub credentials — cannot post check run")
        return

    conclusion = "success" if allow else "failure"
    title = "Policy passed" if allow else "Policy violations found"

    if violations:
        codes = ", ".join(v.get("code", "?") for v in violations)
        summary = f"**Violations:** {codes}\n\n*audit_id: `{audit_id}`*"
    else:
        summary = f"All policy rules passed. *audit_id: `{audit_id}`*"

    payload = {
        "name": "gitpoli / PR Policy",
        "head_sha": head_sha,
        "status": "completed",
        "conclusion": conclusion,
        "output": {
            "title": title,
            "summary": summary,
        },
    }

    url = f"{_GITHUB_API}/repos/{repo_full_name}/check-runs"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    **_COMMON_HEADERS,
                    **auth,
                    "Accept": "application/vnd.github+json",
                },
            )
        if resp.status_code >= 400:
            logger.warning(
                "Check run error status=%d body=%s",
                resp.status_code,
                resp.text[:500],
            )
        logger.info(
            "Check run posted status=%d conclusion=%s sha=%s",
            resp.status_code,
            conclusion,
            head_sha[:8],
        )
    except Exception as exc:
        logger.error("Check run failed: %s", exc)


async def get_pr_approvers(
    *,
    repo_full_name: str,
    pr_number: int,
    installation_id: Optional[int],
) -> list[str]:
    """Fetch the list of GitHub logins who approved a PR."""
    auth = await _auth_header(installation_id)
    if not auth:
        return []

    url = f"{_GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}/reviews"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={**_COMMON_HEADERS, **auth})
        if resp.status_code != 200:
            return []
        reviews = resp.json()
        seen: set[str] = set()
        approvers = []
        for r in reviews:
            if r.get("state") == "APPROVED":
                login = r.get("user", {}).get("login", "")
                if login and login not in seen:
                    seen.add(login)
                    approvers.append(login)
        return approvers
    except Exception as exc:
        logger.error("Failed to fetch PR approvers: %s", exc)
        return []
