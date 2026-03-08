
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
        body = {'location_ids': [LOC_ID], 'query': {'filter': {'date_time_filter': {'created_at': {'start_at': start_utc, 'end_at': end_utc}}, 'state_filter': {'states': ['COMPLETED', 'CANCELED']}}}, 'limit': 500}
        if cursor: body['cursor'] = cursor
        req = urllib.request.Request('https://connect.squareup.com/v2/orders/search', json.dumps(body).encode(), SQ_HEADERS, method='POST')
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        all_orders.extend(data.get('orders', []))
        cursor = data.get('cursor')
        if not cursor: break
    return all_orders

syd = ZoneInfo('Australia/Sydney')

def analyze_date(date_str):
    d = datetime.datetime.strptime(date_str, '%Y-%m-%d')
    start_utc = d.replace(hour=0, minute=0, second=0, tzinfo=syd).astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    end_utc = d.replace(hour=23, minute=59, second=59, tzinfo=syd).astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    orders = fetch_orders(start_utc, end_utc)
    
    total_completed = [o for o in orders if o.get('state') == 'COMPLETED']
    
    print(f"\n--- Analysis for {date_str} ---")
    print(f"Total Completed: {len(total_completed)}")
    
    total_tips = 0
    total_service = 0
    total_refunds_tied = 0
    total_tax = 0
    total_gross = 0
    total_disc = 0
    
    for o in total_completed:
        total_tips += int(o.get('total_tip_money', {}).get('amount', 0))
        total_tax += int(o.get('total_tax_money', {}).get('amount', 0))
        
        for sc in o.get('service_charges', []):
            total_service += int(sc.get('total_money', {}).get('amount', 0))
            
        for li in o.get('line_items', []):
            total_gross += int(li.get('gross_sales_money', {}).get('amount', 0))
            total_disc += int(li.get('total_discount_money', {}).get('amount', 0))
            
        # Refunds tied to these orders (even if processed later)
        for r in o.get('refunds', []):
            if r.get('status') in ['APPROVED', 'COMPLETED']:
                total_refunds_tied += int(r.get('amount_money', {}).get('amount', 0))

    print(f"Gross: {total_gross/100:.2f} | Disc: {total_disc/100:.2f} | Service: {total_service/100:.2f} | Tax: {total_tax/100:.2f}")
    print(f"Tips: {total_tips/100:.2f} | Refunds Tied: {total_refunds_tied/100:.2f}")
    
    # Check for gift card items
    gc_sum = 0
    for o in total_completed:
        for li in o.get('line_items', []):
            if li.get('item_type') == 'GIFT_CARD' or 'gift card' in li.get('name', '').lower():
                gc_sum += int(li.get('total_money', {}).get('amount', 0))
    print(f"Gift Cards: {gc_sum/100:.2f}")

    # Check for orders with NO tenders (maybe offline/unpaid?)
    no_tenders = sum(1 for o in total_completed if not o.get('tenders'))
    print(f"Orders with NO tenders: {no_tenders}")

for day in ['2025-11-10', '2025-11-11', '2025-11-12']:
    analyze_date(day)
