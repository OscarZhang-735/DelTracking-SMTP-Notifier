from fastapi.testclient import TestClient

from app.main import create_app


def test_health_live() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "deltracking-api"}
