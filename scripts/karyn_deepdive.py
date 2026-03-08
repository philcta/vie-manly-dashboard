"""Deep-dive into one overlapping transaction to understand the $ discrepancy."""
import csv, os, glob, json, urllib.request, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()

SUPA_URL = os.getenv('SUPABASE_URL')
SUPA_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

# ── Pick a transaction that appears in both ──────────────────────────
# Let's use 2025-08-27 — has 1 transaction in both, and amounts differ slightly

# Get Supabase data for that date
headers = {"apikey": SUPA_KEY, "Authorization": "Bearer " + SUPA_KEY}
url = (f"{SUPA_URL}/rest/v1/transactions"
       f"?customer_id=eq.YX0N0R2S5D6S5FBEH256XRS9WW"
       f"&date=eq.2025-08-27"
       f"&select=transaction_id,item,category,net_sales,gross_sales,tax,discounts,qty"
       f"&order=item.asc")
req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req)
supa_items = json.loads(resp.read())

print("SUPABASE — 2025-08-27:")
supa_tx = supa_items[0]["transaction_id"] if supa_items else "?"
print(f"  Transaction ID: {supa_tx}")
for i in supa_items:
    print(f"  {i['item']:<50} net={float(i['net_sales']):>7.2f} gross={float(i['gross_sales']):>7.2f} tax={float(i['tax']):>5.2f} disc={float(i['discounts']):>6.2f}")
print(f"  TOTAL: net=${sum(float(i['net_sales']) for i in supa_items):.2f} gross=${sum(float(i['gross_sales']) for i in supa_items):.2f}")

# Get CSV data for same date
folder = r"F:\1. PROPERTY TRACKS\9. Marketing\Content\2026\Denoux\App24\data before Square\Transactions"
files = sorted(glob.glob(os.path.join(folder, "items-*.csv")))

print(f"\nCSV — 2025-08-27:")
csv_items = []
for f in files:
    with open(f, "r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = row.get("Customer Name", "").strip().lower()
            date = row.get("Date", "").strip()
            if "karyn" in name and "zaiter" in name and date == "2025-08-27":
                ns = float(row.get("Net Sales", "0").replace("$", "").replace(",", "").strip() or 0)
                gs = float(row.get("Gross Sales", "0").replace("$", "").replace(",", "").strip() or 0)
                tx = float(row.get("Tax", "0").replace("$", "").replace(",", "").strip() or 0)
                dc = float(row.get("Discounts", "0").replace("$", "").replace(",", "").strip() or 0)
                ps = float(row.get("Product Sales", "0").replace("$", "").replace(",", "").strip() or 0)
                item_name = row.get("Item", "").strip()
                csv_items.append({"item": item_name, "net": ns, "gross": gs, "tax": tx, "disc": dc, "prod": ps,
                                  "tx_id": row.get("Transaction ID", "").strip()})
                print(f"  {item_name:<50} net={ns:>7.2f} gross={gs:>7.2f} tax={tx:>5.2f} disc={dc:>6.2f} prod={ps:>7.2f} tx={row.get('Transaction ID','').strip()[:20]}")

print(f"  TX ID: {csv_items[0]['tx_id'] if csv_items else '?'}")
print(f"  TOTAL: net=${sum(i['net'] for i in csv_items):.2f} gross=${sum(i['gross'] for i in csv_items):.2f}")
print(f"  Same TX ID? {csv_items[0]['tx_id'] == supa_tx if csv_items else 'N/A'}")

# Now check a 2x discrepancy date — Sep 25
print(f"\n{'='*80}")
print(f"2025-09-25 — Checking the 2x discrepancy ($326 CSV vs $163 Supa)")
print(f"{'='*80}")

url2 = (f"{SUPA_URL}/rest/v1/transactions"
        f"?customer_id=eq.YX0N0R2S5D6S5FBEH256XRS9WW"
        f"&date=eq.2025-09-25"
        f"&select=transaction_id,item,net_sales,gross_sales"
        f"&order=transaction_id.asc,item.asc")
req2 = urllib.request.Request(url2, headers=headers)
resp2 = urllib.request.urlopen(req2)
supa_sep25 = json.loads(resp2.read())

supa_txs_sep25 = set(r["transaction_id"] for r in supa_sep25)
print(f"\nSupabase TX IDs: {supa_txs_sep25}")
print(f"Supabase items: {len(supa_sep25)}, net=${sum(float(r['net_sales']) for r in supa_sep25):.2f}")

csv_sep25 = []
for f in files:
    with open(f, "r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = row.get("Customer Name", "").strip().lower()
            date = row.get("Date", "").strip()
            if "karyn" in name and "zaiter" in name and date == "2025-09-25":
                ns = float(row.get("Net Sales", "0").replace("$", "").replace(",", "").strip() or 0)
                tx_id = row.get("Transaction ID", "").strip()
                csv_sep25.append({"tx_id": tx_id, "item": row.get("Item","").strip(), "net": ns,
                                  "source": os.path.basename(f)})

csv_txs_sep25 = set(r["tx_id"] for r in csv_sep25)
print(f"\nCSV TX IDs: {csv_txs_sep25}")
print(f"CSV items: {len(csv_sep25)}, net=${sum(r['net'] for r in csv_sep25):.2f}")

# Check if same TX appears in multiple CSV files
by_file = {}
for r in csv_sep25:
    if r["source"] not in by_file:
        by_file[r["source"]] = []
    by_file[r["source"]].append(r)

print(f"\nCSV items by source file:")
for src, items in sorted(by_file.items()):
    print(f"  {src}: {len(items)} items, ${sum(i['net'] for i in items):.2f}")
    for i in items[:3]:
        print(f"    {i['item'][:45]} ${i['net']:.2f} tx={i['tx_id'][:20]}")
    if len(items) > 3:
        print(f"    ... and {len(items)-3} more")

# Check TX ID overlap between CSV files
if len(by_file) > 1:
    file_keys = list(by_file.keys())
    txs_0 = set(r["tx_id"] for r in by_file[file_keys[0]])
    txs_1 = set(r["tx_id"] for r in by_file[file_keys[1]])
    print(f"\n  TX overlap between files: {txs_0 & txs_1}")
