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
| `daily_store_stats` | 795 | Pre-aggregated daily KPIs (incl. member splits) |
| `daily_item_summary` | 202K | Per-item daily sales aggregation |
| `member_daily_stats` | 50K | Per-member daily stats |
| `loyalty_events` | 24K | Loyalty point events ledger |
| `inventory` | 581K | Inventory snapshots (multiple dates) |
| `inventory_intelligence` | 4.2K | Pre-computed sales velocity, reorder alerts |
| `members` | 2.8K | Member profiles (Square synced) |
| `member_loyalty` | 2.8K | Loyalty balances |
| `staff_shifts` | 1.3K | Staff shift records with labour costs |
| `category_mappings` | 113 | Category → Cafe/Retail side mapping |

## Key Supabase RPCs
| RPC | Purpose |
|---|---|
| `get_inventory_full()` | **Consolidated**: returns latest inventory snapshot + intelligence + 30d sales + category mappings in one JSON call |
| `get_members_full()` | **Consolidated**: returns all members + loyalty + latest stats + spending patterns in one JSON call |
| `get_member_period_kpis(start, end)` | Period-specific member KPIs |
| `get_loyalty_period_kpis(start, end)` | Period-specific loyalty stats |
| `get_member_spending_patterns()` | All-time vs 30d spending patterns (uses materialized view `mv_member_spending_patterns`) |
| `get_category_daily(start, end)` | Daily Cafe/Retail sales (joins `daily_store_stats` for `is_closed` filter) |
| `get_category_detail_daily(start, end)` | Daily per-category sales (also `is_closed` filtered) |
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
3. **Pre-aggregated tables**: `daily_store_stats` and `daily_item_summary` avoid scanning raw transactions
4. **Composite indexes**: `idx_dis_item_date`, `idx_inv_source_product`, plus per-table date/customer indexes
5. **is_closed filtering**: All RPCs exclude pre-opening data (before Aug 2025) via `is_closed` flag

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
