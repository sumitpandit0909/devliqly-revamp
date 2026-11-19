"""A customer whose reps ask every visitor for WhatsApp permission can say so once, instead of ticking each lead.

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "follow_up_settings",
        sa.Column("whatsapp_consent_at_capture", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("follow_up_settings", "whatsapp_consent_at_capture")
