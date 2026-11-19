"""Customers' own WhatsApp numbers, connected through Embedded Signup.

Each customer sees only its own number. The webhook and worker reach every number, to route replies and send
follow-ups.

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE", name="fk_whatsapp_lines_organization_id_organizations"),
            nullable=False,
        ),
        sa.Column("phone_number_id", sa.String(40), nullable=False),
        sa.Column("waba_id", sa.String(40), nullable=False),
        sa.Column("display_phone", sa.String(40)),
        sa.Column("verified_name", sa.String(200)),
        sa.Column("access_token_sealed", sa.Text(), nullable=False),
        sa.Column("on_business_app", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(20), nullable=False, server_default="connected"),
        sa.Column("disconnect_reason", sa.String(200)),
        sa.Column("history_status", sa.String(20), nullable=False, server_default="not_needed"),
        sa.Column("history_progress", sa.Integer()),
        sa.Column("connected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", name="uq_whatsapp_lines_organization_id"),
        sa.UniqueConstraint("phone_number_id", name="uq_whatsapp_lines_phone_number_id"),
        sa.CheckConstraint("status IN ('connected', 'disconnected')", name="ck_whatsapp_lines_known_status"),
        sa.CheckConstraint(
            "history_status IN ('not_needed', 'waiting', 'syncing', 'done', 'not_shared', 'failed')",
            name="ck_whatsapp_lines_known_history_status",
        ),
    )
    op.create_index("ix_whatsapp_lines_waba_id", "whatsapp_lines", ["waba_id"])
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON whatsapp_lines TO platform_app")
    op.execute("ALTER TABLE whatsapp_lines ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE whatsapp_lines FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY whatsapp_lines_tenant ON whatsapp_lines
        USING (organization_id = app_current_org() OR app_is_system())
        WITH CHECK (organization_id = app_current_org() OR app_is_system())
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY whatsapp_lines_tenant ON whatsapp_lines")
    op.drop_index("ix_whatsapp_lines_waba_id", table_name="whatsapp_lines")
    op.drop_table("whatsapp_lines")
