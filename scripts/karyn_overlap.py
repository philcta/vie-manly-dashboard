"""Find the exact overlap between CSV and Supabase for Karyn Zaiter."""
import csv, os, glob, json, urllib.request, sys
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()

SUPA_URL = os.getenv('SUPABASE_URL')
SUPA_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

# ── 1. Get Karyn's Supabase transactions ─────────────────────────────
headers = {"apikey": SUPA_KEY, "Authorization": "Bearer " + SUPA_KEY}
url = (f"{SUPA_URL}/rest/v1/transactions"
       f"?customer_id=eq.YX0N0R2S5D6S5FBEH256XRS9WW"
       f"&select=date,transaction_id,item,net_sales,category"
       f"&order=date.asc"
       f"&limit=10000")
req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req)
supa_rows = json.loads(resp.read())

supa_tx_ids = set(r["transaction_id"] for r in supa_rows)
supa_by_date = defaultdict(list)
for r in supa_rows:
    supa_by_date[r["date"]].append(r)

print(f"Supabase: {len(supa_rows)} line items, {len(supa_tx_ids)} unique transactions")
print(f"Supabase date range: {min(supa_by_date.keys())} → {max(supa_by_date.keys())}")

# ── 2. Get Karyn's CSV transactions ──────────────────────────────────
folder = r"F:\1. PROPERTY TRACKS\9. Marketing\Content\2026\Denoux\App24\data before Square\Transactions"
files = sorted(glob.glob(os.path.join(folder, "items-*.csv")))

csv_rows = []
for f in files:
    with open(f, "r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = row.get("Customer Name", "").strip().lower()
            if "karyn" in name and "zaiter" in name:
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
                csv_rows.append({
                    "date": row.get("Date", "").strip(),
                    "tx_id": row.get("Transaction ID", "").strip(),
                    "item": row.get("Item", "").strip(),
                    "net_sales": ns,
                    "gross_sales": gs,
                    "event_type": row.get("Event Type", "").strip(),
                    "category": row.get("Category", "").strip(),
                    "source_file": os.path.basename(f),
                })

csv_tx_ids = set(r["tx_id"] for r in csv_rows if r["tx_id"])
csv_by_date = defaultdict(list)
for r in csv_rows:
    csv_by_date[r["date"]].append(r)

print(f"CSV: {len(csv_rows)} line items, {len(csv_tx_ids)} unique transactions")
print(f"CSV date range: {min(csv_by_date.keys())} → {max(csv_by_date.keys())}")

# ── 3. Find overlapping transaction IDs ──────────────────────────────
overlap_tx = csv_tx_ids & supa_tx_ids
csv_only_tx = csv_tx_ids - supa_tx_ids
supa_only_tx = supa_tx_ids - csv_tx_ids

print(f"\n{'=' * 80}")
print(f"TRANSACTION ID OVERLAP ANALYSIS")
print(f"{'=' * 80}")
print(f"CSV-only transactions: {len(csv_only_tx)}")
print(f"Supabase-only transactions: {len(supa_only_tx)}")
print(f"OVERLAPPING (in both): {len(overlap_tx)}")

if overlap_tx:
    # Get dates of overlapping transactions
    overlap_dates = set()
    for r in csv_rows:
        if r["tx_id"] in overlap_tx:
            overlap_dates.add(r["date"])
    
    print(f"\nOverlap date range: {min(overlap_dates)} → {max(overlap_dates)}")
    print(f"\nOverlapping transactions by date:")
    for d in sorted(overlap_dates):
        csv_items = [r for r in csv_rows if r["tx_id"] in overlap_tx and r["date"] == d]
        csv_ns = sum(r["net_sales"] for r in csv_items)
        csv_txs = set(r["tx_id"] for r in csv_items)
        print(f"  {d}: {len(csv_txs)} tx, {len(csv_items)} items, ${csv_ns:,.2f}")

# ── 4. Day-by-day overlap analysis ───────────────────────────────────
print(f"\n{'=' * 80}")
print(f"DATE OVERLAP — days appearing in BOTH sources")
print(f"{'=' * 80}")

all_dates = sorted(set(list(csv_by_date.keys()) + list(supa_by_date.keys())))
overlap_dates_both = []
for d in all_dates:
    in_csv = d in csv_by_date
    in_supa = d in supa_by_date
    if in_csv and in_supa:
        overlap_dates_both.append(d)

if overlap_dates_both:
    print(f"Days in both CSV and Supabase: {len(overlap_dates_both)}")
    print(f"\n{'Date':<12} {'CSV txs':>8} {'CSV net':>10} {'Supa txs':>9} {'Supa net':>10} {'Match?':>8}")
    print("-" * 65)
    for d in overlap_dates_both:
        csv_d = csv_by_date[d]
        supa_d = supa_by_date[d]
        csv_txs = set(r["tx_id"] for r in csv_d)
        supa_txs = set(r["transaction_id"] for r in supa_d)
        csv_ns = sum(r["net_sales"] for r in csv_d)
        supa_ns = sum(r["net_sales"] for r in supa_d)
        tx_match = "YES" if csv_txs & supa_txs else "no"
        print(f"{d:<12} {len(csv_txs):>8} ${csv_ns:>8,.2f} {len(supa_txs):>9} ${supa_ns:>8,.2f} {tx_match:>8}")
else:
    print("No overlapping dates found!")

# ── 5. Corrected totals — deduplicated ───────────────────────────────
print(f"\n{'=' * 80}")
print(f"DEDUPLICATED TOTALS")
print(f"{'=' * 80}")

# CSV-only transactions (not in Supabase)
csv_only_rows = [r for r in csv_rows if r["tx_id"] in csv_only_tx]
csv_only_net = sum(r["net_sales"] for r in csv_only_rows)
csv_only_visits = len(csv_only_tx)

# All Supabase transactions
supa_net = sum(r["net_sales"] for r in supa_rows)
supa_visits = len(supa_tx_ids)

# Overlap stats
overlap_rows = [r for r in csv_rows if r["tx_id"] in overlap_tx]
overlap_net = sum(r["net_sales"] for r in overlap_rows)
overlap_visits = len(overlap_tx)

combined_visits = csv_only_visits + supa_visits
combined_net = csv_only_net + supa_net

print(f"\n{'Source':<35} {'Visits':>8} {'Net Sales':>12}")
print("-" * 60)
print(f"{'CSV unique (not in Supabase)':<35} {csv_only_visits:>8} ${csv_only_net:>10,.2f}")
print(f"{'Supabase (all)':<35} {supa_visits:>8} ${supa_net:>10,.2f}")
print(f"{'Overlap (counted once via Supa)':<35} {overlap_visits:>8} ${overlap_net:>10,.2f}")
print(f"{'─' * 60}")
print(f"{'DEDUPLICATED COMBINED':<35} {combined_visits:>8} ${combined_net:>10,.2f}")
print(f"{'Square says':<35} {223:>8} ${11411.99:>10,.2f}")
print(f"{'─' * 60}")
gap_v = 223 - combined_visits
gap_s = 11411.99 - combined_net
print(f"{'Gap':<35} {gap_v:>8} ${gap_s:>10,.2f}")
pct_v = combined_visits / 223 * 100
pct_s = combined_net / 11411.99 * 100
print(f"{'Coverage':<35} {pct_v:>7.1f}% {pct_s:>11.1f}%")

# ── 6. Where does the CSV end / Supabase start? ─────────────────────
print(f"\n{'=' * 80}")
print(f"BOUNDARY ANALYSIS")
print(f"{'=' * 80}")

csv_only_dates = sorted(set(r["date"] for r in csv_only_rows))
if csv_only_dates:
    print(f"CSV-only data spans: {csv_only_dates[0]} → {csv_only_dates[-1]}")

supa_dates = sorted(supa_by_date.keys())
print(f"Supabase data spans: {supa_dates[0]} → {supa_dates[-1]}")

if overlap_dates_both:
    print(f"Overlap zone: {overlap_dates_both[0]} → {overlap_dates_both[-1]}")
    print(f"\nRecommended CSV cutoff for import: rows with date < '{supa_dates[0]}'")
    csv_before_supa = [r for r in csv_rows if r["date"] < supa_dates[0]]
    print(f"  That would be {len(set(r['tx_id'] for r in csv_before_supa))} visits, ${sum(r['net_sales'] for r in csv_before_supa):,.2f}")
