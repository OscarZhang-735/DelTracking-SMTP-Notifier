from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api.router import api_router
from app.api.security import LoginRateLimiter
from app.core.config import Settings, get_settings
from app.routers.health import router as health_router
from app.runtime import AppServices


def create_app(
    settings: Settings | None = None,
    services: AppServices | None = None,
) -> FastAPI:
    application_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        runtime_services = services or AppServices.build(application_settings)
        app.state.services = runtime_services
        runtime_services.start()
        try:
            yield
        finally:
            await runtime_services.shutdown()

    docs_enabled = application_settings.app_environment != "production"
    app = FastAPI(
        title="DelTracking API",
        description="Delivery tracking management service",
        version="0.1.0",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        lifespan=lifespan,
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=application_settings.session_secret.get_secret_value(),
        session_cookie="deltracking_session",
        max_age=application_settings.session_max_age_seconds,
        same_site="lax",
        https_only=application_settings.cookie_secure,
    )
    app.state.login_rate_limiter = LoginRateLimiter()
    app.include_router(health_router)
    app.include_router(api_router)
    return app


app = create_app()
