"""
services/db.py — Compatibility shim

This file redirects all imports to services/db_supabase.py
so that existing chart/analytics code that does:
    from services.db import get_db
continues to work without modification.
"""

from services.db_supabase import (
    get_db,
    get_supabase_client,
    load_transactions,
    load_inventory,
    load_members,
    load_all,
    upsert_transactions,
    upsert_inventory,
    upsert_members,
    table_exists,
    get_table_row_count,
    init_database,
    reset_db_connection,
    db_connection,
    COLUMN_MAP_TO_DISPLAY,
    COLUMN_MAP_TO_DB,
)


def get_db_path():
    """Stub for backward compatibility — returns a placeholder since we use Supabase now."""
    return "supabase://cloud"
