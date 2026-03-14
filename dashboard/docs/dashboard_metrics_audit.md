# Dashboard Metrics Audit → Knowledge Base Coverage

> Complete audit of every KPI, chart, and data point displayed on each dashboard page.
> Each metric is mapped to the weekly knowledge base table that must contain it.

---

## Page 1: Overview (`app/page.tsx`)

### KPI Cards (11 cards across 3 rows)

| # | KPI Card | Value | Subtitle / Breakdown | Source |
|---|---|---|---|---|
| 1 | **Net Sales** | `SUM(total_net_sales)` | Gross: `SUM(total_gross_sales)` | `daily_store_stats` |
| 2 | **Cafe Net Sales** | `SUM(net_sales) WHERE side=Cafe` | — | `get_category_daily` RPC |
| 3 | **Retail Net Sales** | `SUM(net_sales) WHERE side=Retail` | — | `get_category_daily` RPC |
| 4 | **Transactions** | `SUM(total_transactions)` | Cafe: X · Retail: Y | `daily_store_stats` + category |
| 5 | **Customers** | `SUM(total_unique_customers)` | Members + non-members | `daily_store_stats` |
| 6 | **Average Sale** | `net_sales / transactions` | Cafe: X · Retail: Y | Derived |
| 7 | **Labour Cost** | `SUM(labour_cost)` | Cafe: X · Retail: Y | `staff_shifts` |
| 8 | **Labour vs Sales %** | `labour / net_sales × 100` | Cafe: X% · Retail: Y% | Derived |
| 9 | **Avg Profit Margin** | Weighted margin by category sales mix | Cafe: X% · Retail: Y% | `inventory_margins` + `daily_category_stats` |
| 10 | **Real Profit Margin** | `Margin% - Labour%` | Cafe: X% · Retail: Y% | Derived |
| 11 | **Real Profit $** | `Net Sales × Margin% - Labour Cost` | After COGS + labour | Derived |

### Charts

| Chart | Metric Toggles | Side Toggles | Data Source |
|---|---|---|---|
| **Hourly Chart** (today only) | Transactions per hour (0-23) | — | `transactions` aggregated |
| **Time-Series Chart** | `net_sales`, `customers`, `transactions`, `avg_sale`, `real_profit_pct`, `labour_pct` | `All`, `Cafe`, `Retail`, `Category` (individual) | `daily_store_stats`, `daily_category_stats`, `staff_shifts` |
| **Category Margin Table** | `margin_pct`, `product_count`, `stock_value`, `retail_value` per category | `All`, `Cafe`, `Retail` | `inventory_margins` |

### ⚠️ Metrics MISSING from original schema

- ❌ **Gross Sales** (was only tracking net)
- ❌ **Cafe/Retail Avg Sale** (avg transaction value split by side)
- ❌ **Cafe/Retail Labour Cost & %** (labour split by business side)
- ❌ **Weighted Profit Margin** by category sales mix
- ❌ **Real Profit Margin** (margin - labour)
- ❌ **Real Profit $** (dollar profit after COGS + labour)
- ❌ **Hourly transaction distribution** (for pattern analysis)
- ❌ **Per-category daily/weekly data** for chart category filter

---

## Page 2: Members (`app/members/page.tsx`)

### KPI Cards (6 cards)

| # | KPI Card | Value | Subtitle / Breakdown | Source |
|---|---|---|---|---|
| 1 | **Active Members** | Unique members with transactions in period | Repeat: X (Y%) · One-off: Z | `get_member_period_kpis` RPC |
| 2 | **New Enrolments** | First-ever transaction in period | Total enrolled: N (X% active) | RPC |
| 3 | **Member Sales** | `SUM(net_sales) WHERE has member` | Non-member: $X | RPC |
| 4 | **Member Revenue %** | `member_sales / total_sales × 100` | Tx ratio: X% | RPC |
| 5 | **Avg Spend / Visit** | `member_sales / member_transactions` | Member Tx: X · Non-m: Y | RPC |
| 6 | **Points Earned** | Loyalty points earned in period | Redeemed: X · Balance: Y | `get_loyalty_period_kpis` RPC |

### Loyalty Insights Cards (3 cards, not period-filtered)

| Card | Metrics |
|---|---|
| **Points Overview** | Total available, Avg balance/member, Avg redeemed/member, Max lifetime |
| **Redemption Behaviour** | % who redeemed, Never redeemed count/%, Redeemed once, Redeemed 2+ |
| **Re-engagement Opportunity** | Frequent visitors (5+) who never redeemed — count + list |

### Member Chart (Time-Series)

| Metric Toggle | Side Toggles | Data |
|---|---|---|
| `net_sales` | All / Member / Non-Member | `daily_store_stats` (member splits) |
| `transactions` | All / Member / Non-Member | ^ |
| `avg_spend` | All / Member / Non-Member | ^ |
| `sales_ratio` | — (always member %) | ^ |
| `tx_ratio` | — (always member %) | ^ |

### Member Table Columns (per member)

| Column | Source |
|---|---|
| Name, Phone | `members` |
| Total Spent, Visits | `member_daily_stats` aggregated |
| Avg Spend (All / Cafe / Retail) | `mv_member_spending_patterns` |
| 30d Avg Spend (All / Cafe / Retail) | ^ |
| 30d Visits | ^ |
| Spend Trend % | ^ |
| Total Points, Redeemed, Available | `member_loyalty` |
| Days Since Last Visit | `member_daily_stats` |
| Status (Active/Cooling/At Risk/Churned) | Derived |

### ⚠️ Metrics MISSING from original schema

- ❌ **Active Members count** (unique in period)
- ❌ **Repeat vs One-off member counts**
- ❌ **New Enrolments** in period
- ❌ **Member Revenue %** (member sales share)
- ❌ **Member vs Non-Member Avg Spend**
- ❌ **Loyalty Points Earned/Redeemed in period**
- ❌ **Loyalty Redemption Rate** (% who redeemed at least once)
- ❌ **Member Sales Ratio** daily time series
- ❌ **Member Transaction Ratio** daily time series
- ❌ **Member Unique Customers per day**

---

## Page 3: Inventory (`app/inventory/page.tsx`)

### KPI Cards (4 cards)

| # | KPI Card | Value | Subtitle |
|---|---|---|---|
| 1 | **Stock Value (GST inc.)** | `SUM(qty × cost)` all positive-stock items | Ex-GST: $X |
| 2 | **Retail Value** | `SUM(qty × price)` | Snapshot date |
| 3 | **Avg Profit Margin** | `(RV - SV) / RV × 100` | Cafe: X% · Retail: Y% |
| 4 | **Needs Action** | Critical + Low count | X critical · Y low |

### Stock Intelligence Alerts (5 cards)

| Alert | Count of items | Filter |
|---|---|---|
| Critical | `reorder_alert = 'CRITICAL'` | `inventory_intelligence` |
| Low Stock | `reorder_alert = 'LOW'` | ^ |
| Watch | `reorder_alert = 'WATCH'` | ^ |
| Overstock | `reorder_alert = 'OVERSTOCK'` | ^ |
| Dead Stock | `reorder_alert = 'DEAD'` | ^ |

### Inventory Table Columns (per item)

| Column | Source |
|---|---|
| Alert level | `inventory_intelligence.reorder_alert` |
| Product, Category, SKU, Vendor | `inventory` |
| On Hand (qty) | `inventory.current_quantity` |
| Velocity (units/day) | `inventory_intelligence.sales_velocity` |
| Sold 7d, 30d, 90d | `inventory_intelligence.units_sold_*` |
| Days of Stock | `inventory_intelligence.days_of_stock` |
| Last Sold, Last Received | `inventory_intelligence` |
| Cost, Price, Margin % | `inventory` + derived |

### ⚠️ Metrics MISSING from original schema

- ❌ **Stock Value** (total + ex-GST) — weekly snapshot
- ❌ **Retail Value** — weekly snapshot
- ❌ **Cafe vs Retail margin** — from inventory, not sales
- ❌ **Alert counts** by level (Critical/Low/Watch/Overstock/Dead)
- ❌ **Total SKU count** in stock
- ❌ **Total items with zero stock**

---

## Page 4: Staff (`app/staff/page.tsx`)

### KPI Cards (4 cards)

| # | KPI Card | Value | Subtitle |
|---|---|---|---|
| 1 | **Staff Count** | Unique team members in period | Cafe: X · Retail: Y |
| 2 | **Total Hours** | `SUM(effective_hours)` | Cafe: Xh · Retail: Yh |
| 3 | **Labour Cost Ratio** | `labour / net_sales × 100` | Teens: $X · Adults: $Y |
| 4 | **Revenue per Hour** | `net_sales / total_hours` | Teen: Xh · Adult: Yh |

### Staff Charts

| Chart | Data Points |
|---|---|
| **Labour Split** (line chart) | Daily % split by 4 segments: Adult Café, Adult Retail, Teen Café, Teen Retail |
| **Labour Split** (bar chart) | Period totals: hours + cost per segment as % of total |

### Staff Earnings Table (per staff member, per pay period)

| Column | Source |
|---|---|
| Name, Role | `staff_shifts.team_member_name` |
| Total Earnings | Computed from shifts × rates |
| Weekday $, Hours | Filtered by day of week |
| Saturday $, Hours | Filtered |
| Sunday $, Hours | Filtered |
| Public Holiday $, Hours | Filtered |
| Total Hours | SUM all |
| Breaks | Count of 30-min auto-breaks |

### ⚠️ Metrics MISSING from original schema

- ❌ **Staff Count** (unique per period)
- ❌ **Cafe Staff Count** + **Retail Staff Count**
- ❌ **Revenue per Hour** (`net_sales / hours`)
- ❌ **4-way cost split**: Adult Café/Retail × Teen Café/Retail (hours + cost)
- ❌ **4-way % distribution** of labour
- ❌ **Weekday vs Saturday vs Sunday vs Public Holiday** labour breakdown
- ❌ **Pay period total** (bi-weekly payroll)

---

## REVISED Knowledge Base Schema

Based on this complete audit, here is the expanded schema:

### Table 1: `weekly_store_stats` (EXPANDED)

```sql
CREATE TABLE weekly_store_stats (
    week_start date NOT NULL,
    week_label text NOT NULL,
    side text NOT NULL DEFAULT 'All',       -- 'Cafe', 'Retail', 'All'
    day_type text NOT NULL DEFAULT 'all',   -- 'weekday', 'weekend', 'all'
    
    -- Volume
    total_net_sales real NOT NULL DEFAULT 0,
    total_gross_sales real NOT NULL DEFAULT 0,
    total_transactions integer NOT NULL DEFAULT 0,
    total_items real NOT NULL DEFAULT 0,
    trading_days integer NOT NULL DEFAULT 0,
    
    -- Averages
    avg_daily_sales real NOT NULL DEFAULT 0,
    avg_transaction_value real NOT NULL DEFAULT 0,
    avg_daily_transactions real NOT NULL DEFAULT 0,
    
    -- Member split
    member_transactions integer NOT NULL DEFAULT 0,
    member_net_sales real NOT NULL DEFAULT 0,
    non_member_transactions integer NOT NULL DEFAULT 0,
    non_member_net_sales real NOT NULL DEFAULT 0,
    member_sales_ratio real NOT NULL DEFAULT 0,
    member_tx_ratio real NOT NULL DEFAULT 0,
    unique_customers integer NOT NULL DEFAULT 0,
    
    -- Labour (from Aug 20, 2025)
    total_labour_cost real DEFAULT NULL,
    labour_pct real DEFAULT NULL,
    cafe_labour_cost real DEFAULT NULL,
    retail_labour_cost real DEFAULT NULL,
    cafe_labour_pct real DEFAULT NULL,
    retail_labour_pct real DEFAULT NULL,
    
    -- 4-way labour split (teen × side)
    adult_cafe_cost real DEFAULT NULL,
    adult_cafe_hours real DEFAULT NULL,
    adult_retail_cost real DEFAULT NULL,
    adult_retail_hours real DEFAULT NULL,
    teen_cafe_cost real DEFAULT NULL,
    teen_cafe_hours real DEFAULT NULL,
    teen_retail_cost real DEFAULT NULL,
    teen_retail_hours real DEFAULT NULL,
    
    -- Labour by day type
    weekday_labour_cost real DEFAULT NULL,
    saturday_labour_cost real DEFAULT NULL,
    sunday_labour_cost real DEFAULT NULL,
    public_holiday_labour_cost real DEFAULT NULL,
    
    -- Margin & Profit (from inventory_margins)
    weighted_margin_pct real DEFAULT NULL,
    cafe_margin_pct real DEFAULT NULL,
    retail_margin_pct real DEFAULT NULL,
    real_profit_pct real DEFAULT NULL,
    real_profit_dollars real DEFAULT NULL,
    
    -- Staff
    unique_staff integer DEFAULT NULL,
    cafe_staff_count integer DEFAULT NULL,
    retail_staff_count integer DEFAULT NULL,
    total_hours real DEFAULT NULL,
    cafe_hours real DEFAULT NULL,
    retail_hours real DEFAULT NULL,
    teen_hours real DEFAULT NULL,
    adult_hours real DEFAULT NULL,
    revenue_per_hour real DEFAULT NULL,
    
    PRIMARY KEY (week_start, side, day_type),
    created_at timestamptz DEFAULT now()
);
```

### Table 2: `weekly_category_stats` (EXPANDED)

```sql
CREATE TABLE weekly_category_stats (
    week_start date NOT NULL,
    week_label text NOT NULL,
    category text NOT NULL,
    side text NOT NULL DEFAULT 'Retail',
    day_type text NOT NULL DEFAULT 'all',
    
    -- Sales
    total_net_sales real NOT NULL DEFAULT 0,
    total_gross_sales real NOT NULL DEFAULT 0,
    total_qty real NOT NULL DEFAULT 0,
    transaction_count integer NOT NULL DEFAULT 0,
    
    -- Rank / share
    pct_of_total_sales real DEFAULT NULL,
    pct_of_side_sales real DEFAULT NULL,    -- NEW: % within its side
    rank_by_sales integer DEFAULT NULL,
    
    -- Profitability
    category_margin_pct real DEFAULT NULL,  -- from inventory_margins
    estimated_gross_profit real DEFAULT NULL, -- net_sales × margin%
    
    -- Trend
    wow_sales_change_pct real DEFAULT NULL,
    
    PRIMARY KEY (week_start, category, day_type),
    created_at timestamptz DEFAULT now()
);
```

### Table 3: `weekly_member_stats` (EXPANDED)

```sql
CREATE TABLE weekly_member_stats (
    week_start date NOT NULL,
    week_label text NOT NULL,
    customer_type text NOT NULL DEFAULT 'all',
    age_group text NOT NULL DEFAULT 'all',
    day_type text NOT NULL DEFAULT 'all',
    
    -- Volume
    unique_customers integer NOT NULL DEFAULT 0,
    total_visits integer NOT NULL DEFAULT 0,
    total_transactions integer NOT NULL DEFAULT 0,
    total_net_sales real NOT NULL DEFAULT 0,
    
    -- Member-specific
    active_members integer DEFAULT NULL,      -- NEW
    repeat_members integer DEFAULT NULL,      -- NEW: visited 2+ times in week
    one_off_members integer DEFAULT NULL,     -- NEW
    new_enrollments integer DEFAULT NULL,     -- NEW: first-ever transaction
    
    -- Averages
    avg_spend_per_visit real NOT NULL DEFAULT 0,
    avg_visits_per_customer real NOT NULL DEFAULT 0,
    member_revenue_share real DEFAULT NULL,   -- NEW: member $ / total $
    member_tx_share real DEFAULT NULL,        -- NEW: member tx / total tx
    
    -- Loyalty
    total_points_earned integer DEFAULT NULL,
    total_points_redeemed integer DEFAULT NULL,
    rewards_created integer DEFAULT NULL,
    total_loyalty_balance integer DEFAULT NULL,  -- NEW: end-of-week balance
    redemption_rate_pct real DEFAULT NULL,       -- NEW: % who redeemed at least once
    
    -- Churn / Activity
    active_count integer DEFAULT NULL,        -- NEW: visited in last 30d
    cooling_count integer DEFAULT NULL,       -- NEW: 30-89d since last visit
    at_risk_count integer DEFAULT NULL,       -- NEW: 90+ days
    churned_count integer DEFAULT NULL,       -- NEW: no visit in 6+ months
    
    PRIMARY KEY (week_start, customer_type, age_group, day_type),
    created_at timestamptz DEFAULT now()
);
```

### Table 4: `weekly_staff_stats` (EXPANDED)

```sql
CREATE TABLE weekly_staff_stats (
    week_start date NOT NULL,
    week_label text NOT NULL,
    side text NOT NULL DEFAULT 'All',
    day_type text NOT NULL DEFAULT 'all',
    
    -- Labour
    total_shifts integer NOT NULL DEFAULT 0,
    total_hours real NOT NULL DEFAULT 0,
    total_labour_cost real NOT NULL DEFAULT 0,
    
    -- By age group
    teen_cost real DEFAULT 0,
    teen_hours real DEFAULT 0,
    adult_cost real DEFAULT 0,
    adult_hours real DEFAULT 0,
    
    -- By day of week type
    weekday_cost real DEFAULT 0,
    weekday_hours real DEFAULT 0,
    saturday_cost real DEFAULT 0,
    saturday_hours real DEFAULT 0,
    sunday_cost real DEFAULT 0,
    sunday_hours real DEFAULT 0,
    public_holiday_cost real DEFAULT 0,
    public_holiday_hours real DEFAULT 0,
    
    -- Ratios
    labour_cost_ratio real DEFAULT NULL,        -- labour / net_sales %
    revenue_per_hour real DEFAULT NULL,         -- net_sales / hours
    
    -- Staff count
    unique_staff integer NOT NULL DEFAULT 0,
    
    PRIMARY KEY (week_start, side, day_type),
    created_at timestamptz DEFAULT now()
);
```

### Table 5: `weekly_inventory_stats` (EXPANDED)

```sql
CREATE TABLE weekly_inventory_stats (
    week_start date NOT NULL,
    week_label text NOT NULL,
    category text NOT NULL,
    side text NOT NULL DEFAULT 'Retail',
    
    -- Stock levels snapshot
    total_skus integer DEFAULT 0,
    in_stock_skus integer DEFAULT 0,
    zero_stock_skus integer DEFAULT 0,
    stock_value_gst real DEFAULT 0,
    stock_value_ex_gst real DEFAULT 0,
    retail_value real DEFAULT 0,
    
    -- Movement
    units_sold_7d real DEFAULT 0,
    units_sold_30d real DEFAULT 0,
    units_sold_90d real DEFAULT 0,
    revenue_30d real DEFAULT 0,
    sales_velocity real DEFAULT NULL,
    days_of_stock real DEFAULT NULL,
    sell_through_pct real DEFAULT NULL,
    
    -- Alerts (count of items in this category)
    critical_count integer DEFAULT 0,
    low_count integer DEFAULT 0,
    watch_count integer DEFAULT 0,
    overstock_count integer DEFAULT 0,
    dead_count integer DEFAULT 0,
    
    -- Margin
    category_margin_pct real DEFAULT NULL,
    
    PRIMARY KEY (week_start, category),
    created_at timestamptz DEFAULT now()
);
```

### Table 6: `weekly_hourly_patterns` (NEW)

Captures the average hourly transaction/sales pattern per week for AI coaching.

```sql
CREATE TABLE weekly_hourly_patterns (
    week_start date NOT NULL,
    week_label text NOT NULL,
    hour integer NOT NULL,              -- 0-23
    day_type text NOT NULL DEFAULT 'all', -- 'weekday', 'weekend', 'all'
    
    avg_transactions real NOT NULL DEFAULT 0,
    avg_net_sales real NOT NULL DEFAULT 0,
    total_transactions integer NOT NULL DEFAULT 0,
    total_net_sales real NOT NULL DEFAULT 0,
    days_in_sample integer NOT NULL DEFAULT 0,
    
    -- Peak detection
    is_peak boolean DEFAULT false,      -- top 3 hours
    pct_of_daily_total real DEFAULT NULL,
    
    PRIMARY KEY (week_start, hour, day_type),
    created_at timestamptz DEFAULT now()
);
```

---

## Complete Metric Coverage Map

| Dashboard Metric | Knowledge Base Table | Column(s) |
|---|---|---|
| Net Sales | `weekly_store_stats` | `total_net_sales` |
| Gross Sales | `weekly_store_stats` | `total_gross_sales` |
| Cafe Net Sales | `weekly_store_stats` (side=Cafe) | `total_net_sales` |
| Retail Net Sales | `weekly_store_stats` (side=Retail) | `total_net_sales` |
| Transactions | `weekly_store_stats` | `total_transactions` |
| Cafe/Retail Transactions | `weekly_store_stats` (by side) | `total_transactions` |
| Customers | `weekly_store_stats` | `unique_customers` |
| Average Sale | `weekly_store_stats` | `avg_transaction_value` |
| Cafe/Retail Avg Sale | `weekly_store_stats` (by side) | `avg_transaction_value` |
| Labour Cost | `weekly_store_stats` | `total_labour_cost` |
| Cafe/Retail Labour | `weekly_store_stats` | `cafe_labour_cost`, `retail_labour_cost` |
| Labour % | `weekly_store_stats` | `labour_pct` |
| Weighted Profit Margin | `weekly_store_stats` | `weighted_margin_pct` |
| Real Profit Margin | `weekly_store_stats` | `real_profit_pct` |
| Real Profit $ | `weekly_store_stats` | `real_profit_dollars` |
| Hourly patterns | `weekly_hourly_patterns` | all columns |
| Category sales (each) | `weekly_category_stats` | per category row |
| Category margin | `weekly_category_stats` | `category_margin_pct` |
| Category % of total | `weekly_category_stats` | `pct_of_total_sales` |
| Active Members | `weekly_member_stats` | `active_members` |
| Repeat Members | `weekly_member_stats` | `repeat_members` |
| New Enrolments | `weekly_member_stats` | `new_enrollments` |
| Member Sales | `weekly_member_stats` | `total_net_sales` (member type) |
| Member Revenue % | `weekly_member_stats` | `member_revenue_share` |
| Member Avg Spend | `weekly_member_stats` | `avg_spend_per_visit` |
| Points Earned | `weekly_member_stats` | `total_points_earned` |
| Points Redeemed | `weekly_member_stats` | `total_points_redeemed` |
| Loyalty Balance | `weekly_member_stats` | `total_loyalty_balance` |
| Redemption Rate | `weekly_member_stats` | `redemption_rate_pct` |
| Activity Status | `weekly_member_stats` | `active_count`, `cooling_count`, etc. |
| Staff Count | `weekly_staff_stats` | `unique_staff` |
| Total Hours | `weekly_staff_stats` | `total_hours` |
| Labour Cost Ratio | `weekly_staff_stats` | `labour_cost_ratio` |
| Revenue per Hour | `weekly_staff_stats` | `revenue_per_hour` |
| 4-way labour split | `weekly_store_stats` | `adult_cafe_*`, `teen_retail_*`, etc. |
| Day type breakdown | `weekly_staff_stats` | `weekday_*`, `saturday_*`, etc. |
| Stock Value | `weekly_inventory_stats` | `stock_value_gst`, `stock_value_ex_gst` |
| Retail Value | `weekly_inventory_stats` | `retail_value` |
| Inventory Margin | `weekly_inventory_stats` | `category_margin_pct` |
| Alert Counts | `weekly_inventory_stats` | `critical_count`, `low_count`, etc. |
| SKU counts | `weekly_inventory_stats` | `total_skus`, `in_stock_skus` |

✅ **All dashboard metrics are now covered by the knowledge base.**

---

## Estimated Row Counts (Final)

| Table | Rows | Notes |
|---|---|---|
| `weekly_store_stats` | ~2,250 | 120 weeks × 3 sides × 3 day types × ~2 (some sparse) |
| `weekly_category_stats` | ~37,500 | 120 weeks × ~50 cats × 3 day types |
| `weekly_member_stats` | ~6,750 | 35 weeks × 3 types × 3 ages × 3 days (from Aug 2025) |
| `weekly_staff_stats` | ~315 | 35 weeks × 3 sides × 3 day types |
| `weekly_inventory_stats` | ~3,500 | 35 weeks × ~100 categories |
| `weekly_hourly_patterns` | ~10,080 | 120 weeks × 24 hours × 3 day types |
| **Total** | **~60,400** | ~12MB — tiny |
