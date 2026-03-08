"""Check if scheduled shifts contain hourly rates per person, and investigate day types."""
import sys, os, json, urllib.request
from datetime import datetime, timezone, timedelta, date
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
SYD = timedelta(hours=11)
syd_tz = timezone(SYD)

# 1. Check raw scheduled shift for rate info
print("=" * 60)
print("1. RAW SCHEDULED SHIFT — checking for hourly_rate field")
print("=" * 60)

now = datetime.now(syd_tz)
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
today_end = today_start + timedelta(days=1)
start_utc = today_start.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
end_utc = today_end.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')

body = {"query": {"filter": {"start": {"start_at": start_utc, "end_at": end_utc}}}, "limit": 10}
req = urllib.request.Request(base + '/v2/labor/scheduled-shifts/search', data=json.dumps(body).encode(), headers=headers, method='POST')
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
shifts = data.get('scheduled_shifts', [])

# Print FULL raw JSON for first 2 shifts (to see ALL fields)
for i, s in enumerate(shifts[:2]):
    print(f"\n--- Scheduled shift {i+1} (full JSON) ---")
    print(json.dumps(s, indent=2))

# 2. Now check actual (clock-in) shifts for comparison
print(f"\n{'='*60}")
print("2. RAW ACTUAL SHIFT — checking hourly_rate")
print(f"{'='*60}")

body2 = {"query": {"filter": {"start": {"start_at": start_utc}}}, "limit": 5}
req2 = urllib.request.Request(base + '/v2/labor/shifts/search', data=json.dumps(body2).encode(), headers=headers, method='POST')
resp2 = urllib.request.urlopen(req2)
data2 = json.loads(resp2.read())
actual = data2.get('shifts', [])

for i, s in enumerate(actual[:2]):
    print(f"\n--- Actual shift {i+1} (full JSON) ---")
    print(json.dumps(s, indent=2))

# 3. Compare rates: check if different people with same job title have different rates in schedule
print(f"\n{'='*60}")
print("3. PER-PERSON RATE FROM TEAM MEMBERS API")
print(f"{'='*60}")

body3 = {"limit": 200}
req3 = urllib.request.Request(base + '/v2/team-members/search', data=json.dumps(body3).encode(), headers=headers, method='POST')
resp3 = urllib.request.urlopen(req3)
data3 = json.loads(resp3.read())
members = data3.get('team_members', [])

print(f"\nRetail Assistants with different rates:")
for m in sorted(members, key=lambda x: x.get('given_name', '')):
    if m.get('status') != 'ACTIVE':
        continue
    wage = m.get('wage_setting', {})
    for a in wage.get('job_assignments', []):
        title = a.get('job_title', '').strip()
        if title == 'Retail Assistant':
            rate = a.get('hourly_rate', {})
            amount = rate.get('amount', 0) / 100 if rate else 0
            name = f"{m.get('given_name', '')} {m.get('family_name', '')}".strip()
            print(f"  {name:<25} ${amount:.2f}/hr")

# 4. NSW Public Holidays 2025-2026
print(f"\n{'='*60}")
print("4. NSW PUBLIC HOLIDAYS (hard-coded)")
print(f"{'='*60}")

nsw_holidays = [
    # 2025
    date(2025, 1, 1),   # New Year
    date(2025, 1, 27),  # Australia Day
    date(2025, 4, 18),  # Good Friday
    date(2025, 4, 19),  # Saturday before Easter Sunday
    date(2025, 4, 21),  # Easter Monday
    date(2025, 4, 25),  # Anzac Day
    date(2025, 6, 9),   # Queen's Birthday
    date(2025, 8, 4),   # Bank Holiday
    date(2025, 10, 6),  # Labour Day
    date(2025, 12, 25), # Christmas
    date(2025, 12, 26), # Boxing Day
    # 2026
    date(2026, 1, 1),   # New Year
    date(2026, 1, 26),  # Australia Day
    date(2026, 4, 3),   # Good Friday
    date(2026, 4, 4),   # Saturday before Easter Sunday
    date(2026, 4, 6),   # Easter Monday
    date(2026, 4, 25),  # Anzac Day (Saturday)
    date(2026, 6, 8),   # Queen's Birthday
    date(2026, 8, 3),   # Bank Holiday
    date(2026, 10, 5),  # Labour Day
    date(2026, 12, 25), # Christmas
    date(2026, 12, 26), # Boxing Day (Saturday → Mon 28th)
    date(2026, 12, 28), # Boxing Day observed
]

def get_day_type(d):
    if d in nsw_holidays:
        return 'public_holiday'
    if d.weekday() == 5:
        return 'saturday'
    if d.weekday() == 6:
        return 'sunday'
    return 'weekday'

print("  Sample day types:")
sample_dates = [date(2025, 12, 25), date(2025, 12, 26), date(2026, 1, 1), date(2026, 1, 26),
                date(2026, 2, 28), date(2026, 3, 1), date(2026, 3, 2), date(2026, 3, 3)]
for d in sample_dates:
    print(f"    {d.strftime('%a %d %b %Y')}: {get_day_type(d)}")
