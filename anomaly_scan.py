
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
        body = {'location_ids': [LOC_ID], 'query': {'filter': {'date_time_filter': {'closed_at': {'start_at': start_utc, 'end_at': end_utc}}}, 'state_filter': {'states': ['COMPLETED']}}, 'limit': 500}
        if cursor: body['cursor'] = cursor
        req = urllib.request.Request('https://connect.squareup.com/v2/orders/search', json.dumps(body).encode(), SQ_HEADERS, method='POST')
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        all_orders.extend(data.get('orders', []))
        cursor = data.get('cursor')
        if not cursor: break
    return all_orders

syd = ZoneInfo('Australia/Sydney')

def scan_day(date_str):
    d = datetime.datetime.strptime(date_str, '%Y-%m-%d')
    start_utc = d.replace(hour=0, minute=0, second=0, tzinfo=syd).astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    end_utc = d.replace(hour=23, minute=59, second=59, tzinfo=syd).astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    orders = fetch_orders(start_utc, end_utc)
    valid = [o for o in orders if any(t.get('type') in ['CARD', 'CASH'] for t in o.get('tenders', []))]
    
    hidden_tips = 0
    anomalies = []
    
    for o in valid:
        total_pay = sum(int(t.get('amount_money', {}).get('amount', 0)) for t in o.get('tenders', []))
        total_tip_tender = sum(int(t.get('tip_money', {}).get('amount', 0)) for t in o.get('tenders', []))
        order_tip_field = int(o.get('total_tip_money', {}).get('amount', 0))
        
        o_tax = int(o.get('total_tax_money', {}).get('amount', 0))
        o_gross = sum(int(li.get('gross_sales_money', {}).get('amount', 0)) for li in o.get('line_items', []))
        o_disc = sum(int(li.get('total_discount_money', {}).get('amount', 0)) for li in o.get('line_items', []))
        o_sc = sum(int(sc.get('total_money', {}).get('amount', 0)) for sc in o.get('service_charges', []))
        
        expected_total = o_gross - o_disc + o_sc + o_tax + max(total_tip_tender, order_tip_field)
        
        if abs(total_pay - expected_total) > 1:
             anomalies.append({
                 'id': o.get('id'),
                 'pay': total_pay/100,
                 'expected': expected_total/100,
                 'tip_tender': total_tip_tender/100,
                 'tax': o_tax/100
             })
        
        hidden_tips += total_tip_tender

    print(f"\n--- {date_str} Breakdown ---")
    print(f"Total Tenders Sum: {sum(sum(int(t.get('amount_money', {}).get('amount', 0)) for t in o.get('tenders', [])) for o in valid)/100:.2f}")
    print(f"Total Tips from Tenders: {hidden_tips/100:.2f}")
    print(f"Anomalies found: {len(anomalies)}")
    
    if anomalies:
        for a in sorted(anomalies, key=lambda x: abs(x['pay'] - x['expected']), reverse=True)[:5]:
             print(f"  ID: {a['id'][:8]} | Paid: {a['pay']:.2f} | Expected: {a['expected']:.2f} (Gap: {a['pay'] - a['expected']:.2f})")

for day in ['2025-11-10', '2025-11-11', '2025-11-12']:
    scan_day(day)
