"""
Verify shift data: pull from Square + Supabase and compare.
Check day-of-week, hours, and rates.
"""
import sys, os, json, urllib.request
from datetime import datetime, timezone, timedelta, date
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
base = 'https://connect.squareup.com'
SYD = timedelta(hours=11)
syd_tz = timezone(SYD)

# Build team member lookup
body = {"limit": 200}
req = urllib.request.Request(base + '/v2/team-members/search', data=json.dumps(body).encode(), headers=sq_headers, method='POST')
resp = urllib.request.urlopen(req)
members_data = json.loads(resp.read())
names = {}
jobs = {}
for m in members_data.get('team_members', []):
    mid = m['id']
    names[mid] = f"{m.get('given_name', '')} {m.get('family_name', '')}".strip()
    for a in m.get('wage_setting', {}).get('job_assignments', []):
        jid = a.get('job_id', '')
        jobs[jid] = a.get('job_title', '').strip()

# Pull last 9 days from Square (scheduled shifts)
print("=" * 80)
print("SQUARE SCHEDULED SHIFTS — Last 9 days")
print("=" * 80)

today = datetime.now(syd_tz).date()
start_date = today - timedelta(days=9)

for d in range(10):
    target = start_date + timedelta(days=d)
    day_start = datetime(target.year, target.month, target.day, 0, 0, 0, tzinfo=syd_tz)
    day_end = day_start + timedelta(days=1)
    start_utc = day_start.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    end_utc = day_end.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
    body = {"query": {"filter": {"start": {"start_at": start_utc, "end_at": end_utc}}}, "limit": 50}
    req = urllib.request.Request(base + '/v2/labor/scheduled-shifts/search', data=json.dumps(body).encode(), headers=sq_headers, method='POST')
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    shifts = data.get('scheduled_shifts', [])
    
    total_hours = 0
    shift_details = []
    for s in shifts:
        det = s.get('published_shift_details') or s.get('draft_shift_details') or {}
        mid = det.get('team_member_id', '')
        jid = det.get('job_id', '')
        start_str = det.get('start_at', '')
        end_str = det.get('end_at', '')
        
        if start_str and end_str:
            st = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            en = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
            hours = round((en - st).total_seconds() / 3600, 2)
            total_hours += hours
            
            name = names.get(mid, mid[:15])
            job = jobs.get(jid, '?')
            shift_details.append(f"    {name:<22} {job:<18} {hours:.1f}h  ({st.astimezone(syd_tz).strftime('%H:%M')}-{en.astimezone(syd_tz).strftime('%H:%M')})")
    
    # Correct day of week from Python
    py_dow = target.strftime('%a')
    print(f"\n📅 {py_dow} {target.strftime('%d %b %Y')} — {len(shifts)} scheduled shifts, {total_hours:.1f}h total")
    for detail in sorted(shift_details):
        print(detail)

# Now pull from Supabase for same period
print(f"\n{'=' * 80}")
print("SUPABASE staff_shifts — Same period")
print("=" * 80)

supa_headers = {
    'apikey': SUPA_KEY,
    'Authorization': 'Bearer ' + SUPA_KEY,
}
url = f"{SUPA_URL}/rest/v1/staff_shifts?shift_date=gte.{start_date}&shift_date=lte.{today}&select=shift_date,staff_name,job_title,business_side,effective_hours,hourly_rate,labour_cost,source&order=shift_date,staff_name"
req = urllib.request.Request(url, headers=supa_headers)
resp = urllib.request.urlopen(req)
rows = json.loads(resp.read())

# Group by date
from collections import defaultdict
by_date = defaultdict(list)
for r in rows:
    by_date[r['shift_date']].append(r)

for d in range(10):
    target = start_date + timedelta(days=d)
    ds = str(target)
    py_dow = target.strftime('%a')
    day_rows = by_date.get(ds, [])
    
    total_h = sum(float(r['effective_hours']) for r in day_rows)
    cafe_h = sum(float(r['effective_hours']) for r in day_rows if r['business_side'] == 'Bar')
    retail_h = sum(float(r['effective_hours']) for r in day_rows if r['business_side'] == 'Retail')
    total_cost = sum(float(r['labour_cost']) for r in day_rows)
    
    print(f"\n📊 {py_dow} {target.strftime('%d %b %Y')} — {len(day_rows)} rows, ☕{cafe_h:.1f}h 🛍️{retail_h:.1f}h = {total_h:.1f}h total, 💰${total_cost:.0f}")
    for r in day_rows:
        print(f"    {r['staff_name']:<22} {r['job_title']:<22} {r['business_side']:<8} {float(r['effective_hours']):.1f}h × ${float(r['hourly_rate']):.2f} = ${float(r['labour_cost']):.2f}  [{r['source']}]")

# Day of week sanity check
print(f"\n{'=' * 80}")
print("DAY OF WEEK VERIFICATION")
print("=" * 80)
for d in range(10):
    target = start_date + timedelta(days=d)
    print(f"  {target} → Python says: {target.strftime('%A')}")
