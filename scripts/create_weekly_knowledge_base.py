"""
create_weekly_knowledge_base.py - Create the 8 weekly knowledge base tables in Supabase.

Uses Supabase REST API to check if tables exist, then creates via RPC if available,
or outputs instructions if direct SQL execution isn't possible.

Usage:
    py scripts/create_weekly_knowledge_base.py
"""

import os
import sys
import json
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPA_URL or not SUPA_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    sys.exit(1)

HEADERS = {
    "apikey": SUPA_KEY,
    "Authorization": f"Bearer {SUPA_KEY}",
    "Content-Type": "application/json",
}


def supa_get(endpoint, params=""):
    """GET from Supabase REST API."""
    url = f"{SUPA_URL}/rest/v1/{endpoint}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        return None, e.code


def supa_rpc(fn_name, params=None):
    """Call a Supabase RPC function."""
    url = f"{SUPA_URL}/rest/v1/rpc/{fn_name}"
    data = json.dumps(params or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        return json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return {"error": body}, e.code


def check_table_exists(table_name):
    """Check if a table exists by trying to query it."""
    _, status = supa_get(table_name, "select=*&limit=0")
    return status == 200


def create_exec_sql_function():
    """Try to create a helper function for executing SQL via RPC."""
    sql = """
    CREATE OR REPLACE FUNCTION exec_sql(query text) RETURNS void AS $$
    BEGIN
        EXECUTE query;
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER;
    """
    # Try calling an existing exec_sql first
    result, status = supa_rpc("exec_sql", {"query": "SELECT 1"})
    if status == 200:
        return True
    return False


def main():
    migration_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "dashboard", "supabase", "migrations",
        "20260314_create_weekly_knowledge_base.sql"
    )

    print(f"Supabase URL: {SUPA_URL}")
    print()

    # Check which tables already exist
    tables_to_check = [
        "weekly_store_stats",
        "weekly_category_stats",
        "weekly_member_stats",
        "weekly_staff_stats",
        "weekly_inventory_stats",
        "weekly_hourly_patterns",
        "weekly_dow_stats",
        "coach_conversations",
    ]

    print("Checking existing tables...")
    existing = []
    missing = []
    for t in tables_to_check:
        exists = check_table_exists(t)
        status = "EXISTS" if exists else "MISSING"
        print(f"  {t}: {status}")
        if exists:
            existing.append(t)
        else:
            missing.append(t)

    print()
    if not missing:
        print("All 8 tables already exist! Nothing to do.")
        return

    print(f"{len(missing)} tables need to be created: {', '.join(missing)}")
    print()

    # Try using exec_sql RPC
    has_exec_sql = create_exec_sql_function()

    if has_exec_sql:
        print("Found exec_sql RPC function - executing migration via RPC...")
        with open(migration_file, "r", encoding="utf-8") as f:
            full_sql = f.read()

        # Parse into individual statements
        statements = []
        current = []
        for line in full_sql.split("\n"):
            stripped = line.strip()
            if stripped.startswith("--") or stripped == "":
                continue
            current.append(line)
            if stripped.endswith(";"):
                stmt = "\n".join(current).strip()
                if stmt and stmt != ";":
                    statements.append(stmt)
                current = []

        success = 0
        errors = 0
        for i, stmt in enumerate(statements):
            display = stmt[:80].replace("\n", " ")
            print(f"  [{i+1}/{len(statements)}] {display}...")
            result, status = supa_rpc("exec_sql", {"query": stmt})
            if status in (200, 204):
                print(f"    OK")
                success += 1
            else:
                err = str(result).replace("\n", " ")[:150]
                if "already exists" in err:
                    print(f"    SKIP (already exists)")
                    success += 1
                else:
                    print(f"    FAILED: {err}")
                    errors += 1

        print(f"\nDone: {success} succeeded, {errors} failed")
    else:
        # No exec_sql function - provide instructions
        project_ref = SUPA_URL.split("//")[1].split(".")[0]
        sql_editor_url = f"https://supabase.com/dashboard/project/{project_ref}/sql/new"

        print("=" * 60)
        print("MANUAL STEP REQUIRED")
        print("=" * 60)
        print()
        print("The exec_sql RPC function is not available.")
        print("Please run the migration SQL manually:")
        print()
        print(f"1. Open the Supabase SQL Editor:")
        print(f"   {sql_editor_url}")
        print()
        print(f"2. Copy and paste the contents of:")
        print(f"   {migration_file}")
        print()
        print("3. Click 'Run' to create all tables.")
        print()
        print("Alternatively, run this command to create the exec_sql helper first:")
        print("  Go to SQL Editor and run:")
        print("  CREATE OR REPLACE FUNCTION exec_sql(query text) RETURNS void AS $$")
        print("  BEGIN EXECUTE query; END;")
        print("  $$ LANGUAGE plpgsql SECURITY DEFINER;")
        print()
        print("Then re-run this script.")


if __name__ == "__main__":
    main()
