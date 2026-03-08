"""Calculate Karyn Zaiter's total transactions across CSV + Supabase."""
import csv, os, glob, json, urllib.request, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()

SUPA_URL = os.getenv('SUPABASE_URL')
SUPA_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

# ── CSV data ──────────────────────────────────────────────────────────
folder = r"F:\1. PROPERTY TRACKS\9. Marketing\Content\2026\Denoux\App24\data before Square\Transactions"
files = sorted(glob.glob(os.path.join(folder, "items-*.csv")))

karyn_csv_rows = []
karyn_ids_found = set()

for f in files:
    fname = os.path.basename(f)
    # Skip post-Aug files (already in Supabase via API)
    if "2025-08-17" in fname or "2025-09-25" in fname:
        continue
    with open(f, "r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = row.get("Customer Name", "").strip().lower()
            if "karyn" in name and "zaiter" in name:
                evt = row.get("Event Type", "").strip()
                ns_str = row.get("Net Sales", "0").replace("$", "").replace(",", "").strip()
                gs_str = row.get("Gross Sales", "0").replace("$", "").replace(",", "").strip()
                try:
                    ns = float(ns_str)
                except:
                    ns = 0.0
                try:
                    gs = float(gs_str)
                except:
                    gs = 0.0
                
                tx_id = row.get("Transaction ID", "").strip()
                date = row.get("Date", "").strip()
                cid = row.get("Customer ID", "").strip()
                karyn_ids_found.add(cid)
                
                karyn_csv_rows.append({
                    "date": date,
                    "tx_id": tx_id,
                    "category": row.get("Category", "").strip(),
                    "item": row.get("Item", "").strip(),
                    "net_sales": ns,
                    "gross_sales": gs,
                    "event_type": evt,
                    "customer_id": cid,
                })

# Aggregate CSV data
csv_tx_ids = set(r["tx_id"] for r in karyn_csv_rows if r["tx_id"])
csv_dates = [r["date"] for r in karyn_csv_rows if r["date"]]
csv_net_total = sum(r["net_sales"] for r in karyn_csv_rows)
csv_gross_total = sum(r["gross_sales"] for r in karyn_csv_rows)
csv_refunds = [r for r in karyn_csv_rows if r["event_type"].lower() == "refund"]
csv_payments = [r for r in karyn_csv_rows if r["event_type"].lower() != "refund"]

# Monthly breakdown
csv_monthly = {}
for r in karyn_csv_rows:
    m = r["date"][:7] if r["date"] else "?"
    if m not in csv_monthly:
        csv_monthly[m] = {"rows": 0, "tx_ids": set(), "net": 0.0}
    csv_monthly[m]["rows"] += 1
    csv_monthly[m]["tx_ids"].add(r["tx_id"])
    csv_monthly[m]["net"] += r["net_sales"]

print("=" * 80)
print("KARYN ZAITER — CSV ANALYSIS (pre-Aug 2025)")
print("=" * 80)
print(f"Customer IDs in CSVs: {karyn_ids_found}")
print(f"Total CSV line items: {len(karyn_csv_rows)}")
print(f"  Payments: {len(csv_payments)}")
print(f"  Refunds: {len(csv_refunds)}")
print(f"Unique transactions (visits): {len(csv_tx_ids)}")
print(f"Date range: {min(csv_dates)} → {max(csv_dates)}")
print(f"Total net sales: ${csv_net_total:,.2f}")
print(f"Total gross sales: ${csv_gross_total:,.2f}")

print(f"\nMonthly breakdown:")
for m in sorted(csv_monthly.keys()):
    d = csv_monthly[m]
    print(f"  {m}: {len(d['tx_ids']):>3} visits | ${d['net']:>8,.2f} net | {d['rows']} items")

# ── Supabase data (already remapped) ─────────────────────────────────
print(f"\n{'=' * 80}")
print("KARYN ZAITER — SUPABASE (API data, already remapped)")
print("=" * 80)

headers = {"apikey": SUPA_KEY, "Authorization": "Bearer " + SUPA_KEY}
# Use RPC to get her stats
body = json.dumps({"query": """
    SELECT 
        COUNT(DISTINCT transaction_id) AS visits,
        COUNT(*) AS line_items,
        MIN(date) AS earliest,
        MAX(date) AS latest,
        SUM(net_sales) AS net_sales,
        SUM(gross_sales) AS gross_sales
    FROM transactions 
    WHERE customer_id = 'YX0N0R2S5D6S5FBEH256XRS9WW'
"""}).encode()

# Just use a simpler approach - fetch via REST
url = f"{SUPA_URL}/rest/v1/rpc/get_member_period_table"
body = json.dumps({"start_date": "2025-08-01", "end_date": "2026-12-31"}).encode()
req = urllib.request.Request(url, data=body, headers={**headers, "Content-Type": "application/json"}, method="POST")
resp = urllib.request.urlopen(req)
all_period = json.loads(resp.read())
karyn_period = [r for r in all_period if r.get("customer_id") == "YX0N0R2S5D6S5FBEH256XRS9WW"]
if karyn_period:
    k = karyn_period[0]
    supa_visits = k["visits"]
    supa_net = float(k["total_spent"])
    print(f"Visits: {supa_visits}")
    print(f"Net sales: ${supa_net:,.2f}")
else:
    supa_visits = 0
    supa_net = 0
    print("Not found in period table!")

# ── Combined totals ──────────────────────────────────────────────────
print(f"\n{'=' * 80}")
print("COMBINED TOTALS vs SQUARE")
print("=" * 80)

combined_visits = len(csv_tx_ids) + supa_visits
combined_net = csv_net_total + supa_net

# Check for overlap: any CSV transactions that might also be in Supabase
# CSV goes up to Aug 17, Supabase starts Aug 18, so should be clean

print(f"\n{'Source':<25} {'Visits':>8} {'Net Sales':>12}")
print("-" * 50)
print(f"{'CSV (Jan 24 - Aug 25)':<25} {len(csv_tx_ids):>8} ${csv_net_total:>10,.2f}")
print(f"{'Supabase (Aug 25 - now)':<25} {supa_visits:>8} ${supa_net:>10,.2f}")
print(f"{'COMBINED':<25} {combined_visits:>8} ${combined_net:>10,.2f}")
print(f"{'Square says':<25} {223:>8} ${11411.99:>10,.2f}")
print("-" * 50)
gap_visits = 223 - combined_visits
gap_spend = 11411.99 - combined_net
print(f"{'Remaining gap':<25} {gap_visits:>8} ${gap_spend:>10,.2f}")
pct_visits = combined_visits / 223 * 100
pct_spend = combined_net / 11411.99 * 100
print(f"{'Coverage':<25} {pct_visits:>7.1f}% {pct_spend:>11.1f}%")
