"""Row-level security for the inbox, job queue and conversations.

System tables can only be touched by the webhook and worker (app.system) or read by Devliqly staff. Conversations
belong to a customer, and additionally stay reachable by the worker, which acts across customers.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = ("webhook_inbox", "job_queue", "rep_conversations", "conversation_messages")


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION app_is_system() RETURNS boolean LANGUAGE sql STABLE AS
        $$ SELECT COALESCE(current_setting('app.system', true), '') = 'on' $$
        """
    )
    for table in NEW_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO platform_app")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    for table in ("webhook_inbox", "job_queue"):
        op.execute(
            f"""
            CREATE POLICY {table}_system ON {table}
            USING (app_is_system()) WITH CHECK (app_is_system())
            """
        )
    op.execute("CREATE POLICY job_queue_staff_read ON job_queue FOR SELECT USING (app_is_operator())")
    op.execute(
        """
        CREATE POLICY job_queue_staff_retry ON job_queue FOR UPDATE
        USING (app_is_operator()) WITH CHECK (app_is_operator())
        """
    )

    for table in ("rep_conversations", "conversation_messages"):
        op.execute(
            f"""
            CREATE POLICY {table}_tenant ON {table}
            USING (organization_id = app_current_org() OR app_is_system())
            WITH CHECK (organization_id = app_current_org() OR app_is_system())
            """
        )

    # The worker finds which customer a phone number belongs to. It only reads these.
    for table in ("organizations", "users", "memberships"):
        op.execute(f"CREATE POLICY {table}_system_read ON {table} FOR SELECT USING (app_is_system())")


def downgrade() -> None:
    for table in ("organizations", "users", "memberships"):
        op.execute(f"DROP POLICY {table}_system_read ON {table}")
    for table in ("rep_conversations", "conversation_messages"):
        op.execute(f"DROP POLICY {table}_tenant ON {table}")
    op.execute("DROP POLICY job_queue_staff_retry ON job_queue")
    op.execute("DROP POLICY job_queue_staff_read ON job_queue")
    for table in ("webhook_inbox", "job_queue"):
        op.execute(f"DROP POLICY {table}_system ON {table}")
    for table in NEW_TABLES:
        op.execute(f"REVOKE ALL ON {table} FROM platform_app")
    op.execute("DROP FUNCTION app_is_system()")
