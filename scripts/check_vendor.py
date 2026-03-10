"""Check vendor info for a specific SKU from the Square API."""
import sys, os, json, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

token = os.getenv("SQUARE_ACCESS_TOKEN")
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Square-Version": "2025-01-23",
}

sku = sys.argv[1] if len(sys.argv) > 1 else "9349472000073"
print(f"Looking up SKU: {sku}")

# Search for the item variation by SKU
resp = requests.post(
    "https://connect.squareup.com/v2/catalog/search",
    headers=headers,
    json={
        "object_types": ["ITEM_VARIATION"],
        "query": {"exact_query": {"attribute_name": "sku", "attribute_value": sku}},
        "include_related_objects": True,
    },
)
data = resp.json()

for obj in data.get("objects", []):
    vd = obj.get("item_variation_data", {})
    print(f"\nVariation ID: {obj['id']}")
    print(f"  Name: {vd.get('name')}")
    print(f"  SKU: {vd.get('sku')}")
    print(f"  Item ID: {vd.get('item_id')}")
    vis = vd.get("item_variation_vendor_infos", [])
    print(f"  Vendor infos ({len(vis)}):")
    for vi in vis:
        vid = vi.get("item_variation_vendor_info_data", {})
        print(f"    Vendor ID: {vid.get('vendor_id')}")
        print(f"    Price: {vid.get('price_money')}")

print(f"\nRelated objects ({len(data.get('related_objects', []))}):")
for ro in data.get("related_objects", []):
    rtype = ro["type"]
    rid = ro["id"]
    if rtype == "ITEM":
        print(f"  ITEM {rid}: {ro.get('item_data', {}).get('name')}")
    elif rtype == "VENDOR":
        vdata = ro.get("vendor_data", {})
        print(f"  VENDOR {rid}: {vdata.get('name')}")
    else:
        print(f"  {rtype} {rid}")
