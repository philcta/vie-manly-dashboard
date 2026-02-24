"""
Rebuild Supabase transactions table from Square API.

This script:
1. Fetches ALL historical orders from Square (paginated, month by month)
2. Converts UTC timestamps to Sydney local time (matching CSV export format)
3. Maps categories from Square catalog
4. Truncates the existing transactions table
5. Inserts fresh data

Usage: python scripts/rebuild_from_square.py
"""
import os
import sys
import json
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import OrderedDict

from dotenv import load_dotenv

load_dotenv()

# ── Config ──
TOKEN = os.getenv("SQUARE_ACCESS_TOKEN")
LOC_ID = os.getenv("SQUARE_LOCATION_ID")
SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPA_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Needed for delete

SQ_BASE = "https://connect.squareup.com/v2"
SQ_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Square-Version": "2024-01-18",
}

SYDNEY_TZ = ZoneInfo("Australia/Sydney")
BATCH_SIZE = 200

# ── Helpers ──

def sq_request(endpoint, body=None, method="GET"):
    """Make a Square API request."""
    url = f"{SQ_BASE}/{endpoint}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=SQ_HEADERS, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"  ❌ Square API error {e.code}: {err_body[:200]}")
        return None


def supa_request(endpoint, body=None, method="GET", use_service_key=False):
    """Make a Supabase REST API request."""
    key = SUPA_SERVICE_KEY if use_service_key else SUPA_KEY
    url = f"{SUPA_URL}/rest/v1/{endpoint}"
    data = json.dumps(body).encode() if body else None
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    if method == "POST" and body:
        # Upsert on row_key
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        if resp.status in (200, 201):
            try:
                return json.loads(resp.read())
            except Exception:
                return {"status": "ok"}
        return {"status": resp.status}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"  ❌ Supabase error {e.code}: {err_body[:300]}")
        return None


# ============================================================
# STEP 1: Build catalog map (item -> category)
# ============================================================

def build_catalog_map():
    """Fetch Square catalog and build item_name -> category mapping."""
    print("📦 Fetching Square catalog for category mapping...")
    
    # Get all categories first
    cat_names = {}
    cursor = None
    while True:
        params = "types=CATEGORY"
        if cursor:
            params += f"&cursor={cursor}"
        data = sq_request(f"catalog/list?{params}")
        if not data:
            break
        for obj in data.get("objects", []):
            cat_data = obj.get("category_data", {})
            cat_names[obj["id"]] = cat_data.get("name", "")
        cursor = data.get("cursor")
        if not cursor:
            break
    
    print(f"  Found {len(cat_names)} categories")
    
    # Get all items
    item_to_cat = {}  # item_name (lowercase) -> category_name
    cursor = None
    while True:
        params = "types=ITEM"
        if cursor:
            params += f"&cursor={cursor}"
        data = sq_request(f"catalog/list?{params}")
        if not data:
            break
        for obj in data.get("objects", []):
            item_data = obj.get("item_data", {})
            name = item_data.get("name", "")
            cat_id = item_data.get("category_id", "")
            cat_name = cat_names.get(cat_id, "")
            if name:
                item_to_cat[name.lower()] = cat_name
                # Also map variations
                for var in item_data.get("variations", []):
                    var_data = var.get("item_variation_data", {})
                    var_name = var_data.get("name", "")
                    if var_name and var_name != name:
                        item_to_cat[f"{name} - {var_name}".lower()] = cat_name
        cursor = data.get("cursor")
        if not cursor:
            break
    
    print(f"  Built {len(item_to_cat)} item->category mappings")
    return item_to_cat


# ============================================================
# STEP 2: Fetch all orders from Square
# ============================================================

def fetch_orders_for_range(start_date, end_date):
    """Fetch all completed orders for a date range."""
    all_orders = []
    cursor = None
    
    while True:
        body = {
            "location_ids": [LOC_ID],
            "query": {
                "filter": {
                    "date_time_filter": {
                        "created_at": {
                            "start_at": f"{start_date}T00:00:00Z",
                            "end_at": f"{end_date}T23:59:59Z",
                        }
                    },
                    "state_filter": {"states": ["COMPLETED"]},
                },
                "sort": {"sort_field": "CREATED_AT", "sort_order": "ASC"},
            },
            "limit": 500,
        }
        if cursor:
            body["cursor"] = cursor
        
        data = sq_request("orders/search", body=body, method="POST")
        if not data:
            break
        
        orders = data.get("orders", [])
        all_orders.extend(orders)
        
        cursor = data.get("cursor")
        if not cursor or not orders:
            break
    
    return all_orders


def convert_orders_to_rows(orders, catalog_map):
    """Convert Square orders to transaction rows (CSV-compatible format)."""
    rows = []
    
    for order in orders:
        order_id = order.get("id", "")
        created_at = order.get("created_at", "")
        customer_id = order.get("customer_id", "")
        
        # Payment info
        tenders = order.get("tenders", [])
        card_brand = ""
        pan_suffix = ""
        if tenders:
            card_details = tenders[0].get("card_details", {})
            card = card_details.get("card", {})
            card_brand = card.get("card_brand", "")
            pan_suffix = card.get("last_4", "")
            # Also get card brand from tender type
            if not card_brand:
                tender_type = tenders[0].get("type", "")
                if tender_type == "CARD":
                    card_brand = "Card"
                elif tender_type == "CASH":
                    card_brand = "Cash"
        
        # Parse datetime → Sydney local time
        try:
            dt_utc = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            dt_local = dt_utc.astimezone(SYDNEY_TZ)
            datetime_str = dt_local.strftime("%Y-%m-%d %H:%M:%S")
            date_str = dt_local.strftime("%Y-%m-%d")
            time_str = dt_local.strftime("%H:%M:%S")
        except Exception:
            datetime_str = created_at
            date_str = ""
            time_str = ""
        
        # Line items
        for li_idx, item in enumerate(order.get("line_items", [])):
            item_name = item.get("name", "")
            qty = float(item.get("quantity", "0"))
            
            # Variation name
            variation_name = item.get("variation_name", "")
            if variation_name and variation_name != item_name:
                display_name = f"{item_name} - {variation_name}"
            else:
                display_name = item_name
            
            # Category from catalog
            category = catalog_map.get(display_name.lower(), "")
            if not category:
                category = catalog_map.get(item_name.lower(), "")
            
            # Amounts (cents → dollars)
            base_price = int(item.get("base_price_money", {}).get("amount", 0)) / 100
            total_money = int(item.get("total_money", {}).get("amount", 0)) / 100
            total_tax = int(item.get("total_tax_money", {}).get("amount", 0)) / 100
            total_discount = int(item.get("total_discount_money", {}).get("amount", 0)) / 100
            
            gross_sales = base_price * qty
            net_sales = total_money - total_tax
            
            # Modifiers
            modifiers = item.get("modifiers", [])
            modifiers_str = ", ".join(m.get("name", "") for m in modifiers) if modifiers else ""
            
            # Build row_key for deduplication (include line item index for uniqueness)
            base_key = f"{order_id}||{datetime_str}||{display_name}||{net_sales}||{gross_sales}||{total_discount}||{qty}||{customer_id}||{modifiers_str}||{total_tax}||{card_brand}||{pan_suffix}||{li_idx}"
            
            rows.append({
                "datetime": datetime_str,
                "category": category,
                "item": display_name,
                "qty": qty,
                "net_sales": round(net_sales, 2),
                "gross_sales": round(gross_sales, 2),
                "discounts": round(-abs(total_discount), 2) if total_discount else 0,
                "customer_id": customer_id,
                "transaction_id": order_id,
                "tax": str(round(total_tax, 2)),
                "card_brand": card_brand,
                "pan_suffix": pan_suffix,
                "date": date_str,
                "time": time_str,
                "time_zone": "Sydney",
                "modifiers_applied": modifiers_str,
                "row_key": base_key,
            })
    
    return rows


# ============================================================
# STEP 3: Truncate & Insert into Supabase
# ============================================================

def truncate_transactions():
    """Delete all existing transactions from Supabase."""
    print("🗑️  Truncating transactions table...")
    
    # Supabase REST API doesn't have TRUNCATE, so we delete with a wide filter
    # Using service role key for delete permissions
    key = SUPA_SERVICE_KEY or SUPA_KEY
    url = f"{SUPA_URL}/rest/v1/transactions?id=gt.0"
    req = urllib.request.Request(url, headers={
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }, method="DELETE")
    
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        print(f"  ✅ Truncated (status {resp.status})")
        return True
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  ❌ Truncate failed {e.code}: {err[:200]}")
        return False


def insert_batch(records, batch_num, total_batches):
    """Insert a batch of records into Supabase."""
    key = SUPA_SERVICE_KEY or SUPA_KEY
    url = f"{SUPA_URL}/rest/v1/transactions"
    
    req = urllib.request.Request(url, 
        data=json.dumps(records).encode(),
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }, 
        method="POST"
    )
    
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        return True
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  ❌ Batch {batch_num}/{total_batches} failed: {err[:200]}")
        return False


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("🔄 REBUILD SUPABASE FROM SQUARE API")
    print("=" * 60)
    
    if not TOKEN or not LOC_ID:
        print("❌ Missing SQUARE_ACCESS_TOKEN or SQUARE_LOCATION_ID in .env")
        sys.exit(1)
    
    # Step 1: Build catalog
    catalog_map = build_catalog_map()
    
    # Step 2: Determine date range
    # Find the earliest order in Square
    print("\n📅 Determining date range...")
    
    # Start from July 2024 (when the dashboard data begins based on Supabase)
    # Pull month by month to avoid API timeouts
    start_date = datetime(2024, 7, 1)
    end_date = datetime.now()
    
    print(f"  Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # Step 3: Fetch all orders month by month
    all_rows = []
    current = start_date
    
    while current < end_date:
        month_end = current.replace(day=28) + timedelta(days=4)
        month_end = month_end.replace(day=1) - timedelta(days=1)  # Last day of month
        
        if month_end > end_date:
            month_end = end_date
        
        month_str = current.strftime("%Y-%m")
        print(f"\n📥 Fetching {month_str}...", end="", flush=True)
        
        orders = fetch_orders_for_range(
            current.strftime("%Y-%m-%d"),
            month_end.strftime("%Y-%m-%d")
        )
        
        rows = convert_orders_to_rows(orders, catalog_map)
        all_rows.extend(rows)
        
        print(f" {len(orders)} orders → {len(rows)} rows", flush=True)
        
        # Move to next month
        current = month_end + timedelta(days=1)
    
    print(f"\n{'='*60}")
    print(f"📊 Total: {len(all_rows)} transaction rows from Square")
    
    if not all_rows:
        print("❌ No data fetched — aborting")
        sys.exit(1)
    
    # Step 4: Show summary before writing
    daily_summary = OrderedDict()
    for row in all_rows:
        d = row["date"]
        if d not in daily_summary:
            daily_summary[d] = {"rows": 0, "net": 0.0, "txns": set()}
        daily_summary[d]["rows"] += 1
        daily_summary[d]["net"] += row["net_sales"]
        daily_summary[d]["txns"].add(row["transaction_id"])
    
    # Monthly summary
    monthly = OrderedDict()
    for d, info in daily_summary.items():
        m = d[:7]
        if m not in monthly:
            monthly[m] = {"rows": 0, "net": 0.0, "txns": 0, "days": 0}
        monthly[m]["rows"] += info["rows"]
        monthly[m]["net"] += info["net"]
        monthly[m]["txns"] += len(info["txns"])
        monthly[m]["days"] += 1
    
    print(f"\n{'Month':<10} {'Days':>5} {'Rows':>8} {'Txns':>8} {'Net Sales':>14}")
    print("-" * 50)
    for m, info in monthly.items():
        print(f"{m:<10} {info['days']:>5} {info['rows']:>8} {info['txns']:>8} ${info['net']:>12,.2f}")
    print("-" * 50)
    total_net = sum(info["net"] for info in monthly.values())
    total_rows = sum(info["rows"] for info in monthly.values())
    total_txns = sum(info["txns"] for info in monthly.values())
    print(f"{'TOTAL':<10} {'':<5} {total_rows:>8} {total_txns:>8} ${total_net:>12,.2f}")
    
    # Step 5: Insert (table already truncated separately)
    print(f"\n📤 Table already truncated. Inserting {len(all_rows)} rows...")
    
    total_batches = (len(all_rows) + BATCH_SIZE - 1) // BATCH_SIZE
    inserted = 0
    failed = 0
    
    for i in range(0, len(all_rows), BATCH_SIZE):
        batch = all_rows[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        
        if insert_batch(batch, batch_num, total_batches):
            inserted += len(batch)
        else:
            failed += len(batch)
        
        # Progress
        pct = (batch_num / total_batches) * 100
        print(f"\r  Progress: {batch_num}/{total_batches} ({pct:.0f}%) — {inserted} inserted, {failed} failed", end="", flush=True)
    
    print(f"\n\n{'='*60}")
    print(f"✅ REBUILD COMPLETE")
    print(f"   Inserted: {inserted} rows")
    print(f"   Failed:   {failed} rows")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
