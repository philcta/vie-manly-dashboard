"""Sync Square Team Members → Supabase staff_roles table with business side mapping.

⚠️ HOURLY RATES are NOT sourced from Square.
Rates are managed exclusively in Supabase staff_rates table
(editable via Settings > Staff Rates in the dashboard).
"""
import sys, os, json, urllib.request
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

# Cafe-side job titles (stored as 'Bar' in DB, shown as 'Cafe' in UI)
CAFE_TITLES = {'Kitchen', 'Manager', 'Owner'}

# 1. Fetch all team members from Square
print("📥 Fetching team members from Square...")
all_members = []
cursor = None
while True:
    body = {"limit": 200}
    if cursor:
        body["cursor"] = cursor
    req = urllib.request.Request(
        base + '/v2/team-members/search',
        data=json.dumps(body).encode(),
        headers=sq_headers,
        method='POST'
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    members = data.get('team_members', [])
    all_members.extend(members)
    cursor = data.get('cursor')
    if not cursor:
        break

print(f"  Found {len(all_members)} team members")

# 2. Map to staff_roles rows
rows = []
for m in all_members:
    name = f"{m.get('given_name', '')} {m.get('family_name', '')}".strip()
    mid = m.get('id', '')
    status = m.get('status', 'INACTIVE')
    
    # Get job title from Square (rates come from Supabase staff_rates, NOT Square)
    job_title = ''
    wage = m.get('wage_setting', {})
    assignments = wage.get('job_assignments', [])
    if assignments:
        job_title = assignments[0].get('job_title', '').strip()
    
    # Determine business side
    business_side = 'Bar' if job_title in CAFE_TITLES else 'Retail'
    
    rows.append({
        "team_member_id": mid,
        "staff_name": name,
        "job_title": job_title,
        "business_side": business_side,
        "is_active": status == 'ACTIVE',
    })

# 3. Upsert into Supabase (use on_conflict for team_member_id)
upsert_headers = {**supa_headers, 'Prefer': 'resolution=merge-duplicates'}
req = urllib.request.Request(
    f"{SUPA_URL}/rest/v1/staff_roles?on_conflict=team_member_id",
    data=json.dumps(rows).encode(),
    headers=upsert_headers,
    method='POST'
)
try:
    resp = urllib.request.urlopen(req)
    print(f"  ✅ Upserted {len(rows)} staff members")
except urllib.error.HTTPError as e:
    error_body = e.read().decode()
    print(f"  ❌ Error: {error_body[:500]}")

# 4. Summary
print(f"\n📊 Summary:")
cafe_staff = [r for r in rows if r['business_side'] == 'Bar']
retail_staff = [r for r in rows if r['business_side'] == 'Retail']
active = [r for r in rows if r['is_active']]
print(f"  Cafe side (Kitchen/Manager/Owner): {len(cafe_staff)}")
for s in cafe_staff:
    active_str = "✅" if s['is_active'] else "❌"
    print(f"    {active_str} {s['staff_name']:<25} {s['job_title']:<15}")
print(f"  Retail side: {len(retail_staff)}")
for s in retail_staff:
    active_str = "✅" if s['is_active'] else "❌"
    print(f"    {active_str} {s['staff_name']:<25} {s['job_title']:<15}")
print(f"\n  Active staff total: {len(active)}")
print(f"  ℹ️  Hourly rates managed in Settings > Staff Rates (not from Square)")
