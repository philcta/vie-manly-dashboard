
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
day = '2025-11-11'
d = datetime.datetime.strptime(day, '%Y-%m-%d')
start_utc = d.replace(hour=0, minute=0, second=0, tzinfo=syd).astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
end_utc = d.replace(hour=23, minute=59, second=59, tzinfo=syd).astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

orders = fetch_orders(start_utc, end_utc)
print(f"Total API Orders: {len(orders)}")

# Categorize
no_money_orders = []
positive_money_orders = []

for o in orders:
    total_tender = sum(int(t.get('amount_money', {}).get('amount', 0)) for t in o.get('tenders', []))
    if total_tender > 0:
        positive_money_orders.append(o)
    else:
        no_money_orders.append(o)

print(f"Orders with positive payment: {len(positive_money_orders)}")
print(f"Orders with zero/neg payment: {len(no_money_orders)}")

for o in no_money_orders:
    gross = sum(int(li.get('gross_sales_money', {}).get('amount', 0)) for li in o.get('line_items', []))
    tenders = [t.get('type') for t in o.get('tenders', [])]
    print(f"ID: {o.get('id')[:6]} | Gross: {gross:5} | Tenders: {tenders}")
