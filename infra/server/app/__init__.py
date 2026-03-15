"""Policy evaluation server — thin bridge between HTTP clients and OPA."""

import logging

from fastapi import FastAPI

from .audit import init_db
from .routers import audit_api, evaluate, health, webhook

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="Policy Server", version="0.1.0")


@app.on_event("startup")
def _startup():
    init_db()


app.include_router(health.router)
app.include_router(evaluate.router)
app.include_router(webhook.router)
app.include_router(audit_api.router)
