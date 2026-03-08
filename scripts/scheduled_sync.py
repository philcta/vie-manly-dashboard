"""
scheduled_sync.py — Combined sync runner for scheduled execution (every 2 hours).

This script runs TWO complementary sync operations:
  1. SMART BACKFILL: Detect and fill any missing date gaps (last 14 days)
  2. LATEST SYNC: Pull the most recent transactions (last 4 hours overlap)

This approach ensures:
  - No gaps in historical data (smart_backfill catches missed days)
  - Current data is always fresh (latest sync catches recent hours)
  - Inventory & customer data is refreshed each run

Schedule this with Task Scheduler (Windows) or cron (Linux):
  Every 2 hours:  python scripts/scheduled_sync.py
  
Or with GitHub Actions:
  schedule:
    - cron: '0 */2 * * *'

Usage:
    python scripts/scheduled_sync.py              # Normal scheduled run
    python scripts/scheduled_sync.py --lookback 30 # Check last 30 days for gaps
"""
import sys
import os
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from datetime import datetime
from zoneinfo import ZoneInfo

SYDNEY_TZ = ZoneInfo("Australia/Sydney")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scheduled sync: backfill gaps + fetch latest")
    parser.add_argument("--lookback", type=int, default=14, help="Days to check for gaps (default: 14)")
    parser.add_argument("--skip-backfill", action="store_true", help="Skip gap detection, only do latest sync")
    parser.add_argument("--skip-latest", action="store_true", help="Skip latest sync, only do backfill")
    args = parser.parse_args()

    now = datetime.now(SYDNEY_TZ)
    print("=" * 60)
    print(f"SCHEDULED SYNC — {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("=" * 60)

    results = {
        "started_at": now.isoformat(),
        "backfill": None,
        "latest_sync": None,
    }

    # Phase 1: Smart Backfill (detect & fill gaps)
    if not args.skip_backfill:
        print("\n--- PHASE 1: Smart Backfill (gap detection) ---")
        t0 = time.time()
        try:
            from scripts.smart_backfill import run_smart_backfill
            backfill_result = run_smart_backfill(
                lookback_days=args.lookback,
                include_today=True,
            )
            results["backfill"] = backfill_result
            print(f"  Phase 1 completed in {time.time() - t0:.1f}s")
        except Exception as e:
            print(f"  Phase 1 FAILED: {e}")
            results["backfill"] = {"status": "error", "error": str(e)}

    # Phase 2: Latest Sync (recent hours + inventory + customers)
    if not args.skip_latest:
        print("\n--- PHASE 2: Latest Sync (recent data + inventory + customers) ---")
        t0 = time.time()
        try:
            from services.square_sync import run_full_sync
            latest_result = run_full_sync(hours_back=4)  # 4 hour overlap
            results["latest_sync"] = latest_result
            print(f"  Phase 2 completed in {time.time() - t0:.1f}s")
        except Exception as e:
            print(f"  Phase 2 FAILED: {e}")
            results["latest_sync"] = {"status": "error", "error": str(e)}

    # Summary
    completed = datetime.now(SYDNEY_TZ)
    results["completed_at"] = completed.isoformat()
    elapsed = (completed - now).total_seconds()

    print(f"\n{'=' * 60}")
    print(f"SCHEDULED SYNC COMPLETE ({elapsed:.1f}s)")

    if results["backfill"]:
        bf = results["backfill"]
        if bf.get("status") == "complete":
            print("  Backfill: No gaps found (data complete)")
        elif bf.get("status") == "success":
            print(f"  Backfill: Filled {len(bf.get('filled_dates', []))} gap(s)")
            print(f"    Dates: {', '.join(bf.get('filled_dates', []))}")
            print(f"    Rows:  {bf.get('transactions', 0)} tx, {bf.get('summaries', 0)} summaries")
        else:
            print(f"  Backfill: {bf.get('status', 'unknown')}")

    if results["latest_sync"]:
        ls = results["latest_sync"]
        print(f"  Latest:   {ls.get('transactions', 0)} tx, {ls.get('inventory', 0)} inv, {ls.get('customers', 0)} cust")
        print(f"  Status:   {ls.get('status', 'unknown')}")
        if ls.get("errors"):
            print(f"  Errors:   {ls['errors']}")

    print(f"{'=' * 60}")

    # Log to Supabase
    try:
        SUPA_URL = os.getenv("SUPABASE_URL")
        SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if SUPA_URL and SUPA_KEY:
            import json, urllib.request
            url = f"{SUPA_URL}/rest/v1/sync_log"
            headers = {
                "apikey": SUPA_KEY,
                "Authorization": f"Bearer {SUPA_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            }
            # Determine overall status
            statuses = []
            if results["backfill"]:
                statuses.append(results["backfill"].get("status", "unknown"))
            if results["latest_sync"]:
                statuses.append(results["latest_sync"].get("status", "unknown"))
            
            overall = "success" if all(s in ("success", "complete") for s in statuses) else "partial"
            
            backfill_filled = len(results["backfill"].get("filled_dates", [])) if results["backfill"] else 0
            latest_tx = results["latest_sync"].get("transactions", 0) if results["latest_sync"] else 0
            
            log_entry = {
                "sync_type": "scheduled",
                "started_at": results["started_at"],
                "completed_at": results["completed_at"],
                "records_synced": backfill_filled + latest_tx,
                "status": overall,
                "error_message": None,
            }
            body = json.dumps([log_entry]).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            urllib.request.urlopen(req, timeout=30)
    except Exception:
        pass  # Don't fail the whole sync if logging fails

    return results


if __name__ == "__main__":
    main()
