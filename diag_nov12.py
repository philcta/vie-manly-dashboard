
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
end_utc = d.replace(hour=23, minute=59, second=59, tzinfo=syd).astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

orders = fetch_orders(start_utc, end_utc)

# List all orders and their calculated Net Excl Tax
print(f"Date: {day}")
for o in orders:
    o_total = int(o.get('total_money', {}).get('amount', 0))
    o_gross = sum(int(li.get('gross_sales_money', {}).get('amount', 0)) for li in o.get('line_items', []))
    if o_total > 0 or o_gross > 0:
        o_disc = sum(int(li.get('total_discount_money', {}).get('amount', 0)) for li in o.get('line_items', []))
        o_sc = sum(int(sc.get('total_money', {}).get('amount', 0)) for sc in o.get('service_charges', []))
        o_tax = int(o.get('total_tax_money', {}).get('amount', 0))
        net_excl = (o_gross - o_disc + o_sc - o_tax) / 100
        # If any order is around $130-$140, that's our candidate
        if net_excl > 50:
             print(f"ID: {o.get('id')[:8]} | NetExcl: {net_excl:8.2f} | Total: {o_total/100:8.2f} | Time: {o.get('created_at')}")

# Also check for orders just outside the window (maybe they count by 'closed_at'?)
# Let's check 1 hour before and after
start_utc_ext = (d.replace(hour=0, minute=0, second=0, tzinfo=syd) - datetime.timedelta(hours=1)).astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
end_utc_ext = (d.replace(hour=23, minute=59, second=59, tzinfo=syd) + datetime.timedelta(hours=1)).astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
orders_ext = fetch_orders(start_utc_ext, end_utc_ext)

print("\n--- Edge Cases (1hr before/after) ---")
for o in orders_ext:
    ts = o.get('created_at')
    dt_utc = datetime.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
    dt_syd = dt_utc.astimezone(syd)
    if dt_syd.date() != d.date():
        o_gross = sum(int(li.get('gross_sales_money', {}).get('amount', 0)) for li in o.get('line_items', []))
        o_disc = sum(int(li.get('total_discount_money', {}).get('amount', 0)) for li in o.get('line_items', []))
        o_sc = sum(int(sc.get('total_money', {}).get('amount', 0)) for sc in o.get('service_charges', []))
        o_tax = int(o.get('total_tax_money', {}).get('amount', 0))
        net_excl = (o_gross - o_disc + o_sc - o_tax) / 100
        print(f"ID: {o.get('id')[:8]} | SydTime: {dt_syd.strftime('%H:%M:%S')} | NetExcl: {net_excl:8.2f}")
