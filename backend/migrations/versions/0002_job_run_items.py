"""Add per-item job audit records.

Revision ID: 0002_job_run_items
Revises: 0001_initial_schema
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_job_run_items"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "changed_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )

    op.create_table(
        "job_run_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_run_id", sa.Integer(), nullable=False),
        sa.Column("tracking_item_id", sa.Integer(), nullable=True),
        sa.Column("tracking_number", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("changed", sa.Boolean(), nullable=False),
        sa.Column("added_event_count", sa.Integer(), nullable=False),
        sa.Column("previous_status", sa.String(length=50), nullable=True),
        sa.Column("current_status", sa.String(length=50), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_run_id"], ["job_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["tracking_item_id"],
            ["tracking_items.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_job_run_items_job_run_id",
        "job_run_items",
        ["job_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_job_run_items_tracking_item_id",
        "job_run_items",
        ["tracking_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_job_run_items_status",
        "job_run_items",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_job_run_items_status", table_name="job_run_items")
    op.drop_index("ix_job_run_items_tracking_item_id", table_name="job_run_items")
    op.drop_index("ix_job_run_items_job_run_id", table_name="job_run_items")
    op.drop_table("job_run_items")
    with op.batch_alter_table("job_runs") as batch_op:
        batch_op.drop_column("changed_count")
