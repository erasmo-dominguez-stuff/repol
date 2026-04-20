"""OPA REST API client.

Thin wrapper around the OPA /v1/data/{package} HTTP endpoint.
All policy evaluation calls go through here so the rest of the
codebase never speaks HTTP to OPA directly.
"""

import httpx
from fastapi import HTTPException

from .config import OPA_URL


async def query_opa(package: str, input_data: dict) -> dict:
    """Evaluate an OPA package against the given input and return the result.

    Args:
        package: Dot-separated OPA package path (e.g. ``"github.pullrequest"``).
                 Slashes are also accepted (``"github/pullrequest"``).
        input_data: The ``input`` document forwarded to OPA as-is.

    Returns:
        The ``result`` object from OPA's response, which contains at minimum
        ``allow`` (bool) and ``violations`` (list).  Returns an empty dict if
        OPA's response has no ``result`` key (e.g. undefined rule).

    Raises:
        HTTPException 502: When OPA is unreachable or returns a non-200 status.
                           Bubbles up to the API caller as a clear gateway error.
    """
    # OPA accepts both dot-separated and slash-separated package paths.
    # Normalise to slashes to match the REST API convention.
    url = f"{OPA_URL}/v1/data/{package.replace('.', '/')}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"input": input_data})
    except httpx.RequestError as exc:
        # Network-level failure (DNS, connection refused, timeout, etc.)
        raise HTTPException(status_code=502, detail=f"OPA unreachable: {exc}") from exc

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502, detail=f"OPA returned {resp.status_code}: {resp.text}"
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="OPA returned invalid JSON") from exc

    return payload.get("result", {})
