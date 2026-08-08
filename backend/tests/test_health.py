from starlette.middleware.cors import CORSMiddleware

from app.main import create_app
from tests.conftest import ApiHarness


def test_health_live_and_ready(api_harness: ApiHarness) -> None:
    live = api_harness.client.get("/health/live")
    ready = api_harness.client.get("/health/ready")

    assert live.status_code == 200
    assert live.json() == {"status": "ok", "service": "deltracking-api"}
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ok",
        "database": "ok",
        "scheduler_running": True,
    }


def test_production_disables_api_docs_and_does_not_enable_cors(
    api_harness: ApiHarness,
) -> None:
    production_settings = api_harness.services.settings.model_copy(
        update={"app_environment": "production"}
    )
    app = create_app(production_settings, api_harness.services)

    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None
    assert all(middleware.cls is not CORSMiddleware for middleware in app.user_middleware)
