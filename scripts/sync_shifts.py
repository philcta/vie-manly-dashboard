"""
Sync staff shifts to Supabase.

Logic:
  1. Pull SCHEDULED shifts from Square Scheduling API (default)
  2. Pull ACTUAL shifts from Square Labor API (clock in/out)
  3. For each scheduled shift:
     - If a matching actual shift exists with BOTH clock-in AND clock-out → use actual hours
     - Otherwise → use scheduled hours
  4. Determine day type (weekday/saturday/sunday/public_holiday)
  5. Look up hourly rate from Supabase staff_rates table (per person × day type)
     ⚠️ Rates come ONLY from staff_rates — NOT from Square's hourly_rate field
     (Square rates are unreliable: some staff have $0 rates in their wage_setting)
  6. Handle Barrista 80/20 split (Cafe/Retail)
  7. Historical: Jenny Kirkpatrick was "Retail Assistant" but filled Barrista role → 80/20 split
  8. Alert when new staff appear without rates (auto-create $0 stubs for manual setup)
  9. Upsert into Supabase staff_shifts table

Usage: python scripts/sync_shifts.py [--days N] [--backfill N]
"""
import sys, os, json, urllib.request, argparse
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()

SQUARE_TOKEN = os.getenv('SQUARE_ACCESS_TOKEN')
SUPA_URL = os.getenv('SUPABASE_URL')
SUPA_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

sq_headers = {
    'Authorization': 'Bearer ' + SQUARE_TOKEN,
    'Content-Type': 'application/json',
    'Square-Version': '2025-01-23',
}
supa_headers = {
    'apikey': SUPA_KEY,
    'Authorization': 'Bearer ' + SUPA_KEY,
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates',
}
base = 'https://connect.squareup.com'
SYD_TZ = ZoneInfo('Australia/Sydney')  # Handles DST automatically (AEDT=UTC+11, AEST=UTC+10)

# ── Job title → business side mapping ──
CAFE_TITLES = {'Kitchen'}  # 100% Cafe
SPLIT_TITLES = {'Barrista': {'Bar': 0.80, 'Retail': 0.20}}
OVERHEAD_TITLES = {'Expansion/Meeting'}

# Full-time employees exempt from 30-min break deduction
# (they take paid breaks as part of their full-time arrangement)
BREAK_EXEMPT_TEAM_IDS = set()  # populated at runtime from team member lookup
BREAK_EXEMPT_NAMES = {'Ana Flores'}  # full-time Manager

# Break deduction parameters
BREAK_THRESHOLD = 6.25  # 6h15m — shifts longer than this get a break deduction
BREAK_DEDUCTION = 0.5   # 30 minutes

# Historical: Jenny Kirkpatrick (first Retail Assistant alphabetically who
# filled the Barrista role before it was created on 2026-03-03)
BARRISTA_CREATED_DATE = date(2026, 3, 3)
HISTORICAL_BARRISTA_ID = None  # will be resolved at runtime

# ── NSW Public Holidays ──
NSW_HOLIDAYS = {
    date(2025, 1, 1), date(2025, 1, 27), date(2025, 4, 18), date(2025, 4, 19),
    date(2025, 4, 21), date(2025, 4, 25), date(2025, 6, 9), date(2025, 8, 4),
    date(2025, 10, 6), date(2025, 12, 25), date(2025, 12, 26),
    date(2026, 1, 1), date(2026, 1, 26), date(2026, 4, 3), date(2026, 4, 4),
    date(2026, 4, 6), date(2026, 4, 25), date(2026, 6, 8), date(2026, 8, 3),
    date(2026, 10, 5), date(2026, 12, 25), date(2026, 12, 26), date(2026, 12, 28),
}

def get_day_type(d):
    if d in NSW_HOLIDAYS:
        return 'public_holiday'
    if d.weekday() == 5:
        return 'saturday'
    if d.weekday() == 6:
        return 'sunday'
    return 'weekday'

def get_side(job_title):
    if job_title in CAFE_TITLES:
        return 'Bar'
    if job_title in OVERHEAD_TITLES:
        return 'Overhead'
    return 'Retail'

def is_split_role(job_title):
    return job_title in SPLIT_TITLES

def get_split(job_title):
    return SPLIT_TITLES.get(job_title, {})

# ── Build lookups ──
def build_lookups():
    all_members = []
    cursor = None
    while True:
        body = {"limit": 200}
        if cursor:
            body["cursor"] = cursor
        req = urllib.request.Request(
            base + '/v2/team-members/search',
            data=json.dumps(body).encode(), headers=sq_headers, method='POST'
        )
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        all_members.extend(data.get('team_members', []))
        cursor = data.get('cursor')
        if not cursor:
            break

    names = {}
    jobs = {}
    for m in all_members:
        mid = m['id']
        names[mid] = f"{m.get('given_name', '')} {m.get('family_name', '')}".strip()
        wage = m.get('wage_setting', {})
        for a in wage.get('job_assignments', []):
            jid = a.get('job_id', '')
            jobs[jid] = a.get('job_title', '').strip()

    # Find Jenny Kirkpatrick's team_member_id for historical Barrista proxy
    global HISTORICAL_BARRISTA_ID
    for mid, name in names.items():
        if 'Jenny Kirkpatrick' in name:
            HISTORICAL_BARRISTA_ID = mid
            break

    # Build break-exempt IDs
    global BREAK_EXEMPT_TEAM_IDS
    BREAK_EXEMPT_TEAM_IDS = {mid for mid, name in names.items() if name in BREAK_EXEMPT_NAMES}
    if BREAK_EXEMPT_TEAM_IDS:
        print(f"  Break-exempt staff: {', '.join(names[m] for m in BREAK_EXEMPT_TEAM_IDS)}")

    return names, jobs

# ── Load rates from Supabase staff_rates table ──
# ⚠️ This is the ONLY source of truth for hourly rates.
# Square's hourly_rate field is NOT used (unreliable — some staff have $0).
def load_rates():
    """Returns dict: (team_member_id, job_title, day_type) → hourly_rate"""
    req = urllib.request.Request(
        f"{SUPA_URL}/rest/v1/staff_rates?select=team_member_id,staff_name,job_title,day_type,hourly_rate,is_teen",
        headers={
            'apikey': SUPA_KEY,
            'Authorization': 'Bearer ' + SUPA_KEY,
        }
    )
    resp = urllib.request.urlopen(req)
    rows = json.loads(resp.read())
    rates = {}
    teen_ids = set()
    for r in rows:
        key = (r['team_member_id'], r['job_title'], r['day_type'])
        rates[key] = float(r['hourly_rate'])
        if r.get('is_teen'):
            teen_ids.add(r['team_member_id'])
    return rates, teen_ids

def get_rate(rates, mid, job_title, day_type):
    """Look up rate from staff_rates, fallback to weekday if specific day type not set."""
    rate = rates.get((mid, job_title, day_type), 0)
    if rate == 0 and day_type != 'weekday':
        rate = rates.get((mid, job_title, 'weekday'), 0)
    return rate

# ── Track and alert on missing rates ──
_missing_rates = set()  # (name, job_title) tuples for alerting

def check_and_alert_rate(rates, mid, job_title, day_type, name):
    """Check rate and record alert if missing. Returns the rate (may be 0)."""
    rate = get_rate(rates, mid, job_title, day_type)
    if rate == 0:
        _missing_rates.add((name, job_title, mid))
    return rate

def create_rate_stubs(missing_set, names):
    """Auto-create $0 rate stubs in staff_rates for new staff so they appear in dashboard."""
    if not missing_set:
        return
    DAY_TYPES = ['weekday', 'saturday', 'sunday', 'public_holiday']
    stubs = []
    for name, job_title, mid in missing_set:
        if not name or not mid:  # skip ghost entries with no name/id
            continue
        for dt in DAY_TYPES:
            stubs.append({
                "team_member_id": mid,
                "staff_name": name,
                "job_title": job_title,
                "day_type": dt,
                "hourly_rate": 0,
            })
    if stubs:
        stub_headers = {
            'apikey': SUPA_KEY,
            'Authorization': 'Bearer ' + SUPA_KEY,
            'Content-Type': 'application/json',
            'Prefer': 'resolution=ignore-duplicates',  # don't overwrite existing
        }
        req = urllib.request.Request(
            f"{SUPA_URL}/rest/v1/staff_rates?on_conflict=team_member_id,job_title,day_type",
            data=json.dumps(stubs).encode(),
            headers=stub_headers,
            method='POST'
        )
        try:
            urllib.request.urlopen(req)
        except Exception as e:
            print(f"  ⚠️ Could not create rate stubs: {e}")

# ── Fetch scheduled shifts ──
def fetch_scheduled(start_dt, end_dt):
    all_shifts = []
    cursor = None
    start_utc = start_dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    end_utc = end_dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    while True:
        body = {"query": {"filter": {"start": {"start_at": start_utc, "end_at": end_utc}}}, "limit": 50}
        if cursor:
            body["cursor"] = cursor
        req = urllib.request.Request(
            base + '/v2/labor/scheduled-shifts/search',
            data=json.dumps(body).encode(), headers=sq_headers, method='POST'
        )
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        all_shifts.extend(data.get('scheduled_shifts', []))
        cursor = data.get('cursor')
        if not cursor:
            break
    return all_shifts

# ── Fetch actual shifts (clock in/out) ──
def fetch_actual(start_dt):
    all_shifts = []
    cursor = None
    start_utc = start_dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    while True:
        body = {"query": {"filter": {"start": {"start_at": start_utc}}}, "limit": 200}
        if cursor:
            body["cursor"] = cursor
        req = urllib.request.Request(
            base + '/v2/labor/shifts/search',
            data=json.dumps(body).encode(), headers=sq_headers, method='POST'
        )
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        all_shifts.extend(data.get('shifts', []))
        cursor = data.get('cursor')
        if not cursor:
            break
    return all_shifts

# ── Main sync for a single day ──
def sync_day(target_date, names, jobs, rates, teen_ids=None):
    if teen_ids is None:
        teen_ids = set()
    syd_tz = SYD_TZ
    day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=syd_tz)
    day_end = day_start + timedelta(days=1)
    day_type = get_day_type(target_date)

    scheduled = fetch_scheduled(day_start, day_end)
    actual = fetch_actual(day_start)

    # Filter actuals to this day
    actual_today = []
    for s in actual:
        start_str = s.get('start_at', '')
        if start_str:
            st = datetime.fromisoformat(start_str.replace('Z', '+00:00')).astimezone(syd_tz)
            if st.date() == target_date:
                actual_today.append(s)

    # Index actuals by (team_member_id, job_title)
    actual_map = {}
    for s in actual_today:
        mid = s.get('team_member_id', '')
        wage = s.get('wage', {})
        job_title = wage.get('title', '').strip()
        actual_map[(mid, job_title)] = s

    rows = []
    historical_barrista_applied = False

    for sched in scheduled:
        details = sched.get('published_shift_details') or sched.get('draft_shift_details') or {}
        mid = details.get('team_member_id', '')
        job_id = details.get('job_id', '')
        job_title = jobs.get(job_id, '?')
        name = names.get(mid, mid[:15])

        sched_start_str = details.get('start_at', '')
        sched_end_str = details.get('end_at', '')
        sched_start = datetime.fromisoformat(sched_start_str.replace('Z', '+00:00')) if sched_start_str else None
        sched_end = datetime.fromisoformat(sched_end_str.replace('Z', '+00:00')) if sched_end_str else None
        sched_hours = round((sched_end - sched_start).total_seconds() / 3600, 2) if sched_start and sched_end else 0

        # Match with actual
        actual_shift = actual_map.pop((mid, job_title), None)

        if actual_shift and actual_shift.get('status') == 'CLOSED' and actual_shift.get('end_at'):
            act_start = datetime.fromisoformat(actual_shift['start_at'].replace('Z', '+00:00'))
            act_end = datetime.fromisoformat(actual_shift['end_at'].replace('Z', '+00:00'))
            act_hours = round((act_end - act_start).total_seconds() / 3600, 2)
            source = 'actual'
            eff_hours = act_hours
        else:
            act_start = None
            act_end = None
            act_hours = None
            source = 'schedule'
            eff_hours = sched_hours

        # ── 30-min auto-break for shifts > 6h15 (6.25h) ──
        # Applied to the FULL shift duration BEFORE any role split.
        # When an employee works > 6h15 in a single shift, they take
        # a 30-minute unpaid break automatically.
        break_deducted = False
        if eff_hours > BREAK_THRESHOLD and mid not in BREAK_EXEMPT_TEAM_IDS:
            eff_hours = round(eff_hours - BREAK_DEDUCTION, 2)
            break_deducted = True

        # Determine if this is a split role
        should_split = is_split_role(job_title)

        # Historical Barrista proxy: before Barrista was created,
        # Jenny Kirkpatrick worked as "Retail Assistant" but filled the Barrista role.
        # Apply 80/20 split to her Retail Assistant shifts before 2026-03-03.
        if (not should_split
            and job_title == 'Retail Assistant'
            and mid == HISTORICAL_BARRISTA_ID
            and target_date < BARRISTA_CREATED_DATE
            and not historical_barrista_applied):
            should_split = True
            historical_barrista_applied = True  # only one per day

        if should_split:
            split = get_split(job_title) if is_split_role(job_title) else {'Bar': 0.80, 'Retail': 0.20}
            for side, pct in split.items():
                suffix = f"_{side}"
                rate_job = job_title  # look up rate under original job title
                rate = check_and_alert_rate(rates, mid, rate_job, day_type, name)
                split_eff = round(eff_hours * pct, 2)
                cost = round(split_eff * rate, 2)

                rows.append({
                    "shift_date": str(target_date),
                    "team_member_id": mid,
                    "staff_name": name,
                    "job_title": f"{job_title}{suffix}",
                    "business_side": side,
                    "scheduled_start": sched_start.isoformat() if sched_start else None,
                    "scheduled_end": sched_end.isoformat() if sched_end else None,
                    "scheduled_hours": round(sched_hours * pct, 2),
                    "actual_start": act_start.isoformat() if act_start else None,
                    "actual_end": act_end.isoformat() if act_end else None,
                    "actual_hours": round(act_hours * pct, 2) if act_hours else None,
                    "effective_hours": split_eff,
                    "source": source,
                    "hourly_rate": rate,
                    "break_deducted": break_deducted,
                    "no_super_earning": round(cost / 1.12, 2),
                    "is_teen": mid in teen_ids,
                })
        else:
            side = get_side(job_title)
            rate = check_and_alert_rate(rates, mid, job_title, day_type, name)
            cost = round(eff_hours * rate, 2)

            rows.append({
                "shift_date": str(target_date),
                "team_member_id": mid,
                "staff_name": name,
                "job_title": job_title,
                "business_side": side,
                "scheduled_start": sched_start.isoformat() if sched_start else None,
                "scheduled_end": sched_end.isoformat() if sched_end else None,
                "scheduled_hours": sched_hours,
                "actual_start": act_start.isoformat() if act_start else None,
                "actual_end": act_end.isoformat() if act_end else None,
                "actual_hours": act_hours,
                "effective_hours": eff_hours,
                "source": source,
                "hourly_rate": rate,
                "break_deducted": break_deducted,
                "no_super_earning": round(cost / 1.12, 2),
                "is_teen": mid in teen_ids,
            })

    # Unscheduled clock-ins (actuals not matched to schedule)
    for key, s in actual_map.items():
        if s.get('status') == 'CLOSED' and s.get('end_at'):
            mid, job_title_raw = key
            wage = s.get('wage', {})
            job_title = wage.get('title', job_title_raw).strip()
            side = get_side(job_title)
            name = names.get(mid, mid[:15])
            act_start = datetime.fromisoformat(s['start_at'].replace('Z', '+00:00'))
            act_end = datetime.fromisoformat(s['end_at'].replace('Z', '+00:00'))
            act_hours = round((act_end - act_start).total_seconds() / 3600, 2)
            rate = check_and_alert_rate(rates, mid, job_title, day_type, name)

            # Apply break deduction for unscheduled actuals too
            break_ded = False
            eff_h = act_hours
            if eff_h > BREAK_THRESHOLD and mid not in BREAK_EXEMPT_TEAM_IDS:
                eff_h = round(eff_h - BREAK_DEDUCTION, 2)
                break_ded = True
            cost = round(eff_h * rate, 2)

            rows.append({
                "shift_date": str(target_date),
                "team_member_id": mid,
                "staff_name": name,
                "job_title": job_title,
                "business_side": side,
                "scheduled_start": None,
                "scheduled_end": None,
                "scheduled_hours": None,
                "actual_start": act_start.isoformat(),
                "actual_end": act_end.isoformat(),
                "actual_hours": act_hours,
                "effective_hours": eff_h,
                "source": "actual",
                "hourly_rate": rate,
                "break_deducted": break_ded,
                "no_super_earning": round(cost / 1.12, 2),
                "is_teen": mid in teen_ids,
            })

    return rows

def upsert_to_supabase(rows):
    if not rows:
        return 0
    req = urllib.request.Request(
        f"{SUPA_URL}/rest/v1/staff_shifts?on_conflict=shift_date,team_member_id,job_title,scheduled_start",
        data=json.dumps(rows).encode(),
        headers=supa_headers,
        method='POST'
    )
    try:
        urllib.request.urlopen(req)
        return len(rows)
    except urllib.error.HTTPError as e:
        print(f"  ❌ Upsert error: {e.read().decode()[:300]}")
        return 0

# ── CLI ──
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=1, help='Sync last N days')
    parser.add_argument('--backfill', type=int, default=0, help='Backfill N days into the past')
    args = parser.parse_args()

    print("📥 Building lookups...")
    names, jobs = build_lookups()
    print(f"  {len(names)} staff, {len(jobs)} job titles")
    print(f"  Historical Barrista proxy: {names.get(HISTORICAL_BARRISTA_ID, '?')} ({HISTORICAL_BARRISTA_ID})")

    print("📥 Loading rates from staff_rates table...")
    rates, teen_ids = load_rates()
    print(f"  {len(rates)} rate entries loaded, {len(teen_ids)} teen IDs")

    syd_tz = SYD_TZ
    today = datetime.now(syd_tz).date()

    if args.backfill > 0:
        start_date = today - timedelta(days=args.backfill)
        days_to_sync = args.backfill + 1
    else:
        start_date = today - timedelta(days=args.days - 1)
        days_to_sync = args.days

    total = 0
    _missing_rates.clear()  # reset per run

    for i in range(days_to_sync):
        d = start_date + timedelta(days=i)
        rows = sync_day(d, names, jobs, rates, teen_ids)

        day_type = get_day_type(d)
        schedule_count = sum(1 for r in rows if r['source'] == 'schedule')
        actual_count = sum(1 for r in rows if r['source'] == 'actual')
        cafe_h = sum(r['effective_hours'] for r in rows if r['business_side'] == 'Bar')
        retail_h = sum(r['effective_hours'] for r in rows if r['business_side'] == 'Retail')
        total_cost = sum(r['effective_hours'] * r['hourly_rate'] for r in rows)
        break_count = sum(1 for r in rows if r.get('break_deducted'))

        upserted = upsert_to_supabase(rows)
        total += upserted

        has_split = any('_Bar' in r['job_title'] or '_Retail' in r['job_title'] for r in rows)
        split_flag = ' 🔀' if has_split else ''
        break_flag = f' ⏸️{break_count}brk' if break_count else ''

        # Flag shifts with $0 rates for this day
        zero_rate = [r for r in rows if r['hourly_rate'] == 0]
        rate_flag = f' ⚠️{len(zero_rate)} missing rates' if zero_rate else ''

        emoji = '✅' if upserted > 0 else '⚠️'
        print(f"  {emoji} {d.strftime('%a %d %b')} [{day_type[:3]}]: {len(rows)} shifts "
              f"(s:{schedule_count} a:{actual_count}) "
              f"☕{cafe_h:.1f}h 🛍️{retail_h:.1f}h "
              f"💰${total_cost:.0f}{split_flag}{break_flag}{rate_flag}")

    # ── Missing rate alerts ──
    if _missing_rates:
        print(f"\n🚨 MISSING RATES — {len(_missing_rates)} staff×job combos have $0 rate:")
        for name, job_title, mid in sorted(_missing_rates):
            print(f"  ⚠️ {name} ({job_title}) — needs rate setup in Staff dashboard")
        # Auto-create $0 stubs so they appear in dashboard for editing
        create_rate_stubs(_missing_rates, names)
        print(f"  → Created $0 stub entries in staff_rates (edit via Staff dashboard)")

    print(f"\n✅ Done. {total} total rows synced to Supabase.")
