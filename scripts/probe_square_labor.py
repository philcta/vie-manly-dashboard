"""Check shift count and pattern for staff who have clocked in."""
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

# Staff who have shift history
staff_with_shifts = [
    ("Holly Selves", "TMuIQHmMfdJh1SH3"),
    ("Camilla Palombi", "TMQHHCIVfH4hzsGj"),
    ("Noah Le Sueur", "TMR-3Esm1460uu7m"),
    ("Jenny Kirkpatrick", "TMNRXLubB7ft6QTq"),
    ("Catalina Asenjo", "TMZR-rpSqSp3X-mb"),
    ("Charli Coates", "TMjCS-FE1BL5gCoF"),
    ("Ana Flores", "TMrPTJaG1jjIjph6"),
    ("Giovanna Cobitos", "TMZNRteWRW1cV8R6"),
    ("Baptiste Frugier", "TMt5QVFkyHD9CES7"),
]

for name, member_id in staff_with_shifts:
    # Get ALL shifts for this person
    all_shifts = []
    cursor = None
    while True:
        body = {
            "query": {
                "filter": {
                    "team_member_ids": [member_id]
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
    
    # Analyze
    dates = set()
    total_hours = 0
    for s in all_shifts:
        start = s.get('start_at', '')[:10]
        dates.add(start)
        end = s.get('end_at')
        if end and s.get('status') == 'CLOSED':
            from datetime import datetime
            try:
                # Parse ISO timestamps
                s_dt = datetime.fromisoformat(s['start_at'])
                e_dt = datetime.fromisoformat(s['end_at'])
                hours = (e_dt - s_dt).total_seconds() / 3600
                total_hours += hours
            except:
                pass
    
    sorted_dates = sorted(dates)
    first = sorted_dates[0] if sorted_dates else '?'
    last = sorted_dates[-1] if sorted_dates else '?'
    
    print(f"{name}")
    print(f"  Total shifts: {len(all_shifts)}")
    print(f"  Unique days worked: {len(dates)}")
    print(f"  First shift: {first}")
    print(f"  Last shift: {last}")
    print(f"  Total hours: {total_hours:.1f}")
    if len(dates) > 1:
        print(f"  Recent dates: {', '.join(sorted_dates[-5:])}")
    print()
