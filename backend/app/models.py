from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


tracking_recipients = Table(
    "tracking_recipients",
    Base.metadata,
    Column(
        "tracking_item_id",
        ForeignKey("tracking_items.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("recipient_id", ForeignKey("recipients.id", ondelete="CASCADE"), primary_key=True),
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class Admin(TimestampMixin, Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class TrackingItem(TimestampMixin, Base):
    __tablename__ = "tracking_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracking_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    baseline_initialized: Mapped[bool] = mapped_column(Boolean, default=False)

    shipment_id: Mapped[str | None] = mapped_column(String(100))
    client_reference: Mapped[str | None] = mapped_column(String(100))
    outer_carrier_code: Mapped[str | None] = mapped_column(String(100))
    outer_carrier_tracking_number: Mapped[str | None] = mapped_column(String(200))
    shipment_status: Mapped[str | None] = mapped_column(String(50), index=True)
    country: Mapped[str | None] = mapped_column(String(100))
    postcode: Mapped[str | None] = mapped_column(String(50))
    parcel_count: Mapped[int | None] = mapped_column(Integer)

    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    trace_events: Mapped[list[TraceEvent]] = relationship(
        back_populates="tracking_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    recipients: Mapped[list[Recipient]] = relationship(
        secondary=tracking_recipients,
        back_populates="tracking_items",
    )


class TraceEvent(TimestampMixin, Base):
    __tablename__ = "trace_events"
    __table_args__ = (
        UniqueConstraint(
            "tracking_item_id",
            "event_time_raw",
            "info",
            name="uq_trace_event_identity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracking_item_id: Mapped[int] = mapped_column(
        ForeignKey("tracking_items.id", ondelete="CASCADE"),
        index=True,
    )
    event_time_raw: Mapped[str] = mapped_column(String(100))
    info: Mapped[str] = mapped_column(Text)

    tracking_item: Mapped[TrackingItem] = relationship(back_populates="trace_events")


class Recipient(TimestampMixin, Base):
    __tablename__ = "recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    tracking_items: Mapped[list[TrackingItem]] = relationship(
        secondary=tracking_recipients,
        back_populates="recipients",
    )


class AppSettings(TimestampMixin, Base):
    __tablename__ = "app_settings"
    __table_args__ = (
        CheckConstraint(
            "schedule_interval_minutes BETWEEN 5 AND 1440",
            name="ck_schedule_interval_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule_interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    timezone: Mapped[str] = mapped_column(String(100), default="Asia/Shanghai")

    smtp_host: Mapped[str | None] = mapped_column(String(255))
    smtp_port: Mapped[int | None] = mapped_column(Integer)
    smtp_security: Mapped[str | None] = mapped_column(String(20))
    smtp_username: Mapped[str | None] = mapped_column(String(255))
    smtp_password_encrypted: Mapped[str | None] = mapped_column(Text)
    smtp_sender_name: Mapped[str | None] = mapped_column(String(100))
    smtp_sender_email: Mapped[str | None] = mapped_column(String(320))


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trigger: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)

    notifications: Mapped[list[NotificationOutbox]] = relationship(back_populates="job_run")


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_runs.id", ondelete="SET NULL"),
        index=True,
    )
    tracking_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("tracking_items.id", ondelete="SET NULL"),
        index=True,
    )
    recipient_id: Mapped[int | None] = mapped_column(
        ForeignKey("recipients.id", ondelete="SET NULL"),
        index=True,
    )
    recipient_email: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(255))
    body_text: Mapped[str] = mapped_column(Text)
    body_html: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job_run: Mapped[JobRun | None] = relationship(back_populates="notifications")
