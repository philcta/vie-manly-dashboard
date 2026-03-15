"""
scheduled_sync.py — Combined sync runner for scheduled execution (every 2 hours).

This script runs SEVEN complementary sync operations:
  1. SMART BACKFILL: Detect and fill any missing date gaps (last 14 days)
  2. LATEST SYNC: Pull the most recent transactions (last 4 hours overlap)
  3. STOCK INTELLIGENCE: Sales velocity, reorder alerts
  4. MEMBER SPENDING PATTERNS: Refresh materialized view
  5. LOYALTY SYNC: Pull latest loyalty balances + events from Square
  6. MEMBER DAILY STATS: Recalculate member_daily_stats from all transactions
  7. WEEKLY KNOWLEDGE BASE: Rebuild weekly pre-computed stats for AI Coach

This approach ensures:
  - No gaps in historical data (smart_backfill catches missed days)
  - Current data is always fresh (latest sync catches recent hours)
  - Inventory & customer data is refreshed each run
  - Loyalty points & events are always up-to-date
  - Member visit/spend stats are always current

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
    parser.add_argument("--skip-loyalty", action="store_true", help="Skip loyalty sync")
    parser.add_argument("--skip-member-stats", action="store_true", help="Skip member daily stats recalculation")
    parser.add_argument("--skip-weekly-stats", action="store_true", help="Skip weekly knowledge base rebuild")
    args = parser.parse_args()

    now = datetime.now(SYDNEY_TZ)
    print("=" * 60)
    print(f"SCHEDULED SYNC — {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("=" * 60)

    results = {
        "started_at": now.isoformat(),
        "backfill": None,
        "latest_sync": None,
        "intelligence": None,
        "spending_patterns": None,
        "loyalty": None,
        "member_stats": None,
        "weekly_stats": None,
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

    # Phase 3: Stock Intelligence (sales velocity, reorder alerts)
    print("\n--- PHASE 3: Stock Intelligence (reorder alerts) ---")
    t0 = time.time()
    try:
        from scripts.sync_inventory_intelligence import run_intelligence_sync
        intel_result = run_intelligence_sync(days_back=90)
        results["intelligence"] = intel_result
        print(f"  Phase 3 completed in {time.time() - t0:.1f}s")
    except Exception as e:
        print(f"  Phase 3 FAILED: {e}")
        results["intelligence"] = {"status": "error", "error": str(e)}

    # Phase 4: Refresh Member Spending Patterns (materialized view)
    print("\n--- PHASE 4: Refresh Member Spending Patterns ---")
    t0 = time.time()
    try:
        SUPA_URL = os.getenv("SUPABASE_URL")
        SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if SUPA_URL and SUPA_KEY:
            import json, urllib.request
            url = f"{SUPA_URL}/rest/v1/rpc/refresh_member_spending_patterns"
            headers = {
                "apikey": SUPA_KEY,
                "Authorization": f"Bearer {SUPA_KEY}",
                "Content-Type": "application/json",
            }
            req = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
            urllib.request.urlopen(req, timeout=60)
            results["spending_patterns"] = {"status": "success"}
            print(f"  Phase 4 completed in {time.time() - t0:.1f}s")
        else:
            results["spending_patterns"] = {"status": "skipped", "reason": "no credentials"}
            print("  Phase 4 SKIPPED (no Supabase credentials)")
    except Exception as e:
        print(f"  Phase 4 FAILED: {e}")
        results["spending_patterns"] = {"status": "error", "error": str(e)}

    # Phase 5: Loyalty Sync (balances + events from Square)
    if not args.skip_loyalty:
        print("\n--- PHASE 5: Loyalty Sync (balances + events) ---")
        t0 = time.time()
        try:
            # 5a: Sync loyalty account balances
            print("  5a. Syncing loyalty balances...")
            from scripts.sync_loyalty import run_loyalty_balances_sync
            loyalty_bal_result = run_loyalty_balances_sync()

            # 5b: Sync loyalty events (accumulate, redeem, create_reward, etc.)
            print("  5b. Syncing loyalty events...")
            from scripts.sync_loyalty_events import run_loyalty_events_sync
            loyalty_evt_result = run_loyalty_events_sync()

            results["loyalty"] = {
                "status": "success",
                "accounts_synced": loyalty_bal_result.get("accounts_synced", 0),
                "events_synced": loyalty_evt_result.get("events_synced", 0),
                "event_types": loyalty_evt_result.get("event_types", {}),
            }
            # Propagate errors
            errors = []
            if loyalty_bal_result.get("status") != "success":
                errors.append(f"balances: {loyalty_bal_result.get('error', 'unknown')}")
            if loyalty_evt_result.get("status") != "success":
                errors.append(f"events: {loyalty_evt_result.get('error', 'unknown')}")
            if errors:
                results["loyalty"]["status"] = "partial"
                results["loyalty"]["errors"] = errors

            print(f"  Phase 5 completed in {time.time() - t0:.1f}s")
        except Exception as e:
            print(f"  Phase 5 FAILED: {e}")
            results["loyalty"] = {"status": "error", "error": str(e)}

    # Phase 6: Member Daily Stats (recalculate from transactions)
    if not args.skip_member_stats:
        print("\n--- PHASE 6: Member Daily Stats (recalculate visits & spend) ---")
        t0 = time.time()
        try:
            from scripts.backfill_member_analytics import run_member_daily_stats_update
            member_result = run_member_daily_stats_update()
            results["member_stats"] = member_result
            print(f"  Phase 6 completed in {time.time() - t0:.1f}s")
        except Exception as e:
            print(f"  Phase 6 FAILED: {e}")
            results["member_stats"] = {"status": "error", "error": str(e)}

    # Phase 7: Weekly Knowledge Base Stats
    if not args.skip_weekly_stats:
        print("\n--- PHASE 7: Weekly Knowledge Base (AI Coach stats) ---")
        t0 = time.time()
        try:
            from scripts.backfill_weekly_stats import run_weekly_stats_update
            weekly_result = run_weekly_stats_update(weeks_back=4)  # Last 4 weeks
            results["weekly_stats"] = weekly_result
            print(f"  Phase 7 completed in {time.time() - t0:.1f}s")
        except Exception as e:
            print(f"  Phase 7 FAILED: {e}")
            results["weekly_stats"] = {"status": "error", "error": str(e)}

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

    if results["loyalty"]:
        lo = results["loyalty"]
        print(f"  Loyalty:  {lo.get('accounts_synced', 0)} balances, {lo.get('events_synced', 0)} events")
        if lo.get("errors"):
            print(f"  Errors:   {lo['errors']}")

    if results["member_stats"]:
        ms = results["member_stats"]
        print(f"  Members:  {ms.get('member_daily_stats', 0)} member_daily_stats rows updated")
        if ms.get("status") != "success":
            print(f"  Status:   {ms.get('status', 'unknown')}")

    if results["weekly_stats"]:
        ws = results["weekly_stats"]
        print(f"  Weekly:   {ws.get('total_rows', 0)} weekly knowledge base rows")
        if ws.get("status") != "success":
            print(f"  Status:   {ws.get('status', 'unknown')}")

    # Phase 8: Refresh Materialized Views (for AI Coach speed)
    print("\n--- PHASE 8: Refresh Materialized Views ---")
    t0 = time.time()
    try:
        SUPA_URL = os.getenv("SUPABASE_URL")
        SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if SUPA_URL and SUPA_KEY:
            import json, urllib.request
            # Refresh top members materialized view
            url = f"{SUPA_URL}/rest/v1/rpc/refresh_top_members_mv"
            headers = {
                "apikey": SUPA_KEY,
                "Authorization": f"Bearer {SUPA_KEY}",
                "Content-Type": "application/json",
            }
            req = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
            urllib.request.urlopen(req, timeout=60)
            print(f"  Phase 8 completed in {time.time() - t0:.1f}s")
        else:
            print("  Phase 8 SKIPPED (no Supabase credentials)")
    except Exception as e:
        print(f"  Phase 8 FAILED: {e}")

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
            if results["loyalty"]:
                statuses.append(results["loyalty"].get("status", "unknown"))
            if results["member_stats"]:
                statuses.append(results["member_stats"].get("status", "unknown"))
            if results["weekly_stats"]:
                statuses.append(results["weekly_stats"].get("status", "unknown"))
            
            overall = "success" if all(s in ("success", "complete") for s in statuses) else "partial"
            
            backfill_filled = len(results["backfill"].get("filled_dates", [])) if results["backfill"] else 0
            latest_tx = results["latest_sync"].get("transactions", 0) if results["latest_sync"] else 0
            loyalty_events = results["loyalty"].get("events_synced", 0) if results["loyalty"] else 0
            member_rows = results["member_stats"].get("member_daily_stats", 0) if results["member_stats"] else 0
            weekly_rows = results["weekly_stats"].get("total_rows", 0) if results["weekly_stats"] else 0
            
            log_entry = {
                "sync_type": "scheduled",
                "started_at": results["started_at"],
                "completed_at": results["completed_at"],
                "records_synced": backfill_filled + latest_tx + loyalty_events + member_rows + weekly_rows,
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
