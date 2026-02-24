"""
services/db_supabase.py — Supabase (PostgreSQL) database connector

Drop-in replacement for services/db.py (SQLite version).
All functions maintain the same interface so chart/analytics code needs minimal changes.

Uses Supabase REST API via urllib (no supabase-py dependency needed).
This avoids build issues with pyiceberg/pyroaring on Windows.
"""

import os
import json
import urllib.request
import urllib.error
import streamlit as st
import pandas as pd
from contextlib import contextmanager


# ============================================
# Connection Setup
# ============================================

def _get_supabase_config():
    """Get Supabase config from Streamlit secrets or environment variables."""
    # Try Streamlit secrets first (for Streamlit Cloud deployment)
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return url, key
    except Exception:
        pass

    # Fall back to environment variables (for local dev)
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        raise ValueError(
            "Supabase credentials not found. "
            "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env "
            "or in .streamlit/secrets.toml"
        )

    return url, key


class SupabaseClient:
    """Lightweight Supabase REST API client using urllib."""

    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.key = key
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def _request(self, endpoint, method="GET", data=None, extra_headers=None):
        """Make an HTTP request to Supabase REST API."""
        url = f"{self.url}/rest/v1/{endpoint}"
        body = json.dumps(data).encode("utf-8") if data else None

        headers = dict(self.headers)
        if extra_headers:
            headers.update(extra_headers)

        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read().decode("utf-8")
                return {
                    "status": resp.status,
                    "data": json.loads(content) if content else [],
                    "headers": dict(resp.headers),
                }
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise Exception(f"Supabase API error {e.code}: {error_body}")

    def table_select(self, table, columns="*", filters=None, order=None, limit=None, offset=None, count=False):
        """SELECT from a table with optional filters."""
        params = [f"select={columns}"]

        if filters:
            for f in filters:
                params.append(f)

        if order:
            params.append(f"order={order}")

        if limit is not None:
            params.append(f"limit={limit}")

        if offset is not None:
            params.append(f"offset={offset}")

        endpoint = f"{table}?{'&'.join(params)}"

        extra_headers = {}
        if count:
            extra_headers["Prefer"] = "count=exact"

        result = self._request(endpoint, extra_headers=extra_headers)

        if count:
            content_range = result["headers"].get("Content-Range", "*/0")
            count_val = content_range.split("/")[-1]
            result["count"] = int(count_val) if count_val != "*" else 0

        return result

    def table_insert(self, table, records, on_conflict=None):
        """INSERT records into a table."""
        endpoint = table
        extra_headers = {"Prefer": "return=minimal"}

        if on_conflict:
            endpoint += f"?on_conflict={on_conflict}"
            extra_headers["Prefer"] = "resolution=merge-duplicates,return=minimal"

        return self._request(endpoint, method="POST", data=records, extra_headers=extra_headers)

    def table_delete(self, table, filters):
        """DELETE from a table with filters."""
        params = "&".join(filters)
        endpoint = f"{table}?{params}"
        return self._request(endpoint, method="DELETE", extra_headers={"Prefer": "return=minimal"})


@st.cache_resource
def get_supabase_client() -> SupabaseClient:
    """Get cached Supabase client (singleton)."""
    url, key = _get_supabase_config()
    return SupabaseClient(url, key)


# ============================================
# Column Name Mapping
# ============================================
# SQLite used space-separated, bracket-quoted columns like [Net Sales]
# PostgreSQL uses snake_case: net_sales
# We maintain mappings so the analytics/chart code can work with either format

# Map from Supabase (snake_case) → DataFrame (original names used by charts)
COLUMN_MAP_TO_DISPLAY = {
    # Transactions
    "datetime": "Datetime",
    "category": "Category",
    "item": "Item",
    "qty": "Qty",
    "net_sales": "Net Sales",
    "gross_sales": "Gross Sales",
    "discounts": "Discounts",
    "customer_id": "Customer ID",
    "transaction_id": "Transaction ID",
    "tax": "Tax",
    "card_brand": "Card Brand",
    "pan_suffix": "PAN Suffix",
    "date": "Date",
    "time": "Time",
    "time_zone": "Time Zone",
    "modifiers_applied": "Modifiers Applied",
    "row_key": "__row_key",

    # Inventory
    "product_id": "Product ID",
    "product_name": "Product Name",
    "sku": "SKU",
    "categories": "Categories",
    "price": "Price",
    "tax_gst_10": "Tax - GST (10%)",
    "current_quantity": "Current Quantity Vie Market & Bar",
    "default_unit_cost": "Default Unit Cost",
    "unit": "Unit",
    "source_date": "source_date",
    "stock_on_hand": "Stock on Hand",

    # Members
    "square_customer_id": "Square Customer ID",
    "first_name": "First Name",
    "last_name": "Last Name",
    "email_address": "Email Address",
    "phone_number": "Phone Number",
    "creation_date": "Creation Date",
    "customer_note": "Customer Note",
    "reference_id": "Reference ID",
}

# Reverse map: DataFrame (original) → Supabase (snake_case)
COLUMN_MAP_TO_DB = {v: k for k, v in COLUMN_MAP_TO_DISPLAY.items()}


def _rename_to_display(df: pd.DataFrame) -> pd.DataFrame:
    """Rename Supabase snake_case columns to display names used by charts."""
    rename_map = {k: v for k, v in COLUMN_MAP_TO_DISPLAY.items() if k in df.columns}
    return df.rename(columns=rename_map)


def _rename_to_db(df: pd.DataFrame) -> pd.DataFrame:
    """Rename display column names to Supabase snake_case."""
    rename_map = {k: v for k, v in COLUMN_MAP_TO_DB.items() if k in df.columns}
    return df.rename(columns=rename_map)


# ============================================
# Data Loading Functions
# (These replace the SQLite-based load functions)
# ============================================

def _paginated_select(table, filters=None, order=None):
    """Fetch all rows from a table using pagination."""
    client = get_supabase_client()
    all_data = []
    page_size = 1000
    offset = 0

    while True:
        result = client.table_select(
            table,
            filters=filters,
            order=order,
            limit=page_size,
            offset=offset,
        )
        batch = result["data"]
        if not batch:
            break
        all_data.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    return all_data


def get_latest_transaction_date() -> str | None:
    """Return the latest transaction datetime string from Supabase, or None if empty."""
    client = get_supabase_client()
    result = client.table_select(
        "transactions",
        columns="datetime",
        order="datetime.desc",
        limit=1,
    )
    rows = result.get("data", [])
    if rows and rows[0].get("datetime"):
        return rows[0]["datetime"]
    return None


def load_transactions(days=365, time_from=None, time_to=None) -> pd.DataFrame:
    """Load transactions from Supabase, returning DataFrame with original column names."""
    filters = []
    if time_from:
        filters.append(f"datetime=gte.{time_from}")
    if time_to:
        filters.append(f"datetime=lte.{time_to}")

    all_data = _paginated_select("transactions", filters=filters or None)

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data)

    # Remove Supabase internal columns
    for col in ["id", "created_at"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    # Rename to display names (what the charts expect)
    df = _rename_to_display(df)

    # Parse datetime and strip timezone (Supabase stores UTC, charts use naive Timestamps)
    if "Datetime" in df.columns:
        df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce", utc=True).dt.tz_localize(None)

    return df


def load_inventory() -> pd.DataFrame:
    """Load inventory from Supabase."""
    all_data = _paginated_select("inventory")

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data)

    for col in ["id", "created_at"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    df = _rename_to_display(df)
    return df


def load_members() -> pd.DataFrame:
    """Load members from Supabase."""
    all_data = _paginated_select("members")

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data)

    for col in ["id", "created_at"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    df = _rename_to_display(df)
    return df


def load_all(time_from=None, time_to=None, days=None):
    """Load all data — drop-in replacement for analytics.load_all()."""
    tx = load_transactions(days=days or 365, time_from=time_from, time_to=time_to)
    inv = load_inventory()
    mem = load_members()

    # Compute inventory profit if analytics module is available
    try:
        from services.analytics import compute_inventory_profit
        if not inv.empty:
            inv = compute_inventory_profit(inv)
    except (ImportError, Exception):
        pass

    return tx, mem, inv


# ============================================
# Write Functions (for ingestion/sync)
# ============================================

def _clean_for_json(records):
    """Clean records for JSON serialization."""
    import numpy as np

    cleaned = []
    for record in records:
        clean = {}
        for k, v in record.items():
            if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                clean[k] = None
            elif isinstance(v, (np.integer,)):
                clean[k] = int(v)
            elif isinstance(v, (np.floating,)):
                clean[k] = float(v) if not (np.isnan(v) or np.isinf(v)) else None
            elif isinstance(v, np.bool_):
                clean[k] = bool(v)
            elif isinstance(v, pd.Timestamp):
                clean[k] = v.isoformat() if not pd.isna(v) else None
            elif str(v) in ("nan", "NaN", "NaT", "None"):
                clean[k] = None
            else:
                clean[k] = v
        cleaned.append(clean)
    return cleaned


def upsert_transactions(df: pd.DataFrame) -> int:
    """Upsert transactions to Supabase (using row_key for deduplication)."""
    if df is None or df.empty:
        return 0

    client = get_supabase_client()
    df_db = _rename_to_db(df.copy())

    # Convert datetime to string for JSON serialization
    if "datetime" in df_db.columns:
        df_db["datetime"] = pd.to_datetime(df_db["datetime"], errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")

    # Replace NaN with None
    df_db = df_db.where(pd.notnull(df_db), None)

    records = _clean_for_json(df_db.to_dict("records"))

    # Upsert in batches
    batch_size = 200
    total_upserted = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            client.table_insert("transactions", batch, on_conflict="row_key")
            total_upserted += len(batch)
        except Exception as e:
            print(f"❌ Error upserting transactions batch {i}: {e}")

    return total_upserted


def upsert_inventory(df: pd.DataFrame) -> int:
    """Upsert inventory to Supabase."""
    if df is None or df.empty:
        return 0

    client = get_supabase_client()
    df_db = _rename_to_db(df.copy())
    df_db = df_db.where(pd.notnull(df_db), None)

    records = _clean_for_json(df_db.to_dict("records"))

    # For inventory, delete existing records for the same source_date first
    if "source_date" in df_db.columns:
        dates = df_db["source_date"].dropna().unique().tolist()
        for d in dates:
            try:
                client.table_delete("inventory", [f"source_date=eq.{d}"])
            except Exception:
                pass

    batch_size = 200
    total_inserted = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            client.table_insert("inventory", batch)
            total_inserted += len(batch)
        except Exception as e:
            print(f"❌ Error inserting inventory batch {i}: {e}")

    return total_inserted


def upsert_members(df: pd.DataFrame) -> int:
    """Upsert members to Supabase (using square_customer_id for deduplication)."""
    if df is None or df.empty:
        return 0

    client = get_supabase_client()
    df_db = _rename_to_db(df.copy())
    df_db = df_db.where(pd.notnull(df_db), None)

    records = _clean_for_json(df_db.to_dict("records"))

    batch_size = 200
    total_upserted = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            client.table_insert("members", batch, on_conflict="square_customer_id")
            total_upserted += len(batch)
        except Exception as e:
            print(f"❌ Error upserting members batch {i}: {e}")

    return total_upserted


# ============================================
# Utility Functions (matching SQLite interface)
# ============================================

def table_exists(table_name: str) -> bool:
    """Check if a table exists in Supabase."""
    try:
        client = get_supabase_client()
        client.table_select(table_name, limit=1)
        return True
    except Exception:
        return False


def get_table_row_count(table_name: str) -> int:
    """Get approximate row count for a table."""
    try:
        client = get_supabase_client()
        result = client.table_select(table_name, limit=0, count=True)
        return result.get("count", 0)
    except Exception:
        return 0


def init_database():
    """No-op for Supabase — tables are created via SQL in the dashboard."""
    pass


def reset_db_connection():
    """Clear the cached Supabase client."""
    try:
        get_supabase_client.clear()
    except Exception:
        pass


@contextmanager
def db_connection():
    """Context manager for compatibility — yields the Supabase client."""
    client = get_supabase_client()
    try:
        yield client
    finally:
        pass  # Supabase client doesn't need closing


# For backward compatibility
def get_db():
    """Returns Supabase client (replaces sqlite3 connection)."""
    return get_supabase_client()


# ============================================
# Exports
# ============================================
__all__ = [
    'get_db',
    'get_supabase_client',
    'load_transactions',
    'load_inventory',
    'load_members',
    'load_all',
    'upsert_transactions',
    'upsert_inventory',
    'upsert_members',
    'table_exists',
    'get_table_row_count',
    'init_database',
    'reset_db_connection',
    'db_connection',
    'COLUMN_MAP_TO_DISPLAY',
    'COLUMN_MAP_TO_DB',
]
