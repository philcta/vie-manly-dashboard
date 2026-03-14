# AI Coach Knowledge Base — Schema Design

> Pre-computed weekly stats tables in Supabase to power the AI Business Coach.
> All data pre-aggregated by the dimensions that matter for business analysis.

---

## Design Principles

1. **Weekly granularity** — Sweet spot between daily (too noisy) and monthly (too coarse) for trend analysis
2. **Multi-dimensional** — Every table sliced by the key business dimensions
3. **Backfilled from day 1** — Sales/category from Jan 2024, everything else from Aug 20 2025
4. **Automated refresh** — New week computed every Monday as part of scheduled sync
5. **AI-optimized** — Compact enough to fit in a single AI context window (~50-100 rows per table)

---

## Dimensions

| Dimension | Values | Source |
|---|---|---|
| **Week** | `2024-W01` through current | ISO week (Monday start) |
| **Side** | `Cafe`, `Retail`, `All` | `category_mappings.side` |
| **Day Type** | `weekday`, `weekend`, `all` | Day of week (Mon-Fri vs Sat-Sun) |
| **Customer Type** | `member`, `non_member`, `all` | `transactions.customer_id` presence |
| **Age Group** | `teen`, `adult`, `all` | `members` table (age from DOB, <18 = teen) |

---

## Table 1: `weekly_store_stats`

The core business pulse — one row per week per dimension combination.

```sql
CREATE TABLE weekly_store_stats (
    week_start date NOT NULL,           -- Monday of the ISO week
    week_label text NOT NULL,           -- e.g. "2026-W11" (ISO week)
    side text NOT NULL DEFAULT 'All',   -- 'Cafe', 'Retail', 'All'
    day_type text NOT NULL DEFAULT 'all', -- 'weekday', 'weekend', 'all'
    
    -- Volume
    total_transactions integer NOT NULL DEFAULT 0,
    total_net_sales real NOT NULL DEFAULT 0,
    total_gross_sales real NOT NULL DEFAULT 0,
    total_items real NOT NULL DEFAULT 0,
    trading_days integer NOT NULL DEFAULT 0,   -- days with sales in this week
    
    -- Averages
    avg_daily_sales real NOT NULL DEFAULT 0,
    avg_transaction_value real NOT NULL DEFAULT 0,
    avg_daily_transactions real NOT NULL DEFAULT 0,
    
    -- Member split
    member_transactions integer NOT NULL DEFAULT 0,
    member_net_sales real NOT NULL DEFAULT 0,
    non_member_transactions integer NOT NULL DEFAULT 0,
    non_member_net_sales real NOT NULL DEFAULT 0,
    member_sales_ratio real NOT NULL DEFAULT 0,  -- member sales / total
    
    -- Labour (only from Aug 20, 2025)
    total_labour_cost real DEFAULT NULL,
    labour_pct real DEFAULT NULL,                -- labour / net_sales
    
    -- Margin (uses inventory_margins)
    weighted_margin_pct real DEFAULT NULL,        -- weighted avg profit margin
    real_profit_pct real DEFAULT NULL,            -- margin - labour
    real_profit_dollars real DEFAULT NULL,        -- net_sales * margin% - labour
    
    -- Customer count
    unique_customers integer NOT NULL DEFAULT 0,
    
    PRIMARY KEY (week_start, side, day_type),
    created_at timestamptz DEFAULT now()
);

CREATE INDEX idx_wss_week ON weekly_store_stats (week_start);
```

**Expected rows**: ~250 weeks × 3 sides × 3 day_types = **~2,250 rows** (very compact!)

---

## Table 2: `weekly_category_stats`

Per-category weekly breakdown for product-level insights.

```sql
CREATE TABLE weekly_category_stats (
    week_start date NOT NULL,
    week_label text NOT NULL,
    category text NOT NULL,              -- e.g. "Cafe Drinks", "Bread & Bakery"
    side text NOT NULL DEFAULT 'Retail', -- from category_mappings
    day_type text NOT NULL DEFAULT 'all',
    
    -- Sales
    total_net_sales real NOT NULL DEFAULT 0,
    total_gross_sales real NOT NULL DEFAULT 0,
    total_qty real NOT NULL DEFAULT 0,
    transaction_count integer NOT NULL DEFAULT 0,
    
    -- Rank / share
    pct_of_total_sales real DEFAULT NULL,   -- this category / total sales
    rank_by_sales integer DEFAULT NULL,     -- rank within this week
    
    -- Trend
    wow_sales_change_pct real DEFAULT NULL, -- week-over-week % change
    
    PRIMARY KEY (week_start, category, day_type),
    created_at timestamptz DEFAULT now()
);

CREATE INDEX idx_wcs_week ON weekly_category_stats (week_start);
CREATE INDEX idx_wcs_category ON weekly_category_stats (category, week_start);
```

**Expected rows**: ~250 weeks × ~50 active categories × 3 day_types = **~37,500 rows**

---

## Table 3: `weekly_member_stats`

Member/loyalty metrics for customer analytics.

```sql
CREATE TABLE weekly_member_stats (
    week_start date NOT NULL,
    week_label text NOT NULL,
    customer_type text NOT NULL DEFAULT 'all',  -- 'member', 'non_member', 'all'
    age_group text NOT NULL DEFAULT 'all',      -- 'teen', 'adult', 'all'
    day_type text NOT NULL DEFAULT 'all',
    
    -- Volume
    unique_customers integer NOT NULL DEFAULT 0,
    total_visits integer NOT NULL DEFAULT 0,     -- distinct (customer, date) pairs
    total_transactions integer NOT NULL DEFAULT 0,
    total_net_sales real NOT NULL DEFAULT 0,
    
    -- Averages
    avg_spend_per_visit real NOT NULL DEFAULT 0,
    avg_visits_per_customer real NOT NULL DEFAULT 0,
    
    -- New vs returning
    new_customers integer NOT NULL DEFAULT 0,    -- first ever transaction this week
    returning_customers integer NOT NULL DEFAULT 0,
    
    -- Loyalty (members only)
    total_points_earned integer DEFAULT NULL,
    total_points_redeemed integer DEFAULT NULL,
    rewards_created integer DEFAULT NULL,
    
    PRIMARY KEY (week_start, customer_type, age_group, day_type),
    created_at timestamptz DEFAULT now()
);

CREATE INDEX idx_wms_week ON weekly_member_stats (week_start);
```

**Expected rows**: ~250 weeks × 3 types × 3 ages × 3 days = **~6,750 rows** (most combos will be sparse)

---

## Table 4: `weekly_staff_stats`

Labour cost analysis by role and side.

```sql
CREATE TABLE weekly_staff_stats (
    week_start date NOT NULL,
    week_label text NOT NULL,
    side text NOT NULL DEFAULT 'All',    -- 'Cafe', 'Retail', 'All'
    day_type text NOT NULL DEFAULT 'all',
    
    -- Labour
    total_shifts integer NOT NULL DEFAULT 0,
    total_hours real NOT NULL DEFAULT 0,
    total_labour_cost real NOT NULL DEFAULT 0,
    
    -- By role
    barista_cost real DEFAULT 0,
    retail_cost real DEFAULT 0,
    overhead_cost real DEFAULT 0,
    
    -- Ratios
    labour_per_transaction real DEFAULT NULL,
    labour_per_dollar_sales real DEFAULT NULL,  -- cents of labour per $1 revenue
    
    -- Staff count
    unique_staff integer NOT NULL DEFAULT 0,
    
    PRIMARY KEY (week_start, side, day_type),
    created_at timestamptz DEFAULT now()
);

CREATE INDEX idx_wstaff_week ON weekly_staff_stats (week_start);
```

**Expected rows**: ~35 weeks × 3 sides × 3 day_types = **~315 rows** (only from Aug 2025)

---

## Table 5: `weekly_inventory_stats`

Inventory intelligence snapshots per category.

```sql
CREATE TABLE weekly_inventory_stats (
    week_start date NOT NULL,
    week_label text NOT NULL,
    category text NOT NULL,
    side text NOT NULL DEFAULT 'Retail',
    
    -- Stock levels (snapshot at week end)
    total_items integer DEFAULT 0,
    stock_value real DEFAULT 0,          -- cost value
    retail_value real DEFAULT 0,         -- selling value
    
    -- Movement
    units_sold real DEFAULT 0,
    sales_velocity real DEFAULT NULL,    -- units per day
    days_of_stock real DEFAULT NULL,
    sell_through_pct real DEFAULT NULL,
    
    -- Alerts
    critical_stock_items integer DEFAULT 0,
    overstock_items integer DEFAULT 0,
    
    -- Margin
    category_margin_pct real DEFAULT NULL,
    
    PRIMARY KEY (week_start, category),
    created_at timestamptz DEFAULT now()
);

CREATE INDEX idx_winv_week ON weekly_inventory_stats (week_start);
```

**Expected rows**: ~35 weeks × ~100 categories = **~3,500 rows** (from Aug 2025)

---

## Total Knowledge Base Size

| Table | Rows (est.) | Data from |
|---|---|---|
| `weekly_store_stats` | ~2,250 | Jan 2024 |
| `weekly_category_stats` | ~37,500 | Jan 2024 |
| `weekly_member_stats` | ~6,750 | Aug 2025 |
| `weekly_staff_stats` | ~315 | Aug 2025 |
| `weekly_inventory_stats` | ~3,500 | Aug 2025 |
| **Total** | **~50,000** | Compact! |

> [!TIP]
> 50K rows × ~200 bytes avg = ~10MB. Trivially small for Supabase. The entire knowledge base could fit in a single AI context window as a compressed summary.

---

## How the AI Uses This Data

Instead of querying raw tables on every chat message, the API route:

1. **Identifies relevant weeks** based on the user's question (e.g., "How was last month?" → last 4-5 weeks)
2. **Pulls pre-computed rows** from the knowledge base (fast, ~20ms)
3. **Formats as structured context** for the AI prompt
4. **AI reasons over clean, pre-digested data** — no aggregation needed

### Example AI Context (for "How was last week?")

```
## Last Week (2026-W11: Mar 10-14)

### Overall
- Net Sales: $32,450 (▲ 8.2% vs prior week)
- Transactions: 1,247 (▲ 3.1%)
- Avg Transaction: $26.02
- Member Sales: 42% of total

### By Side
| | Cafe | Retail |
|---|---|---|
| Sales | $9,735 | $22,715 |
| Margin | 68.2% | 41.3% |
| Labour % | 32.1% | 8.4% |

### Weekday vs Weekend
| | Weekday (5d) | Weekend (2d) |
|---|---|---|
| Avg Daily Sales | $5,890 | $7,475 |
| Avg Transactions | 225 | 286 |

### Top Categories (by sales)
1. Supplements & Vitamins: $4,230 (13.0%)
2. Cafe Drinks: $3,890 (12.0%)
3. Bread & Bakery: $2,100 (6.5%)

### Member Analysis
- Unique members: 342
- Teen customers: 28 (8.2%)
- Avg member spend: $38.40 vs non-member: $18.20
- New members this week: 12
```

This compact summary (~500 tokens) gives the AI everything it needs to provide actionable advice.

---

## Backfill & Refresh Pipeline

### Backfill Script

A one-time Python script to compute all historical weeks:

```python
# scripts/backfill_weekly_stats.py
# Reads from daily_store_stats, daily_category_stats, transactions, staff_shifts
# Computes weekly aggregations for all dimensions
# Upserts to weekly_* tables

# Runs once to backfill Jan 2024 → present
```

### Weekly Refresh (add to scheduled_sync.py)

```python
# New Phase 7 in scheduled_sync.py:
# Every Monday (or every sync run), recompute current week + prior week
# This ensures the latest data is always available

def refresh_weekly_stats():
    """Recompute current and prior week stats."""
    today = datetime.now(SYDNEY_TZ).date()
    # Find Monday of current week
    current_monday = today - timedelta(days=today.weekday())
    prior_monday = current_monday - timedelta(days=7)
    
    compute_week(prior_monday)  # recompute last week (may have late data)
    compute_week(current_monday)  # compute current partial week
```

### Edge Function Alternative

Could also run as a Supabase Edge Function on a cron schedule:
```
-- Supabase pg_cron (if available)
SELECT cron.schedule('weekly-stats', '0 2 * * 1', $$
    SELECT refresh_weekly_knowledge_base();
$$);
```

---

## RLS Policies

```sql
-- AI coach API uses service_role key (bypasses RLS)
-- But add anon read for potential future dashboard display
ALTER TABLE weekly_store_stats ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read" ON weekly_store_stats FOR SELECT TO anon USING (true);

-- Same for all weekly_* tables
```

---

## Implementation Order

### Phase 1: Schema + Backfill (this session or next)
1. Create all 5 tables in Supabase
2. Write Python backfill script
3. Run backfill for all historical data
4. Verify data accuracy

### Phase 2: Refresh Automation
5. Add weekly refresh to `scheduled_sync.py`
6. Test with current week data

### Phase 3: AI Coach Frontend
7. Install Vercel AI SDK
8. Build context builder that reads from knowledge base
9. Build FAB + chat panel
10. Deploy and test

### Phase 4: Smart Features
11. Proactive daily briefing
12. Anomaly detection
13. Goal tracking
14. Conversation memory
