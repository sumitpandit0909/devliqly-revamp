"""Row-level security: the database itself keeps each customer's data separate.

The app logs in as platform_app, a role without BYPASSRLS. Each transaction declares who it acts for through
app.* settings (see app/db.py). Nothing is visible when no scope is set, so a forgotten scope fails closed.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_TABLES = (
    "organizations",
    "users",
    "memberships",
    "expo_events",
    "login_sessions",
    "password_setup_tokens",
)
SECURED_TABLES = ("organizations", "users", "memberships", "expo_events")


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'platform_app') THEN
                CREATE ROLE platform_app NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
            END IF;
        END $$
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO platform_app")
    for table in APP_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO platform_app")

    op.execute(
        """
        CREATE FUNCTION app_current_org() RETURNS uuid LANGUAGE sql STABLE AS
        $$ SELECT NULLIF(current_setting('app.org_id', true), '')::uuid $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION app_current_user() RETURNS uuid LANGUAGE sql STABLE AS
        $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION app_is_operator() RETURNS boolean LANGUAGE sql STABLE AS
        $$ SELECT COALESCE(current_setting('app.operator', true), '') = 'on' $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION app_is_auth_lookup() RETURNS boolean LANGUAGE sql STABLE AS
        $$ SELECT COALESCE(current_setting('app.auth_lookup', true), '') = 'on' $$
        """
    )

    for table in SECURED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # Customer companies: staff set them up; people see the ones they belong to
    op.execute(
        """
        CREATE POLICY organizations_read ON organizations FOR SELECT USING (
            id = app_current_org()
            OR app_is_operator()
            OR EXISTS (
                SELECT 1 FROM memberships m
                WHERE m.organization_id = organizations.id AND m.user_id = app_current_user()
            )
        )
        """
    )
    op.execute("CREATE POLICY organizations_create ON organizations FOR INSERT WITH CHECK (app_is_operator())")
    op.execute(
        """
        CREATE POLICY organizations_change ON organizations FOR UPDATE
        USING (id = app_current_org() OR app_is_operator())
        WITH CHECK (id = app_current_org() OR app_is_operator())
        """
    )

    # People: yourself, your colleagues, or the email lookup that happens before login
    op.execute(
        """
        CREATE POLICY users_read ON users FOR SELECT USING (
            id = app_current_user()
            OR app_is_operator()
            OR app_is_auth_lookup()
            OR EXISTS (
                SELECT 1 FROM memberships m
                WHERE m.user_id = users.id AND m.organization_id = app_current_org()
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY users_create ON users FOR INSERT
        WITH CHECK (app_is_operator() OR app_current_org() IS NOT NULL)
        """
    )
    op.execute(
        """
        CREATE POLICY users_change ON users FOR UPDATE
        USING (id = app_current_user() OR app_is_operator() OR app_is_auth_lookup())
        WITH CHECK (id = app_current_user() OR app_is_operator() OR app_is_auth_lookup())
        """
    )

    # Memberships: you can read your own, but only your organization or staff can change them
    op.execute(
        """
        CREATE POLICY memberships_read ON memberships FOR SELECT USING (
            organization_id = app_current_org() OR user_id = app_current_user() OR app_is_operator()
        )
        """
    )
    op.execute(
        """
        CREATE POLICY memberships_create ON memberships FOR INSERT
        WITH CHECK (organization_id = app_current_org() OR app_is_operator())
        """
    )
    op.execute(
        """
        CREATE POLICY memberships_change ON memberships FOR UPDATE
        USING (organization_id = app_current_org() OR app_is_operator())
        WITH CHECK (organization_id = app_current_org() OR app_is_operator())
        """
    )
    op.execute(
        """
        CREATE POLICY memberships_remove ON memberships FOR DELETE
        USING (organization_id = app_current_org() OR app_is_operator())
        """
    )

    # Customer-owned data follows this one rule
    op.execute(
        """
        CREATE POLICY expo_events_tenant ON expo_events
        USING (organization_id = app_current_org())
        WITH CHECK (organization_id = app_current_org())
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY expo_events_tenant ON expo_events")
    for name in ("read", "create", "change", "remove"):
        op.execute(f"DROP POLICY memberships_{name} ON memberships")
    for name in ("read", "create", "change"):
        op.execute(f"DROP POLICY users_{name} ON users")
        op.execute(f"DROP POLICY organizations_{name} ON organizations")
    for table in SECURED_TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    for function in ("app_current_org", "app_current_user", "app_is_operator", "app_is_auth_lookup"):
        op.execute(f"DROP FUNCTION {function}()")
    for table in APP_TABLES:
        op.execute(f"REVOKE ALL ON {table} FROM platform_app")
    op.execute("REVOKE USAGE ON SCHEMA public FROM platform_app")
