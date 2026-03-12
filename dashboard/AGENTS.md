# AGENTS.md — VIE. MANLY Dashboard Project

> **This file is the project brain. Read it first in every new conversation.**
> Last updated: 2026-03-12

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

### Data Pipeline
- Square API → `transactions` table (hourly sync)
- `transactions` → aggregated into `daily_store_stats` and `daily_item_summary`
- `staff_shifts` populated from Square Team API
- `inventory` snapshots from Square inventory
- `inventory_intelligence` pre-computed nightly (velocity, reorder alerts)

## Known Gotchas & Past Bugs

1. **`business_side` values**: Staff shifts use "Bar" (not "Cafe"), "Retail", "Overhead". Code maps Bar+Overhead → Cafe.
2. **Function overloading**: `get_category_daily` had a duplicate `(text, text)` overload causing PostgREST 300 errors. Fixed by dropping old overload.
3. **Duplicate transactions**: Square API sync can produce duplicates (happened 2026-03-11 — 465 rows). Dedup key: `(transaction_id, item, qty, net_sales, date)`.
4. **`is_closed` flag**: `daily_store_stats.is_closed = true` marks pre-opening dates and closed days. ALL RPCs and queries must filter this.
5. **Timezone**: All dates are Sydney local time (AEST/AEDT). Square API returns UTC — conversion happens at ingest.
6. **Financial Year**: Australian FY is July 1 – June 30.

## Performance Optimizations Done

1. **Consolidated RPCs**: `get_inventory_full()` and `get_members_full()` replace 4-7 separate API calls each
2. **Virtual scroll**: `SortableTable` renders only visible rows (~20) instead of all 800+
3. **Debounced search**: 150ms debounce on search input prevents re-render storms
4. **Pre-built search extractors**: Avoid `columns.find()` per row per key on each filter pass
5. **Composite indexes**: `idx_dis_item_date`, `idx_inv_source_product`
6. **Materialized views**: `mv_member_spending_patterns` for expensive spending pattern queries

## Session Log (Most Recent First)

### 2026-03-12 — Performance, Invoice, Margin Fix
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
