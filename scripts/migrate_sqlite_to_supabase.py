"""
migrate_sqlite_to_supabase.py — One-time migration via REST API

Reads all data from local SQLite manlyfarm.db and uploads to
Supabase via the HTTPS REST API (no direct PostgreSQL needed).

Usage:
    python scripts/migrate_sqlite_to_supabase.py
"""

import os
import sys
import json
import sqlite3
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# ============================================
# Configuration
# ============================================

SQLITE_DB_PATH = str(PROJECT_ROOT / "db" / "manlyfarm.db")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

BATCH_SIZE = 200  # Supabase REST API handles ~200 rows per request well

# Column mappings: SQLite → Supabase (snake_case)
TX_COL_MAP = {
    "Datetime": "datetime",
    "Category": "category",
    "Item": "item",
    "Qty": "qty",
    "Net Sales": "net_sales",
    "Gross Sales": "gross_sales",
    "Discounts": "discounts",
    "Customer ID": "customer_id",
    "Transaction ID": "transaction_id",
    "Tax": "tax",
    "Card Brand": "card_brand",
    "PAN Suffix": "pan_suffix",
    "Date": "date",
    "Time": "time",
    "Time Zone": "time_zone",
    "Modifiers Applied": "modifiers_applied",
    "__row_key": "row_key",
}

INV_COL_MAP = {
    "Product ID": "product_id",
    "Product Name": "product_name",
    "SKU": "sku",
    "Categories": "categories",
    "Price": "price",
    "Tax - GST (10%)": "tax_gst_10",
    "Current Quantity Vie Market & Bar": "current_quantity",
    "Default Unit Cost": "default_unit_cost",
    "Unit": "unit",
    "source_date": "source_date",
    "Stock on Hand": "stock_on_hand",
}

MEM_COL_MAP = {
    "Square Customer ID": "square_customer_id",
    "First Name": "first_name",
    "Last Name": "last_name",
    "Email Address": "email_address",
    "Phone Number": "phone_number",
    "Creation Date": "creation_date",
    "Customer Note": "customer_note",
    "Reference ID": "reference_id",
}


# ============================================
# Supabase REST API Helper
# ============================================

def supabase_request(table, method="GET", data=None, params=None, on_conflict=None):
    """Make a request to Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())

    body = json.dumps(data).encode("utf-8") if data else None

    headers = {
        "apikey": SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    if on_conflict:
        headers["Prefer"] = f"resolution=merge-duplicates,return=minimal"
        # For upsert, we need the on_conflict in the URL
        sep = "&" if "?" in url else "?"
        url += f"{sep}on_conflict={on_conflict}"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        return e.code, error_body


def supabase_count(table):
    """Get row count for a table."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?select=*&limit=0"
    req = urllib.request.Request(
        url,
        headers={
            "apikey": SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
            "Prefer": "count=exact",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_range = resp.headers.get("Content-Range", "*/0")
            count_str = content_range.split("/")[-1]
            return int(count_str) if count_str != "*" else 0
    except Exception:
        return -1


# ============================================
# Data Cleaning
# ============================================

def clean_value(v):
    """Convert a value to JSON-safe type."""
    if v is None:
        return None
    if isinstance(v, float):
        if np.isnan(v) or np.isinf(v):
            return None
        return v
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        if np.isnan(v) or np.isinf(v):
            return None
        return float(v)
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        if pd.isna(v):
            return None
        return v.isoformat()
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    if str(v) in ("nan", "NaN", "NaT", "None", "nat"):
        return None
    return v


def clean_record(record):
    """Clean all values in a dict for JSON serialization."""
    return {k: clean_value(v) for k, v in record.items()}


# ============================================
# Migration Logic
# ============================================

def load_sqlite_table(table_name):
    """Load a table from SQLite."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    try:
        df = pd.read_sql(f'SELECT * FROM "{table_name}"', conn)
        return df
    except Exception as e:
        print(f"  ❌ Error loading '{table_name}': {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def migrate_table(df, col_map, target_table, on_conflict=None):
    """Migrate a DataFrame to Supabase via REST API."""
    if df.empty:
        print(f"  ⚠️  No data for '{target_table}'")
        return 0

    # Rename columns
    rename_map = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=rename_map)

    # Only keep mapped columns
    valid_cols = list(col_map.values())
    keep_cols = [c for c in df.columns if c in valid_cols]
    df = df[keep_cols]

    # Convert to records and clean
    records = df.to_dict("records")
    records = [clean_record(r) for r in records]

    total = len(records)
    uploaded = 0
    errors = 0

    print(f"  📤 Uploading {total} rows to '{target_table}' ({BATCH_SIZE}/batch)...")

    t0 = time.time()

    for i in range(0, total, BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]

        try:
            if on_conflict:
                status, body = supabase_request(
                    target_table, method="POST", data=batch, on_conflict=on_conflict
                )
            else:
                status, body = supabase_request(
                    target_table, method="POST", data=batch
                )

            if status in (200, 201):
                uploaded += len(batch)
            elif status == 409:
                # Conflict — some duplicates, try upsert
                status2, body2 = supabase_request(
                    target_table, method="POST", data=batch,
                    on_conflict=on_conflict or "id"
                )
                if status2 in (200, 201):
                    uploaded += len(batch)
                else:
                    errors += len(batch)
                    print(f"\n    ⚠️  Batch {i}-{i+len(batch)}: HTTP {status2}")
            else:
                errors += len(batch)
                err_msg = body[:150] if body else "unknown"
                print(f"\n    ⚠️  Batch {i}-{i+len(batch)}: HTTP {status} — {err_msg}")
        except Exception as e:
            errors += len(batch)
            print(f"\n    ❌ Batch {i}-{i+len(batch)}: {e}")

        # Progress bar
        pct = min(100, int((i + len(batch)) / total * 100))
        elapsed = time.time() - t0
        rate = (i + len(batch)) / elapsed if elapsed > 0 else 0
        eta = (total - i - len(batch)) / rate if rate > 0 else 0
        print(f"    [{pct:3d}%] {uploaded:,}/{total:,} rows | {rate:.0f} rows/s | ETA {eta:.0f}s   ", end="\r")

    elapsed = time.time() - t0
    print(f"\n  ✅ Done: {uploaded:,} uploaded, {errors:,} errors ({elapsed:.1f}s)")
    return uploaded


# ============================================
# Main
# ============================================

def main():
    print("=" * 60)
    print("  🔄 SQLite → Supabase Migration (via REST API)")
    print(f"  📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    if not SUPABASE_URL or not SERVICE_ROLE_KEY:
        print("❌ Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")
        return

    if not os.path.exists(SQLITE_DB_PATH):
        print(f"❌ SQLite not found: {SQLITE_DB_PATH}")
        return

    db_size = os.path.getsize(SQLITE_DB_PATH) / (1024 * 1024)
    print(f"\n📦 Source: {SQLITE_DB_PATH} ({db_size:.1f} MB)")
    print(f"🌐 Target: {SUPABASE_URL}")

    # Quick connectivity test
    print("\n🔌 Testing Supabase connection...")
    count = supabase_count("transactions")
    if count < 0:
        print("❌ Cannot reach Supabase. Check your credentials in .env")
        return
    print(f"  ✅ Connected (transactions currently has {count} rows)")

    # =============================================
    # 1) TRANSACTIONS
    # =============================================
    print("\n" + "=" * 50)
    print("📊 1/3: TRANSACTIONS")
    print("=" * 50)

    tx = load_sqlite_table("transactions")
    print(f"  📄 Loaded {len(tx):,} rows from SQLite")

    if not tx.empty:
        # Check if __row_key column exists
        if "__row_key" not in tx.columns:
            print("  ⚠️  No __row_key column — generating row keys...")
            base_cols = [
                "Transaction ID", "Datetime", "Item", "Net Sales",
                "Gross Sales", "Discounts", "Qty", "Customer ID",
                "Modifiers Applied", "Tax", "Card Brand", "PAN Suffix"
            ]
            for c in base_cols:
                if c not in tx.columns:
                    tx[c] = ""
            tx["__base"] = tx[base_cols].astype(str).agg("||".join, axis=1)
            tx["__dup_idx"] = tx.groupby(["Transaction ID", "__base"]).cumcount()
            tx["__row_key"] = tx["__base"] + "||" + tx["__dup_idx"].astype(str)
            tx = tx.drop(columns=["__base", "__dup_idx"])

        migrate_table(tx, TX_COL_MAP, "transactions", on_conflict="row_key")

    # =============================================
    # 2) INVENTORY
    # =============================================
    print("\n" + "=" * 50)
    print("📦 2/3: INVENTORY")
    print("=" * 50)

    inv = load_sqlite_table("inventory")
    print(f"  📄 Loaded {len(inv):,} rows from SQLite")

    if not inv.empty:
        migrate_table(inv, INV_COL_MAP, "inventory")

    # =============================================
    # 3) MEMBERS
    # =============================================
    print("\n" + "=" * 50)
    print("👥 3/3: MEMBERS")
    print("=" * 50)

    mem = load_sqlite_table("members")
    print(f"  📄 Loaded {len(mem):,} rows from SQLite")

    if not mem.empty:
        migrate_table(mem, MEM_COL_MAP, "members", on_conflict="square_customer_id")

    # =============================================
    # VERIFY
    # =============================================
    print("\n" + "=" * 60)
    print("🔍 VERIFICATION")
    print("=" * 60)

    for table in ["transactions", "inventory", "members"]:
        count = supabase_count(table)
        print(f"  📊 {table}: {count:,} rows in Supabase")

    print("\n🎉 Migration complete!")


if __name__ == "__main__":
    main()
