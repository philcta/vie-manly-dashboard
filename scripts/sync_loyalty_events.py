"""
Sync Square Loyalty Events → Supabase loyalty_events table.

Uses Square SearchLoyaltyEvents API to pull the full event ledger:
  - ACCUMULATE_POINTS (earned from purchases)
  - REDEEM_REWARD (points spent on rewards)
  - CREATE_REWARD / DELETE_REWARD
  - ADJUST_POINTS (manual adjustments)
  - EXPIRE_POINTS

Can be run standalone OR imported by scheduled_sync:
    python scripts/sync_loyalty_events.py
    from scripts.sync_loyalty_events import run_loyalty_events_sync
"""
import sys, os, json, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Sydney timezone offset (AEST +10, AEDT +11)
SYDNEY_OFFSET_HOURS = 11  # March is AEDT


def utc_to_sydney_date(ts_str: str) -> str:
    """Convert UTC ISO timestamp to Sydney local date string YYYY-MM-DD."""
    try:
        # Parse ISO 8601 — handles both 'Z' and '+00:00'
        ts_str = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # Offset to Sydney
        sydney_dt = dt + timedelta(hours=SYDNEY_OFFSET_HOURS)
        return sydney_dt.strftime("%Y-%m-%d")
    except Exception:
        return ts_str[:10]  # fallback


def extract_points(event: dict) -> int:
    """Extract net points change from a loyalty event."""
    etype = event.get("type", "")

    if etype == "ACCUMULATE_POINTS":
        meta = event.get("accumulate_points", {})
        return meta.get("points", 0)

    elif etype == "ADJUST_POINTS":
        meta = event.get("adjust_points", {})
        return meta.get("points", 0)  # can be negative

    elif etype == "REDEEM_REWARD":
        meta = event.get("redeem_reward", {})
        return -(meta.get("points", 0))  # negative = spent

    elif etype == "CREATE_REWARD":
        meta = event.get("create_reward", {})
        return -(meta.get("points", 0))

    elif etype == "DELETE_REWARD":
        meta = event.get("delete_reward", {})
        return meta.get("points", 0)  # returned

    elif etype == "EXPIRE_POINTS":
        meta = event.get("expire_points", {})
        return -(meta.get("points", 0))

    return 0


def extract_order_id(event: dict) -> str | None:
    """Extract order_id if present."""
    etype = event.get("type", "")
    if etype == "ACCUMULATE_POINTS":
        return event.get("accumulate_points", {}).get("order_id")
    return None


def run_loyalty_events_sync():
    """
    Sync all loyalty events from Square → Supabase loyalty_events.
    
    Returns:
        dict with status, events_synced count, and event_type breakdown
    """
    SQUARE_TOKEN = os.getenv("SQUARE_ACCESS_TOKEN")
    SUPA_URL = os.getenv("SUPABASE_URL")
    SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    sq_headers = {
        "Authorization": "Bearer " + SQUARE_TOKEN,
        "Content-Type": "application/json",
        "Square-Version": "2025-01-23",
    }
    supa_headers = {
        "apikey": SUPA_KEY,
        "Authorization": "Bearer " + SUPA_KEY,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    SQ_BASE = "https://connect.squareup.com"

    result = {"status": "success", "events_synced": 0, "event_types": {}}

    # ─── 1. Fetch ALL loyalty events from Square ───────────────────
    print("  📥 Fetching loyalty events from Square...")
    all_events = []
    cursor = None
    page = 0

    while True:
        body = {"limit": 30}
        if cursor:
            body["cursor"] = cursor

        req = urllib.request.Request(
            SQ_BASE + "/v2/loyalty/events/search",
            data=json.dumps(body).encode(),
            headers=sq_headers,
            method="POST",
        )

        try:
            resp = urllib.request.urlopen(req)
            data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            print(f"  ❌ Square API error: {e.code} — {error_body[:500]}")
            result["status"] = "error"
            result["error"] = f"Square API error: {e.code}"
            return result

        events = data.get("events", [])
        all_events.extend(events)
        page += 1
        if page % 20 == 0:
            print(f"    Page {page}: {len(all_events)} events so far...")

        cursor = data.get("cursor")
        if not cursor:
            break

    print(f"  ✅ Fetched {len(all_events)} loyalty events total")

    # Count by type
    type_counts = Counter(e.get("type", "UNKNOWN") for e in all_events)
    result["event_types"] = dict(type_counts)
    for etype, count in type_counts.most_common():
        print(f"     {etype}: {count}")

    # ─── 2. Build loyalty_account_id → customer_id map ──────────────
    print("  🔄 Fetching loyalty account → customer mapping...")
    map_req = urllib.request.Request(
        f"{SUPA_URL}/rest/v1/member_loyalty?select=loyalty_account_id,customer_id",
        headers={**supa_headers, "Prefer": ""},
    )
    map_resp = urllib.request.urlopen(map_req)
    loyalty_map_data = json.loads(map_resp.read())
    account_to_customer = {
        r["loyalty_account_id"]: r["customer_id"] for r in loyalty_map_data
    }
    print(f"  Mapped {len(account_to_customer)} loyalty accounts to customers")

    # ─── 3. Transform to rows ──────────────────────────────────────
    rows = []
    for e in all_events:
        event_id = e.get("id", "")
        loyalty_account_id = e.get("loyalty_account_id", "")
        customer_id = account_to_customer.get(loyalty_account_id)
        event_type = e.get("type", "OTHER")
        points = extract_points(e)
        created_at = e.get("created_at", "")
        event_date = utc_to_sydney_date(created_at)
        order_id = extract_order_id(e)
        location_id = e.get("location_id")

        rows.append(
            {
                "event_id": event_id,
                "loyalty_account_id": loyalty_account_id,
                "customer_id": customer_id,
                "event_type": event_type,
                "points": points,
                "order_id": order_id,
                "location_id": location_id,
                "event_date": event_date,
                "event_timestamp": created_at,
            }
        )

    print(f"  Prepared {len(rows)} rows")

    # ─── 4. Upsert into Supabase ───────────────────────────────────
    print("  📤 Upserting to Supabase loyalty_events...")
    BATCH_SIZE = 200
    total_upserted = 0

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        req = urllib.request.Request(
            f"{SUPA_URL}/rest/v1/loyalty_events?on_conflict=event_id",
            data=json.dumps(batch).encode(),
            headers=supa_headers,
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req)
            total_upserted += len(batch)
            if (i // BATCH_SIZE + 1) % 10 == 0:
                print(f"    Batch {i // BATCH_SIZE + 1}: {total_upserted} rows upserted...")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            print(f"  ❌ Batch error: {error_body[:500]}")

    result["events_synced"] = total_upserted
    print(f"  ✅ Loyalty events synced: {total_upserted} events")
    return result


if __name__ == "__main__":
    print("📥 Syncing loyalty events...")
    result = run_loyalty_events_sync()
    print(f"\n✅ Done! Synced: {result['events_synced']} events")
    for etype, count in result.get("event_types", {}).items():
        print(f"   {etype}: {count}")
