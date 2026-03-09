"""
Identify SKU gaps: products in Square CSV but not in Supabase, and vice versa.
Also identifies items without SKUs that can't be matched.
"""
import csv
import json
import os
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

CSV_DIR = Path(__file__).resolve().parent.parent / "Inventory from Square"
ITEM_CSV = CSV_DIR / "projected-profit-EZVZBF6OPY7IJLOZOLVCR33V--2026-03-08.csv"


def parse_dollar(s):
    if not s:
        return 0.0
    return float(s.replace("$", "").replace(",", ""))


def fetch_supabase(source_date):
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        url = (
            f"{SUPABASE_URL}/rest/v1/inventory"
            f"?source_date=eq.{source_date}"
            f"&select=product_name,sku,current_quantity,default_unit_cost,price"
            f"&order=product_name.asc"
            f"&offset={offset}&limit={page_size}"
        )
        req = urllib.request.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        })
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        if not data:
            break
        all_rows.extend(data)
        if len(data) < page_size:
            break
        offset += page_size
    return all_rows


def main():
    dollar = "$"

    # ── Parse Square CSV ──
    with open(ITEM_CSV, "r", encoding="utf-8-sig") as f:
        sq_rows = list(csv.DictReader(f))

    # ── Fetch Supabase ──
    print("Fetching Supabase inventory for 2026-03-08...")
    sb_rows = fetch_supabase("2026-03-08")
    print(f"  Square CSV: {len(sq_rows)} rows")
    print(f"  Supabase:   {len(sb_rows)} rows")
    print()

    # ── Build lookup maps ──
    # Square: group by SKU (some items have multiple variations with same SKU)
    sq_by_sku = {}
    sq_no_sku = []
    for r in sq_rows:
        sku = (r.get("SKU") or "").strip()
        name = r.get("Item Name", "")
        var = r.get("Item Variation Name", "")
        qty = float(r.get("Quantity") or 0)
        val = parse_dollar(r.get("Total Inventory Value", ""))
        retail = parse_dollar(r.get("Total Retail Value Min", ""))
        if not sku:
            sq_no_sku.append({"name": name, "variation": var, "qty": qty, "val": val, "retail": retail})
        else:
            if sku not in sq_by_sku:
                sq_by_sku[sku] = {"name": name, "variation": var, "qty": qty, "val": val, "retail": retail}
            else:
                sq_by_sku[sku]["qty"] += qty
                sq_by_sku[sku]["val"] += val
                sq_by_sku[sku]["retail"] += retail

    # Supabase: by SKU
    sb_by_sku = {}
    sb_by_name = {}
    for r in sb_rows:
        sku = (r.get("sku") or "").strip()
        name = r.get("product_name", "")
        qty = r.get("current_quantity") or 0
        cost = r.get("default_unit_cost") or 0
        price = r.get("price") or 0
        entry = {"name": name, "sku": sku, "qty": qty, "val": qty * cost, "retail": qty * price}
        if sku:
            sb_by_sku[sku] = entry
        sb_by_name[name] = entry

    # ── SECTION 1: Square items with NO SKU ──
    print("=" * 80)
    print("SECTION 1: SQUARE ITEMS WITH NO SKU (cannot match by SKU)")
    print("=" * 80)
    print(f"Total: {len(sq_no_sku)} items")
    print()

    # Try matching by product name instead
    matched_by_name = 0
    unmatched = []
    for item in sq_no_sku:
        name = item["name"]
        if name in sb_by_name:
            matched_by_name += 1
        else:
            unmatched.append(item)

    print(f"  Matched by product name: {matched_by_name}")
    print(f"  Completely unmatched:    {len(unmatched)}")
    print()

    # Show ALL no-SKU items with their status
    print(f"  {'Product':<50} {'Var':<20} {'Qty':>6} {'Value':>10} {'In SB?'}")
    print(f"  {'-'*50} {'-'*20} {'-'*6} {'-'*10} {'-'*6}")
    for item in sorted(sq_no_sku, key=lambda x: x["val"], reverse=True):
        in_sb = "YES" if item["name"] in sb_by_name else "NO"
        print(f"  {item['name'][:50]:<50} {item['variation'][:20]:<20} {item['qty']:>6.1f} {dollar}{item['val']:>9,.2f} {in_sb}")

    print()

    # ── SECTION 2: Square SKUs NOT in Supabase ──
    sq_only_skus = set(sq_by_sku.keys()) - set(sb_by_sku.keys())
    print("=" * 80)
    print("SECTION 2: SQUARE SKUs NOT IN SUPABASE")
    print("=" * 80)
    print(f"Total: {len(sq_only_skus)} SKUs")
    print()

    sq_only_items = [(sku, sq_by_sku[sku]) for sku in sq_only_skus]
    sq_only_items.sort(key=lambda x: abs(x[1]["val"]), reverse=True)

    print(f"  {'SKU':<20} {'Product':<50} {'Qty':>6} {'Value':>10}")
    print(f"  {'-'*20} {'-'*50} {'-'*6} {'-'*10}")
    for sku, item in sq_only_items:
        print(f"  {sku:<20} {item['name'][:50]:<50} {item['qty']:>6.1f} {dollar}{item['val']:>9,.2f}")

    # Try name match for these too
    print()
    print("  Attempting name match for Square-only SKUs:")
    for sku, item in sq_only_items:
        if item["name"] in sb_by_name:
            sb_item = sb_by_name[item["name"]]
            print(f"    {sku}: '{item['name']}' -> found in SB with SKU '{sb_item['sku']}' (qty SQ={item['qty']}, SB={sb_item['qty']})")
        else:
            print(f"    {sku}: '{item['name']}' -> NOT found in Supabase")

    print()

    # ── SECTION 3: Supabase SKUs NOT in Square CSV ──
    sb_only_skus = set(sb_by_sku.keys()) - set(sq_by_sku.keys())
    sb_only_with_stock = [(sku, sb_by_sku[sku]) for sku in sb_only_skus if sb_by_sku[sku]["qty"] > 0]
    sb_only_with_stock.sort(key=lambda x: x[1]["val"], reverse=True)

    print("=" * 80)
    print("SECTION 3: SUPABASE SKUs NOT IN SQUARE CSV")
    print("=" * 80)
    print(f"Total: {len(sb_only_skus)} SKUs")
    print(f"With positive stock: {len(sb_only_with_stock)}")
    print()

    if sb_only_with_stock:
        print(f"  {'SKU':<20} {'Product':<50} {'Qty':>6} {'Value':>10}")
        print(f"  {'-'*20} {'-'*50} {'-'*6} {'-'*10}")
        for sku, item in sb_only_with_stock:
            print(f"  {sku:<20} {item['name'][:50]:<50} {item['qty']:>6.1f} {dollar}{item['val']:>9,.2f}")

    # ── SECTION 4: Value summary ──
    print()
    print("=" * 80)
    print("SECTION 4: IMPACT SUMMARY")
    print("=" * 80)
    
    sq_no_sku_val = sum(i["val"] for i in sq_no_sku if i["qty"] > 0)
    sq_no_sku_unmatched_val = sum(i["val"] for i in unmatched if i["qty"] > 0)
    sq_only_val = sum(sq_by_sku[sku]["val"] for sku in sq_only_skus if sq_by_sku[sku]["qty"] > 0)
    sb_only_val = sum(sb_by_sku[sku]["val"] for sku in sb_only_skus if sb_by_sku[sku]["qty"] > 0)

    print(f"  Square items w/o SKU (pos stock):           {dollar}{sq_no_sku_val:>10,.2f}  ({len([i for i in sq_no_sku if i['qty']>0])} items)")
    print(f"    of which NOT matched by name in SB:       {dollar}{sq_no_sku_unmatched_val:>10,.2f}  ({len([i for i in unmatched if i['qty']>0])} items)")
    print(f"  Square SKUs not in Supabase (pos stock):    {dollar}{sq_only_val:>10,.2f}  ({len([s for s in sq_only_skus if sq_by_sku[s]['qty']>0])} items)")
    print(f"  Supabase SKUs not in Square CSV (pos stock):{dollar}{sb_only_val:>10,.2f}  ({len(sb_only_with_stock)} items)")
    print()
    print(f"  NET unaccounted value in Square:            {dollar}{sq_no_sku_unmatched_val + sq_only_val:>10,.2f}")
    print(f"  NET unaccounted value in Supabase:          {dollar}{sb_only_val:>10,.2f}")


if __name__ == "__main__":
    main()
