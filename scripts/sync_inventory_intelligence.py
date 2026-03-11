"""
sync_inventory_intelligence.py - Stock Intelligence Engine

Pulls inventory change history from Square's Inventory API and computes
per-item intelligence metrics:
  - Sales velocity (units/month)
  - Days of stock remaining
  - Last sold / last received dates
  - Sell-through rate
  - Reorder alert level (CRITICAL / LOW / WATCH / OK / OVERSTOCK / DEAD)

Alert logic:
  CRITICAL  - selling item with <3 days of stock OR out of stock with recent sales
  LOW       - <7 days of stock remaining
  WATCH     - <14 days of stock remaining
  OK        - healthy stock levels
  OVERSTOCK - >90 days of stock remaining and actively selling
  DEAD      - no sales in 90 days and qty > 0

Run: python scripts/sync_inventory_intelligence.py
Schedule: add to scheduled_sync.py (runs every 2 hours)
"""

import os
import sys
import json
import time
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SYDNEY = ZoneInfo("Australia/Sydney")
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def supabase_request(method, path, data=None):
    """Helper for Supabase REST API calls."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal" if method in ("POST", "PUT", "PATCH") else "",
    }
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status in (200, 201):
                text = resp.read().decode()
                return json.loads(text) if text.strip() else []
            return []
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        print(f"  HTTP {e.code}: {body_text[:300]}")
        raise


def fetch_all_inventory_changes(client, location_id, days_back=90):
    """
    Fetch ALL inventory changes from Square for the last N days.
    Returns a dict: variation_id -> list of changes
    """
    cutoff = (datetime.now(SYDNEY) - timedelta(days=days_back)).isoformat()
    
    changes_by_var = defaultdict(list)
    total = 0
    
    # Fetch SOLD adjustments
    print(f"  Fetching SOLD adjustments (last {days_back}d)...")
    t0 = time.time()
    sold_count = 0
    for change in client.inventory.batch_get_changes(
        location_ids=[location_id],
        updated_after=cutoff,
        types=["ADJUSTMENT"],
        states=["SOLD"],
    ):
        adj = change.adjustment
        if adj:
            changes_by_var[adj.catalog_object_id].append({
                "type": "SOLD",
                "quantity": abs(float(adj.quantity or 0)),
                "occurred_at": adj.occurred_at,
                "total_price": int(adj.total_price_money.amount) / 100 if adj.total_price_money and adj.total_price_money.amount else 0,
            })
            sold_count += 1
    print(f"    {sold_count} SOLD adjustments in {time.time()-t0:.1f}s")
    total += sold_count

    # Fetch stock-increase adjustments: ANY positive adjustment into IN_STOCK
    # (not just from_state == "NONE" — that only catches first-time stock adds)
    print(f"  Fetching stock receipt adjustments (last {days_back}d)...")
    t0 = time.time()
    recv_count = 0
    for change in client.inventory.batch_get_changes(
        location_ids=[location_id],
        updated_after=cutoff,
        types=["ADJUSTMENT"],
        states=["IN_STOCK"],
    ):
        adj = change.adjustment
        if adj and adj.to_state == "IN_STOCK" and float(adj.quantity or 0) > 0:
            # Skip SOLD adjustments (from_state IN_STOCK → to_state SOLD are handled above)
            if adj.from_state == "SOLD":
                continue
            changes_by_var[adj.catalog_object_id].append({
                "type": "RECEIVED",
                "quantity": float(adj.quantity or 0),
                "occurred_at": adj.occurred_at,
            })
            recv_count += 1
    print(f"    {recv_count} receipt adjustments in {time.time()-t0:.1f}s")
    total += recv_count

    # Fetch PHYSICAL_COUNT changes (stock reconciliations — often used to "receive" stock)
    print(f"  Fetching physical counts (last {days_back}d)...")
    t0 = time.time()
    count_count = 0
    for change in client.inventory.batch_get_changes(
        location_ids=[location_id],
        updated_after=cutoff,
        types=["PHYSICAL_COUNT"],
    ):
        pc = change.physical_count
        if pc and float(pc.quantity or 0) > 0:
            changes_by_var[pc.catalog_object_id].append({
                "type": "PHYSICAL_COUNT",
                "quantity": float(pc.quantity or 0),
                "occurred_at": pc.occurred_at,
            })
            count_count += 1
    print(f"    {count_count} physical counts in {time.time()-t0:.1f}s")
    total += count_count

    print(f"  Total: {total} changes across {len(changes_by_var)} items")
    return changes_by_var


def build_catalog_map(client):
    """Build variation_id -> {product_name, sku} map from catalog."""
    print("  Building catalog map...")
    cat_map = {}
    count = 0
    for item in client.catalog.list(types="ITEM"):
        item_data = item.item_data
        if not item_data or not item_data.variations:
            continue
        for var in item_data.variations:
            vd = var.item_variation_data
            if not vd:
                continue
            cat_map[var.id] = {
                "product_name": item_data.name or "",
                "sku": vd.sku or "",
            }
        count += 1
    print(f"    {count} catalog items, {len(cat_map)} variations")
    return cat_map


def fetch_current_counts(client, location_id, variation_ids):
    """Fetch current inventory counts for all variations."""
    print(f"  Fetching current counts for {len(variation_ids)} items...")
    counts = {}
    batch_size = 100
    for i in range(0, len(variation_ids), batch_size):
        batch = variation_ids[i:i + batch_size]
        try:
            for cnt in client.inventory.batch_get_counts(
                catalog_object_ids=batch,
                location_ids=[location_id],
            ):
                if cnt.state == "IN_STOCK":
                    counts[cnt.catalog_object_id] = float(cnt.quantity or 0)
        except Exception as e:
            print(f"    Warning: batch error at {i}: {e}")
    print(f"    Got counts for {len(counts)} items")
    return counts


def compute_intelligence(changes_by_var, catalog_map, counts_map):
    """
    Compute per-item intelligence from inventory changes.
    Returns list of intelligence records ready for Supabase.
    """
    now = datetime.now(SYDNEY)
    cutoff_7d = (now - timedelta(days=7)).isoformat()
    cutoff_30d = (now - timedelta(days=30)).isoformat()
    cutoff_90d = (now - timedelta(days=90)).isoformat()
    
    records = []
    
    # Process all variations that have any changes OR have stock
    all_var_ids = set(changes_by_var.keys()) | set(counts_map.keys())
    
    for var_id in all_var_ids:
        cat = catalog_map.get(var_id, {})
        product_name = cat.get("product_name", "Unknown")
        sku = cat.get("sku", "")
        
        changes = changes_by_var.get(var_id, [])
        current_qty = counts_map.get(var_id, 0)
        
        # Separate sales and receipts (include PHYSICAL_COUNT as a form of stock receipt)
        sales = [c for c in changes if c["type"] == "SOLD"]
        receipts = [c for c in changes if c["type"] in ("RECEIVED", "PHYSICAL_COUNT")]
        
        # Sales metrics
        last_sold = max((s["occurred_at"] for s in sales), default=None)
        units_sold_7d = sum(s["quantity"] for s in sales if s["occurred_at"] >= cutoff_7d)
        units_sold_30d = sum(s["quantity"] for s in sales if s["occurred_at"] >= cutoff_30d)
        units_sold_90d = sum(s["quantity"] for s in sales if s["occurred_at"] >= cutoff_90d)
        revenue_30d = sum(s["total_price"] for s in sales if s["occurred_at"] >= cutoff_30d)
        
        # Receiving metrics — only count actual RECEIVED adjustments for quantity
        # (PHYSICAL_COUNT is absolute, not incremental, so don't sum as received qty)
        actual_receipts = [c for c in changes if c["type"] == "RECEIVED"]
        # last_received uses ALL receipt-like events (RECEIVED + PHYSICAL_COUNT)
        last_received = max((r["occurred_at"] for r in receipts), default=None)
        units_received_30d = sum(r["quantity"] for r in actual_receipts if r["occurred_at"] >= cutoff_30d)
        units_received_90d = sum(r["quantity"] for r in actual_receipts if r["occurred_at"] >= cutoff_90d)
        
        # Sales velocity (units per month, based on 30-day window)
        sales_velocity = units_sold_30d  # already 30-day sum = monthly rate
        
        # Days of stock remaining
        daily_rate = sales_velocity / 30 if sales_velocity > 0 else 0
        days_of_stock = current_qty / daily_rate if daily_rate > 0 else 9999
        
        # Sell-through rate (30d): units sold / (starting stock + received)
        starting_stock = current_qty + units_sold_30d - units_received_30d
        denominator = starting_stock + units_received_30d
        sell_through = (units_sold_30d / denominator * 100) if denominator > 0 else 0
        
        # ── Alert Logic ──
        # Smarter thresholds: only flag CRITICAL for items with meaningful velocity
        alert = "OK"
        
        if current_qty <= 0 and sales_velocity > 3:
            alert = "CRITICAL"  # Out of stock AND selling fast (>3/month)
        elif current_qty <= 0 and sales_velocity > 0:
            alert = "WATCH"     # Out of stock but slow seller — monitor, not urgent
        elif current_qty > 0 and daily_rate > 0:
            if days_of_stock < 3 and sales_velocity > 3:
                alert = "CRITICAL"  # About to run out on a fast seller
            elif days_of_stock < 3:
                alert = "LOW"       # Very low but not a fast seller
            elif days_of_stock < 7:
                alert = "LOW"
            elif days_of_stock < 14:
                alert = "WATCH"
            elif days_of_stock > 90:
                alert = "OVERSTOCK"
            else:
                alert = "OK"
        elif current_qty > 0 and units_sold_90d == 0:
            alert = "DEAD"  # Stock but no sales in 90 days
        
        records.append({
            "variation_id": var_id,
            "product_name": product_name,
            "sku": sku,
            "last_sold_date": last_sold,
            "units_sold_7d": round(units_sold_7d, 1),
            "units_sold_30d": round(units_sold_30d, 1),
            "units_sold_90d": round(units_sold_90d, 1),
            "revenue_30d": round(revenue_30d, 2),
            "last_received_date": last_received,
            "units_received_30d": round(units_received_30d, 1),
            "units_received_90d": round(units_received_90d, 1),
            "current_quantity": round(current_qty, 1),
            "sales_velocity": round(sales_velocity, 1),
            "days_of_stock": round(min(days_of_stock, 9999), 0),
            "sell_through_pct": round(sell_through, 1),
            "reorder_alert": alert,
            "synced_at": now.isoformat(),
        })
    
    return records


def upsert_intelligence(records):
    """Upsert intelligence records to Supabase in batches."""
    batch_size = 200
    total = 0
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        url = f"inventory_intelligence?on_conflict=variation_id"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }
        body = json.dumps(batch).encode("utf-8")
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{url}",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=60)
            total += len(batch)
        except urllib.error.HTTPError as e:
            err = e.read().decode()
            print(f"  Error upserting batch at {i}: {err[:300]}")
    
    return total


def run_intelligence_sync(days_back=90):
    """Main entry point for intelligence sync."""
    from services.square_sync import get_square_client, get_location_id
    
    print("=" * 60)
    print("STOCK INTELLIGENCE SYNC")
    print(f"  Time: {datetime.now(SYDNEY).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Looking back: {days_back} days")
    print("=" * 60)
    
    t_start = time.time()
    
    # 1. Setup Square client
    client = get_square_client()
    location_id = get_location_id()
    
    # 2. Build catalog map
    catalog_map = build_catalog_map(client)
    
    # 3. Fetch inventory changes from Square
    changes = fetch_all_inventory_changes(client, location_id, days_back)
    
    # 4. Fetch current counts
    all_var_ids = list(set(list(changes.keys()) + list(catalog_map.keys())))
    counts = fetch_current_counts(client, location_id, all_var_ids)
    
    # 5. Compute intelligence
    print("\n  Computing intelligence metrics...")
    records = compute_intelligence(changes, catalog_map, counts)
    
    # Stats
    alerts = defaultdict(int)
    for r in records:
        alerts[r["reorder_alert"]] += 1
    
    print(f"    Total items: {len(records)}")
    print(f"    CRITICAL: {alerts.get('CRITICAL', 0)}")
    print(f"    LOW:      {alerts.get('LOW', 0)}")
    print(f"    WATCH:    {alerts.get('WATCH', 0)}")
    print(f"    OK:       {alerts.get('OK', 0)}")
    print(f"    OVERSTOCK: {alerts.get('OVERSTOCK', 0)}")
    print(f"    DEAD:     {alerts.get('DEAD', 0)}")
    
    # 6. Upsert to Supabase
    print(f"\n  Upserting {len(records)} records to Supabase...")
    upserted = upsert_intelligence(records)
    
    elapsed = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f"INTELLIGENCE SYNC COMPLETE ({elapsed:.1f}s)")
    print(f"  Upserted: {upserted} records")
    print(f"{'=' * 60}")
    
    return {
        "status": "success",
        "records": upserted,
        "alerts": dict(alerts),
        "elapsed": round(elapsed, 1),
    }


if __name__ == "__main__":
    run_intelligence_sync()
