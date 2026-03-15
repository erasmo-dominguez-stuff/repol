"""OPA REST API client."""

import httpx
from fastapi import HTTPException

from .config import OPA_URL


async def query_opa(path: str, input_data: dict) -> dict:
    """POST to OPA /v1/data/{path} and return the result object."""
    url = f"{OPA_URL}/v1/data/{path}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json={"input": input_data})
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502, detail=f"OPA returned {resp.status_code}: {resp.text}"
        )
    return resp.json().get("result", {})
