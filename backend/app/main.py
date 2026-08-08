from fastapi import FastAPI

from app.routers.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="DelTracking API",
        description="Delivery tracking management service",
        version="0.1.0",
    )
    app.include_router(health_router)
    return app


app = create_app()
