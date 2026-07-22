TENANT_ID_SETTING = "app.tenant_id"


def enable_tenant_rls(table_name: str) -> list[str]:
    """DDL for the standard tenant-isolation policy, used by migrations for every
    tenant-scoped table (and by the isolation suite's probe table).

    current_setting(..., missing_ok := true) yields NULL when no context is set,
    so a connection without a tenant context sees ZERO rows — it fails closed
    instead of erroring or, worse, seeing everything. `table_name` is always a
    developer-authored literal in migration code, never user input.
    """
    predicate = f"tenant_id = current_setting('{TENANT_ID_SETTING}', true)::uuid"
    return [
        f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY",
        f"CREATE POLICY tenant_isolation ON {table_name} "
        f"USING ({predicate}) WITH CHECK ({predicate})",
    ]
