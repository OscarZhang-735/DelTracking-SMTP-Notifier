from fastapi.testclient import TestClient

from tests.conftest import ApiHarness


def test_authentication_requires_csrf_and_valid_credentials(api_harness: ApiHarness) -> None:
    client = api_harness.client

    assert client.get("/api/v1/trackings").status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "initial-password-123"},
    ).status_code == 403

    csrf_response = client.get("/api/v1/auth/csrf")
    csrf_token = csrf_response.json()["csrf_token"]
    cookie = csrf_response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    wrong = client.post(
        "/api/v1/auth/login",
        headers={"X-CSRF-Token": csrf_token},
        json={"username": "admin", "password": "wrong-password"},
    )
    assert wrong.status_code == 401

    authenticated_csrf = api_harness.login()
    assert client.get("/api/v1/auth/me").json()["username"] == "admin"
    assert client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": authenticated_csrf},
    ).status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_rate_limit_blocks_after_five_failures(api_harness: ApiHarness) -> None:
    client = api_harness.client
    csrf_token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    request = {
        "headers": {"X-CSRF-Token": csrf_token},
        "json": {"username": "admin", "password": "wrong-password"},
    }

    for _ in range(5):
        assert client.post("/api/v1/auth/login", **request).status_code == 401
    assert client.post("/api/v1/auth/login", **request).status_code == 429


def test_password_change_invalidates_other_sessions(api_harness: ApiHarness) -> None:
    first_client = api_harness.client
    first_csrf = api_harness.login()

    second_client = TestClient(first_client.app)
    try:
        second_csrf = second_client.get("/api/v1/auth/csrf").json()["csrf_token"]
        response = second_client.post(
            "/api/v1/auth/login",
            headers={"X-CSRF-Token": second_csrf},
            json={"username": "admin", "password": "initial-password-123"},
        )
        assert response.status_code == 200

        changed = first_client.put(
            "/api/v1/auth/password",
            headers={"X-CSRF-Token": first_csrf},
            json={
                "current_password": "initial-password-123",
                "new_password": "replacement-password-456",
            },
        )
        assert changed.status_code == 200
        assert changed.json()["csrf_token"] != first_csrf
        assert second_client.get("/api/v1/auth/me").status_code == 401
    finally:
        second_client.close()

    assert first_client.get("/api/v1/auth/me").status_code == 200
