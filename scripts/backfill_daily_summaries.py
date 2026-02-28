"""
backfill_daily_summaries.py — Populate daily_item_summary from existing transactions.

Run once to backfill, then square_sync.py keeps it updated.

Usage:
    python scripts/backfill_daily_summaries.py
"""
import sys, os, json, urllib.request, time
sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from collections import defaultdict

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


def main():
    print("=" * 60)
    print("Backfilling daily_item_summary from raw transactions")
    print("=" * 60)

    # Step 1: Load all raw transactions
    print("\nStep 1: Loading all transactions...")
    t0 = time.time()
    all_rows = []
    offset = 0
    while True:
        data = supa_get(
            f"transactions?select=date,category,item,qty,net_sales,gross_sales,discounts,tax,transaction_id"
            f"&limit=10000&offset={offset}"
        )
        all_rows.extend(data)
        print(f"  ...loaded {len(all_rows)} rows", end="\r")
        if len(data) < 10000:
            break
        offset += 10000
    print(f"  Loaded {len(all_rows)} transactions in {time.time()-t0:.1f}s")

    # Step 2: Aggregate into (date, category, item) summaries
    print("\nStep 2: Aggregating...")
    summaries = defaultdict(lambda: {
        "total_qty": 0,
        "total_net_sales": 0,
        "total_gross_sales": 0,
        "total_discounts": 0,
        "total_tax": 0,
        "transactions": set(),
    })

    for r in all_rows:
        d = r.get("date", "") or ""
        c = r.get("category", "") or ""
        i = r.get("item", "") or ""
        key = (d, c, i)

        s = summaries[key]
        s["total_qty"] += float(r.get("qty", 0) or 0)
        s["total_net_sales"] += float(r.get("net_sales", 0) or 0)
        s["total_gross_sales"] += float(r.get("gross_sales", 0) or 0)
        s["total_discounts"] += float(r.get("discounts", 0) or 0)
        s["total_tax"] += float(r.get("tax", 0) or 0)
        tid = r.get("transaction_id", "")
        if tid:
            s["transactions"].add(tid)

    print(f"  {len(summaries)} unique (date, category, item) combos")

    # Step 3: Build records for upsert
    records = []
    for (d, c, i), s in summaries.items():
        records.append({
            "date": d,
            "category": c,
            "item": i,
            "total_qty": round(s["total_qty"], 2),
            "total_net_sales": round(s["total_net_sales"], 2),
            "total_gross_sales": round(s["total_gross_sales"], 2),
            "total_discounts": round(s["total_discounts"], 2),
            "total_tax": round(s["total_tax"], 2),
            "transaction_count": len(s["transactions"]),
        })

    # Step 4: Upsert in batches
    print(f"\nStep 3: Upserting {len(records)} summary rows...")
    batch_size = 500
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        status = supa_post(
            "daily_item_summary?on_conflict=date,category,item",
            batch,
            extra_headers={
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
        )
        print(f"  Batch {i//batch_size + 1}: {len(batch)} rows → HTTP {status}")

    print(f"\n✅ Done! {len(records)} summary rows upserted.")


if __name__ == "__main__":
    main()
