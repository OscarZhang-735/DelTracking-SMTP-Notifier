from __future__ import annotations

import asyncio
import smtplib
import ssl
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from typing import Protocol

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import SecretCipher
from app.database import Database
from app.integrations.nextsls import TraceSnapshot, status_label
from app.models import AppSettings, NotificationOutbox

RETRY_DELAYS = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(minutes=60),
    timedelta(minutes=180),
)


@dataclass(frozen=True, slots=True)
class TrackingChange:
    tracking_number: str
    previous_status: str | None
    current_status: str | None
    added_events: tuple[TraceSnapshot, ...]


@dataclass(frozen=True, slots=True)
class OutgoingEmail:
    recipient_email: str
    subject: str
    body_text: str
    body_html: str


@dataclass(frozen=True, slots=True)
class SmtpConfig:
    host: str
    port: int
    security: str
    username: str | None
    password: str | None
    sender_name: str
    sender_email: str
    timeout_seconds: float = 30.0


@dataclass(frozen=True, slots=True)
class DispatchSummary:
    selected: int
    sent: int
    failed: int


class EmailSender(Protocol):
    async def send(self, email: OutgoingEmail) -> None: ...


SenderFactory = Callable[[AppSettings], EmailSender]


def compose_digest(recipient_email: str, changes: Sequence[TrackingChange]) -> OutgoingEmail:
    subject = f"[物流更新] {len(changes)} 个包裹有新进展"
    text_lines = [subject, ""]
    html_items: list[str] = []

    for change in changes:
        previous = status_label(change.previous_status)
        current = status_label(change.current_status)
        text_lines.extend(
            [
                f"运单：{change.tracking_number}",
                f"状态：{previous} → {current}",
            ]
        )
        if change.added_events:
            text_lines.append("新增轨迹：")
            text_lines.extend(
                f"- {event.time_raw}  {event.info}" for event in change.added_events
            )
        text_lines.append("")

        event_items = "".join(
            f"<li><time>{escape(event.time_raw)}</time> {escape(event.info)}</li>"
            for event in change.added_events
        )
        event_section = f"<ul>{event_items}</ul>" if event_items else "<p>运输状态已更新。</p>"
        html_items.append(
            "<section>"
            f"<h2>{escape(change.tracking_number)}</h2>"
            f"<p>{escape(previous)} → <strong>{escape(current)}</strong></p>"
            f"{event_section}"
            "</section>"
        )

    body_html = (
        "<!doctype html><html><body>"
        f"<h1>{escape(subject)}</h1>"
        f"{''.join(html_items)}"
        "<p style=\"color:#68736d\">此邮件由 DelTracking 自动发送。</p>"
        "</body></html>"
    )
    return OutgoingEmail(
        recipient_email=recipient_email,
        subject=subject,
        body_text="\n".join(text_lines).rstrip() + "\n",
        body_html=body_html,
    )


def queue_digest(
    session: Session,
    *,
    job_run_id: int,
    recipient_id: int,
    recipient_email: str,
    changes: Sequence[TrackingChange],
) -> NotificationOutbox:
    email = compose_digest(recipient_email, changes)
    notification = NotificationOutbox(
        job_run_id=job_run_id,
        recipient_id=recipient_id,
        recipient_email=email.recipient_email,
        subject=email.subject,
        body_text=email.body_text,
        body_html=email.body_html,
        status="pending",
        attempt_count=0,
    )
    session.add(notification)
    return notification


class SmtpEmailSender:
    def __init__(self, config: SmtpConfig) -> None:
        if config.security not in {"ssl", "starttls", "none"}:
            raise ValueError("SMTP security must be ssl, starttls, or none")
        self._config = config

    async def send(self, email: OutgoingEmail) -> None:
        await asyncio.to_thread(self._send_sync, email)

    def _send_sync(self, email: OutgoingEmail) -> None:
        message = EmailMessage()
        message["From"] = formataddr((self._config.sender_name, self._config.sender_email))
        message["To"] = email.recipient_email
        message["Subject"] = email.subject
        message.set_content(email.body_text)
        message.add_alternative(email.body_html, subtype="html")

        context = ssl.create_default_context()
        if self._config.security == "ssl":
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                self._config.host,
                self._config.port,
                timeout=self._config.timeout_seconds,
                context=context,
            )
        else:
            server = smtplib.SMTP(
                self._config.host,
                self._config.port,
                timeout=self._config.timeout_seconds,
            )

        with server:
            if self._config.security == "starttls":
                server.starttls(context=context)
            if self._config.username:
                server.login(self._config.username, self._config.password or "")
            server.send_message(message)


def build_smtp_sender(settings: AppSettings, cipher: SecretCipher) -> SmtpEmailSender:
    required = {
        "SMTP host": settings.smtp_host,
        "SMTP port": settings.smtp_port,
        "SMTP security": settings.smtp_security,
        "sender name": settings.smtp_sender_name,
        "sender email": settings.smtp_sender_email,
    }
    missing = [name for name, value in required.items() if value in (None, "")]
    if missing:
        raise ValueError(f"SMTP configuration is incomplete: {', '.join(missing)}")

    password = (
        cipher.decrypt(settings.smtp_password_encrypted)
        if settings.smtp_password_encrypted
        else None
    )
    return SmtpEmailSender(
        SmtpConfig(
            host=settings.smtp_host or "",
            port=settings.smtp_port or 0,
            security=settings.smtp_security or "",
            username=settings.smtp_username,
            password=password,
            sender_name=settings.smtp_sender_name or "",
            sender_email=settings.smtp_sender_email or "",
        )
    )


class OutboxDispatcher:
    def __init__(self, database: Database, sender_factory: SenderFactory) -> None:
        self._database = database
        self._sender_factory = sender_factory

    async def dispatch_due(
        self,
        *,
        now: datetime | None = None,
        notification_ids: Sequence[int] | None = None,
    ) -> DispatchSummary:
        dispatch_time = now or datetime.now(UTC)
        with self._database.session() as session:
            statement = select(NotificationOutbox).where(
                NotificationOutbox.status.in_(("pending", "retrying")),
                or_(
                    NotificationOutbox.next_attempt_at.is_(None),
                    NotificationOutbox.next_attempt_at <= dispatch_time,
                ),
            )
            if notification_ids is not None:
                statement = statement.where(NotificationOutbox.id.in_(notification_ids))
            notifications = list(session.scalars(statement.order_by(NotificationOutbox.id)))
            app_settings = session.get(AppSettings, 1)
            emails = [
                (
                    notification.id,
                    OutgoingEmail(
                        recipient_email=notification.recipient_email,
                        subject=notification.subject,
                        body_text=notification.body_text,
                        body_html=notification.body_html,
                    ),
                )
                for notification in notifications
            ]

        if not emails:
            return DispatchSummary(selected=0, sent=0, failed=0)

        try:
            if app_settings is None:
                raise ValueError("application settings are missing")
            sender = self._sender_factory(app_settings)
        except Exception as exc:
            for notification_id, _email in emails:
                self._mark_failure(notification_id, exc, dispatch_time)
            return DispatchSummary(selected=len(emails), sent=0, failed=len(emails))

        sent = 0
        failed = 0
        for notification_id, email in emails:
            try:
                await sender.send(email)
            except Exception as exc:
                failed += 1
                self._mark_failure(notification_id, exc, dispatch_time)
            else:
                sent += 1
                self._mark_sent(notification_id, dispatch_time)
        return DispatchSummary(selected=len(emails), sent=sent, failed=failed)

    def retry_now(self, notification_id: int, *, now: datetime | None = None) -> bool:
        with self._database.session() as session:
            notification = session.get(NotificationOutbox, notification_id)
            if notification is None or notification.status == "sent":
                return False
            notification.status = "pending"
            notification.attempt_count = 0
            notification.next_attempt_at = now or datetime.now(UTC)
            notification.last_error = None
            return True

    def _mark_sent(self, notification_id: int, sent_at: datetime) -> None:
        with self._database.session() as session:
            notification = session.get(NotificationOutbox, notification_id)
            if notification is None:
                return
            notification.status = "sent"
            notification.sent_at = sent_at
            notification.next_attempt_at = None
            notification.last_error = None

    def _mark_failure(self, notification_id: int, error: Exception, failed_at: datetime) -> None:
        with self._database.session() as session:
            notification = session.get(NotificationOutbox, notification_id)
            if notification is None:
                return
            notification.attempt_count += 1
            notification.last_error = str(error).strip()[:2000] or type(error).__name__
            if notification.attempt_count <= len(RETRY_DELAYS):
                notification.status = "retrying"
                notification.next_attempt_at = (
                    failed_at + RETRY_DELAYS[notification.attempt_count - 1]
                )
            else:
                notification.status = "failed"
                notification.next_attempt_at = None
