"""Add 12% superannuation to all staff_rates (except under-18 tiers), then recalculate all shifts."""
import os, sys, json, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()

SUPA_URL = os.getenv('SUPABASE_URL')
SUPA_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
SUPER_RATE = 0.12  # 12% superannuation

# Under-18 weekday rates (no super)
EXEMPT_WEEKDAY_RATES = {14.94, 15.18}  # under 16, under 17

def supa_get(path):
    req = urllib.request.Request(
        f"{SUPA_URL}/rest/v1/{path}",
        headers={'apikey': SUPA_KEY, 'Authorization': 'Bearer ' + SUPA_KEY}
    )
    return json.loads(urllib.request.urlopen(req).read())

def supa_upsert(table, data, conflict=""):
    headers = {
        'apikey': SUPA_KEY,
        'Authorization': 'Bearer ' + SUPA_KEY,
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates',
    }
    url = f"{SUPA_URL}/rest/v1/{table}"
    if conflict:
        url += f"?on_conflict={conflict}"
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method='POST')
    urllib.request.urlopen(req)

# ═══════════════════════════════════════════════════════════════
# STEP 1: Load all rates and identify who gets super
# ═══════════════════════════════════════════════════════════════
print("=" * 80)
print("STEP 1: Loading staff_rates and identifying super eligibility")
print("=" * 80)

rates = supa_get("staff_rates?select=id,team_member_id,staff_name,job_title,day_type,hourly_rate&order=staff_name,job_title,day_type")

# Build weekday rate per person+job to determine exemption
weekday_rates = {}
for r in rates:
    key = (r['team_member_id'], r['job_title'])
    if r['day_type'] == 'weekday':
        weekday_rates[key] = r['hourly_rate']

# Identify exempt staff
exempt_keys = set()
for key, wd_rate in weekday_rates.items():
    if wd_rate in EXEMPT_WEEKDAY_RATES:
        exempt_keys.add(key)

print(f"\n  Total rate entries: {len(rates)}")
print(f"  Exempt (under 18): {len(exempt_keys)} person×job combos")

# Show who's exempt
for key in sorted(exempt_keys):
    mid, job = key
    name = next(r['staff_name'] for r in rates if r['team_member_id'] == mid)
    wd = weekday_rates[key]
    print(f"    ❌ {name} ({job}) @ ${wd:.2f}/hr — NO super (under 18)")

# ═══════════════════════════════════════════════════════════════
# STEP 2: Calculate new rates with 12% super
# ═══════════════════════════════════════════════════════════════
print(f"\n{'=' * 80}")
print(f"STEP 2: Applying 12% super to eligible staff")
print(f"{'=' * 80}")

updates = []
for r in rates:
    key = (r['team_member_id'], r['job_title'])
    old_rate = r['hourly_rate'] or 0
    
    if key in exempt_keys:
        continue  # skip under-18
    
    if old_rate == 0:
        continue  # skip $0 rates (stubs)
    
    new_rate = round(old_rate * (1 + SUPER_RATE), 2)
    updates.append({
        "team_member_id": r['team_member_id'],
        "staff_name": r['staff_name'],
        "job_title": r['job_title'],
        "day_type": r['day_type'],
        "hourly_rate": new_rate,
    })

# Show preview grouped by person
shown = set()
for u in sorted(updates, key=lambda x: (x['staff_name'], x['job_title'], x['day_type'])):
    person_key = (u['staff_name'], u['job_title'])
    if person_key not in shown:
        shown.add(person_key)
        # Find old weekday rate
        old_wd = weekday_rates.get((u['team_member_id'], u['job_title']), 0)
        new_wd = round(old_wd * 1.12, 2)
        print(f"  ✅ {u['staff_name']:<25} {u['job_title']:<20} ${old_wd:.2f} → ${new_wd:.2f} (+12%)")

print(f"\n  Total entries to update: {len(updates)}")

# Apply updates
supa_upsert("staff_rates", updates, "team_member_id,job_title,day_type")
print(f"  ✅ Updated {len(updates)} rate entries in staff_rates")

# ═══════════════════════════════════════════════════════════════
# STEP 3: Show new rate tiers
# ═══════════════════════════════════════════════════════════════
print(f"\n{'=' * 80}")
print(f"STEP 3: New rate table (with super)")
print(f"{'=' * 80}")

new_rates = supa_get("staff_rates?select=staff_name,job_title,day_type,hourly_rate,team_member_id&order=staff_name,job_title,day_type")

pivot = {}
for r in new_rates:
    key = (r['staff_name'], r['job_title'])
    if key not in pivot:
        pivot[key] = {'mid': r['team_member_id']}
    pivot[key][r['day_type']] = r['hourly_rate']

# Group into tiers
tiers = {}
for (name, job), days in pivot.items():
    wd = days.get('weekday', 0) or 0
    sat = days.get('saturday', 0) or 0
    sun = days.get('sunday', 0) or 0
    ph = days.get('public_holiday', 0) or 0
    tier_key = (wd, sat, sun, ph)
    if tier_key not in tiers:
        tiers[tier_key] = []
    tiers[tier_key].append(name)

print(f"\n  {'Tier':<18} {'Weekday':>8} {'Saturday':>10} {'Sunday':>8} {'Pub Hol':>10}")
print(f"  {'-'*60}")
for tier_key in sorted(tiers.keys(), key=lambda x: -x[0]):
    wd, sat, sun, ph = tier_key
    staff = sorted(set(tiers[tier_key]))
    staff_str = ", ".join(staff[:4])
    if len(staff) > 4:
        staff_str += f" (+{len(staff)-4} more)"
    print(f"  ${wd:>6.2f}    ${sat:>7.2f}  ${sun:>6.2f}   ${ph:>7.2f}   {staff_str}")

# ═══════════════════════════════════════════════════════════════
# STEP 4: Recalculate ALL past shifts
# ═══════════════════════════════════════════════════════════════
print(f"\n{'=' * 80}")
print(f"STEP 4: Recalculating all past shift costs")
print(f"{'=' * 80}")

# Build new rate lookup: (team_member_id, job_title, day_type) → rate
rate_lookup = {}
for r in new_rates:
    rate_lookup[(r['team_member_id'], r['job_title'], r['day_type'])] = r['hourly_rate']

# NSW Public Holidays 2025-2026
NSW_HOLIDAYS = {
    # 2025
    '2025-01-01', '2025-01-27', '2025-04-18', '2025-04-19', '2025-04-21',
    '2025-04-25', '2025-06-09', '2025-08-04', '2025-10-06', '2025-12-25', '2025-12-26',
    # 2026
    '2026-01-01', '2026-01-26', '2026-04-03', '2026-04-04', '2026-04-06',
    '2026-04-25', '2026-06-08', '2026-08-03', '2026-10-05', '2026-12-25', '2026-12-26',
}

from datetime import date

def get_day_type(d):
    ds = str(d)
    if ds in NSW_HOLIDAYS:
        return 'public_holiday'
    wd = d.weekday()
    if wd == 5:
        return 'saturday'
    if wd == 6:
        return 'sunday'
    return 'weekday'

def get_rate(mid, job_title, day_type):
    """Look up rate, handling _Bar/_Retail split suffixes."""
    base_job = job_title.replace('_Bar', '').replace('_Retail', '')
    rate = rate_lookup.get((mid, base_job, day_type), 0)
    if rate == 0 and day_type != 'weekday':
        rate = rate_lookup.get((mid, base_job, 'weekday'), 0)
    return rate

# Fetch ALL shifts
all_shifts = supa_get("staff_shifts?select=id,team_member_id,job_title,shift_date,hourly_rate&order=shift_date")
print(f"  Total shifts in database: {len(all_shifts)}")

updates_shifts = []
for s in all_shifts:
    shift_date = date.fromisoformat(s['shift_date'])
    day_type = get_day_type(shift_date)
    new_rate = get_rate(s['team_member_id'], s['job_title'], day_type)
    old_rate = s['hourly_rate'] or 0
    
    if abs(new_rate - old_rate) > 0.001 and new_rate > 0:
        updates_shifts.append({
            "id": s['id'],
            "hourly_rate": new_rate,
        })

print(f"  Shifts needing rate update: {len(updates_shifts)}")

# Update in batches
batch_size = 50
for i in range(0, len(updates_shifts), batch_size):
    batch = updates_shifts[i:i+batch_size]
    for u in batch:
        headers = {
            'apikey': SUPA_KEY,
            'Authorization': 'Bearer ' + SUPA_KEY,
            'Content-Type': 'application/json',
        }
        req = urllib.request.Request(
            f"{SUPA_URL}/rest/v1/staff_shifts?id=eq.{u['id']}",
            data=json.dumps({"hourly_rate": u['hourly_rate']}).encode(),
            headers=headers,
            method='PATCH'
        )
        urllib.request.urlopen(req)
    print(f"  Updated batch {i//batch_size + 1} ({len(batch)} shifts)")

print(f"\n  ✅ Recalculated {len(updates_shifts)} shifts with new super-inclusive rates")
print(f"\n{'=' * 80}")
print(f"DONE")
print(f"{'=' * 80}")
