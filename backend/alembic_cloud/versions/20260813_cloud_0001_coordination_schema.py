"""create the HC2 coordination relations

Revision ID: 20260813_cloud_0001
Revises: None
Create Date: 2026-08-13
"""

from collections.abc import Sequence

from alembic import op

from app.cloud_db.base import cloud_metadata
import app.cloud_db.schema  # noqa: F401

revision: str = "20260813_cloud_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS coordination')
    cloud_metadata.create_all(bind=op.get_bind(), checkfirst=False)
    for table in cloud_metadata.sorted_tables:
        op.execute(f'ALTER TABLE coordination.{table.name} ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    # Cloud coordination state is durable queue/read-model data. Destructive
    # downgrade is intentionally manual so an automated rollback cannot erase it.
    pass
