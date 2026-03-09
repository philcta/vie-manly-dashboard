"""Probe vendor IDs from catalog items & try to resolve vendor names."""
import sys, os, json, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv('SQUARE_ACCESS_TOKEN')
HEADERS = {
    'Authorization': f'Bearer {TOKEN}',
    'Content-Type': 'application/json',
    'Square-Version': '2025-01-23',
}

def sq_post(endpoint, body):
    req = urllib.request.Request(
        f'https://connect.squareup.com/v2/{endpoint}',
        data=json.dumps(body).encode(), headers=HEADERS,
    )
    return json.loads(urllib.request.urlopen(req).read())

def sq_get(path):
    req = urllib.request.Request(
        f'https://connect.squareup.com/v2/{path}', headers=HEADERS,
    )
    return json.loads(urllib.request.urlopen(req).read())

# Collect unique vendor IDs from first 500 catalog items
vendor_ids = set()
cursor = None
for page in range(5):
    body = {'object_types': ['ITEM'], 'limit': 100}
    if cursor: body['cursor'] = cursor
    data = sq_post('catalog/search', body)
    for obj in data.get('objects', []):
        for var in obj.get('item_data', {}).get('variations', []):
            for vi in var.get('item_variation_data', {}).get('item_variation_vendor_infos', []):
                vid = vi.get('item_variation_vendor_info_data', {}).get('vendor_id')
                if vid: vendor_ids.add(vid)
    cursor = data.get('cursor')
    if not cursor: break

print(f"Found {len(vendor_ids)} unique vendor IDs from first 500 items")
for vid in list(vendor_ids)[:5]:
    print(f"  {vid}")

# Try to retrieve vendors by ID
print("\n=== Trying to retrieve vendors by ID ===")
for vid in list(vendor_ids)[:3]:
    try:
        r = sq_get(f'vendors/{vid}')
        v = r.get('vendor', {})
        print(f"  {vid} → {v.get('name', '?')} (status: {v.get('status')})")
    except Exception as e:
        print(f"  {vid} → Error: {e}")

# Try bulk retrieve
print("\n=== Trying bulk retrieve ===")
try:
    r = sq_post('vendors/bulk-retrieve', {'vendor_ids': list(vendor_ids)[:10]})
    for vid, resp in r.get('responses', {}).items():
        v = resp.get('vendor', {})
        print(f"  {vid} → {v.get('name', '?')}")
except Exception as e:
    print(f"  Error: {e}")
