# Denoux Dashboard — Architecture & Reference

## Stack
- **Framework**: Next.js 16 (App Router) + TypeScript
- **Styling**: Tailwind CSS v4 + custom design tokens (globals.css)
- **Charts**: Recharts (ComposedChart, Area, Line, Bar)
- **Database**: Supabase (PostgreSQL)
- **Hosting**: Vercel
- **UI**: Framer Motion animations, Radix UI primitives (tooltip, dialog)

## Project Structure
```
dashboard/
├── app/
│   ├── page.tsx           # Overview (main dashboard)
│   ├── members/page.tsx   # Members & loyalty
│   ├── inventory/page.tsx # Inventory & stock intelligence
│   ├── staff/page.tsx     # Staff management & labour costs
│   ├── campaigns/page.tsx # SMS campaigns
│   ├── settings/page.tsx  # Settings & category classification
│   ├── layout.tsx         # Root layout (fonts, sidebar shell)
│   └── globals.css        # Design system tokens + responsive CSS
├── components/
│   ├── kpi-card.tsx        # Animated KPI metric card
│   ├── period-selector.tsx # Date range picker (presets + custom)
│   ├── sortable-table.tsx  # Paginated, sortable, searchable table
│   ├── dashboard-shell.tsx # Sidebar + main content layout
│   ├── app-sidebar.tsx     # Collapsible navigation sidebar
│   ├── animated-number.tsx # Smooth number transitions
│   ├── charts/
│   │   ├── metric-timeseries-chart.tsx  # Multi-metric time series
│   │   ├── member-metric-chart.tsx     # Member-specific charts
│   │   ├── hourly-chart.tsx            # Hourly transaction bars
│   │   └── category-sales-chart.tsx    # Category breakdown
│   └── ui/                # Radix UI primitives (tooltip, sidebar, etc.)
├── lib/
│   ├── supabase.ts        # Supabase client
│   ├── dates.ts           # Period/comparison date range utilities
│   ├── format.ts          # Currency, percent, number formatters
│   ├── category-rules.ts  # Cafe vs Retail classification
│   └── queries/
│       ├── overview.ts    # Overview page queries (daily stats, hourly, category, labour)
│       └── members.ts     # Members page queries (KPIs, loyalty, spending patterns)
└── docs/
    ├── formulas_reference.md  # All business formulas
    └── architecture.md        # This file
```

## Supabase Tables
| Table | Rows (~) | Purpose |
|---|---|---|
| `transactions` | 307K | Raw Square transactions |
| `daily_store_stats` | 796 | Pre-aggregated daily KPIs (incl. member splits) |
| `daily_item_summary` | 202K | Per-item daily sales aggregation |
| `member_daily_stats` | 55.6K | Per-member cumulative daily stats (visits, spend, 30d trends) |
| `loyalty_events` | 25.5K | Loyalty point events ledger (accumulate, redeem, create_reward) |
| `inventory` | 581K | Inventory snapshots (multiple dates) |
| `inventory_intelligence` | 4.2K | Pre-computed sales velocity, reorder alerts |
| `members` | 2.8K | Member profiles (Square synced) |
| `member_loyalty` | 2.8K | Loyalty balances (synced from Square every 2h) |
| `staff_shifts` | 1.3K | Staff shift records with labour costs |
| `category_mappings` | 113 | Category → Cafe/Retail side mapping |
| `customer_id_mapping` | 231 | Old → new Square customer ID mappings (store ownership transfer) |
| `sync_log` | ~10 | Audit trail of scheduled sync runs |
| `daily_category_stats` | 38.5K | Pre-computed per-category per-day stats with Cafe/Retail side. Queried directly (not via RPC) to bypass PostgREST 1000-row limit. |

## Key Supabase RPCs
| RPC | Purpose |
|---|---|
| `get_inventory_full()` | **Consolidated**: returns latest inventory snapshot + intelligence + 30d sales + category mappings in one JSON call |
| `get_members_full()` | **Consolidated**: returns all members + loyalty + latest stats + spending patterns in one JSON call |
| `get_member_period_kpis(start, end)` | Period-specific member KPIs |
| `get_loyalty_period_kpis(start, end)` | Period-specific loyalty stats |
| `get_member_spending_patterns()` | All-time vs 30d spending patterns (uses materialized view `mv_member_spending_patterns`) |
| `get_category_daily(start, end)` | Daily Cafe/Retail sales (reads from `daily_category_stats`, joins `daily_store_stats` for `is_closed` filter). **WARNING**: Only ONE version must exist — never create overloaded variants with `(date,date)` params, causes PGRST203. |
| `get_category_detail_daily(start, end)` | Daily per-category sales — **NOT used by dashboard** (dashboard queries `daily_category_stats` table directly with `.range()` pagination to avoid PostgREST 1000-row limit) |
| `get_latest_member_stats()` | Latest stats per member (DISTINCT ON) |

## Key Formulas
See `docs/formulas_reference.md` for complete reference. Key ones:

- **Net Sales**: `SUM(net_sales)` from transactions
- **Profit Margin**: `(Avg Selling Price - Unit Cost) / Avg Selling Price × 100`
- **Labour Cost %**: `Total Labour Cost / Total Net Sales × 100`
- **Member Revenue %**: `member_net_sales / total_net_sales × 100` from daily_store_stats
- **Sales Velocity**: `units_sold_30d / 30` (days per unit)
- **Days of Stock**: `current_quantity / sales_velocity`
- **Sell Through %**: `units_sold / (units_sold + current_quantity) × 100`

## Performance Optimizations
1. **Consolidated RPCs**: `get_inventory_full()` and `get_members_full()` replace 4-7 separate API calls each
2. **Materialized views**: `mv_member_spending_patterns` pre-computes expensive spending pattern queries
3. **Pre-aggregated tables**: `daily_store_stats`, `daily_item_summary`, and `daily_category_stats` avoid scanning raw transactions
4. **Composite indexes**: `idx_dis_item_date`, `idx_inv_source_product`, plus per-table date/customer indexes
5. **is_closed filtering**: Used only on 2 transition days (Aug 18, Aug 20). Pre-Aug 20 data is now visible. Labour/profit metrics show N/A for pre-opening periods.
6. **Direct table queries with `.range()`**: `daily_category_stats` is queried directly from the dashboard (not via RPC) using `.range()` pagination to bypass PostgREST's 1000-row server-side limit.

## Automated Sync Pipeline — `scripts/scheduled_sync.py`

Runs every 2 hours (Task Scheduler / GitHub Actions).

| Phase | Script | What it does |
|---|---|---|
| 1 | `scripts/smart_backfill.py` | Detect & fill missing date gaps (last 14 days). Also populates `daily_category_stats`. |
| 2 | `services/square_sync.py` (`run_full_sync`) | Pull last 4h transactions + inventory + customers |
| 3 | `scripts/sync_inventory_intelligence.py` | Sales velocity, reorder alerts (90 day window) |
| 4 | Supabase RPC `refresh_member_spending_patterns` | Refresh materialized view |
| 5 | `scripts/sync_loyalty.py` + `sync_loyalty_events.py` | Sync loyalty balances + full event ledger from Square |
| 6 | `scripts/backfill_member_analytics.py` | Recalculate `member_daily_stats` from all transactions |

CLI flags: `--skip-backfill`, `--skip-latest`, `--skip-loyalty`, `--skip-member-stats`, `--lookback N`

## Date Range System
- `resolvePeriodRange(period, customStart, customEnd)` → `{startDate, endDate}`
- `resolveComparisonRange(range, comparison, period)` → comparison date range
- Periods: today, yesterday, last_7, last_14, last_30, this_week, this_month, this_quarter, current_fy, past_fy, custom
- Comparisons: prior_period, prior_year, none
- Financial Year (AU): July 1 – June 30
- Store opening: August 20, 2025

## Design System
- **Colors**: Olive `#6B7355` (primary), Coral `#E07A5F` (accent), Positive `#2D936C`, Warning `#D4A843`
- **Fonts**: Inter (body), Playfair Display (display), JetBrains Mono (mono)
- **Cards**: White bg, 12px radius, soft shadow, hover lift
- **Responsive**: p-3/sm:p-4/lg:p-5/xl:p-6 main padding; gap-2 grids; mobile sidebar collapses at 1024px
- **Touch**: 44x44px min targets, smooth transitions 150-300ms

## Deployment
```bash
# Build
npm run build

# Push to Vercel via Git
git add -A && git commit -m "description" && git push origin master
```

## Git Repository
- Remote: `origin` → GitHub → Vercel auto-deploy
- Branch: `master`

## Transaction Deduplication — row_key

All scripts that insert transactions MUST use the same 
ow_key format:
- **Format**: {order_id}-LI-{line_item_index} (e.g., Abc123XYZ-LI-0)
- **Upsert**: on_conflict=row_key with 
esolution=merge-duplicates
- **Order datetime**: Always use closed_at (not created_at) from Square API — matches Square dashboard's "Bills Closed" logic

Scripts that insert transactions:
| Script | row_key source | Square API filter |
|---|---|---|
| scripts/rebuild_from_square.py | {order_id}-LI-{idx} | closed_at |
| scripts/smart_backfill.py | {order_id}-LI-{idx} | closed_at |
| services/square_sync.py | {order_id}-LI-{idx} (set in sync_transactions()) | closed_at |

**CRITICAL**: If you add a new script that inserts transactions, it MUST use this exact format or duplicates will occur.

## Security — Row Level Security (RLS)

All tables have RLS enabled (see sql/enable_rls.sql):
- **Anon key** (dashboard): Read-only on all tables. Write access only on staff_rates and category_mappings.
- **Service role key** (Python scripts): Full access — bypasses RLS entirely.
- **Views**: member_sms_history and sms_campaign_summary are SECURITY DEFINER (expected).

## Staff Pay Period — getPayPeriod()

Biweekly pay period calculator in lib/queries/staff.ts:
- Anchored to March 9, 2026 as first update Monday
- All arithmetic uses UTC (Date.UTC(), getUTC*()) to avoid DST issues
- Never use 	oISOString() for date formatting in Australian timezone (shifts dates back 1 day)

## Utility Scripts
| Script | Purpose |
|---|---|
| scripts/fix_duplicates.py | One-shot cleanup: delete & re-sync transactions for a date range |
| scripts/rebuild_from_square.py | Full rebuild of transactions table from Square API |
