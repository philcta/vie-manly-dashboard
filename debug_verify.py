"""
Diagnose net sales differences between CSV export and Square API rebuild.

Investigates days with largest discrepancies to find root cause:
- Nov 12 (diff = -121, CSV > API)
- Nov 16 (diff = +209, API > CSV)  
- Nov 20 (diff = +159, API > CSV)
- Nov 13 (3 txn diff), Nov 15 (2 txn diff), Nov 23 (1 txn diff)
"""
import os, json, urllib.request, datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("SQUARE_ACCESS_TOKEN")
loc_id = os.getenv("SQUARE_LOCATION_ID")
supa_url = os.getenv("SUPABASE_URL")
supa_key = os.getenv("SUPABASE_ANON_KEY")
SQ_BASE = "https://connect.squareup.com/v2"
SQ_HEADERS = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Square-Version": "2024-01-18"}
SYDNEY_TZ = ZoneInfo("Australia/Sydney")


def fetch_sq_orders(start_utc, end_utc):
    """Fetch orders from Square for UTC range."""
    all_orders = []
    cursor = None
    while True:
        body = {
            "location_ids": [loc_id],
            "query": {
                "filter": {
                    "date_time_filter": {"created_at": {"start_at": start_utc, "end_at": end_utc}},
                    "state_filter": {"states": ["COMPLETED"]},
                },
            },
            "limit": 500,
        }
        if cursor:
            body["cursor"] = cursor
        req = urllib.request.Request(f"{SQ_BASE}/orders/search", data=json.dumps(body).encode(), headers=SQ_HEADERS, method="POST")
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        orders = data.get("orders", [])
        all_orders.extend(orders)
        cursor = data.get("cursor")
        if not cursor or not orders:
            break
    return all_orders


def fetch_supa_rows(date_str):
    """Fetch all rows from Supabase for a date."""
    all_rows = []
    offset = 0
    while True:
        ep = (
            f"{supa_url}/rest/v1/transactions?select=*"
            f"&datetime=gte.{date_str}T00:00:00&datetime=lte.{date_str}T23:59:59"
            f"&limit=1000&offset={offset}"
        )
        req = urllib.request.Request(ep, headers={"apikey": supa_key, "Authorization": f"Bearer {supa_key}"})
        resp = urllib.request.urlopen(req, timeout=15)
        rows = json.loads(resp.read())
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < 1000:
            break
        offset += 1000
    return all_rows


def analyze_day(date_str, csv_net, csv_txns):
    """Deep analysis of a specific day."""
    print(f"\n{'='*70}")
    print(f"ANALYZING: {date_str}")
    print(f"{'='*70}")
    
    # 1. Get Supabase data (rebuilt from API, Sydney time)
    supa_rows = fetch_supa_rows(date_str)
    supa_net = sum(float(r.get("net_sales", 0) or 0) for r in supa_rows)
    supa_gross = sum(float(r.get("gross_sales", 0) or 0) for r in supa_rows)
    supa_disc = sum(float(r.get("discounts", 0) or 0) for r in supa_rows)
    supa_txns = len(set(r.get("transaction_id", "") for r in supa_rows if r.get("transaction_id")))
    
    print(f"\nSupabase (rebuilt, Sydney time):")
    print(f"  Rows: {len(supa_rows)}, Txns: {supa_txns}")
    print(f"  Net Sales:   {supa_net:.2f}")
    print(f"  Gross Sales: {supa_gross:.2f}")
    print(f"  Discounts:   {supa_disc:.2f}")
    print(f"  Check: gross + disc = {supa_gross + supa_disc:.2f} (should ~ net)")
    
    # 2. Check: How many line items have net_sales != gross_sales + discounts?
    mismatches = 0
    for r in supa_rows:
        ns = float(r.get("net_sales", 0) or 0)
        gs = float(r.get("gross_sales", 0) or 0)
        dc = float(r.get("discounts", 0) or 0)
        if abs(ns - (gs + dc)) > 0.02:
            mismatches += 1
    if mismatches:
        print(f"  ⚠ {mismatches} rows where net_sales != gross + discounts")
    
    # 3. Square API: fetch UTC range that covers this Sydney day
    # Sydney day 2025-11-XX 00:00:00 AEDT (UTC+11) = 2025-11-{XX-1} 13:00:00 UTC
    d = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    sydney_start = d.replace(hour=0, minute=0, second=0, tzinfo=SYDNEY_TZ)
    sydney_end = d.replace(hour=23, minute=59, second=59, tzinfo=SYDNEY_TZ)
    utc_start = sydney_start.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    utc_end = sydney_end.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    print(f"\n  Sydney day {date_str} 00:00-23:59 AEDT = UTC {utc_start} to {utc_end}")
    
    orders = fetch_sq_orders(utc_start, utc_end)
    
    # Calculate Square net sales
    # Method A: sum of order-level net_amounts
    sq_net_a = sum(int(o.get("net_amounts", {}).get("total_money", {}).get("amount", 0)) for o in orders) / 100
    
    # Method B: sum line items (total_money - total_tax)
    sq_net_b = 0
    sq_gross_b = 0
    sq_disc_b = 0
    sq_tax_b = 0
    for o in orders:
        for li in o.get("line_items", []):
            total_money = int(li.get("total_money", {}).get("amount", 0)) / 100
            total_tax = int(li.get("total_tax_money", {}).get("amount", 0)) / 100
            base_price = int(li.get("base_price_money", {}).get("amount", 0)) / 100
            qty = float(li.get("quantity", "0"))
            total_disc = int(li.get("total_discount_money", {}).get("amount", 0)) / 100
            sq_net_b += (total_money - total_tax)
            sq_gross_b += (base_price * qty)
            sq_disc_b += total_disc
            sq_tax_b += total_tax
    
    # Method C: Order-level total_money (includes tax)
    sq_total_c = sum(int(o.get("total_money", {}).get("amount", 0)) for o in orders) / 100
    sq_tax_c = sum(int(o.get("total_tax_money", {}).get("amount", 0)) for o in orders) / 100
    
    # Check for refunds, returns
    refund_count = sum(1 for o in orders if o.get("refunds"))
    
    # Check for service charges, tips
    service_charges = 0
    tips = 0
    for o in orders:
        for sc in o.get("service_charges", []):
            service_charges += int(sc.get("total_money", {}).get("amount", 0))
        for t in o.get("tenders", []):
            tip = int(t.get("tip_money", {}).get("amount", 0))
            tips += tip
    
    print(f"\nSquare API (UTC window for this Sydney day):")
    print(f"  Orders: {len(orders)}")
    print(f"  Net (order-level net_amounts): {sq_net_a:.2f}")
    print(f"  Net (line items total-tax):    {sq_net_b:.2f}")
    print(f"  Gross (line items base*qty):   {sq_gross_b:.2f}")
    print(f"  Discounts (line items):        {sq_disc_b:.2f}")
    print(f"  Tax (line items):              {sq_tax_b:.2f}")
    print(f"  Total (order-level):           {sq_total_c:.2f}")
    print(f"  Tax (order-level):             {sq_tax_c:.2f}")
    print(f"  Net = Total-Tax (order-level): {sq_total_c - sq_tax_c:.2f}")
    print(f"  Orders with refunds:           {refund_count}")
    print(f"  Service charges (cents):       {service_charges}")
    print(f"  Tips (cents):                  {tips}")
    
    print(f"\nCOMPARISON:")
    print(f"  CSV net sales:       {csv_net}")
    print(f"  Supabase net sales:  {supa_net:.2f}")
    print(f"  SQ net_amounts:      {sq_net_a:.2f}")
    print(f"  SQ line items net:   {sq_net_b:.2f}")
    print(f"  SQ total-tax:        {sq_total_c - sq_tax_c:.2f}")
    
    diff_csv_vs_supa = csv_net - supa_net
    diff_csv_vs_sq = csv_net - sq_net_b
    print(f"\n  CSV - Supabase = {diff_csv_vs_supa:.2f}")
    print(f"  CSV - SQ line items = {diff_csv_vs_sq:.2f}")
    print(f"  Supabase - SQ line items = {supa_net - sq_net_b:.2f}")
    print(f"  net_amounts - line items net = {sq_net_a - sq_net_b:.2f}")
    
    if csv_txns:
        print(f"\n  CSV txns: {csv_txns}, Supabase txns: {supa_txns}, SQ orders: {len(orders)}")


# Analyze the problem days
# From the spreadsheet:
# Day 1 = Nov 10, Day 3 = Nov 12, Day 4 = Nov 13, Day 7 = Nov 16
# Day 11 = Nov 20, Day 13 = Nov 22, Day 14 = Nov 23

analyze_day("2025-11-12", 4407, 194)   # CSV > API by 121
analyze_day("2025-11-16", 5713, 252)   # API > CSV by 209
analyze_day("2025-11-13", 5115, 206)   # 3 txn diff
analyze_day("2025-11-15", 4785, 205)   # 2 txn diff
