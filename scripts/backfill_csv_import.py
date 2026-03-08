"""
CSV Backfill Import — RESUME version
=====================================
Picks up where the previous import stopped.
Uses upsert with on_conflict=row_key to skip duplicates.
Set RESUME_FROM_DATE to skip already-imported months.
"""
import csv, os, glob, json, sys, hashlib, time, urllib.request, urllib.error
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
HEADERS = {
    "apikey": SUPA_KEY,
    "Authorization": f"Bearer {SUPA_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}

CSV_FOLDER = r"F:\1. PROPERTY TRACKS\9. Marketing\Content\2026\Denoux\App24\data before Square\Transactions"

# Skip CSVs that overlap with API-sourced data
SKIP_FILES = {
    "items-2025-08-17-2025-09-28.csv",
    "items-2025-09-25-2025-10-07.csv",
}

# Only import rows on or after this date (Jan-Nov 2024 already imported)
RESUME_FROM_DATE = "2024-12-01"

BATCH_SIZE = 300


def supa_rpc(fn_name, params=None):
    body = json.dumps(params or {}).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPA_URL}/rest/v1/rpc/{fn_name}",
        data=body,
        headers={
            "apikey": SUPA_KEY,
            "Authorization": f"Bearer {SUPA_KEY}",
            "Content-Type": "application/json",
        },
        method="POST"
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


def supa_post(path, data):
    body = json.dumps(data).encode("utf-8")
    # Use on_conflict=row_key so PostgREST knows which unique column to merge on
    url = f"{SUPA_URL}/rest/v1/{path}?on_conflict=row_key"
    req = urllib.request.Request(
        url,
        data=body,
        headers=HEADERS,
        method="POST"
    )
    try:
        resp = urllib.request.urlopen(req)
        return resp.status
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        raise Exception(f"HTTP {e.code}: {err_body[:200]}")


def supa_get(path, params=""):
    url = f"{SUPA_URL}/rest/v1/{path}?{params}" if params else f"{SUPA_URL}/rest/v1/{path}"
    req = urllib.request.Request(url, headers={
        "apikey": SUPA_KEY,
        "Authorization": f"Bearer {SUPA_KEY}",
    })
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


def parse_money(val):
    v = (val or "0").replace("$", "").replace(",", "").strip()
    try:
        return round(float(v), 2)
    except:
        return 0.0


# ── Step 1: Get existing tx IDs via RPC (fast) ──────────────────────
print("Step 1: Loading existing transaction IDs via RPC...")
t0 = time.time()

# Create a temporary function if needed, or just use the upsert approach
# Since we use row_key for upsert conflict, duplicates will just be skipped
# So we DON'T need to pre-load all IDs at all!
# The `Prefer: resolution=merge-duplicates` header handles it.
print("  Using upsert with row_key dedup — no pre-loading needed ✓")
print(f"  (took {time.time()-t0:.1f}s)")

# ── Step 2: Build customer name → Supabase ID mapping ───────────────
print("\nStep 2: Building customer name mapping...")
members = []
offset = 0
while True:
    batch = supa_get("members", f"select=square_customer_id,first_name,last_name&offset={offset}&limit=5000")
    if not batch:
        break
    members.extend(batch)
    if len(batch) < 5000:
        break
    offset += 5000

name_to_id = {}
for m in members:
    fn = (m.get("first_name") or "").strip()
    ln = (m.get("last_name") or "").strip()
    full = f"{fn} {ln}".strip().lower()
    if full:
        name_to_id[full] = m["square_customer_id"]

print(f"  Built mapping for {len(name_to_id):,} named members")

mappings = supa_get("customer_id_mapping", "select=old_customer_id,new_customer_id")
id_remap = {r["old_customer_id"]: r["new_customer_id"] for r in mappings}
print(f"  Loaded {len(id_remap):,} customer ID remappings")

# ── Step 3: Read and deduplicate CSV rows ────────────────────────────
print("\nStep 3: Reading CSV files...")
files = sorted(glob.glob(os.path.join(CSV_FOLDER, "items-*.csv")))

all_rows = {}
stats = {
    "files_read": 0,
    "total_csv_rows": 0,
    "skipped_refund": 0,
    "skipped_no_tx": 0,
    "csv_dedup": 0,
    "customer_matched": 0,
    "customer_unmatched": 0,
    "to_import": 0,
}

for f in files:
    fname = os.path.basename(f)
    if fname in SKIP_FILES:
        print(f"  SKIP: {fname} (post-API overlap)")
        continue
    if not fname.startswith("items-"):
        continue

    stats["files_read"] += 1
    file_rows = 0

    with open(f, "r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            stats["total_csv_rows"] += 1
            file_rows += 1

            evt = row.get("Event Type", "").strip()
            if evt.lower() == "refund":
                stats["skipped_refund"] += 1
                continue

            tx_id = row.get("Transaction ID", "").strip()
            if not tx_id:
                stats["skipped_no_tx"] += 1
                continue

            date = row.get("Date", "").strip()

            # Skip rows before RESUME_FROM_DATE (already imported)
            if RESUME_FROM_DATE and date < RESUME_FROM_DATE:
                stats.setdefault("skipped_before_resume", 0)
                stats["skipped_before_resume"] += 1
                continue
            item = row.get("Item", "").strip()
            category = row.get("Category", "").strip()
            if not category or category.lower() == "none":
                category = "None"

            net_sales = parse_money(row.get("Net Sales", "0"))
            gross_sales = parse_money(row.get("Gross Sales", "0"))
            tax = parse_money(row.get("Tax", "0"))
            discounts = parse_money(row.get("Discounts", "0"))
            try:
                qty = float(row.get("Qty", "0").strip())
            except:
                qty = 1.0

            csv_cust_id = row.get("Customer ID", "").strip()
            if "," in csv_cust_id:
                csv_cust_id = csv_cust_id.split(",")[0].strip()
            csv_cust_name = row.get("Customer Name", "").strip()
            customer_id = None

            if csv_cust_name:
                name_key = csv_cust_name.lower().strip()
                if name_key in name_to_id:
                    customer_id = name_to_id[name_key]
                    stats["customer_matched"] += 1
                elif csv_cust_id in id_remap:
                    customer_id = id_remap[csv_cust_id]
                    stats["customer_matched"] += 1
                else:
                    stats["customer_unmatched"] += 1
            elif csv_cust_id:
                if csv_cust_id in id_remap:
                    customer_id = id_remap[csv_cust_id]

            raw = f"{tx_id}|{item}|{date}|{net_sales}"
            row_key = hashlib.md5(raw.encode()).hexdigest()

            # Dedup by row_key (same key used as DB unique constraint)
            if row_key in all_rows:
                stats["csv_dedup"] += 1
                continue

            all_rows[row_key] = {
                "date": date,
                "time": row.get("Time", "").strip(),
                "time_zone": "Sydney",
                "category": category,
                "item": item,
                "qty": qty,
                "net_sales": net_sales,
                "gross_sales": gross_sales,
                "tax": tax,
                "discounts": discounts,
                "transaction_id": tx_id,
                "customer_id": customer_id,
                "card_brand": row.get("Card Brand", "").strip() or None,
                "pan_suffix": row.get("PAN Suffix", "").strip() or None,
                "modifiers_applied": row.get("Modifiers Applied", "").strip() or None,
                "row_key": row_key,
            }
            stats["to_import"] += 1

    print(f"  {fname}: {file_rows:,} rows")

print(f"\n  Summary:")
print(f"    Files read:          {stats['files_read']}")
print(f"    Total CSV rows:      {stats['total_csv_rows']:,}")
print(f"    Skipped (refund):    {stats['skipped_refund']:,}")
print(f"    Skipped (no tx_id):  {stats['skipped_no_tx']:,}")
print(f"    Skipped (pre-{RESUME_FROM_DATE}): {stats.get('skipped_before_resume', 0):,}")
print(f"    Skipped (CSV dedup): {stats['csv_dedup']:,}")
print(f"    Customer matched:    {stats['customer_matched']:,}")
print(f"    Customer unmatched:  {stats['customer_unmatched']:,}")
print(f"    Rows to upsert:      {stats['to_import']:,}")

# ── Step 4: Upsert in batches ────────────────────────────────────────
rows_to_insert = list(all_rows.values())
total = len(rows_to_insert)

if total == 0:
    print("\nNothing to import!")
    sys.exit(0)

print(f"\nStep 4: Upserting {total:,} rows in batches of {BATCH_SIZE}...")
print(f"  (Existing duplicates will be merged, not duplicated)")

imported = 0
errors = 0
t_start = time.time()

for i in range(0, total, BATCH_SIZE):
    batch = rows_to_insert[i:i + BATCH_SIZE]
    try:
        supa_post("transactions", batch)
        imported += len(batch)
        elapsed = time.time() - t_start
        rate = imported / elapsed if elapsed > 0 else 0
        remaining = (total - imported) / rate if rate > 0 else 0
        
        if (i // BATCH_SIZE + 1) % 20 == 0 or i + BATCH_SIZE >= total:
            print(f"  {imported:>7,} / {total:,} ({imported/total*100:.0f}%) | {rate:.0f} rows/s | ~{remaining:.0f}s left")
    except Exception as e:
        err_str = str(e)[:120]
        print(f"  Batch {i // BATCH_SIZE + 1} error: {err_str}")
        errors += 1
        # Retry individually
        for j, row in enumerate(batch):
            try:
                supa_post("transactions", [row])
                imported += 1
            except Exception as e2:
                errors += 1
                if errors <= 20:
                    print(f"    SKIP: {row['date']} {row['item'][:30]} - {str(e2)[:60]}")

    # Gentle rate limit
    time.sleep(0.1)

elapsed_total = time.time() - t_start
print(f"\n{'='*60}")
print(f"IMPORT COMPLETE ({elapsed_total:.0f}s)")
print(f"{'='*60}")
print(f"  Upserted: {imported:,}")
print(f"  Errors:   {errors}")

# ── Step 5: Remap customer IDs ───────────────────────────────────────
print(f"\nStep 5: Running customer ID remap...")
result = supa_rpc("remap_customer_ids")
print(f"  Result: {result}")

# ── Step 6: Ensure categories mapped ─────────────────────────────────
print(f"\nStep 6: Checking category mappings...")
cats_in_import = set(r["category"] for r in rows_to_insert)
existing_cats_data = supa_get("category_mappings", "select=category")
existing_cat_set = set(r["category"] for r in existing_cats_data)

new_cats = cats_in_import - existing_cat_set
if new_cats:
    print(f"  Adding {len(new_cats)} new category mappings → Retail:")
    for cat in sorted(new_cats):
        print(f"    + {cat}")
        body = json.dumps({"category": cat, "side": "Retail", "first_seen": "2024-01-01"}).encode()
        req = urllib.request.Request(
            f"{SUPA_URL}/rest/v1/category_mappings",
            data=body,
            headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
            method="POST"
        )
        urllib.request.urlopen(req)
else:
    print(f"  All {len(cats_in_import)} categories already mapped ✓")

# ── Step 7: Verify ───────────────────────────────────────────────────
print(f"\nStep 7: Final verification...")
verify = supa_rpc("execute_sql", {"query": """
    SELECT 
        COUNT(*) AS total_rows,
        COUNT(DISTINCT transaction_id) AS unique_tx,
        MIN(date) AS earliest,
        MAX(date) AS latest,
        ROUND(SUM(net_sales)::numeric, 2) AS total_net
    FROM transactions
"""})
# Just print whatever comes back
print(f"  Transactions table: {verify}")

# Karyn check
print(f"\nKaryn Zaiter:")
karyn = supa_get("transactions",
    "select=transaction_id,date,net_sales"
    "&customer_id=eq.YX0N0R2S5D6S5FBEH256XRS9WW"
    "&order=date.asc&limit=10000")
karyn_txs = set(r["transaction_id"] for r in karyn)
karyn_net = sum(float(r["net_sales"]) for r in karyn)
dates = [r["date"] for r in karyn]
if dates:
    print(f"  Visits: {len(karyn_txs)} (Square says 223)")
    print(f"  Net sales: ${karyn_net:,.2f} (Square says $11,411.99)")
    print(f"  Date range: {min(dates)} → {max(dates)}")

print(f"\nDone! 🎉")
