from app.models import AppSettings, JobRun, NotificationOutbox, TrackingItem
from app.runtime import AppServices
from tests.conftest import ApiHarness


def test_tracking_and_recipient_crud_filters_and_constraints(api_harness: ApiHarness) -> None:
    client = api_harness.client
    csrf = api_harness.login()
    headers = {"X-CSRF-Token": csrf}

    missing_csrf = client.post(
        "/api/v1/recipients",
        json={"name": "Alice", "email": "alice@example.com"},
    )
    assert missing_csrf.status_code == 403

    recipient = client.post(
        "/api/v1/recipients",
        headers=headers,
        json={"name": "Alice", "email": "alice@example.com"},
    )
    assert recipient.status_code == 201
    recipient_id = recipient.json()["id"]
    duplicate_recipient = client.post(
        "/api/v1/recipients",
        headers=headers,
        json={"name": "Duplicate", "email": "alice@example.com"},
    )
    assert duplicate_recipient.status_code == 409

    tracking = client.post(
        "/api/v1/trackings",
        headers=headers,
        json={
            "tracking_number": "1024658760",
            "notes": "API test",
            "recipient_ids": [recipient_id],
        },
    )
    assert tracking.status_code == 201
    tracking_id = tracking.json()["id"]
    assert tracking.json()["recipients"][0]["id"] == recipient_id
    duplicate_tracking = client.post(
        "/api/v1/trackings",
        headers=headers,
        json={"tracking_number": "1024658760"},
    )
    assert duplicate_tracking.status_code == 409

    listing = client.get("/api/v1/trackings?search=2465&page=1&page_size=1")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["page_size"] == 1
    assert client.get("/api/v1/trackings?enabled=false").json()["total"] == 0

    updated = client.patch(
        f"/api/v1/trackings/{tracking_id}",
        headers=headers,
        json={"enabled": False, "notes": "disabled"},
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False

    assert client.delete(f"/api/v1/recipients/{recipient_id}", headers=headers).status_code == 204
    retained = client.get(f"/api/v1/trackings/{tracking_id}")
    assert retained.status_code == 200
    assert retained.json()["recipients"] == []


def test_query_runs_and_run_history(api_harness: ApiHarness) -> None:
    client = api_harness.client
    headers = {"X-CSRF-Token": api_harness.login()}
    tracking = client.post(
        "/api/v1/trackings",
        headers=headers,
        json={"tracking_number": "1024658760"},
    ).json()

    run = client.post(f"/api/v1/trackings/{tracking['id']}/query", headers=headers)
    assert run.status_code == 200
    assert run.json()["success_count"] == 1
    run_id = run.json()["job_run_id"]

    detail = client.get(f"/api/v1/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["items"][0]["tracking_number"] == "1024658760"
    queried = client.get(f"/api/v1/trackings/{tracking['id']}").json()
    assert queried["baseline_initialized"] is True
    assert len(queried["traces"]) == 1

    history = client.get("/api/v1/runs?page=1&page_size=1")
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["page_size"] == 1


def test_schedule_and_smtp_settings_hide_password(
    api_harness: ApiHarness,
    monkeypatch,
) -> None:
    client = api_harness.client
    headers = {"X-CSRF-Token": api_harness.login()}

    invalid = client.put(
        "/api/v1/settings/schedule",
        headers=headers,
        json={"enabled": True, "interval_minutes": 4, "timezone": "Asia/Shanghai"},
    )
    assert invalid.status_code == 422
    valid = client.put(
        "/api/v1/settings/schedule",
        headers=headers,
        json={"enabled": False, "interval_minutes": 45, "timezone": "Asia/Shanghai"},
    )
    assert valid.status_code == 200
    assert valid.json()["interval_minutes"] == 45

    smtp_password = "smtp-secret-password"
    smtp = client.put(
        "/api/v1/settings/smtp",
        headers=headers,
        json={
            "host": "smtp.example.com",
            "port": 587,
            "security": "starttls",
            "username": "mailer@example.com",
            "password": smtp_password,
            "sender_name": "DelTracking",
            "sender_email": "mailer@example.com",
        },
    )
    assert smtp.status_code == 200
    assert smtp.json()["password_configured"] is True
    assert "password" not in smtp.json()
    assert smtp_password not in client.get("/api/v1/settings/smtp").text
    with api_harness.services.database.session() as session:
        encrypted = session.get(AppSettings, 1).smtp_password_encrypted
        assert encrypted is not None
        assert smtp_password not in encrypted

    monkeypatch.setattr(
        AppServices,
        "build_email_sender",
        lambda _services, _settings: api_harness.sender,
    )
    sent = client.post(
        "/api/v1/settings/smtp/test",
        headers=headers,
        json={"recipient_email": "recipient@example.com"},
    )
    assert sent.status_code == 200
    assert api_harness.sender.sent[-1].recipient_email == "recipient@example.com"


def test_failed_notification_can_be_retried(api_harness: ApiHarness) -> None:
    client = api_harness.client
    headers = {"X-CSRF-Token": api_harness.login()}
    with api_harness.services.database.session() as session:
        run = JobRun(trigger="manual", status="completed")
        session.add(run)
        session.flush()
        notification = NotificationOutbox(
            job_run_id=run.id,
            recipient_email="recipient@example.com",
            subject="Retry",
            body_text="Plain",
            body_html="<p>HTML</p>",
            status="failed",
            attempt_count=6,
            last_error="SMTP unavailable",
        )
        session.add(notification)
        session.flush()
        notification_id = notification.id

    retried = client.post(
        f"/api/v1/notifications/{notification_id}/retry",
        headers=headers,
    )
    assert retried.status_code == 200
    assert retried.json()["sent"] == 1
    assert api_harness.sender.sent[-1].subject == "Retry"
    with api_harness.services.database.session() as session:
        notification = session.get(NotificationOutbox, notification_id)
        assert notification.status == "sent"
        assert notification.last_error is None


def test_deleting_tracking_removes_only_requested_item(api_harness: ApiHarness) -> None:
    client = api_harness.client
    headers = {"X-CSRF-Token": api_harness.login()}
    created = client.post(
        "/api/v1/trackings",
        headers=headers,
        json={"tracking_number": "DELETE-ME"},
    ).json()
    assert client.delete(f"/api/v1/trackings/{created['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/trackings/{created['id']}").status_code == 404
    with api_harness.services.database.session() as session:
        assert session.get(TrackingItem, created["id"]) is None
