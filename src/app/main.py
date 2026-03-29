from fastapi import FastAPI
from app.routers import webhook
from app.config import get_settings

def create_app():
    app = FastAPI(title="Gitpoli", version="1.0.0") # Include the webhook router
    app.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)