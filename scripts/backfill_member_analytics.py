"""
backfill_member_analytics.py — Populate member_daily_stats and daily_store_stats
from existing transactions.

Can be run standalone OR imported by scheduled_sync:
    python scripts/backfill_member_analytics.py          # Full backfill
    from scripts.backfill_member_analytics import run_member_daily_stats_update  # Import
"""
import sys, os, json, urllib.request, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from collections import defaultdict
from datetime import datetime, timedelta

SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

HEADERS = {
    "apikey": SUPA_KEY,
    "Authorization": f"Bearer {SUPA_KEY}",
    "Content-Type": "application/json",
}


def supa_get(endpoint):
    url = f"{SUPA_URL}/rest/v1/{endpoint}"
    req = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=60)
    return json.loads(resp.read())


def supa_post(endpoint, data, extra_headers=None):
    url = f"{SUPA_URL}/rest/v1/{endpoint}"
    hdrs = dict(HEADERS)
    if extra_headers:
        hdrs.update(extra_headers)
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    resp = urllib.request.urlopen(req, timeout=60)
    return resp.status


def load_all_transactions():
    """Load all transactions with customer_id, date, net_sales, qty, transaction_id."""
    print("Loading all transactions...")
    all_rows = []
    offset = 0
    page_size = 5000
    while True:
        data = supa_get(
            f"transactions?select=customer_id,date,net_sales,qty,transaction_id"
            f"&order=id&limit={page_size}&offset={offset}"
        )
        all_rows.extend(data)
        print(f"  ...loaded {len(all_rows)} rows", end="\r")
        if len(data) < page_size:
            break
        offset += page_size
    print(f"  Loaded {len(all_rows)} transactions")
    return all_rows


# Note: Only enrolled members have a customer_id in Square transactions.
# Any transaction with a non-empty customer_id = member transaction.


def build_member_daily_stats(transactions):
    """Build member_daily_stats records from raw transactions."""
    print("\nBuilding member_daily_stats...")
    
    # Group transactions by (customer_id, date)
    member_days = defaultdict(lambda: {
        "day_spent": 0.0,
        "day_items": 0,
        "transactions": set(),
    })
    
    for tx in transactions:
        cid = tx.get("customer_id") or ""
        if not cid:  # No customer_id = non-member, skip
            continue
        date = tx.get("date") or ""
        if not date:
            continue
        
        key = (cid, date)
        member_days[key]["day_spent"] += float(tx.get("net_sales", 0) or 0)
        member_days[key]["day_items"] += int(float(tx.get("qty", 0) or 0))
        tid = tx.get("transaction_id")
        if tid:
            member_days[key]["transactions"].add(tid)
    
    # Get all dates sorted
    all_dates = sorted(set(d for _, d in member_days.keys()))
    all_customers = sorted(set(c for c, _ in member_days.keys()))
    
    print(f"  {len(all_customers)} members, {len(all_dates)} dates, {len(member_days)} (member, date) combos")
    
    # Build cumulative stats for each member
    records = []
    for cid in all_customers:
        cum_spent = 0.0
        cum_items = 0
        cum_visits = 0
        cum_transactions = 0
        last_visit_date = None
        recent_visits = []  # dates of visits in last 30 days
        recent_spend = []   # daily spend in last 30 days
        
        for date in all_dates:
            key = (cid, date)
            if key in member_days:
                day = member_days[key]
                cum_spent += day["day_spent"]
                cum_items += day["day_items"]
                cum_visits += 1
                cum_transactions += len(day["transactions"])
                
                # Track recent history for 30d metrics
                recent_visits.append(date)
                recent_spend.append(day["day_spent"])
                
                days_since = 0
                if last_visit_date:
                    d1 = datetime.strptime(last_visit_date, "%Y-%m-%d")
                    d2 = datetime.strptime(date, "%Y-%m-%d")
                    days_since = (d2 - d1).days
                
                last_visit_date = date
                
                # Calculate 30d window
                cutoff_30d = datetime.strptime(date, "%Y-%m-%d")
                cutoff_30d_str = (cutoff_30d - timedelta(days=30)).strftime("%Y-%m-%d")
                visits_30d = sum(1 for d in recent_visits if d >= cutoff_30d_str)
                spend_30d = sum(s for d, s in zip(recent_visits, recent_spend) if d >= cutoff_30d_str)
                
                records.append({
                    "square_customer_id": cid,
                    "date": date,
                    "total_spent": round(cum_spent, 2),
                    "total_items": cum_items,
                    "total_visits": cum_visits,
                    "total_transactions": cum_transactions,
                    "day_spent": round(day["day_spent"], 2),
                    "day_items": day["day_items"],
                    "day_transactions": len(day["transactions"]),
                    "avg_spend_per_visit": round(cum_spent / cum_visits, 2) if cum_visits > 0 else 0,
                    "avg_items_per_visit": round(cum_items / cum_visits, 2) if cum_visits > 0 else 0,
                    "days_since_last_visit": days_since,
                    "visit_frequency_30d": round(visits_30d, 2),
                    "spend_trend_30d": round(spend_30d / 30, 2),
                })
    
    print(f"  Generated {len(records)} member_daily_stats records")
    return records


def build_daily_store_stats(transactions):
    """Build daily_store_stats records with member vs non-member split."""
    print("\nBuilding daily_store_stats...")
    
    # Group by date
    days = defaultdict(lambda: {
        "total_tx": set(),
        "total_sales": 0.0,
        "total_items": 0,
        "total_customers": set(),
        "member_tx": set(),
        "member_sales": 0.0,
        "member_items": 0,
        "member_customers": set(),
        "nonmember_tx": set(),
        "nonmember_sales": 0.0,
        "nonmember_items": 0,
    })
    
    for tx in transactions:
        date = tx.get("date") or ""
        if not date:
            continue
        
        cid = tx.get("customer_id") or ""
        tid = tx.get("transaction_id") or ""
        net = float(tx.get("net_sales", 0) or 0)
        qty = int(float(tx.get("qty", 0) or 0))
        is_member = bool(cid)  # Has customer_id = member
        
        d = days[date]
        if tid:
            d["total_tx"].add(tid)
        d["total_sales"] += net
        d["total_items"] += qty
        if cid:
            d["total_customers"].add(cid)
        
        if is_member:
            if tid:
                d["member_tx"].add(tid)
            d["member_sales"] += net
            d["member_items"] += qty
            d["member_customers"].add(cid)
        else:
            if tid:
                d["nonmember_tx"].add(tid)
            d["nonmember_sales"] += net
            d["nonmember_items"] += qty
    
    records = []
    for date in sorted(days.keys()):
        d = days[date]
        total_tx = len(d["total_tx"])
        member_tx = len(d["member_tx"])
        nonmember_tx = len(d["nonmember_tx"])
        total_sales = d["total_sales"]
        member_sales = d["member_sales"]
        total_items = d["total_items"]
        member_items = d["member_items"]
        
        records.append({
            "date": date,
            "total_transactions": total_tx,
            "total_net_sales": round(total_sales, 2),
            "total_items": total_items,
            "total_unique_customers": len(d["total_customers"]),
            "member_transactions": member_tx,
            "member_net_sales": round(member_sales, 2),
            "member_items": member_items,
            "member_unique_customers": len(d["member_customers"]),
            "non_member_transactions": nonmember_tx,
            "non_member_net_sales": round(d["nonmember_sales"], 2),
            "non_member_items": d["nonmember_items"],
            "member_tx_ratio": round(member_tx / total_tx, 4) if total_tx > 0 else 0,
            "member_sales_ratio": round(member_sales / total_sales, 4) if total_sales > 0 else 0,
            "member_items_ratio": round(member_items / total_items, 4) if total_items > 0 else 0,
        })
    
    print(f"  Generated {len(records)} daily_store_stats records")
    return records


def upsert_batch(table, records, conflict_cols, label=""):
    """Upsert records in batches."""
    batch_size = 500
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        status = supa_post(
            f"{table}?on_conflict={conflict_cols}",
            batch,
            extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )
        total += len(batch)
        print(f"  {label} batch {i//batch_size + 1}: {len(batch)} rows → HTTP {status}")
    return total


def run_member_daily_stats_update():
    """
    Callable entry point for scheduled_sync.
    Loads ALL transactions, rebuilds member_daily_stats from scratch.
    
    Returns:
        dict with status and counts
    """
    t0 = time.time()
    result = {
        "status": "success",
        "member_daily_stats": 0,
    }
    
    try:
        # Load all transactions
        transactions = load_all_transactions()
        
        # Build and upsert member_daily_stats
        member_stats = build_member_daily_stats(transactions)
        if member_stats:
            upserted = upsert_batch(
                "member_daily_stats",
                member_stats,
                "square_customer_id,date",
                label="member_daily_stats"
            )
            result["member_daily_stats"] = upserted
        
        elapsed = time.time() - t0
        print(f"  ✅ member_daily_stats update complete: {result['member_daily_stats']} rows in {elapsed:.1f}s")
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print(f"  ❌ member_daily_stats update failed: {e}")
    
    return result


def main():
    print("=" * 60)
    print("Backfilling member analytics tables")
    print("=" * 60)
    
    t0 = time.time()
    
    # Load data
    transactions = load_all_transactions()
    
    # Build and upsert member_daily_stats
    # (only transactions with customer_id are members)
    member_stats = build_member_daily_stats(transactions)
    if member_stats:
        upsert_batch(
            "member_daily_stats",
            member_stats,
            "square_customer_id,date",
            label="member_daily_stats"
        )
    
    # Build and upsert daily_store_stats
    store_stats = build_daily_store_stats(transactions)
    if store_stats:
        upsert_batch(
            "daily_store_stats",
            store_stats,
            "date",
            label="daily_store_stats"
        )
    
    elapsed = time.time() - t0
    print(f"\n✅ Done in {elapsed:.1f}s!")
    print(f"   member_daily_stats: {len(member_stats)} rows")
    print(f"   daily_store_stats:  {len(store_stats)} rows")


if __name__ == "__main__":
    main()
