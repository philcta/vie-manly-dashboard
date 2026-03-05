# Labour Hours Tracking — Final Plan

## Core Rule

> **Schedule is the default. Actual clock-in/out overrides ONLY when both exist.**

| Scenario | Source | effective_hours |
|----------|--------|-----------------|
| Staff scheduled, no clock-in | `schedule` | Scheduled hours |
| Staff scheduled, clock-in but no clock-out (forgot) | `schedule` | Scheduled hours |
| Staff scheduled, clock-in AND clock-out | `actual` | Actual hours |
| Staff NOT scheduled, but clocked in+out | `actual` | Actual hours |

---

## Business Side Mapping (per shift job title)

| Job Title | Side (DB) | Side (UI) |
|-----------|-----------|-----------|
| **Kitchen** | `Bar` | Cafe |
| **Barrista** | `Bar` | Cafe |
| **Retail Assistant** | `Retail` | Retail |
| **Manager** | `Retail` | Retail |
| **Owner** | `Retail` | Retail |
| **Expansion/Meeting** | `Overhead` | Overhead |

> Determined per shift, not per person. Multi-role staff (e.g., Maya: Kitchen + Retail) are allocated by which role they work that day.

---

## Data Sources

| API | Endpoint | Purpose |
|-----|----------|---------|
| Square Scheduling | `POST /v2/labor/scheduled-shifts/search` | Roster (default hours) |
| Square Labor | `POST /v2/labor/shifts/search` | Clock-in/out (override) |
| Square Team Members | `POST /v2/team-members/search` | Names, job titles, rates |

---

## Supabase Table: `staff_shifts`

```sql
staff_shifts (
  shift_date          DATE         -- e.g., 2026-03-03
  team_member_id      TEXT         -- Square team member ID
  staff_name          TEXT         -- e.g., "Holly Selves"
  job_title           TEXT         -- e.g., "Kitchen"
  business_side       TEXT         -- 'Bar', 'Retail', or 'Overhead'
  scheduled_start/end TIMESTAMPTZ  -- from Square Scheduling API
  scheduled_hours     NUMERIC      -- calculated from schedule
  actual_start/end    TIMESTAMPTZ  -- from Square Labor API (clock-in/out)
  actual_hours        NUMERIC      -- calculated from actuals (null if no clock-out)
  effective_hours     NUMERIC      -- = actual if both exist, else scheduled
  source              TEXT         -- 'schedule' or 'actual'
  hourly_rate         NUMERIC      -- $/hr
  labour_cost         NUMERIC      -- GENERATED: effective_hours × hourly_rate
  UNIQUE(shift_date, team_member_id, job_title)
)
```

---

## Sync Script

```bash
# Sync today
python scripts/sync_shifts.py

# Sync last 7 days
python scripts/sync_shifts.py --days 7

# Backfill last 30 days
python scripts/sync_shifts.py --backfill 30
```

---

## ✅ Current Data (7 days synced)

| Date | Shifts | Schedule | Actual | ☕ Cafe | 🛍️ Retail | 💰 Cost |
|------|--------|----------|--------|--------|---------|---------|
| Tue 25 Feb | 9 | 8 | 1 | 21.0h | 31.8h | $1,601 |
| Wed 26 Feb | 8 | 8 | 0 | 11.8h | 25.0h | $844 |
| Thu 27 Feb | 7 | 7 | 0 | 20.8h | 23.8h | $1,191 |
| Fri 28 Feb | 7 | 7 | 0 | 6.8h | 28.8h | $612 |
| Sat 01 Mar | 7 | 6 | 1 | 6.8h | 33.0h | $1,044 |
| Sun 02 Mar | 9 | 8 | 1 | 19.8h | 31.3h | $1,346 |
| Mon 03 Mar | 7 | 6 | 1 | 7.1h | 31.5h | $900 |

**54 total shifts, avg $1,077/day labour cost**
