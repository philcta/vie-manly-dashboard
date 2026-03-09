"""
Analyze inventory discrepancy between Square CSV export and Supabase data.
Compares the Square 'projected-profit' CSV (2026-03-08) against our inventory table.
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
CAT_CSV = CSV_DIR / "category-profit-EZVZBF6OPY7IJLOZOLVCR33V--2026-03-08.csv"


def parse_dollar(s):
    if not s:
        return 0.0
    return float(s.replace("$", "").replace(",", ""))


def fetch_supabase_inventory(source_date="2026-03-08"):
    """Fetch all inventory rows for a given source_date from Supabase."""
    all_rows = []
    page = 0
    page_size = 1000
    while True:
        url = (
            f"{SUPABASE_URL}/rest/v1/inventory"
            f"?source_date=eq.{source_date}"
            f"&select=product_name,sku,current_quantity,default_unit_cost,price"
            f"&order=product_name.asc"
            f"&offset={page * page_size}&limit={page_size}"
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
        page += 1
    return all_rows


def main():
    # ── Parse Square item-level CSV ──
    with open(ITEM_CSV, "r", encoding="utf-8-sig") as f:
        sq_rows = list(csv.DictReader(f))

    total_sq = len(sq_rows)
    pos_qty_rows = [r for r in sq_rows if r.get("Quantity", "") and float(r["Quantity"]) > 0]
    neg_qty_rows = [r for r in sq_rows if r.get("Quantity", "") and float(r["Quantity"]) < 0]
    zero_qty_rows = [r for r in sq_rows if r.get("Quantity", "") and float(r["Quantity"]) == 0]

    sq_stock_all = sum(parse_dollar(r.get("Total Inventory Value", "")) for r in sq_rows)
    sq_stock_pos = sum(parse_dollar(r.get("Total Inventory Value", "")) for r in pos_qty_rows)
    sq_retail_pos = sum(parse_dollar(r.get("Total Retail Value Min", "")) for r in pos_qty_rows)

    # Items with qty=0 but still have a $0.00 inventory value listed
    zero_qty_with_value = [r for r in zero_qty_rows if parse_dollar(r.get("Total Inventory Value", "")) > 0]

    # ── Parse Square category summary CSV ──
    with open(CAT_CSV, "r", encoding="utf-8-sig") as f:
        cat_rows = list(csv.DictReader(f))
    sq_cat_total = sum(parse_dollar(r.get("Total Inventory Value", "")) for r in cat_rows)

    # ── Fetch Supabase data ──
    print("Fetching Supabase inventory for 2026-03-08...")
    sb_rows = fetch_supabase_inventory("2026-03-08")

    sb_total = len(sb_rows)
    sb_pos = [r for r in sb_rows if (r.get("current_quantity") or 0) > 0]
    sb_neg = [r for r in sb_rows if (r.get("current_quantity") or 0) < 0]
    sb_zero = [r for r in sb_rows if (r.get("current_quantity") or 0) == 0]

    sb_stock_pos = sum(r["current_quantity"] * (r.get("default_unit_cost") or 0) for r in sb_pos)
    sb_retail_pos = sum(r["current_quantity"] * (r.get("price") or 0) for r in sb_pos)
    sb_stock_all = sum((r.get("current_quantity") or 0) * (r.get("default_unit_cost") or 0) for r in sb_rows)

    # ── Report ──
    print()
    print("=" * 70)
    print("SQUARE CSV vs SUPABASE INVENTORY — 2026-03-08")
    print("=" * 70)
    print()
    print("--- Item Counts ---")
    print(f"  Square CSV total rows:     {total_sq:>6}")
    print(f"  Supabase total rows:       {sb_total:>6}")
    print()
    print(f"  Square positive qty:       {len(pos_qty_rows):>6}")
    print(f"  Supabase positive qty:     {len(sb_pos):>6}")
    print()
    print(f"  Square negative qty:       {len(neg_qty_rows):>6}")
    print(f"  Supabase negative qty:     {len(sb_neg):>6}")
    print()
    print(f"  Square zero qty:           {len(zero_qty_rows):>6}")
    print(f"  Supabase zero qty:         {len(sb_zero):>6}")
    print()

    print("--- Stock Value (Cost basis, qty × unit_cost) ---")
    dollar = "$"
    print(f"  Square CSV category total: {dollar}{sq_cat_total:>12,.2f}")
    print(f"  Square CSV item sum (all): {dollar}{sq_stock_all:>12,.2f}")
    print(f"  Square CSV item sum (>0):  {dollar}{sq_stock_pos:>12,.2f}")
    print(f"  Supabase sum (all):        {dollar}{sb_stock_all:>12,.2f}")
    print(f"  Supabase sum (>0):         {dollar}{sb_stock_pos:>12,.2f}")
    print()
    print(f"  Diff (Sq CSV pos - SB pos): {dollar}{sq_stock_pos - sb_stock_pos:>12,.2f}")
    print()

    print("--- Retail Value ---")
    print(f"  Square CSV (pos qty):      {dollar}{sq_retail_pos:>12,.2f}")
    print(f"  Supabase (pos qty):        {dollar}{sb_retail_pos:>12,.2f}")
    print(f"  Diff:                      {dollar}{sq_retail_pos - sb_retail_pos:>12,.2f}")
    print()

    # ── Match items by SKU ──
    # Build SKU → Square data map
    sq_by_sku = {}
    for r in sq_rows:
        sku = (r.get("SKU") or "").strip()
        if sku:
            qty = float(r.get("Quantity") or 0)
            val = parse_dollar(r.get("Total Inventory Value", ""))
            if sku in sq_by_sku:
                sq_by_sku[sku]["qty"] += qty
                sq_by_sku[sku]["val"] += val
            else:
                sq_by_sku[sku] = {"name": r.get("Item Name", ""), "qty": qty, "val": val}

    # Build SKU → Supabase data map
    sb_by_sku = {}
    for r in sb_rows:
        sku = (r.get("sku") or "").strip()
        if sku:
            qty = r.get("current_quantity") or 0
            cost = r.get("default_unit_cost") or 0
            sb_by_sku[sku] = {"name": r.get("product_name", ""), "qty": qty, "val": qty * cost}

    # Find mismatches
    common_skus = set(sq_by_sku.keys()) & set(sb_by_sku.keys())
    sq_only = set(sq_by_sku.keys()) - set(sb_by_sku.keys())
    sb_only = set(sb_by_sku.keys()) - set(sq_by_sku.keys())

    print("--- SKU Matching ---")
    print(f"  Square SKUs:       {len(sq_by_sku):>6}")
    print(f"  Supabase SKUs:     {len(sb_by_sku):>6}")
    print(f"  Common SKUs:       {len(common_skus):>6}")
    print(f"  Square only:       {len(sq_only):>6}")
    print(f"  Supabase only:     {len(sb_only):>6}")
    print()

    # Quantity mismatches
    qty_diff = []
    val_diff = []
    for sku in common_skus:
        sq = sq_by_sku[sku]
        sb = sb_by_sku[sku]
        if abs(sq["qty"] - sb["qty"]) > 0.01:
            qty_diff.append((sku, sq["name"], sq["qty"], sb["qty"], sq["qty"] - sb["qty"]))
        if abs(sq["val"] - sb["val"]) > 0.01:
            val_diff.append((sku, sq["name"], sq["val"], sb["val"], sq["val"] - sb["val"]))

    print(f"  Quantity mismatches: {len(qty_diff):>5}")
    print(f"  Value mismatches:    {len(val_diff):>5}")
    print()

    # Top 20 biggest value differences
    val_diff.sort(key=lambda x: abs(x[4]), reverse=True)
    if val_diff:
        print("--- Top 20 Value Differences (by absolute diff) ---")
        print(f"  {'SKU':<16} {'Item':<45} {'Sq Val':>10} {'SB Val':>10} {'Diff':>10}")
        print(f"  {'-'*16} {'-'*45} {'-'*10} {'-'*10} {'-'*10}")
        for sku, name, sq_v, sb_v, diff in val_diff[:20]:
            print(f"  {sku:<16} {name[:45]:<45} {dollar}{sq_v:>9,.2f} {dollar}{sb_v:>9,.2f} {dollar}{diff:>9,.2f}")

    # Items in Supabase but not in Square (by SKU)
    if sb_only:
        sb_only_val = sum(sb_by_sku[sku]["val"] for sku in sb_only if sb_by_sku[sku]["qty"] > 0)
        sb_only_pos = [sku for sku in sb_only if sb_by_sku[sku]["qty"] > 0]
        print()
        print(f"--- Supabase-only items (not in Square CSV) ---")
        print(f"  Total:             {len(sb_only):>6}")
        print(f"  With positive qty: {len(sb_only_pos):>6}  (value: {dollar}{sb_only_val:,.2f})")
        if sb_only_pos:
            print(f"  Top 10:")
            sorted_sb = sorted(sb_only_pos, key=lambda s: sb_by_sku[s]["val"], reverse=True)
            for sku in sorted_sb[:10]:
                r = sb_by_sku[sku]
                print(f"    {sku:<16} {r['name'][:45]:<45} qty={r['qty']:<6} val={dollar}{r['val']:,.2f}")

    # Square items with no SKU
    no_sku = [r for r in sq_rows if not (r.get("SKU") or "").strip()]
    no_sku_pos = [r for r in no_sku if r.get("Quantity", "") and float(r["Quantity"]) > 0]
    no_sku_val = sum(parse_dollar(r.get("Total Inventory Value", "")) for r in no_sku_pos)
    print()
    print(f"--- Square items with NO SKU ---")
    print(f"  Total:             {len(no_sku):>6}")
    print(f"  With positive qty: {len(no_sku_pos):>6}  (value: {dollar}{no_sku_val:,.2f})")
    if no_sku_pos:
        sorted_nosku = sorted(no_sku_pos, key=lambda r: parse_dollar(r.get("Total Inventory Value", "")), reverse=True)
        print(f"  Top 10:")
        for r in sorted_nosku[:10]:
            name = r.get("Item Name", "")
            var = r.get("Item Variation Name", "")
            qty = float(r.get("Quantity") or 0)
            val = parse_dollar(r.get("Total Inventory Value", ""))
            print(f"    {name[:40]:<40} [{var}] qty={qty:<6} val={dollar}{val:,.2f}")


if __name__ == "__main__":
    main()
