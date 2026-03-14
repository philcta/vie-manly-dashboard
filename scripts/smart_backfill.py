"""
smart_backfill.py — Detect and fill missing date gaps in Supabase data.

Unlike run_smart_sync (which only looks at the latest timestamp),
this script:
  1. Queries all distinct dates that SHOULD have data (store open days)
  2. Compares against dates that DO have data in daily_store_stats
  3. Fetches from Square API only for the missing days
  4. Updates daily_item_summary AND daily_store_stats for those days

Designed to run on a schedule (e.g. every 2 hours) and be idempotent.

Usage:
    python scripts/smart_backfill.py                 # Auto-detect & fill gaps
    python scripts/smart_backfill.py --from 2026-03-01  # Fill from specific date
    python scripts/smart_backfill.py --days 14          # Check last N days (default: 14)
"""
import sys
import os
import json
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict

SYDNEY_TZ = ZoneInfo("Australia/Sydney")

# Square API
TOKEN = os.getenv("SQUARE_ACCESS_TOKEN")
LOCATION_ID = os.getenv("SQUARE_LOCATION_ID")

SQ_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Square-Version": "2024-01-18",
}

# Supabase
SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
SUPA_HEADERS = {
    "apikey": SUPA_KEY,
    "Authorization": f"Bearer {SUPA_KEY}",
    "Content-Type": "application/json",
}


# ============================================
# Supabase Helpers
# ============================================

def supa_get(endpoint):
    """GET from Supabase REST API."""
    url = f"{SUPA_URL}/rest/v1/{endpoint}"
    req = urllib.request.Request(url, headers=SUPA_HEADERS)
    resp = urllib.request.urlopen(req, timeout=60)
    return json.loads(resp.read())


def supa_post(endpoint, data, extra_headers=None):
    """POST to Supabase REST API (upsert)."""
    url = f"{SUPA_URL}/rest/v1/{endpoint}"
    hdrs = dict(SUPA_HEADERS)
    if extra_headers:
        hdrs.update(extra_headers)
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    resp = urllib.request.urlopen(req, timeout=120)
    return resp.status


# ============================================
# Square API Helpers
# ============================================

def sq_request(endpoint, body=None, method="POST"):
    """Make a request to Square API."""
    url = f"https://connect.squareup.com/v2/{endpoint}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=SQ_HEADERS, method=method)
    resp = urllib.request.urlopen(req, timeout=60)
    return json.loads(resp.read())


def build_catalog_map():
    """Build item_name -> category_name map from Square Catalog API."""
    catalog_map = {}
    cursor = None
    cat_names = {}

    while True:
        params = "types=CATEGORY"
        if cursor:
            params += f"&cursor={cursor}"
        url = f"https://connect.squareup.com/v2/catalog/list?{params}"
        req = urllib.request.Request(url, headers=SQ_HEADERS)
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read())

        for obj in data.get("objects", []):
            cat_data = obj.get("category_data", {})
            cat_names[obj["id"]] = cat_data.get("name", "")

        cursor = data.get("cursor")
        if not cursor:
            break

    # Now get items
    cursor = None
    while True:
        params = "types=ITEM"
        if cursor:
            params += f"&cursor={cursor}"
        url = f"https://connect.squareup.com/v2/catalog/list?{params}"
        req = urllib.request.Request(url, headers=SQ_HEADERS)
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read())

        for obj in data.get("objects", []):
            item_data = obj.get("item_data", {})
            name = item_data.get("name", "")
            # Use reporting_category
            rep_cat = item_data.get("reporting_category", {})
            cat_id = rep_cat.get("id", "")
            cat_name = cat_names.get(cat_id, "")

            if name:
                catalog_map[name.lower()] = cat_name

        cursor = data.get("cursor")
        if not cursor:
            break

    print(f"  Catalog map: {len(catalog_map)} items, {len(cat_names)} categories")
    return catalog_map


def lookup_category(display_name, item_name, catalog_map):
    """Look up category from catalog map."""
    key = display_name.lower().strip()
    if key in catalog_map:
        return catalog_map[key]
    key2 = item_name.lower().strip()
    if key2 in catalog_map:
        return catalog_map[key2]
    return ""


# ============================================
# Gap Detection
# ============================================

# Days the store is known to be closed (add public holidays, etc.)
KNOWN_CLOSED_DAYS = set()  # e.g. {"2026-12-25", "2026-01-01"}

# Store is normally open every day (7 days/week)
# If your store is closed on specific weekdays, set them here (0=Mon, 6=Sun)
CLOSED_WEEKDAYS = set()  # e.g. {6} for closed on Sundays


def detect_missing_dates(lookback_days=14, from_date=None):
    """
    Detect dates that should have data but don't.

    Returns a list of date strings (YYYY-MM-DD) that are missing.
    """
    today = datetime.now(SYDNEY_TZ).date()

    if from_date:
        start = datetime.strptime(from_date, "%Y-%m-%d").date()
    else:
        start = today - timedelta(days=lookback_days)

    # Don't include today (it's still in progress)
    end = today - timedelta(days=1)

    # Get existing dates from daily_store_stats
    existing = supa_get(
        f"daily_store_stats?select=date&date=gte.{start.isoformat()}&date=lte.{end.isoformat()}"
    )
    existing_dates = {row["date"] for row in existing}

    # Also check transactions table for dates
    tx_dates_raw = supa_get(
        f"transactions?select=date&date=gte.{start.isoformat()}&date=lte.{end.isoformat()}&limit=1&order=date"
    )

    # Build expected dates
    expected = []
    current = start
    while current <= end:
        date_str = current.isoformat()
        weekday = current.weekday()

        # Skip known closed days
        if date_str not in KNOWN_CLOSED_DAYS and weekday not in CLOSED_WEEKDAYS:
            expected.append(date_str)

        current += timedelta(days=1)

    # Missing = expected minus existing
    missing = [d for d in expected if d not in existing_dates]

    return sorted(missing)


# ============================================
# Fetch Orders for a Single Date
# ============================================

def fetch_orders_for_date(date_str, catalog_map):
    """
    Fetch all completed orders from Square for a single date (Sydney time).
    Returns list of transaction row dicts ready for Supabase.
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    start_dt = dt.replace(hour=0, minute=0, second=0, tzinfo=SYDNEY_TZ)
    end_dt = dt.replace(hour=23, minute=59, second=59, tzinfo=SYDNEY_TZ)

    all_orders = []
    cursor = None

    while True:
        body = {
            "location_ids": [LOCATION_ID],
            "query": {
                "filter": {
                    "date_time_filter": {
                        "closed_at": {
                            "start_at": start_dt.isoformat(),
                            "end_at": end_dt.isoformat(),
                        }
                    },
                    "state_filter": {"states": ["COMPLETED"]},
                },
                "sort": {"sort_field": "CLOSED_AT", "sort_order": "ASC"},
            },
            "limit": 500,
        }
        if cursor:
            body["cursor"] = cursor

        data = sq_request("orders/search", body)

        if "errors" in data:
            print(f"  Square API error for {date_str}: {data['errors']}")
            break

        orders = data.get("orders", [])
        all_orders.extend(orders)

        cursor = data.get("cursor")
        if not cursor:
            break

    # Process orders into transaction rows
    rows = []
    matched = 0
    unmatched = 0

    for order in all_orders:
        order_id = order.get("id", "")
        created_at = order.get("closed_at") or order.get("created_at", "")
        customer_id = order.get("customer_id", "")

        # Parse tenders
        tenders = order.get("tenders", [])
        card_brand = ""
        pan_suffix = ""
        if tenders:
            cd = tenders[0].get("card_details", {})
            if cd:
                card = cd.get("card", {})
                card_brand = card.get("card_brand", "")
                pan_suffix = card.get("last_4", "")

        for idx, item in enumerate(order.get("line_items", [])):
            item_name = item.get("name", "")
            qty = float(item.get("quantity", "0"))

            base_cents = int(item.get("base_price_money", {}).get("amount", 0))
            total_cents = int(item.get("total_money", {}).get("amount", 0))
            tax_cents = int(item.get("total_tax_money", {}).get("amount", 0))
            disc_cents = int(item.get("total_discount_money", {}).get("amount", 0))

            base_price = base_cents / 100
            gross_sales = base_price * qty
            net_sales = (total_cents - tax_cents) / 100
            tax = tax_cents / 100
            discounts = disc_cents / 100

            # Modifiers
            mods = item.get("modifiers", [])
            mod_names = [m.get("name", "") for m in mods]
            mod_str = ", ".join(mod_names) if mod_names else ""

            # Variation
            var_name = item.get("variation_name", "")
            display_name = f"{item_name} - {var_name}" if var_name and var_name != item_name else item_name

            # Category
            category = lookup_category(display_name, item_name, catalog_map)
            if category:
                matched += 1
            else:
                unmatched += 1

            # Parse datetime to Sydney (use closed_at to match Square dashboard)
            try:
                dt_utc = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                dt_local = dt_utc.astimezone(SYDNEY_TZ)
                local_date = dt_local.strftime("%Y-%m-%d")
                local_time = dt_local.strftime("%H:%M:%S")
                local_datetime = dt_local.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                local_date = date_str
                local_time = ""
                local_datetime = ""

            # Build row_key for dedup — MUST match rebuild_from_square.py format
            # Format: "{order_id}-LI-{line_item_index}"
            row_key = f"{order_id}-LI-{idx}"

            rows.append({
                "transaction_id": order_id,
                "datetime": local_datetime,
                "date": local_date,
                "time": local_time,
                "time_zone": "Australia/Sydney",
                "item": display_name,
                "category": category,
                "qty": qty,
                "net_sales": round(net_sales, 2),
                "gross_sales": round(gross_sales, 2),
                "discounts": round(discounts, 2),
                "tax": round(tax, 2),
                "customer_id": customer_id,
                "card_brand": card_brand,
                "pan_suffix": pan_suffix,
                "modifiers_applied": mod_str,
                "row_key": row_key,
            })

    # Deduplicate by row_key
    seen = set()
    unique_rows = []
    for r in rows:
        if r["row_key"] not in seen:
            seen.add(r["row_key"])
            unique_rows.append(r)

    return unique_rows, matched, unmatched


# ============================================
# Daily Summary Builders
# ============================================

def build_daily_item_summary(rows):
    """Aggregate transaction rows into daily_item_summary records."""
    summaries = defaultdict(lambda: {
        "total_qty": 0, "total_net_sales": 0, "total_gross_sales": 0,
        "total_discounts": 0, "total_tax": 0, "transactions": set(),
    })

    for r in rows:
        key = (r["date"], r["category"], r["item"])
        s = summaries[key]
        s["total_qty"] += r["qty"]
        s["total_net_sales"] += r["net_sales"]
        s["total_gross_sales"] += r["gross_sales"]
        s["total_discounts"] += r["discounts"]
        s["total_tax"] += r["tax"]
        s["transactions"].add(r["transaction_id"])

    records = []
    for (d, c, i), s in summaries.items():
        records.append({
            "date": d, "category": c, "item": i,
            "total_qty": round(s["total_qty"], 2),
            "total_net_sales": round(s["total_net_sales"], 2),
            "total_gross_sales": round(s["total_gross_sales"], 2),
            "total_discounts": round(s["total_discounts"], 2),
            "total_tax": round(s["total_tax"], 2),
            "transaction_count": len(s["transactions"]),
        })
    return records


def build_daily_store_stats(rows):
    """Aggregate transaction rows into daily_store_stats records."""
    by_date = defaultdict(list)
    for r in rows:
        by_date[r["date"]].append(r)

    records = []
    for date_str, day_rows in by_date.items():
        tx_ids = set()
        member_tx_ids = set()
        total_net = 0
        member_net = 0
        nonmember_net = 0
        total_items = 0
        member_ids = set()

        for r in day_rows:
            tx_ids.add(r["transaction_id"])
            total_net += r["net_sales"]
            total_items += r["qty"]

            if r.get("customer_id"):
                member_tx_ids.add(r["transaction_id"])
                member_net += r["net_sales"]
                member_ids.add(r["customer_id"])
            else:
                nonmember_net += r["net_sales"]

        total_tx = len(tx_ids)
        member_tx = len(member_tx_ids)
        nonmember_tx = total_tx - member_tx

        records.append({
            "date": date_str,
            "total_transactions": total_tx,
            "total_net_sales": round(total_net, 2),
            "total_items": int(total_items),
            "total_unique_customers": len(member_ids),
            "member_transactions": member_tx,
            "member_net_sales": round(member_net, 2),
            "member_items": 0,  # can be refined later
            "member_unique_customers": len(member_ids),
            "non_member_transactions": nonmember_tx,
            "non_member_net_sales": round(nonmember_net, 2),
            "non_member_items": 0,
            "member_tx_ratio": round(member_tx / total_tx, 4) if total_tx > 0 else 0,
            "member_sales_ratio": round(member_net / total_net, 4) if total_net > 0 else 0,
            "member_items_ratio": 0,
        })
    return records


def build_daily_category_stats(rows):
    """Aggregate transaction rows into daily_category_stats records.
    Resolves category -> side (Cafe/Retail) from the category_mappings table."""
    # Fetch category_mappings from Supabase
    try:
        mappings = supa_get("category_mappings?select=category,side")
        side_map = {m["category"]: m["side"] for m in mappings}
    except Exception:
        side_map = {}

    # Aggregate by date + category
    agg = defaultdict(lambda: {"net": 0, "gross": 0, "qty": 0, "txns": set()})
    for r in rows:
        cat = r.get("category", "") or "(Uncategorized)"
        key = (r["date"], cat)
        a = agg[key]
        a["net"] += r["net_sales"]
        a["gross"] += r["gross_sales"]
        a["qty"] += r["qty"]
        a["txns"].add(r["transaction_id"])

    records = []
    for (d, cat), a in agg.items():
        records.append({
            "date": d,
            "category": cat,
            "side": side_map.get(cat, "Retail"),
            "total_net_sales": round(a["net"], 2),
            "total_gross_sales": round(a["gross"], 2),
            "total_qty": round(a["qty"], 2),
            "transaction_count": len(a["txns"]),
        })
    return records


# ============================================
# Main Orchestrator
# ============================================

def run_smart_backfill(lookback_days=14, from_date=None, include_today=False):
    """
    Main entry point: detect gaps and fill them.

    Args:
        lookback_days: How many days back to check for gaps (default: 14)
        from_date: Optional start date string (YYYY-MM-DD)
        include_today: Whether to also sync today's partial data
    """
    print("=" * 60)
    print("SMART BACKFILL — Detecting & filling date gaps")
    print("=" * 60)

    if not all([TOKEN, LOCATION_ID, SUPA_URL, SUPA_KEY]):
        print("ERROR: Missing environment variables (SQUARE_ACCESS_TOKEN, SQUARE_LOCATION_ID, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)")
        return {"status": "error", "missing_dates": [], "filled_dates": []}

    # Step 1: Detect missing dates
    print(f"\nStep 1: Detecting missing dates (lookback={lookback_days} days)...")
    missing = detect_missing_dates(lookback_days=lookback_days, from_date=from_date)

    if include_today:
        today_str = datetime.now(SYDNEY_TZ).strftime("%Y-%m-%d")
        if today_str not in missing:
            missing.append(today_str)
            missing.sort()

    if not missing:
        print("  No missing dates found! Data is complete.")
        return {"status": "complete", "missing_dates": [], "filled_dates": []}

    print(f"  Found {len(missing)} missing date(s): {', '.join(missing)}")

    # Step 2: Build catalog map (once — reused for all dates)
    print("\nStep 2: Building catalog map...")
    catalog_map = build_catalog_map()

    # Step 3: Fetch and upsert for each missing date
    print(f"\nStep 3: Fetching data from Square for {len(missing)} date(s)...")
    filled = []
    total_tx_rows = 0
    total_summary_rows = 0
    total_stats_rows = 0

    for date_str in missing:
        print(f"\n  [{date_str}] Fetching orders...", end=" ", flush=True)
        t0 = time.time()

        rows, matched, unmatched = fetch_orders_for_date(date_str, catalog_map)
        elapsed = time.time() - t0

        if not rows:
            print(f"no orders found ({elapsed:.1f}s). Skipping.")
            # This might be a legitimately closed day
            continue

        print(f"{len(rows)} line items ({elapsed:.1f}s)", flush=True)

        # Upsert transactions
        for i in range(0, len(rows), 200):
            batch = rows[i:i + 200]
            try:
                supa_post(
                    "transactions?on_conflict=row_key",
                    batch,
                    extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                )
            except Exception as e:
                print(f"    WARNING: Transaction upsert batch failed: {e}")

        total_tx_rows += len(rows)

        # Build & upsert daily_item_summary
        item_summary = build_daily_item_summary(rows)
        if item_summary:
            for i in range(0, len(item_summary), 500):
                batch = item_summary[i:i + 500]
                try:
                    supa_post(
                        "daily_item_summary?on_conflict=date,category,item",
                        batch,
                        extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                    )
                except Exception as e:
                    print(f"    WARNING: Summary upsert failed: {e}")
            total_summary_rows += len(item_summary)

        # Build & upsert daily_store_stats
        store_stats = build_daily_store_stats(rows)
        if store_stats:
            try:
                supa_post(
                    "daily_store_stats?on_conflict=date",
                    store_stats,
                    extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                )
            except Exception as e:
                print(f"    WARNING: Store stats upsert failed: {e}")
            total_stats_rows += len(store_stats)

        filled.append(date_str)

        # Build & upsert daily_category_stats
        cat_stats = build_daily_category_stats(rows)
        if cat_stats:
            for i in range(0, len(cat_stats), 500):
                batch = cat_stats[i:i + 500]
                try:
                    supa_post(
                        "daily_category_stats?on_conflict=date,category",
                        batch,
                        extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                    )
                except Exception as e:
                    print(f"    WARNING: Category stats upsert failed: {e}")

        cat_total = matched + unmatched
        cat_pct = (matched / cat_total * 100) if cat_total > 0 else 0
        print(f"    -> {len(rows)} tx rows, {len(item_summary)} summaries, "
              f"categories: {matched}/{cat_total} ({cat_pct:.0f}%)")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"SMART BACKFILL COMPLETE")
    print(f"  Missing dates detected: {len(missing)}")
    print(f"  Dates filled:           {len(filled)}")
    print(f"  Transaction rows:       {total_tx_rows}")
    print(f"  Item summary rows:      {total_summary_rows}")
    print(f"  Store stats rows:       {total_stats_rows}")
    if set(missing) - set(filled):
        skipped = sorted(set(missing) - set(filled))
        print(f"  Skipped (no orders):    {', '.join(skipped)}")
    print(f"{'=' * 60}")

    return {
        "status": "success",
        "missing_dates": missing,
        "filled_dates": filled,
        "transactions": total_tx_rows,
        "summaries": total_summary_rows,
        "store_stats": total_stats_rows,
    }


# ============================================
# CLI Entry Point
# ============================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Smart backfill: detect and fill missing date gaps")
    parser.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=14, help="Lookback days (default: 14)")
    parser.add_argument("--include-today", action="store_true", help="Also refresh today's data")
    args = parser.parse_args()

    result = run_smart_backfill(
        lookback_days=args.days,
        from_date=args.from_date,
        include_today=args.include_today,
    )
