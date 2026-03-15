"""GitHub API client — supports GitHub App (JWT) and PAT authentication.

When GITHUB_APP_ID + GITHUB_APP_PRIVATE_KEY_PATH are set the server
authenticates as a GitHub App, generating short-lived installation tokens
from the installation_id present in every webhook payload.

Falls back to a static GITHUB_TOKEN (PAT) if no App credentials are
configured.
"""

import logging
import time

import httpx
import jwt

from .config import GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY_PATH, GITHUB_TOKEN

logger = logging.getLogger("policy-server")

_GITHUB_API = "https://api.github.com"
_COMMON_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


# ── GitHub App JWT ────────────────────────────────────────────────────────────

_private_key: str | None = None


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


async def _auth_header(installation_id: int | None) -> dict[str, str]:
    """Return the Authorization header for a GitHub API call.

    Prefers GitHub App auth when configured; falls back to PAT.
    """
    if is_app_configured() and installation_id:
        token = await _get_installation_token(installation_id)
        return {"Authorization": f"token {token}"}

    if GITHUB_TOKEN:
        return {"Authorization": f"token {GITHUB_TOKEN}"}

    return {}


# ── Callback ──────────────────────────────────────────────────────────────────


async def github_callback(
    callback_url: str,
    allow: bool,
    violations: list,
    audit_id: str,
    *,
    installation_id: int | None = None,
):
    """POST back to GitHub deployment_callback_url to approve/reject.

    GitHub custom deployment protection rules require the app to call
    back asynchronously to signal the decision.

    Args:
        callback_url: The deployment_callback_url from the webhook payload.
        allow: Whether the policy allows the deployment.
        violations: List of violation dicts.
        audit_id: ID of the audit event for traceability.
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
        "environment_name": "",
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
        logger.info(
            "GitHub callback status=%d state=%s auth=%s",
            resp.status_code,
            state,
            "app" if is_app_configured() and installation_id else "token",
        )
    except Exception as exc:
        logger.error("GitHub callback failed: %s", exc)
