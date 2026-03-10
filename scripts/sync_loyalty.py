"""Sync Square Loyalty accounts → Supabase member_loyalty table."""
import sys, os, json, urllib.request
from datetime import datetime, timezone
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()

SQUARE_TOKEN = os.getenv('SQUARE_ACCESS_TOKEN')
SUPA_URL = os.getenv('SUPABASE_URL')
SUPA_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

sq_headers = {
    'Authorization': 'Bearer ' + SQUARE_TOKEN,
    'Content-Type': 'application/json',
    'Square-Version': '2025-01-23',
}
supa_headers = {
    'apikey': SUPA_KEY,
    'Authorization': 'Bearer ' + SUPA_KEY,
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates',
}
base = 'https://connect.squareup.com'

# 1. Fetch ALL loyalty accounts from Square
print("📥 Fetching loyalty accounts from Square...")
all_accounts = []
cursor = None
while True:
    body = {"limit": 200}
    if cursor:
        body["cursor"] = cursor
    req = urllib.request.Request(
        base + '/v2/loyalty/accounts/search',
        data=json.dumps(body).encode(),
        headers=sq_headers,
        method='POST'
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    accounts = data.get('loyalty_accounts', [])
    all_accounts.extend(accounts)
    cursor = data.get('cursor')
    if not cursor:
        break

print(f"  Found {len(all_accounts)} loyalty accounts")

# 2. Upsert into Supabase in batches
BATCH_SIZE = 100
total_upserted = 0

for i in range(0, len(all_accounts), BATCH_SIZE):
    batch = all_accounts[i:i+BATCH_SIZE]
    rows = []
    for a in batch:
        balance = a.get('balance', 0)
        lifetime = a.get('lifetime_points', 0)
        rows.append({
            "customer_id": a['customer_id'],
            "loyalty_account_id": a['id'],
            "balance": balance,
            "lifetime_points": lifetime,
            "enrolled_at": a.get('enrolled_at') or a.get('created_at'),
            "last_synced": datetime.now(timezone.utc).isoformat(),
        })
    
    req = urllib.request.Request(
        f"{SUPA_URL}/rest/v1/member_loyalty?on_conflict=customer_id",
        data=json.dumps(rows).encode(),
        headers=supa_headers,
        method='POST'
    )
    try:
        resp = urllib.request.urlopen(req)
        total_upserted += len(rows)
        print(f"  ✅ Upserted batch {i//BATCH_SIZE + 1}: {len(rows)} rows (total: {total_upserted})")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  ❌ Batch error: {error_body[:300]}")

# 3. Verify
req = urllib.request.Request(
    f"{SUPA_URL}/rest/v1/member_loyalty?select=count",
    headers={**supa_headers, 'Prefer': 'count=exact', 'Range-Unit': 'items', 'Range': '0-0'}
)
resp = urllib.request.urlopen(req)
count_header = resp.headers.get('Content-Range', '?')
print(f"\n✅ Done! Supabase member_loyalty: {count_header}")
print(f"   Total synced: {total_upserted}")
