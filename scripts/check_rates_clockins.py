"""Check updated hourly rates and today's clock-ins from Square."""
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

CAFE_TITLES = {'Kitchen', 'Manager', 'Owner'}

# 1. Fetch all team members with updated rates
print("=" * 60)
print("1. HOURLY RATES (freshly fetched)")
print("=" * 60)

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

active_members = [m for m in all_members if m.get('status') == 'ACTIVE']
set_count = 0
missing_count = 0

print(f"\n{'Name':<25} {'Job Title':<18} {'Side':<8} {'Rate/hr':>10} {'Status'}")
print(f"{'-'*25} {'-'*18} {'-'*8} {'-'*10} {'-'*8}")

for m in sorted(active_members, key=lambda x: x.get('given_name', '')):
    name = f"{m.get('given_name', '')} {m.get('family_name', '')}".strip()
    wage = m.get('wage_setting', {})
    assignments = wage.get('job_assignments', [])
    job_title = assignments[0].get('job_title', '').strip() if assignments else ''
    side = 'Cafe' if job_title in CAFE_TITLES else 'Retail'
    
    rate = 0
    if assignments:
        r = assignments[0].get('hourly_rate', {})
        rate = r.get('amount', 0) / 100 if r else 0
    
    if rate > 0:
        set_count += 1
        status = '✅'
    else:
        missing_count += 1
        status = '⚠️ $0'
    
    print(f"{name:<25} {job_title:<18} {side:<8} ${rate:>8.2f} {status}")

print(f"\n  Active staff: {len(active_members)}")
print(f"  Rates set: {set_count}")
print(f"  Rates missing: {missing_count}")

# 2. Check today's shifts (clock-ins)
print(f"\n{'='*60}")
print(f"2. TODAY'S SHIFTS (Clock-ins for {datetime.now().strftime('%d %b %Y')})")
print(f"{'='*60}")

# Sydney timezone = UTC+11
syd_offset = timedelta(hours=11)
now_syd = datetime.now(timezone(syd_offset))
today_start = now_syd.replace(hour=0, minute=0, second=0, microsecond=0)
today_start_utc = today_start.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

body = {
    "query": {
        "filter": {
            "start": {
                "start_at": today_start_utc
            }
        }
    },
    "limit": 200
}
req = urllib.request.Request(
    base + '/v2/labor/shifts/search',
    data=json.dumps(body).encode(),
    headers=headers,
    method='POST'
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
shifts = data.get('shifts', [])

# Build member ID → name lookup
member_lookup = {}
for m in all_members:
    mid = m.get('id', '')
    name = f"{m.get('given_name', '')} {m.get('family_name', '')}".strip()
    member_lookup[mid] = name

if shifts:
    print(f"\n  {len(shifts)} shift(s) found today:\n")
    print(f"  {'Name':<25} {'Status':<10} {'Start (Sydney)':<20} {'End (Sydney)':<20} {'Hours':>6}")
    print(f"  {'-'*25} {'-'*10} {'-'*20} {'-'*20} {'-'*6}")
    
    for s in shifts:
        mid = s.get('team_member_id', '')
        name = member_lookup.get(mid, mid[:15])
        status = s.get('status', '?')
        
        start_utc = s.get('start_at', '')
        end_utc = s.get('end_at', '')
        
        # Convert to Sydney time
        if start_utc:
            st = datetime.fromisoformat(start_utc.replace('Z', '+00:00')).astimezone(timezone(syd_offset))
            start_syd = st.strftime('%H:%M')
        else:
            start_syd = '?'
        
        if end_utc:
            et = datetime.fromisoformat(end_utc.replace('Z', '+00:00')).astimezone(timezone(syd_offset))
            end_syd = et.strftime('%H:%M')
            hours = (et - st).total_seconds() / 3600
            hours_str = f"{hours:.1f}h"
        else:
            end_syd = 'still working'
            hours_str = '-'
        
        clock_emoji = '🟢' if status == 'OPEN' else '⏹️'
        print(f"  {name:<25} {clock_emoji} {status:<7} {start_syd:<20} {end_syd:<20} {hours_str:>6}")
else:
    print(f"\n  ❌ No shifts found for today.")
    print(f"  No one has clocked in yet today ({now_syd.strftime('%A %d %b %Y, %I:%M %p')} Sydney time).")

# 3. Quick summary of recent shifts (last 3 days)
print(f"\n{'='*60}")
print(f"3. RECENT SHIFTS (Last 3 days)")
print(f"{'='*60}")

three_days_ago = (now_syd - timedelta(days=3)).replace(hour=0, minute=0, second=0)
three_days_utc = three_days_ago.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

body = {
    "query": {
        "filter": {
            "start": {
                "start_at": three_days_utc
            }
        }
    },
    "limit": 200
}
req = urllib.request.Request(
    base + '/v2/labor/shifts/search',
    data=json.dumps(body).encode(),
    headers=headers,
    method='POST'
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
recent_shifts = data.get('shifts', [])

if recent_shifts:
    # Group by date
    by_date = {}
    for s in recent_shifts:
        start = s.get('start_at', '')
        if start:
            st = datetime.fromisoformat(start.replace('Z', '+00:00')).astimezone(timezone(syd_offset))
            day = st.strftime('%a %d %b')
            name = member_lookup.get(s.get('team_member_id', ''), '?')
            by_date.setdefault(day, []).append(name)
    
    for day, names in sorted(by_date.items()):
        print(f"  {day}: {', '.join(names)} ({len(names)} staff)")
else:
    print(f"  No shifts in the last 3 days.")
