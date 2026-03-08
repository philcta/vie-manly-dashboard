
import urllib.request, json, os, datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('SQUARE_ACCESS_TOKEN')
LOC_ID = os.getenv('SQUARE_LOCATION_ID')
SQ_HEADERS = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json', 'Square-Version': '2024-01-18'}

def fetch_orders(start_utc, end_utc):
    all_orders = []
    cursor = None
    while True:
        body = {'location_ids': [LOC_ID], 'query': {'filter': {'date_time_filter': {'created_at': {'start_at': start_utc, 'end_at': end_utc}}, 'state_filter': {'states': ['COMPLETED']}}}, 'limit': 500}
        if cursor: body['cursor'] = cursor
        req = urllib.request.Request('https://connect.squareup.com/v2/orders/search', json.dumps(body).encode(), SQ_HEADERS, method='POST')
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        all_orders.extend(data.get('orders', []))
        cursor = data.get('cursor')
        if not cursor: break
    return all_orders

syd = ZoneInfo('Australia/Sydney')
day = '2025-11-12'
d = datetime.datetime.strptime(day, '%Y-%m-%d')
start_utc = d.replace(hour=0, minute=0, second=0, tzinfo=syd).astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
# Fetch until 1 hour after to be safe
end_utc = (d.replace(hour=23, minute=59, second=59, tzinfo=syd) + datetime.timedelta(hours=1)).astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

orders = fetch_orders(start_utc, end_utc)

summary = []
for o in orders:
    o_total = int(o.get('total_money', {}).get('amount', 0))
    o_gross = sum(int(li.get('gross_sales_money', {}).get('amount', 0)) for li in o.get('line_items', []))
    o_disc = sum(int(li.get('total_discount_money', {}).get('amount', 0)) for li in o.get('line_items', []))
    o_sc = sum(int(sc.get('total_money', {}).get('amount', 0)) for sc in o.get('service_charges', []))
    o_tax = int(o.get('total_tax_money', {}).get('amount', 0))
    o_tip = int(o.get('total_tip_money', {}).get('amount', 0))
    
    tenders = o.get('tenders', [])
    tender_types = [t.get('type') for t in tenders]
    
    # Calculate Net Excl Tax
    net_excl = (o_gross - o_disc + o_sc - o_tax) / 100
    
    summary.append({
        'id': o.get('id'),
        'created_at': o.get('created_at'),
        'net_excl': net_excl,
        'total': o_total / 100,
        'tax': o_tax / 100,
        'tip': o_tip / 100,
        'gross': o_gross / 100,
        'disc': o_disc / 100,
        'sc': o_sc / 100,
        'tenders': tender_types
    })

with open('nov12_dump.json', 'w') as f:
    json.dump(summary, f, indent=2)

print(f"Dumped {len(summary)} orders to nov12_dump.json")
