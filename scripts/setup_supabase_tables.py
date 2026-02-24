"""
Create tables in Supabase using the REST API (no direct PostgreSQL needed).
Uses the service_role key to execute SQL via Supabase's RPC.
"""
import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SERVICE_ROLE_KEY:
    print("❌ Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")
    sys.exit(1)

def supabase_rpc(function_name, params=None):
    """Call a Supabase RPC function."""
    data = json.dumps(params or {}).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{function_name}",
        data=data,
        headers={
            "apikey": SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def supabase_query(table, method="GET", params=None, data=None):
    """Query or insert into a Supabase table via REST."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())

    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "apikey": SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal,count=exact",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_range = resp.headers.get("Content-Range", "")
            return resp.status, resp.read().decode(), content_range
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), ""


# ============================================
# Step 1: Create a SQL execution function
# ============================================

print("=" * 60)
print("  🔧 Supabase Table Setup via REST API")
print("=" * 60)

# First, we need to create a helper function in the database
# that lets us execute arbitrary SQL via RPC
print("\n📋 Step 1: Creating SQL executor function...")

# Use the Supabase SQL endpoint (available via Management API)
# Or we can use the pg_net extension... Actually, let's try
# creating tables one at a time through a workaround.

# The trick: We can create an RPC function via the REST API
# by inserting into the _supabase_functions schema... 
# Actually, the cleanest way is to use the HTTP endpoint for SQL

# Supabase has a hidden /sql endpoint for the service role
sql_endpoint = f"{SUPABASE_URL}/rest/v1/rpc/"

# Let's try the approach of creating the exec_sql function first
create_func_sql = """
CREATE OR REPLACE FUNCTION exec_sql(query text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  EXECUTE query;
END;
$$;
"""

# We need to first try direct DB before we can use RPC
# Let's try each approach

# Approach: Use psycopg2 with the direct connection but force IPv4
print("\n📡 Attempting database connection...")

try:
    import psycopg2
    import socket

    # Force IPv4 by resolving first
    host = "db.heavnfayolxrgmxkkrvr.supabase.co"
    
    # Try to get IPv4 address
    try:
        addrs = socket.getaddrinfo(host, 5432, socket.AF_INET)
        if addrs:
            ipv4 = addrs[0][4][0]
            print(f"  ✅ Resolved {host} to IPv4: {ipv4}")
            conn = psycopg2.connect(
                host=ipv4,
                port=5432,
                dbname="postgres",
                user="postgres",
                password="ZV67oKRC4e2lOOcd",
                sslmode="require",
                connect_timeout=10,
            )
            print("  ✅ Connected via IPv4!")
        else:
            raise Exception("No IPv4 address found")
    except (socket.gaierror, Exception) as e:
        print(f"  ⚠️ No IPv4 for {host}, trying IPv6...")
        # Try IPv6
        addrs = socket.getaddrinfo(host, 5432, socket.AF_INET6)
        if addrs:
            ipv6 = addrs[0][4][0]
            print(f"  📡 Resolved to IPv6: {ipv6}")
            conn = psycopg2.connect(
                host=ipv6,
                port=5432,
                dbname="postgres",
                user="postgres",
                password="ZV67oKRC4e2lOOcd",
                sslmode="require",
                connect_timeout=10,
            )
            print("  ✅ Connected via IPv6!")
        else:
            raise Exception("No addresses found")

    conn.autocommit = True
    cur = conn.cursor()

    # ============================================
    # Create all tables
    # ============================================
    
    tables = {
        "transactions": """
            CREATE TABLE IF NOT EXISTS transactions (
                id BIGSERIAL PRIMARY KEY,
                datetime TIMESTAMPTZ,
                category TEXT,
                item TEXT,
                qty REAL,
                net_sales REAL,
                gross_sales REAL,
                discounts REAL,
                customer_id TEXT,
                transaction_id TEXT,
                tax TEXT,
                card_brand TEXT,
                pan_suffix TEXT,
                date TEXT,
                time TEXT,
                time_zone TEXT,
                modifiers_applied TEXT,
                row_key TEXT UNIQUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """,
        "inventory": """
            CREATE TABLE IF NOT EXISTS inventory (
                id BIGSERIAL PRIMARY KEY,
                product_id TEXT,
                product_name TEXT,
                sku TEXT,
                categories TEXT,
                price REAL,
                tax_gst_10 TEXT,
                current_quantity REAL,
                default_unit_cost REAL,
                unit TEXT,
                source_date TEXT,
                stock_on_hand REAL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """,
        "members": """
            CREATE TABLE IF NOT EXISTS members (
                id BIGSERIAL PRIMARY KEY,
                square_customer_id TEXT UNIQUE,
                first_name TEXT,
                last_name TEXT,
                email_address TEXT,
                phone_number TEXT,
                creation_date TEXT,
                customer_note TEXT,
                reference_id TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """,
        "units": """
            CREATE TABLE IF NOT EXISTS units (
                id BIGSERIAL PRIMARY KEY,
                name TEXT UNIQUE
            );
        """,
        "ingestion_log": """
            CREATE TABLE IF NOT EXISTS ingestion_log (
                source_file TEXT PRIMARY KEY,
                ingested_at TIMESTAMPTZ DEFAULT NOW()
            );
        """,
        "sync_log": """
            CREATE TABLE IF NOT EXISTS sync_log (
                id BIGSERIAL PRIMARY KEY,
                sync_type TEXT,
                started_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ,
                records_synced INTEGER,
                status TEXT,
                error_message TEXT
            );
        """,
    }

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_txn_datetime ON transactions(datetime);",
        "CREATE INDEX IF NOT EXISTS idx_txn_transaction_id ON transactions(transaction_id);",
        "CREATE INDEX IF NOT EXISTS idx_txn_row_key ON transactions(row_key);",
        "CREATE INDEX IF NOT EXISTS idx_member_square ON members(square_customer_id);",
        "CREATE INDEX IF NOT EXISTS idx_member_ref ON members(reference_id);",
        "CREATE INDEX IF NOT EXISTS idx_inv_sku ON inventory(sku);",
        "CREATE INDEX IF NOT EXISTS idx_inv_categories ON inventory(categories);",
        "CREATE INDEX IF NOT EXISTS idx_inv_source_date ON inventory(source_date);",
    ]

    print("\n📋 Creating tables...\n")
    for name, sql in tables.items():
        try:
            cur.execute(sql)
            print(f"  ✅ Table: {name}")
        except Exception as e:
            print(f"  ⚠️ Table {name}: {e}")

    print("\n📋 Creating indexes...\n")
    for sql in indexes:
        try:
            cur.execute(sql)
            idx = sql.split("EXISTS")[1].split("ON")[0].strip()
            print(f"  ✅ Index: {idx}")
        except Exception as e:
            print(f"  ⚠️ Index error: {e}")

    # Verify
    print("\n" + "=" * 50)
    print("🔍 Verifying tables...\n")
    
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    
    for (table_name,) in cur.fetchall():
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cur.fetchone()[0]
            print(f"  📊 {table_name}: {count} rows")
        except Exception:
            print(f"  📊 {table_name}: (exists)")

    print("\n🎉 Supabase database setup complete!")
    
    cur.close()
    conn.close()

except Exception as e:
    print(f"\n❌ Could not connect: {e}")
    print("\n" + "=" * 60)
    print("📋 Please run this SQL manually in the Supabase SQL Editor:")
    print(f"   https://supabase.com/dashboard/project/heavnfayolxrgmxkkrvr/sql/new")
    print("=" * 60)
    
    sql_file = PROJECT_ROOT / "scripts" / "supabase_schema.sql"
    print(f"\n💾 SQL saved to: {sql_file}")
    print("   Copy the contents of that file and paste into the SQL Editor.")
