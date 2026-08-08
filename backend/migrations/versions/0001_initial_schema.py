"""Create the initial server-management schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admins_username", "admins", ["username"], unique=True)

    op.create_table(
        "tracking_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tracking_number", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("baseline_initialized", sa.Boolean(), nullable=False),
        sa.Column("shipment_id", sa.String(length=100), nullable=True),
        sa.Column("client_reference", sa.String(length=100), nullable=True),
        sa.Column("outer_carrier_code", sa.String(length=100), nullable=True),
        sa.Column("outer_carrier_tracking_number", sa.String(length=200), nullable=True),
        sa.Column("shipment_status", sa.String(length=50), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("postcode", sa.String(length=50), nullable=True),
        sa.Column("parcel_count", sa.Integer(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tracking_items_tracking_number",
        "tracking_items",
        ["tracking_number"],
        unique=True,
    )
    op.create_index(
        "ix_tracking_items_shipment_status",
        "tracking_items",
        ["shipment_status"],
        unique=False,
    )

    op.create_table(
        "recipients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recipients_email", "recipients", ["email"], unique=True)

    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("schedule_enabled", sa.Boolean(), nullable=False),
        sa.Column("schedule_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column("smtp_host", sa.String(length=255), nullable=True),
        sa.Column("smtp_port", sa.Integer(), nullable=True),
        sa.Column("smtp_security", sa.String(length=20), nullable=True),
        sa.Column("smtp_username", sa.String(length=255), nullable=True),
        sa.Column("smtp_password_encrypted", sa.Text(), nullable=True),
        sa.Column("smtp_sender_name", sa.String(length=100), nullable=True),
        sa.Column("smtp_sender_email", sa.String(length=320), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "schedule_interval_minutes BETWEEN 5 AND 1440",
            name="ck_schedule_interval_range",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_runs_status", "job_runs", ["status"], unique=False)

    op.create_table(
        "trace_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tracking_item_id", sa.Integer(), nullable=False),
        sa.Column("event_time_raw", sa.String(length=100), nullable=False),
        sa.Column("info", sa.Text(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["tracking_item_id"], ["tracking_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tracking_item_id",
            "event_time_raw",
            "info",
            name="uq_trace_event_identity",
        ),
    )
    op.create_index(
        "ix_trace_events_tracking_item_id",
        "trace_events",
        ["tracking_item_id"],
        unique=False,
    )

    op.create_table(
        "tracking_recipients",
        sa.Column("tracking_item_id", sa.Integer(), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["recipient_id"], ["recipients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tracking_item_id"], ["tracking_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tracking_item_id", "recipient_id"),
    )

    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_run_id", sa.Integer(), nullable=True),
        sa.Column("tracking_item_id", sa.Integer(), nullable=True),
        sa.Column("recipient_id", sa.Integer(), nullable=True),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_run_id"], ["job_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recipient_id"], ["recipients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["tracking_item_id"],
            ["tracking_items.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_outbox_job_run_id",
        "notification_outbox",
        ["job_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_outbox_tracking_item_id",
        "notification_outbox",
        ["tracking_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_outbox_recipient_id",
        "notification_outbox",
        ["recipient_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_outbox_status",
        "notification_outbox",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_notification_outbox_next_attempt_at",
        "notification_outbox",
        ["next_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notification_outbox_next_attempt_at", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_status", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_recipient_id", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_tracking_item_id", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_job_run_id", table_name="notification_outbox")
    op.drop_table("notification_outbox")
    op.drop_table("tracking_recipients")
    op.drop_index("ix_trace_events_tracking_item_id", table_name="trace_events")
    op.drop_table("trace_events")
    op.drop_index("ix_job_runs_status", table_name="job_runs")
    op.drop_table("job_runs")
    op.drop_table("app_settings")
    op.drop_index("ix_recipients_email", table_name="recipients")
    op.drop_table("recipients")
    op.drop_index("ix_tracking_items_shipment_status", table_name="tracking_items")
    op.drop_index("ix_tracking_items_tracking_number", table_name="tracking_items")
    op.drop_table("tracking_items")
    op.drop_index("ix_admins_username", table_name="admins")
    op.drop_table("admins")
