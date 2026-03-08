"""Probe Square Team Members API — get job titles and roles for all staff."""
import sys, os, json, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()

token = os.getenv('SQUARE_ACCESS_TOKEN')
headers = {
    'Authorization': 'Bearer ' + token,
    'Content-Type': 'application/json',
    'Square-Version': '2025-01-23',
}
base = 'https://connect.squareup.com'

# Fetch all team members
all_members = []
cursor = None
while True:
    body = {"limit": 200}
    if cursor:
        body["cursor"] = cursor
    req = urllib.request.Request(
        base + '/v2/team-members/search',
        data=json.dumps(body).encode(),
        headers=headers,
        method='POST'
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    members = data.get('team_members', [])
    all_members.extend(members)
    cursor = data.get('cursor')
    if not cursor:
        break

print(f"Total team members: {len(all_members)}\n")

CAFE_TITLES = {'Kitchen', 'Manager', 'Owner'}

print(f"{'Name':<25} {'ID':<20} {'Job Title':<15} {'Status':<10} {'Side'}")
print(f"{'-'*25} {'-'*20} {'-'*15} {'-'*10} {'-'*10}")
for m in all_members:
    name = f"{m.get('given_name', '')} {m.get('family_name', '')}".strip()
    mid = m.get('id', '?')
    status = m.get('status', '?')
    
    # Job title from assigned_locations or wage_setting
    job_title = ''
    wage = m.get('wage_setting', {})
    assignments = wage.get('job_assignments', [])
    if assignments:
        job_title = assignments[0].get('job_title', '')
    
    side = 'Cafe' if job_title in CAFE_TITLES else 'Retail'
    
    print(f"{name:<25} {mid:<20} {job_title:<15} {status:<10} {side}")

    # Show hourly rate if available
    if assignments:
        for a in assignments:
            rate = a.get('hourly_rate', {})
            if rate:
                amt = rate.get('amount', 0) / 100
                print(f"  {'':25} {'':20} Rate: ${amt:.2f}/hr")

print()
# Also dump raw JSON for first 2 members to see full structure
print("=== Raw sample (first 2 members) ===")
for m in all_members[:2]:
    print(json.dumps(m, indent=2))
