"""
Sync Square Loyalty Events → Supabase loyalty_events table.

Uses Square SearchLoyaltyEvents API to pull the full event ledger:
  - ACCUMULATE_POINTS (earned from purchases)
  - REDEEM_REWARD (points spent on rewards)
  - CREATE_REWARD / DELETE_REWARD
  - ADJUST_POINTS (manual adjustments)
  - EXPIRE_POINTS

Run:  python scripts/sync_loyalty_events.py
"""
import sys, os, json, urllib.request, urllib.error
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv

load_dotenv()

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
        from datetime import timedelta

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


# ─── 1. Fetch ALL loyalty events from Square ───────────────────

print("📥 Fetching loyalty events from Square...")
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
        break

    events = data.get("events", [])
    all_events.extend(events)
    page += 1
    print(f"  Page {page}: {len(events)} events (total: {len(all_events)})")

    cursor = data.get("cursor")
    if not cursor:
        break

print(f"\n✅ Fetched {len(all_events)} loyalty events total")

# Count by type
from collections import Counter

type_counts = Counter(e.get("type", "UNKNOWN") for e in all_events)
for etype, count in type_counts.most_common():
    print(f"   {etype}: {count}")

# ─── 2. Transform to rows ──────────────────────────────────────

print("\n🔄 Transforming events...")

# Build loyalty_account_id → customer_id map from member_loyalty
print("  Fetching loyalty account → customer mapping...")
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

# ─── 3. Upsert into Supabase ───────────────────────────────────

print("\n📤 Upserting to Supabase loyalty_events...")
BATCH_SIZE = 200
total_upserted = 0

for i in range(0, len(rows), BATCH_SIZE):
    batch = rows[i : i + BATCH_SIZE]
    req = urllib.request.Request(
        f"{SUPA_URL}/rest/v1/loyalty_events",
        data=json.dumps(batch).encode(),
        headers=supa_headers,
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req)
        total_upserted += len(batch)
        print(
            f"  ✅ Batch {i // BATCH_SIZE + 1}: {len(batch)} rows (total: {total_upserted})"
        )
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  ❌ Batch error: {error_body[:500]}")

# ─── 4. Verify ──────────────────────────────────────────────────

req = urllib.request.Request(
    f"{SUPA_URL}/rest/v1/loyalty_events?select=count",
    headers={**supa_headers, "Prefer": "count=exact", "Range-Unit": "items", "Range": "0-0"},
)
resp = urllib.request.urlopen(req)
count_header = resp.headers.get("Content-Range", "?")
print(f"\n✅ Done! Supabase loyalty_events: {count_header}")
print(f"   Total upserted: {total_upserted}")

# Show date range
req2 = urllib.request.Request(
    f"{SUPA_URL}/rest/v1/loyalty_events?select=event_date&order=event_date.asc&limit=1",
    headers={**supa_headers, "Prefer": ""},
)
resp2 = urllib.request.urlopen(req2)
first = json.loads(resp2.read())

req3 = urllib.request.Request(
    f"{SUPA_URL}/rest/v1/loyalty_events?select=event_date&order=event_date.desc&limit=1",
    headers={**supa_headers, "Prefer": ""},
)
resp3 = urllib.request.urlopen(req3)
last = json.loads(resp3.read())

if first and last:
    print(f"   Date range: {first[0]['event_date']} → {last[0]['event_date']}")
