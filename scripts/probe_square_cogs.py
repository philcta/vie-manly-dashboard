"""Probe Square API for COGS / unit cost data on catalog items."""
import os, json, urllib.request, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("SQUARE_ACCESS_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Square-Version": "2024-01-18",
}

def sq_post(endpoint, body):
    req = urllib.request.Request(
        f"https://connect.squareup.com/v2/{endpoint}",
        data=json.dumps(body).encode(),
        headers=HEADERS,
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


# 1. Search for a known Cafe item (Smoothie)
print("=== Searching for 'Tropical Bliss' (Smoothie Bar) ===")
data = sq_post("catalog/search", {
    "object_types": ["ITEM"],
    "query": {"text_query": {"keywords": ["Tropical Bliss"]}},
    "limit": 1,
})

for obj in data.get("objects", []):
    item_data = obj.get("item_data", {})
    name = item_data.get("name", "?")
    print(f"\nItem: {name} (id: {obj['id']})")
    
    for var in item_data.get("variations", []):
        vd = var.get("item_variation_data", {})
        print(f"  Variation: {vd.get('name', 'Default')}")
        print(f"    Price: {vd.get('price_money')}")
        # Check all available fields
        print(f"    All fields: {sorted(vd.keys())}")
        # Specifically look for cost fields
        for key in sorted(vd.keys()):
            if "cost" in key.lower() or "cog" in key.lower():
                print(f"    *** COST FIELD: {key} = {vd[key]}")


# 2. Search for a Retail item for comparison
print("\n\n=== Searching for a Retail item ===")
data2 = sq_post("catalog/search", {
    "object_types": ["ITEM"],
    "query": {"text_query": {"keywords": ["Pumpkin Seeds"]}},
    "limit": 1,
})

for obj in data2.get("objects", []):
    item_data = obj.get("item_data", {})
    name = item_data.get("name", "?")
    print(f"\nItem: {name} (id: {obj['id']})")
    
    for var in item_data.get("variations", []):
        vd = var.get("item_variation_data", {})
        print(f"  Variation: {vd.get('name', 'Default')}")
        print(f"    Price: {vd.get('price_money')}")
        print(f"    All fields: {sorted(vd.keys())}")
        for key in sorted(vd.keys()):
            if "cost" in key.lower() or "cog" in key.lower():
                print(f"    *** COST FIELD: {key} = {vd[key]}")


# 3. Check inventory counts endpoint (may have cost info)
print("\n\n=== Checking Inventory API for cost data ===")
# List a catalog item's inventory to see if cost is attached
if data.get("objects"):
    item_id = data["objects"][0]["id"]
    variations = data["objects"][0].get("item_data", {}).get("variations", [])
    if variations:
        var_id = variations[0]["id"]
        print(f"Checking inventory for variation: {var_id}")
        inv_data = sq_post("inventory/batch-retrieve-counts", {
            "catalog_object_ids": [var_id],
        })
        for count in inv_data.get("counts", []):
            print(f"  Count: {json.dumps(count, indent=2)}")


# 4. Try retrieving full catalog object with all related objects
print("\n\n=== Full catalog object retrieve ===")
if data.get("objects"):
    item_id = data["objects"][0]["id"]
    req = urllib.request.Request(
        f"https://connect.squareup.com/v2/catalog/object/{item_id}?include_related_objects=true",
        headers=HEADERS,
    )
    resp = urllib.request.urlopen(req)
    full = json.loads(resp.read())
    obj = full.get("object", {})
    item_data = obj.get("item_data", {})
    print(f"Item: {item_data.get('name')}")
    print(f"Top-level fields: {sorted(obj.keys())}")
    print(f"Item data fields: {sorted(item_data.keys())}")
    for var in item_data.get("variations", []):
        vd = var.get("item_variation_data", {})
        print(f"\n  Variation '{vd.get('name')}':")
        for k, v in sorted(vd.items()):
            print(f"    {k}: {v}")
