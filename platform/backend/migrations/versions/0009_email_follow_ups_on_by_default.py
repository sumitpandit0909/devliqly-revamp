"""Email follow-ups start on with a standard message, for customers who haven't chosen otherwise.

Customers who already saved their settings keep them. A customer with no settings row gets the defaults from the
application when its first card is saved.

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE follow_up_settings ALTER COLUMN email_enabled SET DEFAULT true")


def downgrade() -> None:
    op.execute("ALTER TABLE follow_up_settings ALTER COLUMN email_enabled SET DEFAULT false")
