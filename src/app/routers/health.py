from fastapi import APIRouter

from ..opa import query_opa

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    opa_ok = True
    try:
        await query_opa("github/deploy", {"healthcheck": True})
    except Exception:
        opa_ok = False
    return {"ok": opa_ok}
