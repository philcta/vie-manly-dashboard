"""Re-sync inventory with vendor names."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()

from services.square_sync import sync_inventory
from services.db_supabase import upsert_inventory

print("Starting inventory sync...", flush=True)
inv_df = sync_inventory()
print(f"Got {len(inv_df)} items", flush=True)

vendor_counts = inv_df["Default Vendor"].apply(lambda x: bool(x and str(x).strip())).sum()
print(f"Items with vendor: {vendor_counts}/{len(inv_df)}", flush=True)

# Show some samples
with_vendor = inv_df[inv_df["Default Vendor"].apply(lambda x: bool(x and str(x).strip()))]
print(f"\nSample items with vendors:")
for _, row in with_vendor.head(10).iterrows():
    print(f"  {row['SKU']:20s} | {row['Product Name'][:30]:30s} | {row['Default Vendor']}")

count = upsert_inventory(inv_df)
print(f"\nUpserted {count} rows", flush=True)
