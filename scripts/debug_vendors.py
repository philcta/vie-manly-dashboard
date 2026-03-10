"""Debug vendor API."""
import sys, os, requests, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

token = os.getenv("SQUARE_ACCESS_TOKEN")
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Square-Version": "2025-01-23",
}

# Approach 1: Use filter with status ACTIVE
resp = requests.post("https://connect.squareup.com/v2/vendors/search", headers=headers, json={
    "filter": {"status": ["ACTIVE"]}
})
data = resp.json()
print(f"Status: {resp.status_code}")
print(f"Vendors count: {len(data.get('vendors', []))}")
if data.get("errors"):
    print(f"Errors: {data['errors']}")
for v in data.get("vendors", []):
    print(f"  {v['id']}: {v.get('name', '')}")
if data.get("cursor"):
    print(f"Has more pages")
