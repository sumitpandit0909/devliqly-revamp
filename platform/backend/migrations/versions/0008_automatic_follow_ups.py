"""Follow-ups send automatically unless a customer chooses to approve each one.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE follow_up_settings ALTER COLUMN auto_send SET DEFAULT true")


def downgrade() -> None:
    op.execute("ALTER TABLE follow_up_settings ALTER COLUMN auto_send SET DEFAULT false")
