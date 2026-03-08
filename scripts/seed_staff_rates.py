"""Populate staff_rates table with $0 stub entries for all staff × job × day_type combos.
Creates 4 rows per person per job: weekday, saturday, sunday, public_holiday.
All rates start at $0 — set actual rates via Settings > Staff Rates in the dashboard.

⚠️ Hourly rates are NOT sourced from Square.
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

# Fetch all team members
all_members = []
cursor = None
while True:
    body = {"limit": 200}
    if cursor:
        body["cursor"] = cursor
    req = urllib.request.Request(base + '/v2/team-members/search', data=json.dumps(body).encode(), headers=sq_headers, method='POST')
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    all_members.extend(data.get('team_members', []))
    cursor = data.get('cursor')
    if not cursor:
        break

DAY_TYPES = ['weekday', 'saturday', 'sunday', 'public_holiday']
rows = []

for m in all_members:
    mid = m['id']
    name = f"{m.get('given_name', '')} {m.get('family_name', '')}".strip()
    status = m.get('status', 'INACTIVE')
    if not name:
        continue

    wage = m.get('wage_setting', {})
    for a in wage.get('job_assignments', []):
        job_title = a.get('job_title', '').strip()
        if not job_title:
            continue
        
        for dt in DAY_TYPES:
            rows.append({
                "team_member_id": mid,
                "staff_name": name,
                "job_title": job_title,
                "day_type": dt,
                "hourly_rate": 0,  # all rates start at $0 — set in Settings
            })

# Upsert
print(f"📥 Inserting {len(rows)} rate rows ({len(rows)//4} staff×job combos × 4 day types)")

# batch in chunks of 50
for i in range(0, len(rows), 50):
    batch = rows[i:i+50]
    req = urllib.request.Request(
        f"{SUPA_URL}/rest/v1/staff_rates?on_conflict=team_member_id,job_title,day_type",
        data=json.dumps(batch).encode(),
        headers=supa_headers,
        method='POST'
    )
    try:
        urllib.request.urlopen(req)
        print(f"  ✅ Batch {i//50 + 1}: {len(batch)} rows")
    except urllib.error.HTTPError as e:
        print(f"  ❌ Error: {e.read().decode()[:300]}")

# Summary
print(f"\n📊 Summary:")
active = [m for m in all_members if m.get('status') == 'ACTIVE']
print(f"  Active staff: {len(active)}")
print(f"  Total rate entries: {len(rows)}")
print(f"  All rates start at $0 — set actual rates in Settings > Staff Rates")
print(f"  (Existing rates in Supabase are NOT overwritten due to ignore-duplicates policy)")
