"""
Sync inventory enrichment data from Square Catalog API.

Pulls for each catalog item:
  - status: ACTIVE / ARCHIVED (from is_deleted flag)
  - is_taxable: whether item is marked taxable
  - gst_applicable: whether the GST tax ID is in the item's tax_ids
  - default_vendor: vendor name from item variation supplier info

Updates the latest inventory snapshot in Supabase.

Usage: python scripts/sync_inventory_enrichment.py
"""
import sys, os, json, urllib.request, urllib.error

sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("SQUARE_ACCESS_TOKEN")
SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

sq_headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Square-Version": "2025-01-23",
}
supa_headers = {
    "apikey": SUPA_KEY,
    "Authorization": f"Bearer {SUPA_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}


def sq_post(endpoint, body):
    """POST to Square API."""
    req = urllib.request.Request(
        f"https://connect.squareup.com/v2/{endpoint}",
        data=json.dumps(body).encode(),
        headers=sq_headers,
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


def supa_get(table, params=""):
    """GET from Supabase REST."""
    url = f"{SUPA_URL}/rest/v1/{table}?{params}"
    req = urllib.request.Request(url, headers={
        "apikey": SUPA_KEY,
        "Authorization": f"Bearer {SUPA_KEY}",
        "Content-Type": "application/json",
    })
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


def supa_patch_batch(table, rows):
    """Bulk UPSERT via Supabase REST (PATCH with merge-duplicates)."""
    url = f"{SUPA_URL}/rest/v1/{table}"
    req = urllib.request.Request(
        url,
        data=json.dumps(rows).encode(),
        headers={
            "apikey": SUPA_KEY,
            "Authorization": f"Bearer {SUPA_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        },
        method="POST",
    )
    urllib.request.urlopen(req)


def supa_update(table, row_id, data):
    """Update a single row by id."""
    url = f"{SUPA_URL}/rest/v1/{table}?id=eq.{row_id}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={
            "apikey": SUPA_KEY,
            "Authorization": f"Bearer {SUPA_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="PATCH",
    )
    urllib.request.urlopen(req)


# ── Square data fetchers ─────────────────────────────────────

def fetch_all_catalog_items():
    """Fetch all ITEM objects from Square catalog, including deleted/archived."""
    items = []
    cursor = None
    page = 0

    while True:
        body = {
            "object_types": ["ITEM"],
            "include_deleted_objects": True,
            "limit": 100,
        }
        if cursor:
            body["cursor"] = cursor

        data = sq_post("catalog/search", body)
        objects = data.get("objects", [])
        items.extend(objects)
        page += 1
        print(f"  📦 Page {page}: {len(objects)} items (total: {len(items)})")

        cursor = data.get("cursor")
        if not cursor:
            break

    return items


def fetch_tax_objects():
    """Fetch all TAX catalog objects to map tax_id → name."""
    taxes = {}
    data = sq_post("catalog/search", {"object_types": ["TAX"], "limit": 100})
    for obj in data.get("objects", []):
        tax_data = obj.get("tax_data", {})
        taxes[obj["id"]] = {
            "name": tax_data.get("name", ""),
            "percentage": tax_data.get("percentage", "0"),
        }
    return taxes


def fetch_vendor_names(vendor_ids):
    """Bulk-retrieve vendor names by IDs via POST /v2/vendors/bulk-retrieve."""
    vendors = {}
    id_list = list(vendor_ids)
    # Process in batches of 100 (API limit)
    for i in range(0, len(id_list), 100):
        batch = id_list[i:i+100]
        try:
            data = sq_post('vendors/bulk-retrieve', {'vendor_ids': batch})
            for vid, resp in data.get('responses', {}).items():
                v = resp.get('vendor', {})
                if v.get('name'):
                    vendors[vid] = v['name']
        except Exception as e:
            print(f"  ⚠ Bulk retrieve batch {i//100}: {e}")
    return vendors


# ── Main ─────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🔄 Inventory Enrichment Sync")
    print("=" * 60)

    # Step 1: Get the latest source_date
    latest = supa_get("inventory", "select=source_date&order=source_date.desc&limit=1")
    source_date = latest[0]["source_date"] if latest else None
    if not source_date:
        print("❌ No inventory data found")
        return
    print(f"📅 Latest inventory snapshot: {source_date}")

    # Step 2: Fetch tax objects
    print("\n🏷️  Fetching tax definitions...")
    tax_map = fetch_tax_objects()
    print(f"  Found {len(tax_map)} tax types:")
    for tid, tinfo in tax_map.items():
        print(f"    {tinfo['name']} ({tinfo['percentage']}%) → {tid[:20]}...")

    gst_tax_id = None
    for tid, tinfo in tax_map.items():
        if "gst" in tinfo["name"].lower():
            gst_tax_id = tid
            break
    print(f"  GST tax ID: {gst_tax_id[:20] + '...' if gst_tax_id else 'NOT FOUND'}")

    # Step 3: Fetch all catalog items (skip deleted/archived)
    print("\n📦 Fetching all catalog items...")
    catalog_items = fetch_all_catalog_items()
    print(f"  Total catalog items: {len(catalog_items)}")

    # Step 4: Collect all vendor IDs from catalog items
    print("\n🏪 Collecting vendor IDs from catalog...")
    all_vendor_ids = set()
    for obj in catalog_items:
        item_data = obj.get('item_data', {})
        for var in item_data.get('variations', []):
            vd = var.get('item_variation_data', {})
            for vi in vd.get('item_variation_vendor_infos', []):
                vid = vi.get('item_variation_vendor_info_data', {}).get('vendor_id')
                if vid:
                    all_vendor_ids.add(vid)
    print(f"  Found {len(all_vendor_ids)} unique vendor IDs")

    # Step 5: Bulk-resolve vendor names
    print("\n🏪 Resolving vendor names...")
    vendor_map = fetch_vendor_names(all_vendor_ids)
    print(f"  Resolved {len(vendor_map)} vendors")
    for vname in list(vendor_map.values())[:8]:
        print(f"    {vname}")
    if len(vendor_map) > 8:
        print(f"    ... and {len(vendor_map) - 8} more")

    # Step 6: Build enrichment map
    enrichment = {}
    archived_count = 0
    gst_count = 0

    for obj in catalog_items:
        item_data = obj.get("item_data", {})
        name = item_data.get("name", "")
        if not name:
            continue

        is_deleted = obj.get("is_deleted", False)
        is_taxable = item_data.get("is_taxable", True)
        tax_ids = item_data.get("tax_ids", [])

        has_gst = gst_tax_id in tax_ids if gst_tax_id else False

        status = "ARCHIVED" if is_deleted else "ACTIVE"
        if is_deleted:
            archived_count += 1
        if has_gst:
            gst_count += 1

        # Get vendor from first variation's vendor info
        default_vendor_name = None
        for var in item_data.get('variations', []):
            vd = var.get('item_variation_data', {})
            for vi in vd.get('item_variation_vendor_infos', []):
                vid = vi.get('item_variation_vendor_info_data', {}).get('vendor_id')
                if vid and vid in vendor_map:
                    default_vendor_name = vendor_map[vid]
                    break
            if default_vendor_name:
                break

        enrichment[name] = {
            "status": status,
            "is_taxable": is_taxable,
            "gst_applicable": has_gst,
            "default_vendor": default_vendor_name,
        }

    print(f"\n📊 Enrichment Summary:")
    print(f"  Active items: {len(enrichment) - archived_count}")
    print(f"  Archived items: {archived_count}")
    print(f"  GST applicable: {gst_count}")
    print(f"  Total mapped: {len(enrichment)}")

    # Step 7: Fetch inventory rows and update
    print(f"\n💾 Updating inventory rows for {source_date}...")

    # Fetch in pages of 1000
    all_inv_rows = []
    offset = 0
    while True:
        rows = supa_get(
            "inventory",
            f"select=id,product_name&source_date=eq.{source_date}"
            f"&order=id&limit=1000&offset={offset}"
        )
        all_inv_rows.extend(rows)
        if len(rows) < 1000:
            break
        offset += 1000

    print(f"  Found {len(all_inv_rows)} inventory rows to enrich")

    updated = 0
    not_found = 0

    for row in all_inv_rows:
        name = row["product_name"]
        enrich = enrichment.get(name)
        if not enrich and name.startswith("*"):
            enrich = enrichment.get(name[1:])

        if enrich:
            try:
                supa_update("inventory", row["id"], {
                    "status": enrich["status"],
                    "is_taxable": enrich["is_taxable"],
                    "gst_applicable": enrich["gst_applicable"],
                    "default_vendor": enrich["default_vendor"],
                })
                updated += 1
            except Exception as e:
                print(f"  ⚠ Error updating {name}: {e}")
        else:
            not_found += 1

        total = updated + not_found
        if total % 500 == 0:
            print(f"  Progress: {total}/{len(all_inv_rows)} ({updated} updated, {not_found} not matched)")

    print(f"\n✅ Done!")
    print(f"  Updated: {updated}")
    print(f"  Not matched in catalog: {not_found}")


if __name__ == "__main__":
    main()
