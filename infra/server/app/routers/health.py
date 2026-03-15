"""Health check endpoint."""

import httpx
from fastapi import APIRouter

from ..config import OPA_URL

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OPA_URL}/health")
        opa_ok = r.status_code == 200
    except Exception:
        opa_ok = False
    return {"status": "ok" if opa_ok else "degraded", "opa": opa_ok}
