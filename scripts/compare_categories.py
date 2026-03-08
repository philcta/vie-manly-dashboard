"""Compare CSV categories with Supabase categories + Retail vs Cafe split."""
import csv, os, glob, json, urllib.request, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()

SUPA_URL = os.getenv('SUPABASE_URL')
SUPA_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

# ── 1. Collect all categories from CSVs (pre-Aug 2025) ──────────────
folder = r"F:\1. PROPERTY TRACKS\9. Marketing\Content\2026\Denoux\App24\data before Square\Transactions"
files = sorted(glob.glob(os.path.join(folder, "items-*.csv")))

csv_cats = {}   # category -> {rows, net_sales, items_sample}
for f in files:
    fname = os.path.basename(f)
    if "2025-08-17" in fname or "2025-09-25" in fname:
        continue
    with open(f, "r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            cat = row.get("Category", "").strip()
            if not cat:
                cat = "(uncategorized)"
            evt = row.get("Event Type", "").strip()
            if evt.lower() == "refund":
                continue  # skip refund rows for cleaner analysis
            
            ns_str = row.get("Net Sales", "0").replace("$", "").replace(",", "").strip()
            try:
                ns = float(ns_str)
            except:
                ns = 0.0
            
            item = row.get("Item", "").strip()
            
            if cat not in csv_cats:
                csv_cats[cat] = {"rows": 0, "net_sales": 0.0, "items": set()}
            csv_cats[cat]["rows"] += 1
            csv_cats[cat]["net_sales"] += ns
            if len(csv_cats[cat]["items"]) < 5:
                csv_cats[cat]["items"].add(item)

# ── 2. Get Supabase categories ──────────────────────────────────────
headers = {"apikey": SUPA_KEY, "Authorization": "Bearer " + SUPA_KEY}
body = json.dumps({"query": """
    SELECT category, COUNT(*) as rows, SUM(net_sales) as net_sales
    FROM transactions
    GROUP BY category
    ORDER BY net_sales DESC
"""}).encode()
req = urllib.request.Request(
    f"{SUPA_URL}/rest/v1/rpc/execute_raw_sql",
    data=body, headers={**headers, "Content-Type": "application/json"},
    method="POST"
)
# Use direct RPC instead — just fetch distinct categories
url = f"{SUPA_URL}/rest/v1/transactions?select=category&limit=50000"
req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req)
tx_data = json.loads(resp.read())
supa_cats = {}
for t in tx_data:
    cat = t.get("category", "") or "(uncategorized)"
    supa_cats[cat] = supa_cats.get(cat, 0) + 1

# ── 3. Print comparison ─────────────────────────────────────────────
print("=" * 120)
print("CSV CATEGORIES (pre-Aug 2025) — sorted by revenue")
print("=" * 120)
sorted_csv = sorted(csv_cats.items(), key=lambda x: x[1]["net_sales"], reverse=True)
print(f"{'Category':<45} {'Rows':>8} {'Net Sales':>12} {'In Supa?':>10} {'Sample Items'}")
print("-" * 120)

csv_only = []
for cat, data in sorted_csv:
    in_supa = "YES" if cat in supa_cats else "no"
    samples = ", ".join(list(data["items"])[:3])
    if len(samples) > 40:
        samples = samples[:40] + "..."
    print(f"{cat:<45} {data['rows']:>8,} ${data['net_sales']:>10,.2f} {in_supa:>10} {samples}")
    if cat not in supa_cats:
        csv_only.append(cat)

print(f"\nTotal CSV categories: {len(csv_cats)}")
print(f"Also in Supabase: {len(csv_cats) - len(csv_only)}")
print(f"CSV-only (not in Supabase): {len(csv_only)}")

# ── 4. Supabase-only categories ──────────────────────────────────────
supa_only = [c for c in supa_cats if c not in csv_cats]
print(f"\n{'=' * 80}")
print(f"SUPABASE-ONLY CATEGORIES (not in CSVs)")
print(f"{'=' * 80}")
for cat in sorted(supa_only):
    print(f"  {cat} ({supa_cats[cat]:,} rows)")

# ── 5. Categories that differ ────────────────────────────────────────
print(f"\n{'=' * 80}")
print(f"CSV-ONLY CATEGORIES (need mapping)")
print(f"{'=' * 80}")
for cat in sorted(csv_only):
    data = csv_cats[cat]
    samples = ", ".join(list(data["items"])[:4])
    print(f"  {cat:<45} {data['rows']:>6,} rows  ${data['net_sales']:>8,.2f}  Items: {samples[:60]}")

# ── 6. Check what the current Retail/Cafe category mapping looks like ─
print(f"\n{'=' * 80}")
print(f"CURRENT CATEGORY SPLIT CHECK")
print(f"{'=' * 80}")

# Get the category mapping from the sync script
mapping_file = r"F:\1. PROPERTY TRACKS\9. Marketing\Content\2026\Denoux\App24\services\square_sync.py"
if os.path.exists(mapping_file):
    with open(mapping_file, "r") as mf:
        content = mf.read()
    # Find category mapping
    if "CATEGORY_MAP" in content or "category_map" in content.lower():
        start = content.find("CATEGORY_MAP")
        if start == -1:
            start = content.lower().find("category_map")
        if start >= 0:
            end = content.find("}", start) + 1
            snippet = content[start:end+50]
            print(f"Found category mapping in square_sync.py")
    
    if "cafe_categories" in content.lower() or "retail" in content.lower():
        # Find the relevant section
        for line in content.split("\n"):
            ll = line.lower().strip()
            if "cafe" in ll or "retail" in ll or "bar" in ll:
                if "=" in line or "[" in line or "category" in ll:
                    print(f"  {line.strip()}")
