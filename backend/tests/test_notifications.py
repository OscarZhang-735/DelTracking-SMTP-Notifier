import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet

from app.core.security import SecretCipher
from app.database import Database
from app.integrations.nextsls import TraceSnapshot
from app.migrations import upgrade_database
from app.models import AppSettings, NotificationOutbox
from app.services.notifications import (
    OutboxDispatcher,
    OutgoingEmail,
    TrackingChange,
    build_smtp_sender,
    compose_digest,
)


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


class FakeSender:
    def __init__(self, failures_remaining: int = 0) -> None:
        self.failures_remaining = failures_remaining
        self.sent: list[OutgoingEmail] = []

    async def send(self, email: OutgoingEmail) -> None:
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise RuntimeError("SMTP unavailable")
        self.sent.append(email)


def test_digest_is_recipient_specific_and_html_escaped() -> None:
    email = compose_digest(
        "recipient@example.com",
        [
            TrackingChange(
                tracking_number="<TRACK-001>",
                previous_status="ready",
                current_status="in_transit",
                added_events=(
                    TraceSnapshot(time_raw="2026-08-08 10:00", info="<已发出>"),
                ),
            )
        ],
    )

    assert email.recipient_email == "recipient@example.com"
    assert "<TRACK-001>" in email.body_text
    assert "&lt;TRACK-001&gt;" in email.body_html
    assert "<已发出>" not in email.body_html
    assert "已下单 → 转运中" in email.body_text


def test_outbox_retries_five_times_then_supports_manual_reset(tmp_path: Path) -> None:
    database_url = sqlite_url(tmp_path / "outbox.sqlite3")
    upgrade_database(database_url)
    database = Database(database_url)
    with database.session() as session:
        session.add(AppSettings(id=1))
        notification = NotificationOutbox(
            recipient_email="recipient@example.com",
            subject="subject",
            body_text="plain",
            body_html="<p>html</p>",
            status="pending",
        )
        session.add(notification)
        session.flush()
        notification_id = notification.id

    sender = FakeSender(failures_remaining=6)
    dispatcher = OutboxDispatcher(database, lambda _settings: sender)
    dispatch_at = datetime(2026, 8, 8, 10, 0, tzinfo=UTC)
    expected_delays = [1, 5, 15, 60, 180]

    for expected_attempt in range(1, 7):
        attempted_at = dispatch_at
        summary = asyncio.run(dispatcher.dispatch_due(now=dispatch_at))
        assert summary.failed == 1
        with database.session() as session:
            notification = session.get(NotificationOutbox, notification_id)
            assert notification is not None
            assert notification.attempt_count == expected_attempt
            if expected_attempt <= 5:
                assert notification.status == "retrying"
                assert notification.next_attempt_at is not None
                expected_next = attempted_at + expected_delays[expected_attempt - 1] * timedelta(
                    minutes=1
                )
                assert notification.next_attempt_at.replace(tzinfo=UTC) == expected_next
                dispatch_at = notification.next_attempt_at.replace(tzinfo=UTC)
            else:
                assert notification.status == "failed"
                assert notification.next_attempt_at is None

    assert dispatcher.retry_now(notification_id, now=dispatch_at)
    summary = asyncio.run(dispatcher.dispatch_due(now=dispatch_at))
    assert summary.sent == 1
    assert len(sender.sent) == 1
    with database.session() as session:
        notification = session.get(NotificationOutbox, notification_id)
        assert notification is not None
        assert notification.status == "sent"
        assert notification.attempt_count == 0
        assert notification.last_error is None

    database.dispose()


def test_incomplete_smtp_settings_are_rejected() -> None:
    cipher = SecretCipher(Fernet.generate_key().decode("ascii"))

    try:
        build_smtp_sender(AppSettings(id=1), cipher)
    except ValueError as exc:
        assert "SMTP configuration is incomplete" in str(exc)
    else:
        raise AssertionError("incomplete SMTP settings should be rejected")
