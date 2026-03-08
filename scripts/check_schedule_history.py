"""Check how far back Square Scheduling API has data."""
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
SYD = timedelta(hours=11)
syd_tz = timezone(SYD)

# Try progressively further back in monthly chunks
print("Checking schedule availability by month...\n")

now = datetime.now(syd_tz)
found_earliest = None

for months_back in range(0, 24):  # Check up to 2 years back
    start = (now - timedelta(days=months_back * 30)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=30)
    
    start_utc = start.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    end_utc = end.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
    body = {"query": {"filter": {"start": {"start_at": start_utc, "end_at": end_utc}}}, "limit": 1}
    req = urllib.request.Request(
        base + '/v2/labor/scheduled-shifts/search',
        data=json.dumps(body).encode(), headers=headers, method='POST'
    )
    try:
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        shifts = data.get('scheduled_shifts', [])
        count = len(shifts)
        
        if count > 0:
            found_earliest = start
            month_str = start.strftime('%b %Y')
            print(f"  ✅ {month_str}: has data")
        else:
            month_str = start.strftime('%b %Y')
            print(f"  ❌ {month_str}: no data")
            if found_earliest:
                # We found data before but not now — stop
                break
    except Exception as e:
        month_str = start.strftime('%b %Y')
        print(f"  ⚠️ {month_str}: error ({e})")

if found_earliest:
    print(f"\n📅 Earliest schedule data: {found_earliest.strftime('%B %Y')}")
    
    # Get the exact earliest shift
    start_utc = found_earliest.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    end_utc = (found_earliest + timedelta(days=60)).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    body = {"query": {"filter": {"start": {"start_at": start_utc, "end_at": end_utc}}}, "limit": 50}
    req = urllib.request.Request(base + '/v2/labor/scheduled-shifts/search', data=json.dumps(body).encode(), headers=headers, method='POST')
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    shifts = data.get('scheduled_shifts', [])
    
    if shifts:
        dates = []
        for s in shifts:
            details = s.get('published_shift_details') or s.get('draft_shift_details') or {}
            start_at = details.get('start_at', '')
            if start_at:
                dt = datetime.fromisoformat(start_at.replace('Z', '+00:00')).astimezone(syd_tz)
                dates.append(dt.date())
        
        if dates:
            earliest = min(dates)
            latest = max(dates)
            days_of_data = (datetime.now(syd_tz).date() - earliest).days
            print(f"  Earliest shift: {earliest.strftime('%a %d %b %Y')}")
            print(f"  That's {days_of_data} days of schedule history available")
else:
    print("\n❌ No schedule data found in the last 2 years")

# Also count total shifts per month
print(f"\n📊 Monthly shift counts:")
for months_back in range(0, 12):
    start = (now - timedelta(days=months_back * 30)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=31)
    start_utc = start.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    end_utc = end.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
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
    
    if all_shifts:
        print(f"  {start.strftime('%b %Y')}: {len(all_shifts)} scheduled shifts")
    else:
        if months_back > 0:
            break
        print(f"  {start.strftime('%b %Y')}: 0 shifts")
