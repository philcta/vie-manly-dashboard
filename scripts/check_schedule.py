"""Pull today's and this week's scheduled roster from Square Scheduling API."""
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

# Build lookups
all_members = []
cursor = None
while True:
    mbody = {"limit": 200}
    if cursor:
        mbody["cursor"] = cursor
    req = urllib.request.Request(base + '/v2/team-members/search', data=json.dumps(mbody).encode(), headers=headers, method='POST')
    resp = urllib.request.urlopen(req)
    mdata = json.loads(resp.read())
    all_members.extend(mdata.get('team_members', []))
    cursor = mdata.get('cursor')
    if not cursor:
        break

name_lookup = {m.get('id', ''): f"{m.get('given_name', '')} {m.get('family_name', '')}".strip() for m in all_members}
job_lookup = {}
for m in all_members:
    for a in m.get('wage_setting', {}).get('job_assignments', []):
        job_lookup[a.get('job_id', '')] = a.get('job_title', '').strip()

CAFE_TITLES = {'Kitchen', 'Barrista'}

def fetch_schedule(start_dt, end_dt):
    """Fetch scheduled shifts for a date range."""
    start_utc = start_dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    end_utc = end_dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
    all_shifts = []
    cursor = None
    while True:
        body = {"query": {"filter": {"start": {"start_at": start_utc, "end_at": end_utc}}}, "limit": 50}
        if cursor:
            body["cursor"] = cursor
        req = urllib.request.Request(base + '/v2/labor/scheduled-shifts/search', data=json.dumps(body).encode(), headers=headers, method='POST')
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        all_shifts.extend(data.get('scheduled_shifts', []))
        cursor = data.get('cursor')
        if not cursor:
            break
    return all_shifts

def parse_shift(s):
    """Extract useful info from a scheduled shift."""
    details = s.get('published_shift_details') or s.get('draft_shift_details') or {}
    team_member_id = details.get('team_member_id', s.get('team_member_id', ''))
    name = name_lookup.get(team_member_id, team_member_id[:15])
    job_id = details.get('job_id', '')
    job_title = job_lookup.get(job_id, '?')
    side = 'Cafe' if job_title in CAFE_TITLES else 'Retail'
    
    start = details.get('start_at', '')
    end = details.get('end_at', '')
    
    st = datetime.fromisoformat(start.replace('Z', '+00:00')).astimezone(timezone(syd_offset)) if start else None
    et = datetime.fromisoformat(end.replace('Z', '+00:00')).astimezone(timezone(syd_offset)) if end else None
    hours = (et - st).total_seconds() / 3600 if st and et else 0
    
    return {
        'name': name, 'team_member_id': team_member_id,"job_title": job_title,
        'side': side, 'start': st, 'end': et, 'hours': hours
    }

# 1. TODAY
print("=" * 70)
print(f"TODAY'S ROSTER — {now_syd.strftime('%A %d %b %Y')}")
print("=" * 70)

today_start = now_syd.replace(hour=0, minute=0, second=0, microsecond=0)
today_end = today_start + timedelta(days=1)
today_shifts = fetch_schedule(today_start, today_end)

if today_shifts:
    parsed = [parse_shift(s) for s in today_shifts]
    parsed.sort(key=lambda x: x['start'] or datetime.min.replace(tzinfo=timezone.utc))
    
    cafe_hours = sum(p['hours'] for p in parsed if p['side'] == 'Cafe')
    retail_hours = sum(p['hours'] for p in parsed if p['side'] == 'Retail')
    
    print(f"\n  {'Name':<22} {'Job Title':<18} {'Side':<8} {'Start':>6} {'End':>6} {'Hours':>6}")
    print(f"  {'-'*22} {'-'*18} {'-'*8} {'-'*6} {'-'*6} {'-'*6}")
    for p in parsed:
        start_str = p['start'].strftime('%H:%M') if p['start'] else '?'
        end_str = p['end'].strftime('%H:%M') if p['end'] else '?'
        print(f"  {p['name']:<22} {p['job_title']:<18} {p['side']:<8} {start_str:>6} {end_str:>6} {p['hours']:>5.1f}h")
    
    print(f"\n  Total: {len(parsed)} shifts, {sum(p['hours'] for p in parsed):.1f}h")
    print(f"  ☕ Cafe: {cafe_hours:.1f}h | 🛍️ Retail: {retail_hours:.1f}h")
else:
    print("  No scheduled shifts today.")

# 2. Also compare with actual clock-ins
print(f"\n{'='*70}")
print(f"ACTUAL vs SCHEDULED (today)")
print(f"{'='*70}")

body = {"query": {"filter": {"start": {"start_at": today_start.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}}}, "limit": 50}
req = urllib.request.Request(base + '/v2/labor/shifts/search', data=json.dumps(body).encode(), headers=headers, method='POST')
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
actual_shifts = data.get('shifts', [])

scheduled_ids = set()
if today_shifts:
    for s in today_shifts:
        details = s.get('published_shift_details') or s.get('draft_shift_details') or {}
        scheduled_ids.add(details.get('team_member_id', ''))

actual_ids = set()
for s in actual_shifts:
    actual_ids.add(s.get('team_member_id', ''))

clocked_in = scheduled_ids & actual_ids
not_clocked = scheduled_ids - actual_ids
extra_clocked = actual_ids - scheduled_ids

print(f"\n  Scheduled: {len(scheduled_ids)} staff")
print(f"  Clocked in: {len(actual_ids)} staff")
print(f"\n  ✅ Clocked in as scheduled: {', '.join(name_lookup.get(x, x[:10]) for x in clocked_in) or 'None'}")
print(f"  ⚠️ Scheduled but NOT clocked in: {', '.join(name_lookup.get(x, x[:10]) for x in not_clocked) or 'None'}")
print(f"  ❓ Clocked in but NOT scheduled: {', '.join(name_lookup.get(x, x[:10]) for x in extra_clocked) or 'None'}")

# 3. THIS WEEK
print(f"\n{'='*70}")
print(f"THIS WEEK'S SCHEDULE (Mon-Sun)")
print(f"{'='*70}")

days_since_monday = now_syd.weekday()
monday = (now_syd - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
sunday = monday + timedelta(days=7)
week_shifts = fetch_schedule(monday, sunday)

if week_shifts:
    by_day = {}
    for s in week_shifts:
        p = parse_shift(s)
        if p['start']:
            day = p['start'].strftime('%a %d %b')
            by_day.setdefault(day, []).append(p)
    
    for day in sorted(by_day.keys()):
        entries = by_day[day]
        total = sum(e['hours'] for e in entries)
        cafe_h = sum(e['hours'] for e in entries if e['side'] == 'Cafe')
        retail_h = sum(e['hours'] for e in entries if e['side'] == 'Retail')
        print(f"\n  {day} — {len(entries)} staff, {total:.1f}h (☕{cafe_h:.1f}h + 🛍️{retail_h:.1f}h)")
        for e in sorted(entries, key=lambda x: x['start'] or datetime.min.replace(tzinfo=timezone.utc)):
            start_str = e['start'].strftime('%H:%M') if e['start'] else '?'
            end_str = e['end'].strftime('%H:%M') if e['end'] else '?'
            print(f"    {e['name']:<22} {e['job_title']:<16} {e['side']:<6} {start_str}-{end_str} ({e['hours']:.1f}h)")
else:
    print("  No scheduled shifts this week.")
