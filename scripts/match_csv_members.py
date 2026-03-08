"""Match CSV customer names to Supabase members."""
import csv, os, glob, json, urllib.request, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()

SUPA_URL = os.getenv('SUPABASE_URL')
SUPA_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

# 1. Collect all customer names from CSVs (pre Aug 2025 only)
folder = r"F:\1. PROPERTY TRACKS\9. Marketing\Content\2026\Denoux\App24\data before Square\Transactions"
files = sorted(glob.glob(os.path.join(folder, "items-*.csv")))

csv_names = {}  # normalized_name -> set of customer_ids
csv_name_rows = {}  # normalized_name -> row count
for f in files:
    fname = os.path.basename(f)
    if "2025-08-17" in fname or "2025-09-25" in fname:
        continue
    with open(f, "r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            cid = row.get("Customer ID", "").strip()
            name = row.get("Customer Name", "").strip()
            if cid and name:
                key = name.lower().strip()
                if key not in csv_names:
                    csv_names[key] = set()
                    csv_name_rows[key] = 0
                csv_names[key].add(cid)
                csv_name_rows[key] += 1

print(f"Unique customer names in CSVs: {len(csv_names):,}")

# 2. Get all members from Supabase
headers = {"apikey": SUPA_KEY, "Authorization": "Bearer " + SUPA_KEY}
url = f"{SUPA_URL}/rest/v1/members?select=square_customer_id,first_name,last_name"
req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req)
members = json.loads(resp.read())

supa_names = {}
for m in members:
    fn = (m.get("first_name") or "").strip()
    ln = (m.get("last_name") or "").strip()
    full = f"{fn} {ln}".strip().lower()
    if full:
        supa_names[full] = m["square_customer_id"]

print(f"Unique named members in Supabase: {len(supa_names):,}")

# 3. Match by name
matched = 0
matched_names = []
total_matched_rows = 0
for csv_name, cids in csv_names.items():
    if csv_name in supa_names:
        matched += 1
        total_matched_rows += csv_name_rows[csv_name]
        if matched <= 15:
            matched_names.append((csv_name, list(cids)[0], supa_names[csv_name], csv_name_rows[csv_name]))

unmatched = len(csv_names) - matched
print(f"Matched by name: {matched:,}")
print(f"Not matched: {unmatched:,}")
pct = matched / len(csv_names) * 100
print(f"Match rate: {pct:.1f}%")
print(f"Total CSV rows from matched members: {total_matched_rows:,}")

print(f"\nSample matches (first 15):")
for name, old_id, new_id, rows in matched_names:
    print(f"  {name:<30} CSV rows: {rows:>5} | old: {old_id[:22]:<24} -> new: {new_id[:22]}")

# Karyn specifically
karyn_key = "karyn zaiter"
if karyn_key in csv_names:
    print(f"\nKaryn Zaiter:")
    print(f"  CSV IDs: {csv_names[karyn_key]}")
    supa_id = supa_names.get(karyn_key, "NOT FOUND")
    print(f"  Supabase ID: {supa_id}")
    print(f"  CSV rows: {csv_name_rows[karyn_key]}")
else:
    # Try partial match
    partial = [k for k in csv_names if "karyn" in k or "zaiter" in k]
    print(f"\nKaryn not found exactly. Partial matches: {partial}")
    for p in partial:
        print(f"  {p}: IDs={csv_names[p]}, rows={csv_name_rows[p]}")
