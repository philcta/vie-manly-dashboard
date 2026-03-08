"""Investigate CSV transaction files from pre-API Square exports."""
import csv, os, glob, sys
sys.stdout.reconfigure(encoding='utf-8')

folder = r"F:\1. PROPERTY TRACKS\9. Marketing\Content\2026\Denoux\App24\data before Square\Transactions"
files = sorted(glob.glob(os.path.join(folder, "items-*.csv")))

print(f"Total CSV files: {len(files)}\n")

total_rows = 0
total_with_cust = 0
all_customers = set()
all_columns = None
results = []

for f in files:
    fname = os.path.basename(f)
    rows = 0
    with_cust = 0
    dates = []
    custs = set()
    refund_count = 0
    
    with open(f, "r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if all_columns is None:
            all_columns = reader.fieldnames
        
        for row in reader:
            rows += 1
            cid = row.get("Customer ID", "").strip()
            if cid:
                with_cust += 1
                custs.add(cid)
                all_customers.add(cid)
            d = row.get("Date", "").strip()
            if d:
                dates.append(d)
            evt = row.get("Event Type", "").strip()
            if evt and evt.lower() == "refund":
                refund_count += 1
    
    first_d = min(dates) if dates else "?"
    last_d = max(dates) if dates else "?"
    total_rows += rows
    total_with_cust += with_cust
    results.append((fname, rows, first_d, last_d, with_cust, len(custs), refund_count))

# Print header
print(f"{'File':<50} {'Rows':>8} {'First':>12} {'Last':>12} {'W/Cust':>8} {'Uniq':>6} {'Refund':>6}")
print("-" * 110)

for r in results:
    print(f"{r[0]:<50} {r[1]:>8,} {r[2]:>12} {r[3]:>12} {r[4]:>8,} {r[5]:>6,} {r[6]:>6,}")

print("-" * 110)
print(f"TOTAL: {total_rows:,} rows | {total_with_cust:,} with customer ID | {len(all_customers):,} unique customers")

# Print columns
print(f"\n--- COLUMNS ({len(all_columns)}) ---")
for i, col in enumerate(all_columns):
    print(f"  [{chr(65+i) if i < 26 else chr(65+i//26-1)+chr(65+i%26)}] {col}")

# Check date format
print(f"\n--- DATE FORMAT SAMPLE ---")
sample_file = files[-1]
with open(sample_file, "r", encoding="utf-8-sig") as fh:
    reader = csv.DictReader(fh)
    for i, row in enumerate(reader):
        if i >= 3:
            break
        print(f"  Date: {row.get('Date','')} | Time: {row.get('Time','')} | TZ: {row.get('Time Zone','')}")

# Check overlap with Supabase date range (our data starts 2025-08-18)
print(f"\n--- OVERLAP ANALYSIS ---")
print(f"Supabase transactions start: 2025-08-18")
print(f"CSV files covering pre-Aug 2025:")
pre_aug = [r for r in results if r[2] < "2025-08-18"]
for r in pre_aug:
    print(f"  {r[0]}: {r[2]} → {r[3]} ({r[1]:,} rows, {r[4]:,} with cust)")

overlap = [r for r in results if r[2] < "2025-08-18" and r[3] >= "2025-08-18"]
post_aug = [r for r in results if r[2] >= "2025-08-18"]
print(f"\nFiles AFTER Aug 2025 (already in Supabase via API):")
for r in post_aug:
    print(f"  {r[0]}: {r[2]} → {r[3]} ({r[1]:,} rows)")

# Check Karyn specifically
print(f"\n--- KARYN ZAITER SEARCH ---")
karyn_cids = set()
karyn_rows = 0
for f in files:
    with open(f, "r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = row.get("Customer Name", "").strip()
            if "karyn" in name.lower() or "zaiter" in name.lower():
                karyn_rows += 1
                cid = row.get("Customer ID", "").strip()
                if cid:
                    karyn_cids.add(cid)

print(f"  Found {karyn_rows} rows mentioning Karyn")
print(f"  Customer IDs used: {karyn_cids}")
