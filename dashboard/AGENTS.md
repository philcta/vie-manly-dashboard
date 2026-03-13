# AGENTS.md — VIE. MANLY Dashboard Project

> **This file is the project brain. Read it first in every new conversation.**
> Last updated: 2026-03-13

## Identity

- **Client**: VIE Market (organic grocery + cafe), Shop 16/17, 25 Wentworth St, Manly NSW 2095
- **Consultant**: Philippe Antoine — Your AI Business Consultant, 5 Galway Ave, Killarney Heights NSW 2087
- **Project**: Real-time business intelligence dashboard — cloud-hosted at Vercel
- **Store opened**: August 20, 2025
- **POS System**: Square (API integrated for hourly data sync)

## Stack

- **Framework**: Next.js 16 (App Router) + TypeScript
- **Styling**: Tailwind CSS v4 + custom design tokens in `globals.css`
- **Database**: Supabase PostgreSQL (project ID: `heavnfayolxrgmxkkrvr`)
- **Hosting**: Vercel (auto-deploy from `master` branch)
- **Charts**: Recharts | **Animation**: Framer Motion | **UI Primitives**: Radix UI
- **Repo**: `github.com/philcta/vie-manly-dashboard` branch `master`

## Key Files to Read First

| File | What it contains |
|---|---|
| `docs/architecture.md` | Full project structure, Supabase tables/RPCs, formulas, design system, deployment |
| `docs/formulas_reference.md` | Every business calculation (margins, labour, profit, member metrics) |
| `docs/business_improvement_plan.md` | Data-driven business analysis with 6 prioritised actions |
| `app/page.tsx` | Overview dashboard — 12 KPI cards, charts, comparison logic |
| `app/members/page.tsx` | Members page — loyalty, spending patterns, CSV export |
| `app/inventory/page.tsx` | Inventory page — stock intelligence, alerts, CSV export |
| `app/staff/page.tsx` | Staff page — labour costs, shift breakdown |
| `components/sortable-table.tsx` | Shared table component with debounced search + virtual scroll |
| `lib/queries/overview.ts` | All Supabase queries for the overview page |
| `lib/dates.ts` | Period/comparison date range resolution |

## Business Concepts

### Two Sides of the Business
- **Cafe** (mapped from "Bar" in `staff_shifts.business_side`): Coffee, smoothies, chia bowls, sweet treats — ~70% margin, ~30% of sales
- **Retail** (grocery shelves): Organic groceries — ~41% margin, ~70% of sales
- Category → Side mapping is in `category_mappings` table (maintained via Settings page)

### Key Metrics
- **Avg Profit Margin** = Weighted average of per-category inventory margins, weighted by each category's actual sales in the selected period. Uses `inventory_margins` table.
- **Real Profit Margin** = `effectiveMargin - labourRatio` (weighted margin minus labour as % of sales)
- **Real Profit $** = `Net Sales × (effectiveMargin / 100) - Labour Cost`
- **Labour is split** Cafe/Retail using `staff_shifts.business_side` (Bar → Cafe, Retail → Retail, Overhead → Cafe)
- **Barista split**: 80/20 rule — barista labour is 80% Cafe, 20% Retail

### Data Pipeline — `scheduled_sync.py` (every 2 hours)

The automated sync runs 6 phases in sequence:

| Phase | Script/Module | What it does |
|---|---|---|
| 1. Smart Backfill | `scripts/smart_backfill.py` | Detects & fills missing date gaps (last 14 days) |
| 2. Latest Sync | `services/square_sync.py` | Pulls last 4h of transactions + inventory + customers from Square API |
| 3. Stock Intelligence | `scripts/sync_inventory_intelligence.py` | Calculates sales velocity, reorder alerts (90 days) |
| 4. Spending Patterns | Supabase RPC | Refreshes `mv_member_spending_patterns` materialized view |
| 5. Loyalty Sync | `scripts/sync_loyalty.py` + `sync_loyalty_events.py` | Pulls all loyalty balances (2,836 accounts) + events (25K+) from Square |
| 6. Member Stats | `scripts/backfill_member_analytics.py` | Recalculates `member_daily_stats` for ALL members from transactions |

**Key derived tables**:
- `transactions` → aggregated into `daily_store_stats` (member/non-member split) and `daily_item_summary`
- `transactions` → `member_daily_stats` (cumulative visits, spend, 30d trends per member)
- `staff_shifts` populated from Square Team API
- `inventory` snapshots from Square, enriched into `inventory_intelligence`
- `member_loyalty` synced from Square Loyalty API (balances + lifetime points)
- `loyalty_events` synced from Square Loyalty Events API (full ledger: accumulate, redeem, create_reward)

## Known Gotchas & Past Bugs

1. **`business_side` values**: Staff shifts use "Bar" (not "Cafe"), "Retail", "Overhead". Code maps Bar+Overhead → Cafe.
2. **Function overloading**: `get_category_daily` had a duplicate `(text, text)` overload causing PostgREST 300 errors. Fixed by dropping old overload.
3. **Duplicate transactions (FIXED 2026-03-13)**: Root cause was 3 scripts generating `row_key` in incompatible formats: `rebuild_from_square.py` used `{order_id}-LI-{idx}`, `smart_backfill.py` used plain concatenation, `square_sync.py` used MD5 hash. All three now use the deterministic `{order_id}-LI-{idx}` format. Also fixed `smart_backfill.py` to use `closed_at` instead of `created_at` for consistency.
4. **`is_closed` flag**: `daily_store_stats.is_closed = true` marks pre-opening dates and closed days. ALL RPCs and queries must filter this.
5. **Timezone**: All dates are Sydney local time (AEST/AEDT). Square API returns UTC — conversion happens at ingest.
6. **Financial Year**: Australian FY is July 1 – June 30.
7. **`member_daily_stats` must be recalculated**: This table is NOT incrementally updated — it requires a full rebuild from `transactions` (Phase 6 of scheduled_sync). Before 2026-03-12, it was only populated by manual one-off backfills. Gap incident: 228 members had stale data for 4 days (Mar 9–12). Now automated.
8. **`loyalty_events` upsert needs `on_conflict=event_id`**: Without this, re-syncing causes duplicate key errors (23505). Fixed 2026-03-12.
9. **Staff pay period dates**: `getPayPeriod()` in `lib/queries/staff.ts` must use UTC-only arithmetic (`Date.UTC()`, `getUTCDate()` etc). Using `toISOString()` or local-time ms arithmetic causes dates to shift by 1 day in Australian timezone (UTC+11). Also vulnerable to DST transitions if using `86400000ms` with local time.
10. **RLS enabled on all tables (2026-03-13)**: Row Level Security is now active. Dashboard (anon key) has read-only access to most tables. Write access is only granted on `staff_rates` (rate editor) and `category_mappings` (side assignment). Python scripts use `service_role` key which bypasses RLS. SQL policies are in `sql/enable_rls.sql`.
11. **Old Square account customer IDs**: The store had a previous owner with a different Square account. ~1,664 old customer IDs exist in transactions but have no matching `member_daily_stats`. These are reconciled via `customer_id_mapping` table (231 mappings). The old IDs are expected — not a bug.

## Performance Optimizations Done

1. **Consolidated RPCs**: `get_inventory_full()` and `get_members_full()` replace 4-7 separate API calls each
2. **Virtual scroll**: `SortableTable` renders only visible rows (~20) instead of all 800+
3. **Debounced search**: 150ms debounce on search input prevents re-render storms
4. **Pre-built search extractors**: Avoid `columns.find()` per row per key on each filter pass
5. **Composite indexes**: `idx_dis_item_date`, `idx_inv_source_product`
6. **Materialized views**: `mv_member_spending_patterns` for expensive spending pattern queries

## Session Log (Most Recent First)

### 2026-03-13 - Duplicate Transaction Fix + Staff Pay Period + RLS Security
- **Root cause of duplicate transactions identified and fixed**:
  - 3 scripts (`rebuild_from_square.py`, `smart_backfill.py`, `square_sync.py`) each generated `row_key` in different formats
  - When `scheduled_sync.py` ran Phase 1 + Phase 2, same transactions got inserted twice with different keys
  - March 11: ~1.3x inflation ($6,255 dashboard vs $4,832 Square). March 12: ~2x ($10,625 vs $5,376)
  - Fix: Aligned all 3 scripts to use `{order_id}-LI-{idx}` format. Also fixed `smart_backfill.py` to use `closed_at` instead of `created_at`
- **Cleaned duplicate data**: Deleted 572 excess rows (1,575 → 1,003) for March 11-13, recalculated daily summaries
- **Staff pay period off by 1 day**: `getPayPeriod()` used `toISOString()` which converts to UTC before formatting — in UTC+11, this shifts dates back 1 day. Fixed with UTC-only arithmetic (`Date.UTC()` + `getUTC*()` methods) to be DST-proof
- **Enabled Row Level Security**: All Supabase tables now have RLS. Anon key = read-only (except `staff_rates` and `category_mappings`). Script saved as `sql/enable_rls.sql`
- Pushed commits: `02c46b5` (dup fix), `1424262` (pay period), `d9ea50b` (UTC DST), `7157d77` (RLS)

### 2026-03-12 (evening) — Member Data Gap Fix + Automated Sync Pipeline
- **Investigated missing member visits**: Grace Loke's Mar 10 visit was in `transactions` but missing from `member_daily_stats` and `loyalty_events`
- **Root cause**: `member_daily_stats` was never part of the automated sync — only populated by manual one-off backfills
- **Impact**: 228 members had stale visit/spend data for 4 days (Mar 9–12)
- **Fix**: Added Phase 5 (loyalty sync) and Phase 6 (member_daily_stats recalculation) to `scheduled_sync.py`
- Refactored `sync_loyalty.py`, `sync_loyalty_events.py`, `backfill_member_analytics.py` into importable modules
- Fixed `loyalty_events` upsert: added `on_conflict=event_id` to prevent duplicate key errors
- Full backfill completed: 55,605 member_daily_stats rows + 25,538 loyalty events + 2,836 loyalty balances
- Pushed to git: commit `6f1cb48`

### 2026-03-12 (morning) — Performance, Invoice, Margin Fix
- Fixed Real Profit Margin formula: now uses weighted `effectiveMargin` (not unweighted `overallMargin`)
- Real Profit Margin subtitle shows per-side breakdown: Cafe: 40.3% · Retail: 18.2%
- Added CSV export to Inventory Stock Levels table
- Optimized SortableTable: debounced search + virtual scroll + pre-built extractors
- Created business invoice (INV-002) for VIE Market: $2,000 + GST, due 31 Mar
- Cleaned 465 duplicate transaction rows from 2026-03-11
- Created Business Improvement Plan (MD + PDF)

### 2026-03-11 — Dashboard Optimization & Bug Fixes
- Created `get_inventory_full()` and `get_members_full()` consolidated RPCs
- Fixed Overview page showing all zeros (duplicate `get_category_daily` function overload)
- UI tightening: mobile responsive CSS, compact tables and KPI cards
- Created `docs/architecture.md` and `docs/formulas_reference.md`
- Added composite database indexes

### Earlier Sessions
- Backfilled historical transaction data from CSVs (2026-03-04 to 03-08)
- Refined labour rates with weekday/Saturday/Sunday/public holiday differentials (2026-02-27)
- Rebuilt Supabase transactions table from Square API with timezone correction (2026-02-23)
- Initial dashboard build, Supabase setup, Square API integration (2026-02)

## How to Continue Work

1. **Read this file first** — it's the project context
2. **Read `docs/architecture.md`** for technical details
3. **Read `docs/formulas_reference.md`** if working on calculations
4. **Build check**: `npm run build` (from `dashboard/` directory)
5. **Deploy**: `git add -A && git commit -m "msg" && git push origin master` (from `App24/` directory — Vercel auto-deploys)
6. **Supabase**: Project ID is `heavnfayolxrgmxkkrvr` — use MCP tools to query/modify
