"""GitHub webhook endpoints.

Handles incoming GitHub webhook events, transforms the payload into
the OPA input format, evaluates the policy, and (for deploy) calls
back to GitHub to approve/reject.

Provides both:
  - POST /webhook  — single entrypoint (routes by X-GitHub-Event header)
  - POST /webhook/deployment_protection_rule  — direct endpoint
  - POST /webhook/pull_request               — direct endpoint
"""

import yaml
from fastapi import APIRouter, HTTPException, Request

from ..config import REPOL_DIR
from ..github import get_pr_approvers, github_callback, github_check_run
from ..helpers import record_audit
from ..opa import query_opa

router = APIRouter(prefix="/webhook", tags=["webhook"])


# ── Webhook-specific helpers ──────────────────────────────────────────────────


def _load_yaml(name: str) -> dict:
    """Load a YAML policy file from REPOL_DIR."""
    path = REPOL_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=500, detail=f"Policy file not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


def _csv_header(request: Request, name: str) -> list[str]:
    """Parse a comma-separated header into a trimmed list."""
    raw = request.headers.get(name, "")
    return [v.strip() for v in raw.split(",") if v.strip()] if raw else []


def _bool_header(request: Request, name: str, default: bool = False) -> bool:
    return request.headers.get(name, str(default)).lower() == "true"


def _int_header(request: Request, name: str, default: int = 0) -> int:
    try:
        return int(request.headers.get(name, str(default)))
    except ValueError:
        return default


# ── Dispatch (single entrypoint for real GitHub webhooks) ─────────────────────


@router.post("")
async def webhook_dispatch(request: Request):
    """Route incoming GitHub webhooks by X-GitHub-Event header.

    This is the target URL you configure in GitHub / smee-client.
    It reads the event type from the header and delegates to the
    appropriate handler.
    """
    event_type = request.headers.get("X-GitHub-Event", "")
    body = await request.json()

    if event_type == "deployment_protection_rule":
        return await _handle_deploy(request, body)
    if event_type == "deployment":
        return await _handle_deploy(request, body)
    if event_type in ("pull_request", "pull_request_review"):
        return await _handle_pr(request, body)

    # Acknowledge events we don't act on (ping, workflow_run, etc.)
    return {"event": event_type, "action": "ignored"}


# ── Deployment protection rule ────────────────────────────────────────────────


@router.post("/deployment_protection_rule")
async def webhook_deploy(request: Request):
    """Handle deployment_protection_rule event (direct endpoint)."""
    body = await request.json()
    return await _handle_deploy(request, body)


async def _handle_deploy(request: Request, event: dict) -> dict:
    """Core logic for deployment policy evaluation.

    Supports two GitHub event shapes:
      - deployment_protection_rule: has event["deployment"]["ref"] and
        event["deployment_callback_url"]
      - deployment: has event["deployment"]["ref"] and
        event["deployment"]["environment"]

    Optional headers for workflow metadata not present in the webhook:
      X-Approvers            comma-separated logins
      X-Tests-Passed         true / false
      X-Signed-Off           true / false
      X-Deployments-Today    integer
    """
    deployment = event.get("deployment", {})
    environment = event.get("environment") or deployment.get("environment", "")
    ref = deployment.get("ref", "")
    if ref and not ref.startswith("refs/"):
        ref = f"refs/heads/{ref}"

    callback_url = event.get("deployment_callback_url", "")
    installation_id = (event.get("installation") or {}).get("id")

    repo_policy = _load_yaml("deploy.yaml")
    env_names = list(repo_policy.get("policy", {}).get("environments", {}).keys())

    opa_input = {
        "environment": environment,
        "ref": ref,
        "repo_environments": env_names,
        "workflow_meta": {
            "approvers": _csv_header(request, "X-Approvers"),
            "checks": {"tests": _bool_header(request, "X-Tests-Passed")},
            "signed_off": _bool_header(request, "X-Signed-Off"),
            "deployments_today": _int_header(request, "X-Deployments-Today"),
        },
        "repo_policy": repo_policy,
    }

    result = await query_opa("github/deploy", opa_input)
    resp = record_audit("deploy", result, opa_input, request, source="webhook")
    resp["input"] = opa_input

    if callback_url:
        await github_callback(
            callback_url,
            resp["allow"],
            resp["violations"],
            resp["audit_id"],
            environment_name=environment,
            installation_id=installation_id,
        )
        resp["callback_url"] = callback_url
        resp["callback_sent"] = True

    return resp


# ── Pull request ──────────────────────────────────────────────────────────────


@router.post("/pull_request")
async def webhook_pr(request: Request):
    """Handle pull_request event (direct endpoint)."""
    body = await request.json()
    return await _handle_pr(request, body)


async def _handle_pr(request: Request, event: dict) -> dict:
    """Core logic for pull request policy evaluation.

    Handles both pull_request and pull_request_review events.
    Fetches the list of PR approvers from the GitHub API and posts
    a Check Run with the policy result.

    Optional override headers (for local testing without a real GitHub App):
      X-Approvers    comma-separated logins
      X-Signed-Off   true / false
    """
    pr = event.get("pull_request", event)
    head_ref = pr.get("head", {}).get("ref", pr.get("head_ref", ""))
    base_ref = pr.get("base", {}).get("ref", pr.get("base_ref", ""))
    head_sha = pr.get("head", {}).get("sha", "")
    pr_number = pr.get("number", 0)
    repo_full_name = (event.get("repository") or {}).get("full_name", "")
    installation_id = (event.get("installation") or {}).get("id")

    # Prefer real approvers from GitHub API; fall back to X-Approvers header
    if installation_id and repo_full_name and pr_number:
        approvers = await get_pr_approvers(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            installation_id=installation_id,
        )
    else:
        approvers = _csv_header(request, "X-Approvers")

    repo_policy = _load_yaml("pullrequest.yaml")

    opa_input = {
        "head_ref": head_ref,
        "base_ref": base_ref,
        "workflow_meta": {
            "approvers": approvers,
            "signed_off": _bool_header(request, "X-Signed-Off"),
        },
        "repo_policy": repo_policy,
    }

    result = await query_opa("github/pullrequest", opa_input)
    resp = record_audit("pullrequest", result, opa_input, request, source="webhook")
    resp["input"] = opa_input

    if head_sha and repo_full_name:
        await github_check_run(
            repo_full_name=repo_full_name,
            head_sha=head_sha,
            allow=resp["allow"],
            violations=resp["violations"],
            audit_id=resp["audit_id"],
            installation_id=installation_id,
        )
        resp["check_run_posted"] = True

    return resp
