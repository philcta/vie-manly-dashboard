"""Investigate the 'None' category rows in CSV files."""
import csv, os, glob, sys
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding='utf-8')

folder = r"F:\1. PROPERTY TRACKS\9. Marketing\Content\2026\Denoux\App24\data before Square\Transactions"
files = sorted(glob.glob(os.path.join(folder, "items-*.csv")))

none_rows = []
none_by_file = defaultdict(int)
none_items = Counter()
none_by_month = defaultdict(lambda: {"rows": 0, "net": 0.0})

for f in files:
    fname = os.path.basename(f)
    if "2025-08-17" in fname or "2025-09-25" in fname:
        continue
    with open(f, "r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for line_num, row in enumerate(reader, start=2):  # +2 for header + 1-indexing
            cat = row.get("Category", "").strip()
            if cat == "None" or cat == "" or cat.lower() == "none":
                ns_str = row.get("Net Sales", "0").replace("$", "").replace(",", "").strip()
                try:
                    ns = float(ns_str)
                except:
                    ns = 0.0
                
                item = row.get("Item", "").strip()
                date = row.get("Date", "").strip()
                month = date[:7] if date else "?"
                
                none_rows.append({
                    "file": fname,
                    "line": line_num,
                    "date": date,
                    "item": item,
                    "net_sales": ns,
                    "category": cat,
                })
                
                none_by_file[fname] += 1
                none_items[item] += 1
                none_by_month[month]["rows"] += 1
                none_by_month[month]["net"] += ns

print(f"Total 'None' category rows: {len(none_rows):,}")
print(f"Total net sales: ${sum(r['net_sales'] for r in none_rows):,.2f}")

# ── By file ──────────────────────────────────────────────────────────
print(f"\n{'=' * 80}")
print(f"DISTRIBUTION BY FILE")
print(f"{'=' * 80}")
for fname in sorted(none_by_file.keys()):
    count = none_by_file[fname]
    print(f"  {fname:<50} {count:>6,} rows")

# ── By month ─────────────────────────────────────────────────────────
print(f"\n{'=' * 80}")
print(f"DISTRIBUTION BY MONTH")
print(f"{'=' * 80}")
for m in sorted(none_by_month.keys()):
    d = none_by_month[m]
    print(f"  {m}: {d['rows']:>5,} rows  ${d['net']:>10,.2f}")

# ── Top items ────────────────────────────────────────────────────────
print(f"\n{'=' * 80}")
print(f"TOP 50 ITEMS in 'None' category (by frequency)")
print(f"{'=' * 80}")
for item, count in none_items.most_common(50):
    # Calculate total net for this item
    item_net = sum(r["net_sales"] for r in none_rows if r["item"] == item)
    print(f"  {count:>5}x  ${item_net:>8,.2f}  {item[:70]}")

# ── Unique items count ───────────────────────────────────────────────
print(f"\nTotal unique items in 'None': {len(none_items)}")

# ── Sample rows with file + line numbers ─────────────────────────────
print(f"\n{'=' * 80}")
print(f"SAMPLE ROWS (first 20 from each end)")
print(f"{'=' * 80}")
for r in none_rows[:20]:
    print(f"  {r['file']}:{r['line']}  {r['date']}  ${r['net_sales']:>7.2f}  {r['item'][:55]}")
print(f"  ...")
for r in none_rows[-10:]:
    print(f"  {r['file']}:{r['line']}  {r['date']}  ${r['net_sales']:>7.2f}  {r['item'][:55]}")

# ── Check: are these mostly from specific price ranges? ──────────────
print(f"\n{'=' * 80}")
print(f"PRICE DISTRIBUTION")
print(f"{'=' * 80}")
prices = [r["net_sales"] for r in none_rows]
brackets = [(0, 5), (5, 10), (10, 20), (20, 50), (50, 100), (100, 500)]
for lo, hi in brackets:
    cnt = sum(1 for p in prices if lo <= p < hi)
    total = sum(p for p in prices if lo <= p < hi)
    print(f"  ${lo:>3} - ${hi:<3}: {cnt:>5,} rows  ${total:>10,.2f}")
neg = sum(1 for p in prices if p < 0)
print(f"  Negative:  {neg:>5,} rows  ${sum(p for p in prices if p < 0):>10,.2f}")
