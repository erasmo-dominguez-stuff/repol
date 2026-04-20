from pathlib import Path

import yaml
from fastapi import FastAPI

from .config import REPOL_DIR
from .routers.audit_api import router as audit_router
from .routers.evaluate import router as evaluate_router
from .routers.health import router as health_router
from .routers.webhook import router as webhook_router


def _read_yaml_or_empty(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if isinstance(data, dict):
        return data
    return {}


app = FastAPI(title="gitpoli")


@app.on_event("startup")
async def load_repo_policy_configs() -> None:
    app.state.repo_policy_deploy = _read_yaml_or_empty(REPOL_DIR / "deploy.yaml")
    app.state.repo_policy_pullrequest = _read_yaml_or_empty(REPOL_DIR / "pullrequest.yaml")


app.include_router(health_router)
app.include_router(evaluate_router)
app.include_router(audit_router)
app.include_router(webhook_router)
