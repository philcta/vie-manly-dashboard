# AGENTS.md — VIE. MANLY Dashboard Project

> **This file is the project brain. Read it first in every new conversation.**
> Last updated: 2026-03-16

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
- **AI SDK**: `ai` v6 + `@ai-sdk/openai` v3 + `@ai-sdk/react` v2 (GPT-4o)
- **Repo**: `github.com/philcta/vie-manly-dashboard` branch `master`
- **Live URL**: `https://viemarket.app`

## Key Files to Read First

| File | What it contains |
|---|---|
| `docs/architecture.md` | Full project structure, Supabase tables/RPCs, formulas, design system, deployment |
| `docs/formulas_reference.md` | Every business calculation (margins, labour, profit, member metrics) |
| `docs/ai_coach_implementation.md` | **AI Coach full blueprint** — all 4 phases, architecture, code, reuse guide |
| `docs/ai_coach_supabase_rpcs.md` | **AI Coach SQL** — all RPCs, indexes, tables, RLS policies |
| `docs/business_improvement_plan.md` | Data-driven business analysis with 6 prioritised actions |
| `app/page.tsx` | Overview dashboard — 12 KPI cards, charts, comparison logic |
| `app/api/chat/route.ts` | **AI Coach API** — context builder, system prompt, 4 tools, streaming |
| `components/ai-coach-panel.tsx` | **AI Coach UI** — 53 questions, 5 categories, navigation, history, favorites |
| `lib/export-pdf.ts` | PDF export with markdown table/chart formatting |
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

### KPI Targets (Active)
| Metric | Target | Timeline | Category |
|---|---|---|---|
| Labour vs Sales % | ≤ 24% | 4 weeks | profitability |
| Average Sale | ≥ $24.00 | 8 weeks | revenue |
| Real Profit Margin | ≥ 25% | 3 months | profitability |
| Member Revenue % | +5% vs current | 3 months | members |
| Dead/Overstock Items | −30% vs current | 6 weeks | inventory |

### Data Pipeline — `scheduled_sync.py` (every 2 hours)

The automated sync runs 6 phases in sequence:

| Phase | Script/Module | What it does |
|---|---|---|
| 1. Smart Backfill | `scripts/smart_backfill.py` | Detects & fills missing date gaps (last 14 days). Also populates `daily_category_stats`. |
| 2. Latest Sync | `services/square_sync.py` | Pulls last 4h of transactions + inventory + customers from Square API |
| 3. Stock Intelligence | `scripts/sync_inventory_intelligence.py` | Calculates sales velocity, reorder alerts (90 days) |
| 4. Spending Patterns | Supabase RPC | Refreshes `mv_member_spending_patterns` materialized view |
| 5. Loyalty Sync | `scripts/sync_loyalty.py` + `sync_loyalty_events.py` | Pulls all loyalty balances (2,836 accounts) + events (25K+) from Square |
| 6. Member Stats | `scripts/backfill_member_analytics.py` | Recalculates `member_daily_stats` for ALL members from transactions |

**Key derived tables**:
- `transactions` → aggregated into `daily_store_stats` (member/non-member split), `daily_item_summary`, and `daily_category_stats`
- `daily_category_stats`: pre-computed per-category per-day stats with Cafe/Retail side. Replaces expensive `daily_item_summary` aggregation for chart queries. Queried directly from dashboard (not via RPC) with `.range()` pagination to bypass PostgREST's 1000-row limit.
- `transactions` → `member_daily_stats` (cumulative visits, spend, 30d trends per member)
- `staff_shifts` populated from Square Team API
- `inventory` snapshots from Square, enriched into `inventory_intelligence`
- `member_loyalty` synced from Square Loyalty API (balances + lifetime points)
- `loyalty_events` synced from Square Loyalty Events API (full ledger: accumulate, redeem, create_reward)

## AI Coach (Built 2026-03-14 to 2026-03-16)

> **Full implementation guide**: `docs/ai_coach_implementation.md`
> **SQL reference**: `docs/ai_coach_supabase_rpcs.md`

### Architecture
- **Phase 1**: Pre-computed weekly context → streamed to GPT-4o in system prompt (zero latency)
- **Phase 2**: Conversation persistence + history + favorites + PDF export
- **Phase 3**: Anti-hallucination guardrails (model upgrade to GPT-4o, data integrity rules)
- **Phase 4**: Tool use — 4 Supabase RPC functions called on-demand by the AI

### AI Tools (RPC Functions)
| Tool | Purpose | Avg Response |
|---|---|---|
| `lookup_product(search_term)` | Fuzzy product search (4,290 items) | 7ms |
| `lookup_category_products(cat_name)` | All products in a category | 9ms |
| `get_daily_sales(num_days)` | Day-by-day sales breakdown | 33ms |
| `get_mtd_summary()` | Month-to-date totals | 21ms |

### UI Components
- **Floating panel**: chat in bottom-right, full-screen on mobile
- **5 question categories**: Labour (10), Margins (10), Members (10), Stock (12), Game Plan (11) = 53 total
- **Navigation**: Home button (header), New Topic banner (top of conversation), Browse Topics strip (collapsible above input)
- **History**: past conversations saved to Supabase, restorable
- **Favorites**: star-to-bookmark any question (localStorage)
- **Export**: PDF with markdown table formatting preserved

### AI SDK v6 Gotchas
- Use `inputSchema` not `parameters` in tool definitions
- Use `stopWhen: stepCountIs(N)` not `maxSteps: N`
- Use inline tool objects, not `tool()` helper (Zod v3/v4 compatibility)
- `import { stepCountIs } from "ai"` — in main `ai` package

## Known Gotchas & Past Bugs

1. **`business_side` values**: Staff shifts use "Bar" (not "Cafe"), "Retail", "Overhead". Code maps Bar+Overhead → Cafe.
2. **Function overloading (FIXED 2026-03-14)**: `get_category_daily` had TWO versions — one with `(text, text)` and one with `(date, date)` params. PostgREST can't disambiguate → `PGRST203` error → `Promise.all()` crash → entire dashboard shows $0. Fix: drop the `(date, date)` version. **NEVER create a function with same name but different param types.**
3. **Duplicate transactions (FIXED 2026-03-13)**: Root cause was 3 scripts generating `row_key` in incompatible formats: `rebuild_from_square.py` used `{order_id}-LI-{idx}`, `smart_backfill.py` used plain concatenation, `square_sync.py` used MD5 hash. All three now use the deterministic `{order_id}-LI-{idx}` format. Also fixed `smart_backfill.py` to use `closed_at` instead of `created_at` for consistency.
4. **`is_closed` flag**: `daily_store_stats.is_closed = true` marks only genuinely closed/transition days (Aug 18, Aug 20 — sub-$100 sales during ownership changeover). Historical data pre-Aug 20 is now `is_closed = false` so it shows on the dashboard. Labour/profit metrics show N/A for periods spanning pre-Aug 20 since no shift data exists.
12. **PostgREST 1000-row limit**: RPCs returning `SETOF` are capped at 1000 rows by PostgREST's server-side `max_rows`. Client-side `.limit()` CANNOT override this. Workaround: query tables directly with `.range()` pagination, or use pre-computed summary tables. The `daily_category_stats` table + direct `.from()` query with `.range()` pagination is the current solution.
13. **Pre-Aug 20 data & N/A cards**: The store opened Aug 20, 2025. Pre-Aug 20 data is CSV-imported from previous owner. No labour/shift data exists before this date. Dashboard shows N/A on Labour Cost, Labour %, Real Profit Margin, Real Profit $ when period includes pre-Aug 20. Chart greys out "Real Profit %" and "Labour %" toggles. Constant `STORE_OPENING_DATE = "2025-08-20"` in both `app/page.tsx` and `metric-timeseries-chart.tsx`.
14. **Promise.all crash pattern**: All 19 data fetches in `loadData()` are wrapped in one `Promise.all()`. If ANY single fetch throws, ALL data shows as zero/empty. Always check browser console for the specific failing RPC/query.
5. **Timezone**: All dates are Sydney local time (AEST/AEDT). Square API returns UTC — conversion happens at ingest.
6. **Financial Year**: Australian FY is July 1 – June 30.
7. **`member_daily_stats` must be recalculated**: This table is NOT incrementally updated — it requires a full rebuild from `transactions` (Phase 6 of scheduled_sync). Before 2026-03-12, it was only populated by manual one-off backfills. Gap incident: 228 members had stale data for 4 days (Mar 9–12). Now automated.
8. **`loyalty_events` upsert needs `on_conflict=event_id`**: Without this, re-syncing causes duplicate key errors (23505). Fixed 2026-03-12.
9. **Staff pay period dates**: `getPayPeriod()` in `lib/queries/staff.ts` must use UTC-only arithmetic (`Date.UTC()`, `getUTCDate()` etc). Using `toISOString()` or local-time ms arithmetic causes dates to shift by 1 day in Australian timezone (UTC+11). Also vulnerable to DST transitions if using `86400000ms` with local time.
10. **RLS enabled on all tables (2026-03-13)**: Row Level Security is now active. Dashboard (anon key) has read-only access to most tables. Write access is only granted on `staff_rates` (rate editor) and `category_mappings` (side assignment). Python scripts use `service_role` key which bypasses RLS. SQL policies are in `sql/enable_rls.sql`.
11. **Old Square account customer IDs**: The store had a previous owner with a different Square account. ~1,664 old customer IDs exist in transactions but have no matching `member_daily_stats`. These are reconciled via `customer_id_mapping` table (231 mappings). The old IDs are expected — not a bug.
15. **AI SDK v6 `tool()` helper breaks with Zod v3**: The `tool()` helper from `ai` requires Zod v4. If project uses Zod v3, define tools inline with `inputSchema` property instead.

## Performance Optimizations Done

1. **Consolidated RPCs**: `get_inventory_full()` and `get_members_full()` replace 4-7 separate API calls each
2. **Virtual scroll**: `SortableTable` renders only visible rows (~20) instead of all 800+
3. **Debounced search**: 150ms debounce on search input prevents re-render storms
4. **Pre-built search extractors**: Avoid `columns.find()` per row per key on each filter pass
5. **Composite indexes**: `idx_dis_item_date`, `idx_inv_source_product`
6. **Materialized views**: `mv_member_spending_patterns` for expensive spending pattern queries
7. **Pre-computed `daily_category_stats`**: Eliminates expensive `daily_item_summary` GROUP BY at query time for category charts. 38,547 rows pre-aggregated by date+category+side.
8. **AI Coach tool RPCs indexed**: `pg_trgm` GIN indexes on `product_name` + `category` (7ms fuzzy search). B-tree on `transactions.date` (33ms daily aggregation).

## AI Coach Knowledge Base (Created 2026-03-14)

8 weekly pre-computed tables for AI business coaching. Migration SQL in `supabase/migrations/01-08_*.sql`.

| Table | Purpose | PK Dimensions | Backfill From |
|---|---|---|---|
| `weekly_store_stats` | Sales, labour, margins, staff per week | `(week_start, side, day_type)` | Jan 2024 (sales), Aug 2025 (labour) |
| `weekly_category_stats` | Per-category sales, rank, trends | `(week_start, category, day_type)` | Jan 2024 |
| `weekly_member_stats` | Member engagement, loyalty, churn | `(week_start, customer_type, age_group, day_type)` | Aug 2025 |
| `weekly_staff_stats` | Labour by side, day type, age group | `(week_start, side, day_type)` | Aug 2025 |
| `weekly_inventory_stats` | Stock snapshots per category | `(week_start, category)` | Aug 2025 |
| `weekly_hourly_patterns` | Avg hourly transaction patterns | `(week_start, hour, day_type)` | Jan 2024 |
| `weekly_dow_stats` | Day-of-week patterns (Mon-Sun) | `(week_start, dow, side)` | Jan 2024 |
| `coach_conversations` | AI coach chat memory | `(id)` | N/A |

**Dimension values**: `side`: All/Cafe/Retail | `day_type`: all/weekday/weekend | `customer_type`: all/member/non_member | `age_group`: all/teen/adult | `dow`: 0-6 (Sun-Sat)

## Session Log (Most Recent First)

### 2026-03-16 — AI Coach Navigation Overhaul + Enriched Questions

**Objective**: Improve AI Coach navigation (users got trapped in conversations) and enrich question categories

**What was done**:
1. **Enriched all 5 question categories** with data-backed queries — 39 → 53 questions total
   - Labour: Added revenue-per-hour, labour gap, 4-week trend (10 questions)
   - Margins: Added MTD performance, Cafe vs Retail split, KPI status (10 questions)
   - Members: Added re-engagement SMS, points redemption, reactivation revenue impact (10 questions)
   - Stock: Added dead stock capital audit, OOS revenue loss, tool-based product lookup (12 questions)
   - Game Plan: Added all-5-KPI status check, promotional plan, MTD pace check (11 questions)
2. **Navigation overhaul** — 3 new navigation elements:
   - **Home button** in header — always visible, returns to welcome screen
   - **"New topic" banner** — at top of conversation messages with question counter
   - **"Browse topics" strip** — collapsible panel above input with full category browser
3. Removed old "Clear" button (replaced by Home), removed old "New Conversation" (replaced by New Topic)

**Data verified for questions**:
- 410 dead stock items, 400 overstock, 248 out-of-stock still in demand
- 593 high-margin underselling items, 841 items with stockout risk dates
- 5 active KPI targets in `kpi_targets` table
- 15,867 loyalty points earned, 0 redeemed
- Member lifecycle data available: active/cooling/at-risk/churned

**Commits**: `62c245d` (enriched questions), `4486775` (navigation overhaul)

### 2026-03-15 — AI Coach Phase 4 (Tool Use) + Phases 2-3

**Objective**: Give the AI Coach direct database query capabilities + conversation persistence + anti-hallucination

**Phase 2 — Conversation Persistence**:
- Auto-save conversations to `ai_coach_conversations` table
- History panel (load, restore, delete, export from history)
- Favorites system (localStorage, star toggle on questions, bulk delete)
- PDF export with markdown table formatting preserved (fixed print dialog auto-open)

**Phase 3 — Anti-Hallucination**:
- Upgraded model to GPT-4o (from gpt-4o-mini)
- Added side-by-side current/prior week comparison data
- Added data freshness timestamp
- Strict system prompt rules preventing number fabrication

**Phase 4 — Tool Use**:
- Created 4 Supabase RPC functions: `lookup_product`, `lookup_category_products`, `get_daily_sales`, `get_mtd_summary`
- Added `pg_trgm` GIN indexes → response times from 287ms → 7ms
- Integrated tools in `route.ts` using AI SDK v6 syntax
- Fixed `inputSchema` vs `parameters` (v6 API change) and `stepCountIs` vs `maxSteps`
- Tested: kombucha product lookup and MTD summary both returned accurate results

**Migrations**: `20260314042907_fix_tool_rpcs_correct_columns.sql`, `20260314043140_add_indexes_for_tool_rpcs.sql`

### 2026-03-14 (PM) — AI Coach Knowledge Base Tables Created

**Objective**: Build comprehensive pre-computed weekly knowledge base for AI Business Coach

**What was done**:
1. **Full dashboard audit**: Went through every KPI, chart, and table across all 4 pages (Overview, Members, Inventory, Staff) to capture EVERY metric
2. **Schema design**: Designed 8 tables covering 100% of dashboard metrics plus hourly patterns and day-of-week analysis
3. **Created 8 SQL migration files** in `supabase/migrations/01-08_*.sql`
4. **Tables created in Supabase** (user ran SQL manually in SQL Editor)
5. **RLS enabled** on all 8 tables (anon read-only)

**Tables are EMPTY** — need backfill script next session.

**Key design decisions**:
- Weekly granularity (not daily) for compact AI context (~60K total rows)
- Multi-dimensional slicing: side × day_type × customer_type × age_group
- `weekly_hourly_patterns` captures peak hours at weekly level
- `weekly_dow_stats` captures Mon-Sun patterns within each week (avoids need for full daily tables)
- Phase 2 (later): daily_hourly_patterns if AI coach needs deeper drill

**Files created**:
- `supabase/migrations/01_weekly_store_stats.sql` through `08_coach_conversations.sql`
- `supabase/migrations/20260314_create_weekly_knowledge_base.sql` (combined)
- `scripts/create_weekly_knowledge_base.py` (helper script, optional)

### 2026-03-14 (AM) — Pre-Aug 20 Historical Data + Category Chart Fix
- **Investigated missing historical data**: $2.19M in CSV-imported sales (Jan 2024 – Aug 2025) was hidden because all 590 pre-Aug 18 rows in `daily_store_stats` had `is_closed = true`
- **Unflagged 590 rows**: Set `is_closed = false` for all pre-Aug 18 dates. Kept Aug 18 ($79.60) and Aug 20 ($56.90) as closed — genuine transition days
- **N/A on labour/profit cards**: When selected period includes pre-Aug 20 dates, Labour Cost, Labour %, Real Profit Margin, Real Profit $ now show "N/A" with subtitle "No shift data before Aug 20"
- **Chart toggle greying**: "Real Profit %" and "Labour %" pills are greyed out (disabled) when period spans pre-Aug 20 — extends existing Category-mode greying pattern
- **Category chart truncation fixed**: `get_category_detail_daily` RPC was returning only 1000 rows (PostgREST `max_rows` cap), cutting off category charts at ~Jan 21. Tried `.limit()` (doesn't override server cap), tried JSON-returning RPC (broke Supabase JS client). Final fix: created `daily_category_stats` pre-computed table and query it directly with `.range()` pagination
- **New table: `daily_category_stats`**: Pre-computed per-category per-day stats (date, category, side, net_sales, gross_sales, qty, transaction_count). Backfilled 38,547 rows. Sync pipeline updated to populate on every run
- **Function overloading crash (PGRST203)**: Creating new `get_category_daily(text, text)` alongside old `get_category_daily(date, date)` caused PostgREST ambiguity error → entire `Promise.all()` crashed → dashboard showed $0 everywhere. Fixed by dropping the old `(date, date)` version
- **Updated RPCs**: `get_category_daily` and `get_category_detail_daily_v2` now read from `daily_category_stats` instead of `daily_item_summary`
- **Sync pipeline**: `smart_backfill.py` now also builds and upserts `daily_category_stats` alongside `daily_item_summary` and `daily_store_stats`
- Commits: `c5ad2fb` (pre-Aug 20 data + N/A cards), `63ca7cf` (limit attempt), `9f49bf0` (JSON RPC), `4041e8c` (pre-computed table + sync), `8cc2a1d` (direct table query + pagination)

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
