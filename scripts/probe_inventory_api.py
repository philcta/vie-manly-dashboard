"""
Probe the Square Inventory API to discover:
1. Historical inventory changes (adjustments, sales, receives) with cost data
2. What fields are available on InventoryChange / InventoryAdjustment
3. Can we derive "last sold", "last received", "sales velocity"?
"""
import os, sys, json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.square_sync import get_square_client, get_location_id

SYDNEY = ZoneInfo("Australia/Sydney")

client = get_square_client()
location_id = get_location_id()
print(f"Location ID: {location_id}")
print()

# ── TEST 1: Pick known products ──
print("=" * 70)
print("TEST 1: Fetch a few catalog items -> variation IDs")
print("=" * 70)

catalog_items = []
count = 0
for item in client.catalog.list(types="ITEM"):
    item_data = item.item_data
    if not item_data or not item_data.variations:
        continue
    for var in item_data.variations:
        var_data = var.item_variation_data
        if not var_data:
            continue
        catalog_items.append({
            "item_id": item.id,
            "var_id": var.id,
            "name": item_data.name,
            "sku": var_data.sku or "",
        })
    count += 1
    if count >= 5:
        break

for ci in catalog_items[:5]:
    print(f"  {ci['name']} (SKU: {ci['sku']}) -> var_id: {ci['var_id']}")

test_var_id = catalog_items[0]["var_id"]
test_name = catalog_items[0]["name"]
print(f"\nUsing '{test_name}' ({test_var_id}) for probing")

# ── TEST 2: Inventory CHANGES (last 30 days) ──
print()
print("=" * 70)
print("TEST 2: Inventory CHANGES for this item (last 30d)")
print("=" * 70)

thirty_days_ago = (datetime.now(SYDNEY) - timedelta(days=30)).isoformat()

try:
    changes = list(client.inventory.batch_get_changes(
        catalog_object_ids=[test_var_id],
        location_ids=[location_id],
        updated_after=thirty_days_ago,
    ))
    print(f"  Got {len(changes)} changes")
    for c in changes[:5]:
        print(f"    Type: {c.type}")
        if c.adjustment:
            adj = c.adjustment
            print(f"      from: {adj.from_state} -> to: {adj.to_state}")
            print(f"      quantity: {adj.quantity}")
            print(f"      occurred_at: {adj.occurred_at}")
            print(f"      source: {adj.source}")
            # Dump ALL attributes to find cost data
            attrs = {a: getattr(adj, a, None) for a in dir(adj) if not a.startswith('_')}
            print(f"      ALL FIELDS: {json.dumps({k:str(v) for k,v in attrs.items() if v is not None}, indent=8)}")
        if c.physical_count:
            pc = c.physical_count
            print(f"      quantity: {pc.quantity}")
            print(f"      occurred_at: {pc.occurred_at}")
            attrs = {a: getattr(pc, a, None) for a in dir(pc) if not a.startswith('_')}
            print(f"      ALL FIELDS: {json.dumps({k:str(v) for k,v in attrs.items() if v is not None}, indent=8)}")
except Exception as e:
    print(f"  ERROR: {e}")

# ── TEST 3: Find SALE adjustments (any item, last 3 days) ──
print()
print("=" * 70)
print("TEST 3: SOLD adjustments (any item, last 3 days)")
print("=" * 70)

three_days_ago = (datetime.now(SYDNEY) - timedelta(days=3)).isoformat()
try:
    sale_count = 0
    for change in client.inventory.batch_get_changes(
        location_ids=[location_id],
        updated_after=three_days_ago,
        types=["ADJUSTMENT"],
        states=["SOLD"],
    ):
        adj = change.adjustment
        if adj and sale_count < 3:
            print(f"  var_id: {adj.catalog_object_id}")
            print(f"    {adj.from_state} -> {adj.to_state}, qty: {adj.quantity}")
            print(f"    occurred_at: {adj.occurred_at}")
            if adj.source:
                print(f"    source.product: {adj.source.product}")
                print(f"    source.name: {adj.source.name}")
            # Check for cost / price fields
            for f in ['total_price_money', 'cost_amount_money', 'cost_price_money']:
                val = getattr(adj, f, 'MISSING')
                if val != 'MISSING':
                    print(f"    {f}: {val}")
            print()
        sale_count += 1
        if sale_count >= 200:
            break
    print(f"  Total SOLD adjustments in 3 days: {sale_count}")
except Exception as e:
    print(f"  ERROR: {e}")

# ── TEST 4: Find stock receipts (IN_STOCK from NONE) ──
print()
print("=" * 70)
print("TEST 4: Stock receipt adjustments (last 30 days)")
print("=" * 70)

try:
    recv_count = 0
    recv_samples = []
    for change in client.inventory.batch_get_changes(
        location_ids=[location_id],
        updated_after=thirty_days_ago,
        types=["ADJUSTMENT"],
    ):
        adj = change.adjustment
        if adj and adj.to_state == "IN_STOCK" and adj.from_state in ("NONE", None, ""):
            recv_count += 1
            if len(recv_samples) < 5:
                recv_samples.append(adj)
    
    print(f"  Total stock receipts (30d): {recv_count}")
    for adj in recv_samples:
        print(f"    var_id: {adj.catalog_object_id}")
        print(f"    qty: {adj.quantity}, occurred: {adj.occurred_at}")
        if adj.source:
            print(f"    source: {adj.source.product} / {adj.source.name}")
        attrs = {a: getattr(adj, a, None) for a in dir(adj) if not a.startswith('_') and getattr(adj, a, None) is not None}
        cost_fields = {k:str(v) for k,v in attrs.items() if 'cost' in k.lower() or 'price' in k.lower() or 'money' in k.lower()}
        if cost_fields:
            print(f"    COST FIELDS: {cost_fields}")
        print()
except Exception as e:
    print(f"  ERROR: {e}")

# ── TEST 5: Catalog variation full dump (cost fields) ──
print()
print("=" * 70)
print("TEST 5: Detailed catalog variation (all fields)")
print("=" * 70)

try:
    result = client.catalog.get(object_id=catalog_items[0]["item_id"])
    item_data = result.item_data
    print(f"  Item: {item_data.name}")

    for var in (item_data.variations or []):
        vd = var.item_variation_data
        print(f"\n  Variation: {var.id}")
        print(f"    SKU: {vd.sku}")
        print(f"    price_money: {vd.price_money}")
        print(f"    default_unit_cost: {getattr(vd, 'default_unit_cost', 'N/A')}")
        
        # Vendor infos
        vendor_infos = getattr(vd, 'item_variation_vendor_infos', None)
        if vendor_infos:
            for vi in vendor_infos:
                vi_data = getattr(vi, 'item_variation_vendor_info_data', vi)
                print(f"    vendor: {getattr(vi_data, 'vendor_id', 'N/A')}")
                print(f"    vendor price: {getattr(vi_data, 'price_money', 'N/A')}")
        
        # Dump ALL variation data attributes
        all_attrs = [a for a in dir(vd) if not a.startswith('_')]
        print(f"    ALL ATTRS: {all_attrs}")
except Exception as e:
    print(f"  ERROR: {e}")

# ── TEST 6: Check inventory changes for a high-volume item ──
# Find PEPESAY ORG Ghee which we saw in the screenshot
print()
print("=" * 70)
print("TEST 6: Inventory history for a known product")
print("=" * 70)

ghee_var_id = None
for item in client.catalog.list(types="ITEM"):
    if item.item_data and "PEPESAY" in (item.item_data.name or ""):
        if item.item_data.variations:
            ghee_var_id = item.item_data.variations[0].id
            print(f"  Found: {item.item_data.name} -> {ghee_var_id}")
            break

if ghee_var_id:
    ninety_days = (datetime.now(SYDNEY) - timedelta(days=90)).isoformat()
    changes = list(client.inventory.batch_get_changes(
        catalog_object_ids=[ghee_var_id],
        location_ids=[location_id],
        updated_after=ninety_days,
    ))
    print(f"  {len(changes)} changes in last 90 days:")
    
    sales = [c for c in changes if c.adjustment and c.adjustment.to_state == "SOLD"]
    receives = [c for c in changes if c.adjustment and c.adjustment.to_state == "IN_STOCK"]
    other = [c for c in changes if c not in sales and c not in receives]
    
    print(f"    Sales: {len(sales)}")
    print(f"    Receipts: {len(receives)}")
    print(f"    Other: {len(other)}")
    
    if sales:
        total_sold = sum(abs(float(c.adjustment.quantity)) for c in sales)
        first_sale = min(c.adjustment.occurred_at for c in sales)
        last_sale = max(c.adjustment.occurred_at for c in sales)
        print(f"    Total sold: {total_sold}")
        print(f"    First sale: {first_sale}")
        print(f"    Last sale: {last_sale}")
    
    if receives:
        total_recv = sum(float(c.adjustment.quantity) for c in receives)
        last_recv = max(c.adjustment.occurred_at for c in receives)
        print(f"    Total received: {total_recv}")
        print(f"    Last received: {last_recv}")

print()
print("=" * 70)
print("PROBE COMPLETE")
print("=" * 70)
