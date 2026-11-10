from contextvars import ContextVar
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

current_tenant_var: ContextVar[Optional[int]] = ContextVar("current_tenant_var", default=None)
current_superadmin_var: ContextVar[bool] = ContextVar("current_superadmin_var", default=False)


class TenantRLSContext:
    """
    Context manager binding `current_tenant_var` and `current_superadmin_var` for the active async task.
    """

    def __init__(self, tenant_id: Optional[int], is_superadmin: bool = False):
        self.tenant_id = tenant_id
        self.is_superadmin = is_superadmin
        self._token_tenant = None
        self._token_super = None

    def __enter__(self):
        self._token_tenant = current_tenant_var.set(self.tenant_id)
        self._token_super = current_superadmin_var.set(self.is_superadmin)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._token_tenant is not None:
            current_tenant_var.reset(self._token_tenant)
        if self._token_super is not None:
            current_superadmin_var.reset(self._token_super)


async def apply_rls_session_vars(
    session: AsyncSession,
    tenant_id: Optional[int] = None,
    is_superadmin: Optional[bool] = None,
) -> dict:
    """
    Propagates `app.current_tenant_id` and `app.is_superadmin` into the active PostgreSQL transaction
    using `SET LOCAL` so Row-Level Security policies isolate tenant rows at the kernel level.
    """
    tid = tenant_id if tenant_id is not None else current_tenant_var.get()
    super_flag = is_superadmin if is_superadmin is not None else current_superadmin_var.get()

    tid_str = str(tid) if tid is not None else ""
    super_str = "true" if super_flag else "false"

    bind = getattr(session, "bind", None)
    dialect_name = getattr(getattr(bind, "dialect", None), "name", "postgresql")

    if dialect_name == "postgresql":
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"),
            {"tid": tid_str},
        )
        await session.execute(
            text("SELECT set_config('app.is_superadmin', :sup, true)"),
            {"sup": super_str},
        )

    return {"app.current_tenant_id": tid_str, "app.is_superadmin": super_str}


def generate_rls_policies_sql() -> list[str]:
    """
    Returns standard PostgreSQL Row-Level Security (RLS) DDL statements for tenant-scoped tables.
    """
    tables = ["games", "player_profiles", "chat_members", "player_cards", "inventory_items"]
    statements = []
    for tbl in tables:
        statements.append(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        statements.append(
            f"""CREATE POLICY tenant_isolation_{tbl} ON {tbl}
    FOR ALL
    USING (
        chat_id = NULLIF(current_setting('app.current_tenant_id', true), '')::bigint
        OR current_setting('app.is_superadmin', true) = 'true'
        OR current_setting('app.current_tenant_id', true) IS NULL
        OR current_setting('app.current_tenant_id', true) = ''
    );"""
        )
    return statements
