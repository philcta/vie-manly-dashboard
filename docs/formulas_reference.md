# Vie Market & Bar — Formula Reference

> Every KPI card, chart, and metric in the dashboard, with the exact formula behind it.
> All formulas are **period-agnostic** — substitute `[period]` with the selected date range.

---

## 1. Overview — Performance Section

### KPI Cards

| Card | Formula | Unit | Source |
|------|---------|------|--------|
| **Net Sales** | `SUM(gross_amount) − SUM(discount_amount) − SUM(refund_amount)` for `[period]` | $ | `transactions` |
| **Transactions** | `COUNT(DISTINCT order_id)` for `[period]` | # | `transactions` |
| **Gross Sales** | `SUM(gross_amount)` for `[period]` | $ | `transactions` |
| **Average Sale** | `Net Sales / Transactions` | $ | derived |
| **Actual Sales Profit** | `Net Sales − COGS` where `COGS = SUM(quantity × unit_cost)` for all items sold in `[period]` | $ | `transactions` + `catalog` (unit cost) |
| **Labour Cost vs Sales Profit %** | `Total Labour Cost / Actual Sales Profit × 100` where `Total Labour Cost = SUM(hours_worked × hourly_rate)` for `[period]` | % | `shifts` + `staff_rates` |

### Change Badges (▲ / ▼)

| Badge | Formula |
|-------|---------|
| **% change** | `(current_value − comparison_value) / comparison_value × 100` |
| **Comparison period** | User-selected via "vs." pill (prior day, prior same weekday, 4 weeks prior, etc.) |

### Hourly Bar Chart

| Element | Formula |
|---------|---------|
| **Current bars** | `SUM(net_amount)` grouped by `HOUR(transaction_time)` for `[period]` |
| **Comparison bars** | Same formula applied to the comparison period |
| **X-axis** | Hours of operation (e.g., 7am–5pm) |

---

## 2. Overview — Category Breakdown Section

### Line Chart Series

| Series | Formula |
|--------|---------|
| **Cafe** | `SUM(net_amount) WHERE category = 'Bar'` grouped by `DATE(transaction_time)` for `[period]`. UI label = "Cafe", DB value = `Bar` |
| **Retail** | `SUM(net_amount) WHERE category = 'Retail'` grouped by `DATE(transaction_time)` for `[period]` |
| **Cafe vs Retail** | Both lines plotted together on the same axes |

### Bottom KPI Cards (6 cards, 2 rows × 3 cols)

| Card | Formula | Unit |
|------|---------|------|
| **Cafe Net Sales** | `SUM(net_amount) WHERE category = 'Bar'` for `[period]` | $ |
| **Retail Net Sales** | `SUM(net_amount) WHERE category = 'Retail'` for `[period]` | $ |
| **Cafe Sales Profit %** | `(Cafe Net Sales − Cafe COGS) / Cafe Net Sales × 100` | % |
| **Retail Sales Profit %** | `(Retail Net Sales − Retail COGS) / Retail Net Sales × 100` | % |
| **Cafe Labour Cost vs Sales Profit %** | `SUM(hours × rate WHERE staff business_side = 'Bar') / Cafe Sales Profit × 100` | % |
| **Retail Labour Cost vs Sales Profit %** | `SUM(hours × rate WHERE staff business_side = 'Retail') / Retail Sales Profit × 100` | % |

---

## 3. Members

### KPI Cards (5 cards)

| Card | Formula | Unit |
|------|---------|------|
| **Active Members** | `COUNT(DISTINCT member_id) WHERE last_visit_date >= [period_start]` | # |
| **Member Revenue Share** | `SUM(net_amount WHERE member_id IS NOT NULL) / SUM(net_amount) × 100` for `[period]` | % |
| **Avg Lifetime Value** | `SUM(total_spent) / COUNT(DISTINCT member_id)` across all members who have visited at least once | $ |
| **Churn Risk** | `COUNT(DISTINCT member_id) WHERE days_since_last_visit > [at_risk_threshold]` (default: 14 days, configurable in Settings) | # |
| **Loyalty Points** | `SUM(balance)` from `member_loyalty`. Subtext: `COUNT(*)` enrolled | # |

### Charts

| Chart | X-axis | Y-axis | Formula |
|-------|--------|--------|---------|
| **Member vs Non-Member Revenue** (dual line) | Date | $ | Blue line: `SUM(net_amount WHERE member_id IS NOT NULL)` per day. Gray line: `SUM(net_amount WHERE member_id IS NULL)` per day |
| **Transaction Ratio** (sparkline) | Date | % | `COUNT(orders WHERE member_id IS NOT NULL) / COUNT(all orders) × 100` per day |
| **Sales Ratio** (sparkline) | Date | % | `SUM(net_amount WHERE member_id IS NOT NULL) / SUM(net_amount) × 100` per day |
| **Items Ratio** (sparkline) | Date | % | `SUM(quantity WHERE member_id IS NOT NULL) / SUM(quantity) × 100` per day |

### Top Members Table

| Column | Formula |
|--------|---------|
| **Name** | `member.first_name + member.last_name` |
| **Total Spent** | `SUM(net_amount) WHERE member_id = X` (all time) |
| **Visits** | `COUNT(DISTINCT DATE(transaction_time)) WHERE member_id = X` (all time) |
| **Points** | `member_loyalty.balance WHERE customer_id = member.customer_id` |
| **Last Visit** | `MAX(DATE(transaction_time)) WHERE member_id = X` |
| **30d Trend** | Sparkline of `SUM(net_amount) WHERE member_id = X` grouped by week for last 30 days |
| **Status** | Based on `days_since_last_visit`: Active < `[active_threshold]` (default 7d), At Risk < `[at_risk_threshold]` (default 30d), Churned > `[churned_threshold]` (default 45d). All configurable in Settings → Member Criteria |

### Loyalty Insights (below Top Members table)

| Card | Metric | Formula |
|------|--------|---------|
| **Lifetime Points** | Min | `MIN(lifetime_points)` from `member_loyalty` |
| | Max | `MAX(lifetime_points)` from `member_loyalty` |
| | Avg | `ROUND(AVG(lifetime_points))` from `member_loyalty` |
| **Points Redeemed** | Min | `MIN(lifetime_points - balance)` from `member_loyalty` |
| | Max | `MAX(lifetime_points - balance)` from `member_loyalty` |
| | Avg | `ROUND(AVG(lifetime_points - balance))` from `member_loyalty` |
| **Redemption Behaviour** | % Redeemed | `COUNT(*) FILTER (WHERE points_redeemed > 0) / COUNT(*) × 100` |
| | Never | `COUNT(*) FILTER (WHERE points_redeemed = 0)` |
| | Once | `COUNT(*) FILTER (WHERE points_redeemed > 0 AND points_redeemed <= 200)` (one reward = 200 pts) |
| | 2+ times | `COUNT(*) FILTER (WHERE points_redeemed > 200)` |

---

## 4. Inventory

### KPI Cards

| Card | Formula | Unit |
|------|---------|------|
| **Stock Value** | `SUM(current_quantity × unit_cost)` across all products | $ |
| **Retail Value** | `SUM(current_quantity × retail_price)` across all products | $ |
| **Avg Profit Margin** | `SUM(retail_price − unit_cost) / SUM(retail_price) × 100` weighted by quantity | % |
| **Low Stock Items** | `COUNT(products WHERE current_quantity < low_threshold)` — threshold per category from Settings | # |

### Stock Levels Table

| Column | Formula |
|--------|---------|
| **Product** | `product.name` from catalog |
| **Category** | `product.category` from catalog |
| **Qty** | `current_quantity` from inventory |
| **Unit Cost** | `product.unit_cost` from catalog |
| **Price** | `product.retail_price` from catalog |
| **Actual Profit %** | `(avg_selling_price − unit_cost) / avg_selling_price × 100` where `avg_selling_price = SUM(net_amount for this product) / SUM(quantity sold for this product)` over last 30 days. Accounts for discounts. |
| **Potential Profit %** | `(retail_price − unit_cost) / retail_price × 100` — max margin if sold at full price, no discounts |
| **Popularity Rank** | `RANK() OVER (ORDER BY SUM(quantity sold) DESC)` for `[period]`. #1 = most units sold |
| **Actual Profit Rank** | `RANK() OVER (ORDER BY (avg_selling_price − unit_cost) DESC)` for `[period]`. #1 = highest real profit per unit |
| **Days Left** | `current_quantity / avg_daily_sales` where `avg_daily_sales = SUM(quantity sold last 30 days) / 30` |
| **Status** | `Low` if `current_quantity < [low_threshold]`, `Warning` if `< [warning_threshold]`, else `OK`. Thresholds per category from Settings → Inventory Thresholds |

### Color Rules (configurable in Settings)

| Metric | Green | Orange | Red |
|--------|-------|--------|-----|
| Actual Profit % | > `[green_threshold]` (default 40%) | > `[red_threshold]` (default 20%) | ≤ 20% |
| Potential Profit % | Same bands as above | | |
| Rank highlight | Top `[N]` (default 3) shown in blue bold | | |

### Category Insights Charts

| Chart | Formula |
|-------|---------|
| **Stock Available vs Sold (30d)** — horizontal grouped bars | Per category: Dark blue bar = `SUM(current_quantity)`, Light blue bar = `SUM(quantity sold)` last 30 days |
| **Sales Velocity** — line chart | Per category per day: `SUM(quantity sold)` / trading days. Velocity label = `AVG(daily units sold)` with direction arrow: ▲ if last 7d avg > prior 7d avg, → if roughly equal, ▼ if declining |

### Bottom Mini KPI Cards

| Card | Formula |
|------|---------|
| **Fastest Moving** | Product with highest `avg_daily_sales` over last 30 days |
| **Slowest Moving** | Product with lowest `avg_daily_sales` (excluding zero-stock items) |
| **Best Margin** | Product with highest `actual_profit_percent` |
| **Restock Urgent** | Product with lowest `days_left` (excluding items with status = OK) |

### Reorder Suggestions

| Field | Formula |
|-------|---------|
| **Suggested Qty** | `avg_daily_sales × lead_time_days × safety_factor` — where `lead_time_days` and `safety_factor` are from Settings |

---

## 5. Staff

### KPI Cards

| Card | Formula | Unit |
|------|---------|------|
| **Staff Today** | `COUNT(DISTINCT staff_id) WHERE shift includes today` | # |
| **Total Hours** | `SUM(clock_out − clock_in)` for all staff in `[period]` | hours |
| **Labor Cost Ratio** | `SUM(hours_worked × hourly_rate) / Actual Sales Profit × 100` for `[period]`. Target band: 25–35% (configurable in Settings) | % |
| **Revenue per Hour** | `Net Sales / Total Hours` for `[period]` | $/hr |

### Charts

| Chart | X-axis | Y-axis | Formula |
|-------|--------|--------|---------|
| **Labor Cost vs Revenue** (dual axis) | Day | $ / % | Blue bars: `Net Sales` per day. Red line: `Labor Cost Ratio` per day. Green band between 25–35% target |
| **Peak Hour Staffing** (overlay) | Hour (7am–5pm) | # | Gray bars: `COUNT(DISTINCT staff_id on shift)` per hour. Blue line: `COUNT(DISTINCT order_id)` per hour |
| **Staff Coverage** (Gantt) | Day of week (Mon–Sun) | Staff name | Horizontal bars showing start_time → end_time per shift per staff. Each staff member gets a unique color (Holly=blue, Camilla=red, Noah=green, Sarah=amber) |
| **Transactions per Staff** (line) | Date | # | `COUNT(DISTINCT order_id) / COUNT(DISTINCT staff_id on shift)` per day, 7-day smoothed |

### Gap Annotations (Peak Hour Staffing)

| Annotation | Trigger |
|------------|---------|
| **"Overstaffed gap"** | Hours where `staff_count > transactions × [overstaffed_ratio]` (configurable). Highlighted with light red/pink tint |
| **"Understaffed gap"** | Hours where `staff_count < transactions × [understaffed_ratio]`. Highlighted with light orange tint |

---

## 6. SMS Campaigns

### Auto-Enrollment Rules

| Rule Slider | Filter Applied |
|-------------|---------------|
| **Total Spent** | `SUM(net_amount) WHERE member_id = X` between `[min, max]` |
| **Days Since Last Visit** | `CURRENT_DATE − MAX(transaction_date WHERE member_id = X)` ≥ threshold |
| **Total Items** | `SUM(quantity) WHERE member_id = X` between `[min, max]` |
| **Match logic** | ALL = AND (all conditions must match), ANY = OR (any one condition matches) |
| **Members matching** | `COUNT(DISTINCT member_id)` satisfying the active rule conditions |

### Campaign Analytics

| Metric | Formula |
|--------|---------|
| **Sent** | `COUNT(sms_records WHERE campaign_id = X AND status = 'sent')` |
| **Delivered** | `COUNT(sms_records WHERE campaign_id = X AND status = 'delivered')` |
| **Delivered %** | `Delivered / Sent × 100` |
| **Response Rate** | `COUNT(sms_records WHERE campaign_id = X AND member visited within 7 days) / Delivered × 100` |
| **Revenue Impact** | `SUM(net_amount WHERE member_id IN campaign_recipients AND transaction_date BETWEEN send_date AND send_date + 14 days) − avg_expected_spend` where `avg_expected_spend = avg 14-day spend per member before campaign × recipient count` |

---

## 7. Comparison Logic

All sections support "vs." period comparison. The badges show relative change.

| Comparison Option | Formula for Comparison Value |
|-------------------|------------------------------|
| **Prior day** | Same metric for `[period_start − 1 day]` |
| **Prior same weekday** | Same metric for the same weekday in the prior week |
| **Average of last 4 same weekdays** | `AVG(metric)` for the same weekday across the last 4 occurrences (skipping days with zero sales/non-trading days) |
| **4 weeks prior** | Same metric for `[period_start − 28 days]` |
| **52 weeks prior** | Same metric for `[period_start − 364 days]` |
| **Prior year** | Same metric for `[period_start − 1 year]` |

### 7-Day Smoothing

| Setting | Formula |
|---------|---------|
| **7-day moving average** | For any daily metric: `AVG(metric) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)` — eliminates daily noise, shows true trend |
| **Non-trading day filter** | Days where `COUNT(transactions) = 0` are excluded from averages and charts to avoid distorting trends |

---

## 8. Data Sources

| Table | Key Fields Used |
|-------|----------------|
| `transactions` | order_id, member_id, transaction_time, gross_amount, net_amount, discount_amount, refund_amount, quantity, item_name, category |
| `catalog` (Square) | product_id, name, category, retail_price, unit_cost |
| `inventory` (Square) | product_id, current_quantity |
| `members` | member_id, first_name, last_name, email, phone, created_at |
| `member_daily_stats` | member_id, stat_date, total_spent, total_visits, avg_spend_per_visit, days_since_last_visit, visit_frequency_30d, spend_trend_30d |
| `daily_store_stats` | stat_date, total_net_sales, total_transactions, member_tx_ratio, member_sales_ratio, member_items_ratio |
| `shifts` (Square Labor) | staff_id, start_time, end_time, hourly_rate |
| `member_loyalty` | customer_id, loyalty_account_id, balance, lifetime_points, points_redeemed (computed), enrolled_at |
| `staff_roles` | team_member_id, staff_name, job_title, business_side (Bar/Retail), hourly_rate, is_active |
| `sms_campaigns` | campaign_id, name, message, send_date, status |
| `sms_recipients` | campaign_id, member_id, delivery_status |
| `settings` | All configurable thresholds, color bands, targets |
