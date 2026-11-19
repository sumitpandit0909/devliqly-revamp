"""Row-level security for the CRM tables.

These belong to one customer and stay reachable by the worker, which acts across customers. Staff can read usage and
AI costs, which hold no personal data. A logged-in person can queue only the two kinds of job their actions start.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = (
    "companies",
    "contacts",
    "leads",
    "business_cards",
    "lead_activities",
    "follow_up_settings",
    "follow_ups",
    "opt_outs",
    "usage_months",
    "ai_calls",
)


def upgrade() -> None:
    for table in NEW_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO platform_app")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant ON {table}
            USING (organization_id = app_current_org() OR app_is_system())
            WITH CHECK (organization_id = app_current_org() OR app_is_system())
            """
        )
    for table in ("usage_months", "ai_calls"):
        op.execute(f"CREATE POLICY {table}_staff_read ON {table} FOR SELECT USING (app_is_operator())")

    # The worker checks which event a new card belongs to
    op.execute("CREATE POLICY expo_events_system_read ON expo_events FOR SELECT USING (app_is_system())")
    op.execute(
        """
        CREATE POLICY job_queue_tenant_enqueue ON job_queue FOR INSERT
        WITH CHECK (app_current_org() IS NOT NULL AND kind IN ('send_follow_up', 'delete_stored_files'))
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY job_queue_tenant_enqueue ON job_queue")
    op.execute("DROP POLICY expo_events_system_read ON expo_events")
    for table in ("usage_months", "ai_calls"):
        op.execute(f"DROP POLICY {table}_staff_read ON {table}")
    for table in NEW_TABLES:
        op.execute(f"DROP POLICY {table}_tenant ON {table}")
        op.execute(f"REVOKE ALL ON {table} FROM platform_app")
