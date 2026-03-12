"""
fix_duplicates.py — Clean up duplicate transactions created by row_key mismatch.

BUG: smart_backfill.py used a plain-concatenated row_key, while square_sync.py 
used MD5 hashes, and rebuild_from_square.py used {order_id}-LI-{idx}.
This caused the same transaction to be inserted multiple times with different
row_key values, bypassing the upsert deduplication.

FIX STRATEGY:
1. Delete ALL transactions for affected dates (March 11, 2026 onwards)
2. Delete daily_item_summary for those dates  
3. Delete daily_store_stats for those dates
4. Re-sync those dates from Square using the FIXED smart_backfill.py
5. Recalculate daily_store_stats for those dates

Usage:
    python scripts/fix_duplicates.py              # Fix March 11 onwards
    python scripts/fix_duplicates.py --from 2026-01-01  # Fix from specific date
    python scripts/fix_duplicates.py --full        # Full rebuild from Aug 2025
"""
import sys
import os
import json
import time
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SYDNEY_TZ = ZoneInfo("Australia/Sydney")

SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
SUPA_HEADERS = {
    "apikey": SUPA_KEY,
    "Authorization": f"Bearer {SUPA_KEY}",
    "Content-Type": "application/json",
}


def supa_delete(endpoint):
    """DELETE from Supabase REST API."""
    url = f"{SUPA_URL}/rest/v1/{endpoint}"
    req = urllib.request.Request(url, headers=SUPA_HEADERS, method="DELETE")
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        return resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  DELETE error {e.code}: {body[:300]}")
        return e.code


def supa_count(table, date_filter):
    """Count rows in a table for a date filter."""
    url = f"{SUPA_URL}/rest/v1/{table}?select=id&{date_filter}&limit=0"
    headers = dict(SUPA_HEADERS)
    headers["Prefer"] = "count=exact"
    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        cr = resp.headers.get("Content-Range", "*/0")
        total = cr.split("/")[-1]
        return int(total) if total != "*" else 0
    except Exception:
        return -1


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fix duplicate transactions")
    parser.add_argument("--from", dest="from_date", default="2026-03-11",
                        help="Start date to fix (default: 2026-03-11)")
    parser.add_argument("--full", action="store_true",
                        help="Full rebuild from store opening (Aug 2025)")
    args = parser.parse_args()

    if args.full:
        start_date = "2025-08-01"
    else:
        start_date = args.from_date

    today = datetime.now(SYDNEY_TZ).strftime("%Y-%m-%d")
    
    print("=" * 60)
    print(f"FIX DUPLICATES — {datetime.now(SYDNEY_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  Fixing dates: {start_date} → {today}")
    print("=" * 60)

    if not all([SUPA_URL, SUPA_KEY]):
        print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        return

    # ── Step 1: Count existing rows (for before/after comparison) ──
    print(f"\n--- STEP 1: Counting existing rows for dates >= {start_date} ---")
    
    tx_count_before = supa_count("transactions", f"date=gte.{start_date}")
    dis_count_before = supa_count("daily_item_summary", f"date=gte.{start_date}")
    dss_count_before = supa_count("daily_store_stats", f"date=gte.{start_date}")
    
    print(f"  transactions:       {tx_count_before:,} rows")
    print(f"  daily_item_summary: {dis_count_before:,} rows")
    print(f"  daily_store_stats:  {dss_count_before:,} rows")

    # ── Step 2: Delete all data for affected dates ──
    print(f"\n--- STEP 2: Deleting data for dates >= {start_date} ---")
    
    print("  Deleting transactions...", end=" ", flush=True)
    status = supa_delete(f"transactions?date=gte.{start_date}")
    print(f"status={status}")
    
    print("  Deleting daily_item_summary...", end=" ", flush=True)
    status = supa_delete(f"daily_item_summary?date=gte.{start_date}")
    print(f"status={status}")
    
    print("  Deleting daily_store_stats...", end=" ", flush=True)
    status = supa_delete(f"daily_store_stats?date=gte.{start_date}")
    print(f"status={status}")

    # Verify deletion
    time.sleep(1)
    tx_after_delete = supa_count("transactions", f"date=gte.{start_date}")
    print(f"\n  Verification: {tx_count_before:,} → {tx_after_delete:,} transactions")
    
    if tx_after_delete > 0:
        print(f"  WARNING: {tx_after_delete} rows remain. Retrying delete...")
        supa_delete(f"transactions?date=gte.{start_date}")
        time.sleep(2)
        tx_after_delete2 = supa_count("transactions", f"date=gte.{start_date}")
        print(f"  After retry: {tx_after_delete2:,} transactions remain")

    # ── Step 3: Re-sync from Square using FIXED smart_backfill ──
    print(f"\n--- STEP 3: Re-syncing from Square ({start_date} → {today}) ---")
    t0 = time.time()
    
    from scripts.smart_backfill import run_smart_backfill
    
    result = run_smart_backfill(
        from_date=start_date,
        include_today=True,
    )
    
    elapsed = time.time() - t0
    print(f"\n  Smart backfill completed in {elapsed:.1f}s")
    if result.get("status") == "success":
        print(f"  Filled: {len(result.get('filled_dates', []))} dates")
        print(f"  Transactions: {result.get('transactions', 0):,} rows")
        print(f"  Summaries: {result.get('summaries', 0):,} rows")
    else:
        print(f"  Status: {result.get('status')}")

    # ── Step 4: Recalculate daily_store_stats for affected dates ──
    print(f"\n--- STEP 4: Recalculating daily_store_stats ---")
    t0 = time.time()
    
    try:
        recalc_daily_store_stats(start_date, today)
    except Exception as e:
        print(f"  ERROR: {e}")
    
    elapsed = time.time() - t0
    print(f"  Completed in {elapsed:.1f}s")

    # ── Step 5: Verify final counts ──
    print(f"\n--- STEP 5: Final verification ---")
    time.sleep(1)
    
    tx_count_after = supa_count("transactions", f"date=gte.{start_date}")
    dis_count_after = supa_count("daily_item_summary", f"date=gte.{start_date}")
    dss_count_after = supa_count("daily_store_stats", f"date=gte.{start_date}")
    
    print(f"  transactions:       {tx_count_before:>8,} → {tx_count_after:>8,} (was {tx_count_before:,})")
    print(f"  daily_item_summary: {dis_count_before:>8,} → {dis_count_after:>8,}")
    print(f"  daily_store_stats:  {dss_count_before:>8,} → {dss_count_after:>8,}")
    
    if tx_count_before > 0 and tx_count_after > 0:
        ratio = tx_count_before / tx_count_after
        if ratio > 1.3:
            print(f"\n  ✅ Removed ~{ratio:.1f}x duplicate data ({tx_count_before - tx_count_after:,} excess rows)")
        else:
            print(f"\n  ✅ Data looks clean (ratio: {ratio:.2f}x)")

    print(f"\n{'=' * 60}")
    print("FIX DUPLICATES COMPLETE")
    print(f"{'=' * 60}")


def recalc_daily_store_stats(start_date, end_date):
    """Recalculate daily_store_stats from transactions for a date range."""
    from collections import defaultdict
    
    # Fetch all transactions for the date range
    print(f"  Loading transactions {start_date} → {end_date}...")
    
    all_rows = []
    offset = 0
    page_size = 10000
    
    while True:
        url = (
            f"{SUPA_URL}/rest/v1/transactions"
            f"?select=transaction_id,date,net_sales,gross_sales,qty,customer_id"
            f"&date=gte.{start_date}&date=lte.{end_date}"
            f"&limit={page_size}&offset={offset}"
        )
        req = urllib.request.Request(url, headers=SUPA_HEADERS)
        resp = urllib.request.urlopen(req, timeout=60)
        batch = json.loads(resp.read())
        
        if not batch:
            break
        all_rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    
    print(f"  Loaded {len(all_rows):,} transactions")
    
    if not all_rows:
        return
    
    # Group by date
    by_date = defaultdict(list)
    for r in all_rows:
        by_date[r["date"]].append(r)
    
    records = []
    for date_str, day_rows in sorted(by_date.items()):
        tx_ids = set()
        member_tx_ids = set()
        total_net = 0
        total_gross = 0
        member_net = 0
        nonmember_net = 0
        total_items = 0
        member_items = 0
        nonmember_items = 0
        member_ids = set()
        
        for r in day_rows:
            tid = r.get("transaction_id", "")
            cid = r.get("customer_id") or ""
            ns = float(r.get("net_sales", 0) or 0)
            gs = float(r.get("gross_sales", 0) or 0)
            qty = float(r.get("qty", 0) or 0)
            
            tx_ids.add(tid)
            total_net += ns
            total_gross += gs
            total_items += qty
            
            if cid.strip():
                member_tx_ids.add(tid)
                member_net += ns
                member_items += qty
                member_ids.add(cid)
            else:
                nonmember_net += ns
                nonmember_items += qty
        
        total_tx = len(tx_ids)
        member_tx = len(member_tx_ids)
        nonmember_tx = total_tx - member_tx
        
        records.append({
            "date": date_str,
            "total_transactions": total_tx,
            "total_net_sales": round(total_net, 2),
            "total_gross_sales": round(total_gross, 2),
            "total_items": int(total_items),
            "total_unique_customers": len(member_ids),
            "member_transactions": member_tx,
            "member_net_sales": round(member_net, 2),
            "member_items": int(member_items),
            "member_unique_customers": len(member_ids),
            "non_member_transactions": nonmember_tx,
            "non_member_net_sales": round(nonmember_net, 2),
            "non_member_items": int(nonmember_items),
            "member_tx_ratio": round(member_tx / total_tx, 4) if total_tx > 0 else 0,
            "member_sales_ratio": round(member_net / total_net, 4) if total_net > 0 else 0,
            "member_items_ratio": round(member_items / total_items, 4) if total_items > 0 else 0,
        })
    
    # Upsert to daily_store_stats
    print(f"  Upserting {len(records)} daily_store_stats records...")
    
    for i in range(0, len(records), 200):
        batch = records[i:i+200]
        url = f"{SUPA_URL}/rest/v1/daily_store_stats?on_conflict=date"
        headers = dict(SUPA_HEADERS)
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        body = json.dumps(batch).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError as e:
            err = e.read().decode()
            print(f"  Upsert error: {err[:300]}")
    
    print(f"  ✅ daily_store_stats updated for {len(records)} dates")


if __name__ == "__main__":
    main()
