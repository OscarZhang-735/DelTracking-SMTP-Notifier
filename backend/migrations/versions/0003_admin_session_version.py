"""Add administrator session invalidation version.

Revision ID: 0003_admin_session_version
Revises: 0002_job_run_items
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_admin_session_version"
down_revision: str | None = "0002_job_run_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("admins") as batch_op:
        batch_op.add_column(
            sa.Column(
                "session_version",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("admins") as batch_op:
        batch_op.drop_column("session_version")
