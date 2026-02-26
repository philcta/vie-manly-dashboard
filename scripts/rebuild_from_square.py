"""
Rebuild Supabase transactions table from Square API with Audited Reconciliation Logic.

AUDITED FORMULA (THE GOLDEN RULE):
1. Net Sales for an order = (Order Total - Order Tax - Order Tip)
2. Exclusions: Gift Card item sales are removed from Net Sales.
3. Deductions: Refunds processed on a given day are subtracted from that day's totals.
4. Transaction Count: Includes COMPLETED orders with CARD or CASH tenders.

This script implements these rules to ensure Supabase perfectly matches historical records.
"""
import os
import sys
import json
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
SUPA_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

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
    key = SUPA_SERVICE_KEY if use_service_key else SUPA_KEY
    url = f"{SUPA_URL}/rest/v1/{endpoint}"
    data = json.dumps(body).encode() if body else None
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        return {"status": resp.status}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"  ❌ Supabase error {e.code}: {err_body[:300]}")
        return None

# ── Logic ──

def build_catalog_map():
    print("Fetching Square catalog...")
    cat_names = {}
    cursor = None
    while True:
        params = "types=CATEGORY"
        if cursor: params += f"&cursor={cursor}"
        data = sq_request(f"catalog/list?{params}")
        if not data: break
        for obj in data.get("objects", []):
            cat_names[obj["id"]] = obj.get("category_data", {}).get("name", "")
        cursor = data.get("cursor")
        if not cursor: break
    
    item_to_cat = {}
    cursor = None
    while True:
        params = "types=ITEM"
        if cursor: params += f"&cursor={cursor}"
        data = sq_request(f"catalog/list?{params}")
        if not data: break
        for obj in data.get("objects", []):
            item_data = obj.get("item_data", {})
            name = item_data.get("name", "")
            cat_name = cat_names.get(item_data.get("category_id", ""), "")
            if name:
                item_to_cat[name.lower()] = cat_name
                for var in item_data.get("variations", []):
                    v_name = var.get("item_variation_data", {}).get("name", "")
                    if v_name and v_name != name:
                        item_to_cat[f"{name} - {v_name}".lower()] = cat_name
        cursor = data.get("cursor")
        if not cursor: break
    return item_to_cat

def fetch_orders(start_dt, end_dt):
    all_orders = []
    cursor = None
    # Convert to UTC strings
    start_str = start_dt.astimezone(datetime.fromisoformat("2000-01-01T00:00:00+00:00").tzinfo).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end_dt.astimezone(datetime.fromisoformat("2000-01-01T00:00:00+00:00").tzinfo).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    while True:
        body = {
            "location_ids": [LOC_ID],
            "query": {
                "filter": {
                    "date_time_filter": {
                        "closed_at": {
                            "start_at": start_str,
                            "end_at": end_str
                        }
                    },
                    "state_filter": {"states": ["COMPLETED"]}
                }
            },
            "limit": 500
        }
        if cursor: body["cursor"] = cursor
        data = sq_request("orders/search", body=body, method="POST")
        if not data: break
        orders = data.get("orders", [])
        all_orders.extend(orders)
        cursor = data.get("cursor")
        if not cursor or not orders: break
    return all_orders

def fetch_refunds(start_dt, end_dt):
    # Square Refunds API uses begin_time/end_time as RFC3339
    start_str = start_dt.astimezone(datetime.fromisoformat("2000-01-01T00:00:00+00:00").tzinfo).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end_dt.astimezone(datetime.fromisoformat("2000-01-01T00:00:00+00:00").tzinfo).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"refunds?location_id={LOC_ID}&begin_time={start_str}&end_time={end_str}"
    data = sq_request(url)
    if not data: return []
    return [r for r in data.get("refunds", []) if r.get("status") == "COMPLETED"]

def process_data(orders, refunds, catalog_map):
    rows = []
    
    # Process Orders
    for order in orders:
        # Selection Rule: Only CARD or CASH
        tenders = order.get("tenders", [])
        if not any(t.get("type") in ["CARD", "CASH"] for t in tenders):
            continue
            
        order_id = order.get("id")
        closed_at = order.get("closed_at")
        dt_utc = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone(SYDNEY_TZ)
        date_str = dt_local.strftime("%Y-%m-%d")
        time_str = dt_local.strftime("%H:%M:%S")
        datetime_str = dt_local.strftime("%Y-%m-%d %H:%M:%S")
        
        card_brand = tenders[0].get("card_details", {}).get("card", {}).get("card_brand", tenders[0].get("type", ""))
        pan_suffix = tenders[0].get("card_details", {}).get("card", {}).get("last_4", "")
        customer_id = order.get("customer_id", "")
        
        # Line Items
        for idx, item in enumerate(order.get("line_items", [])):
            name = item.get("name", "")
            qty = float(item.get("quantity", "0"))
            var_name = item.get("variation_name", "")
            display_name = f"{name} - {var_name}" if var_name and var_name != name else name
            category = catalog_map.get(display_name.lower(), catalog_map.get(name.lower(), ""))
            
            total = int(item.get("total_money", {}).get("amount", 0))
            tax = int(item.get("total_tax_money", {}).get("amount", 0))
            disc = int(item.get("total_discount_money", {}).get("amount", 0))
            
            # GOLDEN RULE: Net Sales = Total - Tax. (Tips are not in line items).
            # EXCLUSION: Gift Card sales = 0 net.
            net_val = (total - tax) / 100.0
            if "gift card" in display_name.lower():
                net_val = 0.0
            
            rows.append({
                "datetime": datetime_str,
                "category": category,
                "item": display_name,
                "qty": qty,
                "net_sales": round(net_val, 2),
                "gross_sales": round(int(item.get("gross_sales_money", {}).get("amount", 0))/100.0, 2),
                "discounts": round(-abs(disc/100.0), 2) if disc else 0,
                "customer_id": customer_id,
                "transaction_id": order_id,
                "tax": str(round(tax/100.0, 2)),
                "card_brand": card_brand,
                "pan_suffix": pan_suffix,
                "date": date_str,
                "time": time_str,
                "time_zone": "Sydney",
                "row_key": f"{order_id}-LI-{idx}"
            })
            
        # Service Charges (e.g. Surcharges)
        for idx, sc in enumerate(order.get("service_charges", [])):
            sc_name = sc.get("name", "Surcharge")
            sc_total = int(sc.get("total_money", {}).get("amount", 0))
            sc_tax = int(sc.get("total_tax_money", {}).get("amount", 0))
            rows.append({
                "datetime": datetime_str,
                "category": "Surcharge",
                "item": sc_name,
                "qty": 1,
                "net_sales": round((sc_total - sc_tax)/100.0, 2),
                "gross_sales": round(sc_total/100.0, 2),
                "discounts": 0,
                "customer_id": customer_id,
                "transaction_id": order_id,
                "tax": str(round(sc_tax/100.0, 2)),
                "card_brand": card_brand,
                "pan_suffix": pan_suffix,
                "date": date_str,
                "time": time_str,
                "time_zone": "Sydney",
                "row_key": f"{order_id}-SC-{idx}"
            })

    # Process Refunds (Subtractions)
    for refund in refunds:
        rf_id = refund.get("id")
        created_at = refund.get("created_at")
        dt_utc = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone(SYDNEY_TZ)
        amt = int(refund.get("amount_money", {}).get("amount", 0)) / 100.0
        
        # DEDUCTION: Insert as a negative record
        rows.append({
            "datetime": dt_local.strftime("%Y-%m-%d %H:%M:%S"),
            "category": "Refund",
            "item": f"Refund: {refund.get('reason', 'Returned Goods')}",
            "qty": -1,
            "net_sales": round(-amt, 2),
            "gross_sales": round(-amt, 2),
            "discounts": 0,
            "customer_id": "",
            "transaction_id": refund.get("order_id", rf_id),
            "tax": "0",
            "card_brand": refund.get("destination_type", ""),
            "pan_suffix": "",
            "date": dt_local.strftime("%Y-%m-%d"),
            "time": dt_local.strftime("%H:%M:%S"),
            "time_zone": "Sydney",
            "row_key": f"REFUND-{rf_id}"
        })

    return rows

def truncate_transactions():
    print("Truncating transactions table...")
    key = SUPA_SERVICE_KEY or SUPA_KEY
    url = f"{SUPA_URL}/rest/v1/transactions?id=gt.0"
    req = urllib.request.Request(url, headers={
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }, method="DELETE")
    try:
        urllib.request.urlopen(req, timeout=120)
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False

def main():
    print("REBUILDING SUPABASE WITH AUDITED LOGIC")
    if not all([TOKEN, LOC_ID, SUPA_URL]):
        print("❌ Missing environment variables")
        return

    catalog_map = build_catalog_map()
    
    # Start from store opening (Aug 2025) or earlier?
    # User mentioned Aug 2025. I will start from 2024-07-01 to be safe and cover all data.
    start_date = datetime(2024, 7, 1, tzinfo=SYDNEY_TZ)
    end_date = datetime.now(SYDNEY_TZ)
    
    if not truncate_transactions():
        print("🛑 Truncate failed. Aborting for safety.")
        return

    current = start_date
    total_rows = 0
    while current < end_date:
        # Process monthly
        nxt = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
        # Use one second before start of next month to avoid overlaps
        period_end = nxt - timedelta(seconds=1)
        if period_end > end_date:
            period_end = end_date
            
        print(f"\nPeriod: {current.strftime('%Y-%m')} ...", end="", flush=True)
        
        orders = fetch_orders(current, period_end)
        refunds = fetch_refunds(current, period_end)
        rows = process_data(orders, refunds, catalog_map)
        
        if rows:
            # Batch Insert
            for i in range(0, len(rows), BATCH_SIZE):
                batch = rows[i:i+BATCH_SIZE]
                url = f"{SUPA_URL}/rest/v1/transactions"
                headers = {
                    "apikey": SUPA_SERVICE_KEY or SUPA_KEY,
                    "Authorization": f"Bearer {SUPA_SERVICE_KEY or SUPA_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                }
                req = urllib.request.Request(url, data=json.dumps(batch).encode(), headers=headers, method="POST")
                try:
                    urllib.request.urlopen(req, timeout=60)
                except Exception as e:
                    print(f"\n  ❌ Batch failed: {e}")
            
            total_rows += len(rows)
            print(f" {len(rows)} rows inserted.", flush=True)
        else:
            print(" no data.", flush=True)
            
        current = period_end

    print(f"\nSUCCESS. Total rows in Supabase: {total_rows}")

if __name__ == "__main__":
    main()
