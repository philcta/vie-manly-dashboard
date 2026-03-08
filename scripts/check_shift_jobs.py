"""Check Square Labor API for scheduled shifts vs actual shifts."""
import sys, os, json, urllib.request
from datetime import datetime, timezone, timedelta
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

syd_offset = timedelta(hours=11)
now_syd = datetime.now(timezone(syd_offset))

# 1. Search for shifts with different statuses
print("=" * 60)
print("1. SHIFT STATUSES (last 30 days)")
print("=" * 60)

thirty_days_ago = (now_syd - timedelta(days=30)).replace(hour=0, minute=0, second=0)
start_utc = thirty_days_ago.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

# Fetch ALL shifts (both OPEN and CLOSED)
all_shifts = []
cursor = None
while True:
    body = {
        "query": {
            "filter": {
                "start": {"start_at": start_utc}
            }
        },
        "limit": 200
    }
    if cursor:
        body["cursor"] = cursor
    req = urllib.request.Request(
        base + '/v2/labor/shifts/search',
        data=json.dumps(body).encode(),
        headers=headers,
        method='POST'
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    shifts = data.get('shifts', [])
    all_shifts.extend(shifts)
    cursor = data.get('cursor')
    if not cursor:
        break

print(f"Total shifts found: {len(all_shifts)}")

# Count by status
status_count = {}
for s in all_shifts:
    st = s.get('status', '?')
    status_count[st] = status_count.get(st, 0) + 1
print(f"By status: {status_count}")

# Check for shifts missing end_at (forgot to clock out)
no_end = [s for s in all_shifts if not s.get('end_at') and s.get('status') != 'OPEN']
print(f"Closed shifts without end_at: {len(no_end)}")

open_shifts = [s for s in all_shifts if s.get('status') == 'OPEN']
if open_shifts:
    print(f"\nCurrently OPEN shifts:")
    for s in open_shifts:
        start = s.get('start_at', '')
        st = datetime.fromisoformat(start.replace('Z', '+00:00')).astimezone(timezone(syd_offset))
        hours_open = (now_syd - st).total_seconds() / 3600
        print(f"  {s.get('team_member_id', '?')[:15]} started {st.strftime('%H:%M')} ({hours_open:.1f}h ago)")

# 2. Check for scheduled/draft shifts
print(f"\n{'='*60}")
print("2. CHECKING FOR SCHEDULED SHIFTS (draft status)")
print(f"{'='*60}")

# Try to search with no filter to see if there are scheduled shifts
body = {
    "query": {
        "filter": {
            "status": {"status": ["DRAFT"]},
            "start": {"start_at": start_utc}
        }
    },
    "limit": 50
}
try:
    req = urllib.request.Request(
        base + '/v2/labor/shifts/search',
        data=json.dumps(body).encode(),
        headers=headers,
        method='POST'
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    draft_shifts = data.get('shifts', [])
    print(f"Draft/scheduled shifts: {len(draft_shifts)}")
    for s in draft_shifts[:5]:
        print(f"  {json.dumps(s, indent=2)[:200]}")
except Exception as e:
    print(f"Error checking draft shifts: {e}")

# 3. Check for break periods in shifts
print(f"\n{'='*60}")
print("3. BREAK PERIODS IN SHIFTS")
print(f"{'='*60}")
has_breaks = [s for s in all_shifts if s.get('breaks')]
print(f"Shifts with break records: {len(has_breaks)}/{len(all_shifts)}")
if has_breaks:
    print(f"Sample break: {json.dumps(has_breaks[0].get('breaks', []), indent=2)[:300]}")

# 4. Anomaly detection: shifts > 12h or < 1h
print(f"\n{'='*60}")
print("4. ANOMALIES (potential missed clock-outs)")
print(f"{'='*60}")

for s in all_shifts:
    if s.get('status') != 'CLOSED' or not s.get('end_at'):
        continue
    start = datetime.fromisoformat(s['start_at'].replace('Z', '+00:00'))
    end = datetime.fromisoformat(s['end_at'].replace('Z', '+00:00'))
    hours = (end - start).total_seconds() / 3600
    
    if hours > 12:
        name_id = s.get('team_member_id', '?')[:15]
        day = start.astimezone(timezone(syd_offset)).strftime('%a %d %b')
        print(f"  ⚠️ {name_id} on {day}: {hours:.1f}h (likely forgot to clock out)")
    elif hours < 0.5:
        name_id = s.get('team_member_id', '?')[:15]
        day = start.astimezone(timezone(syd_offset)).strftime('%a %d %b')
        print(f"  ⚠️ {name_id} on {day}: {hours:.1f}h (very short shift)")

# 5. Check if Square has a separate scheduling endpoint
print(f"\n{'='*60}")
print("5. TEAM MEMBER WAGES (for schedule reference)")
print(f"{'='*60}")

# List all job titles
body = {"limit": 200}
req = urllib.request.Request(
    base + '/v2/team-members/search',
    data=json.dumps(body).encode(),
    headers=headers,
    method='POST'
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
members = data.get('team_members', [])

# Check if anyone has multiple job assignments (could work different roles)
multi_role = []
for m in members:
    wage = m.get('wage_setting', {})
    assignments = wage.get('job_assignments', [])
    if len(assignments) > 1:
        name = f"{m.get('given_name', '')} {m.get('family_name', '')}".strip()
        roles = [a.get('job_title', '').strip() for a in assignments]
        multi_role.append((name, roles))

if multi_role:
    print(f"\nStaff with MULTIPLE job roles:")
    for name, roles in multi_role:
        print(f"  {name}: {', '.join(roles)}")
else:
    print(f"No staff with multiple roles.")
