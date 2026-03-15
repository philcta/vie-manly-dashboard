"""
sync_inventory_intelligence.py - Stock Intelligence Engine (Phase 2)

Pulls inventory change history from Square's Inventory API and computes
per-item intelligence metrics:
  - Sales velocity (units/month)
  - Days of stock remaining
  - Last sold / last received dates
  - Sell-through rate
  - Reorder alert level (CRITICAL / LOW / WATCH / OK / OVERSTOCK / DEAD)
  - Waste & damage tracking (Phase 2)
  - Weekly velocity trends (Phase 2)
  - Stockout risk date prediction (Phase 2)
  - Recommended order quantities (Phase 2)

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
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from pathlib import Path
from collections import defaultdict
from math import ceil

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
                "source": getattr(adj, 'source', None) and getattr(adj.source, 'name', None),
                "team_member_id": getattr(adj, 'employee_id', None),
            })
            sold_count += 1
    print(f"    {sold_count} SOLD adjustments in {time.time()-t0:.1f}s")
    total += sold_count

    # Fetch stock-increase adjustments: ANY positive adjustment into IN_STOCK
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
            if adj.from_state == "SOLD":
                continue
            changes_by_var[adj.catalog_object_id].append({
                "type": "RECEIVED",
                "quantity": float(adj.quantity or 0),
                "occurred_at": adj.occurred_at,
                "purchase_order_id": getattr(adj, 'purchase_order_id', None),
                "goods_receipt_id": getattr(adj, 'goods_receipt_id', None),
                "source": getattr(adj, 'source', None) and getattr(adj.source, 'name', None),
                "team_member_id": getattr(adj, 'employee_id', None),
            })
            recv_count += 1
    print(f"    {recv_count} receipt adjustments in {time.time()-t0:.1f}s")
    total += recv_count

    # Phase 2: Fetch WASTE adjustments (expired food, breakage)
    print(f"  Fetching WASTE adjustments (last {days_back}d)...")
    t0 = time.time()
    waste_count = 0
    for change in client.inventory.batch_get_changes(
        location_ids=[location_id],
        updated_after=cutoff,
        types=["ADJUSTMENT"],
        states=["WASTE"],
    ):
        adj = change.adjustment
        if adj:
            changes_by_var[adj.catalog_object_id].append({
                "type": "WASTE",
                "quantity": abs(float(adj.quantity or 0)),
                "occurred_at": adj.occurred_at,
                "source": getattr(adj, 'source', None) and getattr(adj.source, 'name', None),
                "team_member_id": getattr(adj, 'employee_id', None),
            })
            waste_count += 1
    print(f"    {waste_count} WASTE adjustments in {time.time()-t0:.1f}s")
    total += waste_count

    # Note: Square API doesn't have a separate DAMAGED state — damage is tracked
    # within WASTE adjustments. We skip the DAMAGED fetch.
    damage_count = 0

    # Fetch PHYSICAL_COUNT changes (stock reconciliations)
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
                "team_member_id": getattr(pc, 'employee_id', None),
            })
            count_count += 1
    print(f"    {count_count} physical counts in {time.time()-t0:.1f}s")
    total += count_count

    print(f"  Total: {total} changes across {len(changes_by_var)} items")
    print(f"    (WASTE: {waste_count}, DAMAGED: {damage_count})")
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
            # Extract category name safely
            cat_name = ""
            try:
                if hasattr(item_data, 'categories') and item_data.categories:
                    cat_obj = item_data.categories[0]
                    # Try different attribute patterns for the category name
                    if hasattr(cat_obj, 'category_data') and cat_obj.category_data:
                        cat_name = getattr(cat_obj.category_data, 'name', '') or ''
                    elif hasattr(cat_obj, 'name'):
                        cat_name = cat_obj.name or ''
                    elif hasattr(cat_obj, 'id'):
                        cat_name = cat_obj.id or ''
            except Exception:
                pass
            
            # Extract unit cost safely
            cost = 0
            try:
                if vd.default_unit_cost and vd.default_unit_cost.amount:
                    cost = int(vd.default_unit_cost.amount) / 100
            except Exception:
                pass
            
            cat_map[var.id] = {
                "product_name": item_data.name or "",
                "sku": vd.sku or "",
                "category": cat_name,
                "unit_cost": cost,
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


def enrich_catalog_from_supabase(catalog_map):
    """
    Enrich catalog_map with vendor and price data from Supabase inventory table.
    This fills in data that Square's catalog API doesn't easily provide.
    """
    print("  Enriching catalog with vendor/price from Supabase...")
    # Fetch latest inventory snapshot
    path = "inventory?source_date=eq." + urllib.request.quote("(SELECT MAX(source_date) FROM inventory)")
    # Simpler: just fetch latest source_date first
    try:
        dates = supabase_request("GET", "inventory?select=source_date&order=source_date.desc&limit=1")
        if dates:
            latest = dates[0]["source_date"]
            rows = supabase_request("GET", f"inventory?source_date=eq.{latest}&select=sku,default_vendor,price,categories,default_unit_cost")
            enrich_count = 0
            for row in rows:
                sku = row.get("sku", "")
                if not sku:
                    continue
                # Find matching entries in catalog_map by SKU
                for var_id, cat in catalog_map.items():
                    if cat.get("sku") == sku:
                        if not cat.get("vendor") and row.get("default_vendor"):
                            cat["vendor"] = row["default_vendor"]
                        if not cat.get("price") and row.get("price"):
                            cat["price"] = row["price"]
                        if not cat.get("category") and row.get("categories"):
                            cat["category"] = row["categories"]
                        if not cat.get("unit_cost") and row.get("default_unit_cost"):
                            cat["unit_cost"] = row["default_unit_cost"]
                        enrich_count += 1
            print(f"    Enriched {enrich_count} items with vendor/price data")
    except Exception as e:
        print(f"    Warning: could not enrich catalog: {e}")
    return catalog_map


def compute_intelligence(changes_by_var, catalog_map, counts_map):
    """
    Compute per-item intelligence from inventory changes.
    Returns list of intelligence records ready for Supabase.
    Phase 2: includes waste/damage, trends, stockout prediction.
    """
    now = datetime.now(SYDNEY)
    cutoff_7d = (now - timedelta(days=7)).isoformat()
    cutoff_14d = (now - timedelta(days=14)).isoformat()
    cutoff_30d = (now - timedelta(days=30)).isoformat()
    cutoff_90d = (now - timedelta(days=90)).isoformat()
    
    records = []
    
    # Process all variations that have any changes OR have stock
    all_var_ids = set(changes_by_var.keys()) | set(counts_map.keys())
    
    for var_id in all_var_ids:
        cat = catalog_map.get(var_id, {})
        product_name = cat.get("product_name", "Unknown")
        sku = cat.get("sku", "")
        unit_cost = cat.get("unit_cost", 0)
        
        changes = changes_by_var.get(var_id, [])
        current_qty = counts_map.get(var_id, 0)
        
        # Separate by type
        sales = [c for c in changes if c["type"] == "SOLD"]
        receipts = [c for c in changes if c["type"] in ("RECEIVED", "PHYSICAL_COUNT")]
        waste = [c for c in changes if c["type"] == "WASTE"]
        damage = [c for c in changes if c["type"] == "DAMAGED"]
        
        # Sales metrics
        last_sold = max((s["occurred_at"] for s in sales), default=None)
        units_sold_7d = sum(s["quantity"] for s in sales if s["occurred_at"] >= cutoff_7d)
        units_sold_30d = sum(s["quantity"] for s in sales if s["occurred_at"] >= cutoff_30d)
        units_sold_90d = sum(s["quantity"] for s in sales if s["occurred_at"] >= cutoff_90d)
        revenue_30d = sum(s["total_price"] for s in sales if s["occurred_at"] >= cutoff_30d)
        
        # Previous period sales (days 8-14) for trend comparison
        units_sold_prev_7d = sum(s["quantity"] for s in sales
                                 if s["occurred_at"] >= cutoff_14d and s["occurred_at"] < cutoff_7d)
        
        # Receiving metrics
        actual_receipts = [c for c in changes if c["type"] == "RECEIVED"]
        last_received = max((r["occurred_at"] for r in receipts), default=None)
        units_received_30d = sum(r["quantity"] for r in actual_receipts if r["occurred_at"] >= cutoff_30d)
        units_received_90d = sum(r["quantity"] for r in actual_receipts if r["occurred_at"] >= cutoff_90d)
        
        # Phase 2: Waste & Damage metrics
        waste_30d = sum(w["quantity"] for w in waste if w["occurred_at"] >= cutoff_30d)
        waste_90d = sum(w["quantity"] for w in waste if w["occurred_at"] >= cutoff_90d)
        waste_cost_30d = waste_30d * unit_cost if unit_cost else 0
        damage_30d = sum(d["quantity"] for d in damage if d["occurred_at"] >= cutoff_30d)
        
        # Sales velocity (units per month, based on 30-day window)
        sales_velocity = units_sold_30d
        
        # Days of stock remaining
        daily_rate = sales_velocity / 30 if sales_velocity > 0 else 0
        days_of_stock = current_qty / daily_rate if daily_rate > 0 else 9999
        
        # Phase 2: Average daily sales
        avg_daily_sales = round(daily_rate, 2)
        
        # Phase 2: Stockout risk date prediction
        stockout_risk_date = None
        if daily_rate > 0 and current_qty > 0 and days_of_stock < 60:
            stockout_risk_date = (now + timedelta(days=days_of_stock)).strftime("%Y-%m-%d")
        
        # Phase 2: Recommended order quantity (2 weeks supply × 1.2 safety buffer)
        recommended_order_qty = 0
        if daily_rate > 0:
            recommended_order_qty = ceil(daily_rate * 14 * 1.2)
        
        # Phase 2: Weekly velocity trend
        velocity_change_pct = 0.0
        weekly_trend = "STABLE"
        if units_sold_prev_7d > 0:
            velocity_change_pct = round(((units_sold_7d - units_sold_prev_7d) / units_sold_prev_7d) * 100, 1)
            if velocity_change_pct > 20:
                weekly_trend = "UP"
            elif velocity_change_pct < -20:
                weekly_trend = "DOWN"
        elif units_sold_7d > 0 and units_sold_prev_7d == 0:
            weekly_trend = "UP"
            velocity_change_pct = 100.0
        
        # Sell-through rate (30d)
        starting_stock = current_qty + units_sold_30d - units_received_30d
        denominator = starting_stock + units_received_30d
        sell_through = (units_sold_30d / denominator * 100) if denominator > 0 else 0
        
        # ── Alert Logic ──
        alert = "OK"
        if current_qty <= 0 and sales_velocity > 3:
            alert = "CRITICAL"
        elif current_qty <= 0 and sales_velocity > 0:
            alert = "WATCH"
        elif current_qty > 0 and daily_rate > 0:
            if days_of_stock < 3 and sales_velocity > 3:
                alert = "CRITICAL"
            elif days_of_stock < 3:
                alert = "LOW"
            elif days_of_stock < 7:
                alert = "LOW"
            elif days_of_stock < 14:
                alert = "WATCH"
            elif days_of_stock > 90:
                alert = "OVERSTOCK"
            else:
                alert = "OK"
        elif current_qty > 0 and units_sold_90d == 0:
            alert = "DEAD"
        
        records.append({
            "variation_id": var_id,
            "product_name": product_name,
            "sku": sku,
            # Denormalized for fast RPC (no JOIN needed)
            "category": cat.get("category", ""),
            "vendor": cat.get("vendor", ""),
            "price": cat.get("price", 0),
            "unit_cost": unit_cost,
            "margin_pct": round(((cat.get("price", 0) - unit_cost) / cat.get("price", 1) * 100), 1) if cat.get("price", 0) > 0 and unit_cost > 0 else None,
            # Core metrics
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
            # Phase 2 columns
            "waste_30d": round(waste_30d, 1),
            "waste_90d": round(waste_90d, 1),
            "waste_cost_30d": round(waste_cost_30d, 2),
            "damage_30d": round(damage_30d, 1),
            "weekly_trend": weekly_trend,
            "velocity_change_pct": velocity_change_pct,
            "stockout_risk_date": stockout_risk_date,
            "recommended_order_qty": recommended_order_qty,
            "avg_daily_sales": avg_daily_sales,
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


def store_inventory_changes(changes_by_var, catalog_map):
    """
    Phase 2: Store raw inventory changes as a ledger in Supabase.
    Uses upsert with (variation_id, change_type, occurred_at) for deduplication.
    """
    print("\n  Storing inventory changes ledger...")
    rows = []
    for var_id, changes in changes_by_var.items():
        cat = catalog_map.get(var_id, {})
        for c in changes:
            rows.append({
                "variation_id": var_id,
                "sku": cat.get("sku", ""),
                "product_name": cat.get("product_name", "Unknown"),
                "change_type": c["type"],
                "quantity": round(c["quantity"], 2),
                "total_price": round(c.get("total_price", 0) or 0, 2) if c.get("total_price") else None,
                "occurred_at": c["occurred_at"],
                "source": c.get("source"),
                "purchase_order_id": c.get("purchase_order_id"),
                "goods_receipt_id": c.get("goods_receipt_id"),
                "team_member_id": c.get("team_member_id"),
            })
    
    if not rows:
        print("    No changes to store")
        return 0
    
    # Deduplicate rows (same variation_id + change_type + occurred_at)
    seen = set()
    deduped = []
    for r in rows:
        key = (r["variation_id"], r["change_type"], r["occurred_at"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    print(f"    {len(rows)} raw rows -> {len(deduped)} unique rows")
    rows = deduped
    
    batch_size = 200
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        url = f"inventory_changes?on_conflict=variation_id,change_type,occurred_at"
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
            print(f"    Error storing changes batch at {i}: {err[:300]}")
    
    print(f"    Stored {total} change records")
    return total


def generate_weekly_snapshots(changes_by_var, catalog_map, counts_map):
    """
    Phase 2: Generate weekly snapshots for trend analysis.
    Creates/updates records in inventory_weekly_snapshots.
    """
    now = datetime.now(SYDNEY)
    # Current week start (Monday)
    today = now.date()
    week_start = today - timedelta(days=today.weekday())
    cutoff_week = week_start.isoformat()
    
    print(f"\n  Generating weekly snapshot (week of {week_start})...")
    
    snapshots = []
    for var_id in set(changes_by_var.keys()) | set(counts_map.keys()):
        cat = catalog_map.get(var_id, {})
        changes = changes_by_var.get(var_id, [])
        current_qty = counts_map.get(var_id, 0)
        
        # This week's changes
        sales_this_week = sum(c["quantity"] for c in changes
                              if c["type"] == "SOLD" and c["occurred_at"] >= cutoff_week)
        received_this_week = sum(c["quantity"] for c in changes
                                 if c["type"] == "RECEIVED" and c["occurred_at"] >= cutoff_week)
        waste_this_week = sum(c["quantity"] for c in changes
                              if c["type"] in ("WASTE", "DAMAGED") and c["occurred_at"] >= cutoff_week)
        
        # Opening = closing - received + sold + waste
        opening_qty = current_qty - received_this_week + sales_this_week + waste_this_week
        
        # Sell-through for the week
        denom = opening_qty + received_this_week
        sell_through = (sales_this_week / denom * 100) if denom > 0 else 0
        
        snapshots.append({
            "week_start": str(week_start),
            "variation_id": var_id,
            "product_name": cat.get("product_name", "Unknown"),
            "sku": cat.get("sku", ""),
            "category": cat.get("category", ""),
            "opening_qty": round(opening_qty, 1),
            "received_qty": round(received_this_week, 1),
            "sold_qty": round(sales_this_week, 1),
            "waste_qty": round(waste_this_week, 1),
            "closing_qty": round(current_qty, 1),
            "sell_through_pct": round(sell_through, 1),
        })
    
    # Upsert snapshots
    batch_size = 200
    total = 0
    for i in range(0, len(snapshots), batch_size):
        batch = snapshots[i:i + batch_size]
        url = f"inventory_weekly_snapshots?on_conflict=week_start,variation_id"
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
            print(f"    Error storing snapshot batch at {i}: {err[:300]}")
    
    print(f"    Stored {total} weekly snapshots")
    return total


def run_intelligence_sync(days_back=90):
    """Main entry point for intelligence sync (Phase 2 enhanced)."""
    from services.square_sync import get_square_client, get_location_id
    
    print("=" * 60)
    print("STOCK INTELLIGENCE SYNC (Phase 2)")
    print(f"  Time: {datetime.now(SYDNEY).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Looking back: {days_back} days")
    print("=" * 60)
    
    t_start = time.time()
    
    # 1. Setup Square client
    client = get_square_client()
    location_id = get_location_id()
    
    # 2. Build catalog map
    catalog_map = build_catalog_map(client)
    
    # 2b. Enrich with vendor/price from Supabase (for denormalized columns)
    catalog_map = enrich_catalog_from_supabase(catalog_map)
    
    # 3. Fetch inventory changes from Square (now includes WASTE + DAMAGED)
    changes = fetch_all_inventory_changes(client, location_id, days_back)
    
    # 4. Fetch current counts
    all_var_ids = list(set(list(changes.keys()) + list(catalog_map.keys())))
    counts = fetch_current_counts(client, location_id, all_var_ids)
    
    # 5. Phase 2: Store raw changes ledger
    store_inventory_changes(changes, catalog_map)
    
    # 6. Compute intelligence (now includes waste, trends, stockout prediction)
    print("\n  Computing intelligence metrics (Phase 2)...")
    records = compute_intelligence(changes, catalog_map, counts)
    
    # Stats
    alerts = defaultdict(int)
    waste_items = 0
    trending_up = 0
    trending_down = 0
    for r in records:
        alerts[r["reorder_alert"]] += 1
        if r.get("waste_30d", 0) > 0:
            waste_items += 1
        if r.get("weekly_trend") == "UP":
            trending_up += 1
        elif r.get("weekly_trend") == "DOWN":
            trending_down += 1
    
    print(f"    Total items: {len(records)}")
    print(f"    CRITICAL: {alerts.get('CRITICAL', 0)}")
    print(f"    LOW:      {alerts.get('LOW', 0)}")
    print(f"    WATCH:    {alerts.get('WATCH', 0)}")
    print(f"    OK:       {alerts.get('OK', 0)}")
    print(f"    OVERSTOCK: {alerts.get('OVERSTOCK', 0)}")
    print(f"    DEAD:     {alerts.get('DEAD', 0)}")
    print(f"    [UP]    Trending UP:   {trending_up}")
    print(f"    [DOWN]  Trending DOWN: {trending_down}")
    print(f"    [WASTE] Items with waste: {waste_items}")
    
    # 7. Upsert intelligence to Supabase
    print(f"\n  Upserting {len(records)} records to Supabase...")
    upserted = upsert_intelligence(records)
    
    # 8. Phase 2: Generate weekly snapshots
    generate_weekly_snapshots(changes, catalog_map, counts)
    
    elapsed = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f"INTELLIGENCE SYNC COMPLETE ({elapsed:.1f}s)")
    print(f"  Upserted: {upserted} records")
    print(f"  Waste items: {waste_items} | Trending: UP={trending_up} DOWN={trending_down}")
    print(f"{'=' * 60}")
    
    return {
        "status": "success",
        "records": upserted,
        "alerts": dict(alerts),
        "waste_items": waste_items,
        "trending_up": trending_up,
        "trending_down": trending_down,
        "elapsed": round(elapsed, 1),
    }


if __name__ == "__main__":
    run_intelligence_sync()
