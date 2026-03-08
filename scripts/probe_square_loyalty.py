"""Probe Square Loyalty API — check program, accounts, and point balances."""
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


def api_get(path):
    req = urllib.request.Request(base + path, headers=headers)
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


def api_post(path, body):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode(),
        headers=headers,
        method='POST'
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


# 1. Check if a loyalty program exists
print("=" * 60)
print("1. LOYALTY PROGRAM")
print("=" * 60)
try:
    prog_data = api_get('/v2/loyalty/programs/main')
    program = prog_data.get('program', {})
    print(f"  Program ID:    {program.get('id')}")
    print(f"  Status:        {program.get('status')}")
    print(f"  Created:       {program.get('created_at', '')[:10]}")
    print(f"  Updated:       {program.get('updated_at', '')[:10]}")
    
    # Terminology
    terminology = program.get('terminology', {})
    print(f"  Points name:   {terminology.get('one', 'point')} / {terminology.get('other', 'points')}")
    
    # Accrual rules
    accrual = program.get('accrual_rules', [])
    for rule in accrual:
        print(f"  Accrual type:  {rule.get('accrual_type')}")
        if rule.get('spend_data'):
            sd = rule['spend_data']
            print(f"    Earn {rule.get('points', '?')} pts per ${sd.get('amount_money', {}).get('amount', 0)/100:.0f} spent")
        elif rule.get('visit_data'):
            print(f"    Earn {rule.get('points', '?')} pts per visit")
    
    # Reward tiers
    tiers = program.get('reward_tiers', [])
    print(f"\n  Reward Tiers ({len(tiers)}):")
    for t in tiers:
        pts = t.get('points', 0)
        name = t.get('name', 'Unknown')
        definition = t.get('definition', {})
        disc_type = definition.get('discount_type', '')
        pct = definition.get('percentage_discount', '')
        fixed = definition.get('fixed_discount_money', {})
        scope = definition.get('scope', '')
        print(f"    {pts} pts → {name} ({disc_type} {pct or ''}{fixed or ''}) scope={scope}")

    # Expiration
    expiry = program.get('expiration_policy', {})
    if expiry:
        print(f"\n  Expiration: {expiry.get('expiration_duration', 'None')}")
    
except urllib.error.HTTPError as e:
    body = e.read().decode()
    if '404' in str(e.code) or 'NOT_FOUND' in body:
        print("  ❌ No loyalty program found for this seller.")
        print("  You need to set one up in Square Dashboard first.")
    else:
        print(f"  Error {e.code}: {body[:300]}")
    sys.exit(0)

# 2. Fetch ALL loyalty accounts
print("\n" + "=" * 60)
print("2. LOYALTY ACCOUNTS (Members with Points)")
print("=" * 60)

all_accounts = []
cursor = None
while True:
    body = {"limit": 200}
    if cursor:
        body["cursor"] = cursor
    data = api_post('/v2/loyalty/accounts/search', body)
    accounts = data.get('loyalty_accounts', [])
    all_accounts.extend(accounts)
    cursor = data.get('cursor')
    if not cursor:
        break

print(f"  Total loyalty accounts: {len(all_accounts)}")

if all_accounts:
    # Summary stats
    balances = [a.get('balance', 0) for a in all_accounts]
    lifetime = [a.get('lifetime_points', 0) for a in all_accounts]
    print(f"  Total points in circulation: {sum(balances):,}")
    print(f"  Avg balance per member: {sum(balances)/len(balances):.1f}")
    print(f"  Max balance: {max(balances):,}")
    print(f"  Total lifetime points earned: {sum(lifetime):,}")
    
    # Show first 15 accounts
    print(f"\n  First 15 accounts:")
    print(f"  {'Customer ID':<30} {'Balance':>8} {'Lifetime':>10} {'Enrolled':>12}")
    print(f"  {'-'*30} {'-'*8} {'-'*10} {'-'*12}")
    for a in all_accounts[:15]:
        cid = a.get('customer_id', '?')
        bal = a.get('balance', 0)
        ltp = a.get('lifetime_points', 0)
        enrolled = (a.get('enrolled_at') or a.get('created_at', ''))[:10]
        print(f"  {cid:<30} {bal:>8} {ltp:>10} {enrolled:>12}")

    # Check how many have customer_id (needed to join with members)
    with_customer = sum(1 for a in all_accounts if a.get('customer_id'))
    print(f"\n  Accounts with customer_id: {with_customer}/{len(all_accounts)}")

# 3. Check rewards
print("\n" + "=" * 60)
print("3. RECENT REWARD REDEMPTIONS")
print("=" * 60)
try:
    body = {"limit": 10}
    data = api_post('/v2/loyalty/rewards/search', body)
    rewards = data.get('rewards', [])
    print(f"  Recent rewards: {len(rewards)}")
    for r in rewards[:5]:
        print(f"    {r.get('loyalty_account_id', '?')[:20]}... → {r.get('status')} ({r.get('points', 0)} pts) {r.get('created_at', '')[:10]}")
except Exception as e:
    print(f"  Could not fetch rewards: {e}")

print("\n✅ Done — loyalty data is accessible via Square API!")
