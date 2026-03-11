# Denoux Dashboard — Business Formulas Reference

## 1. Sales Metrics

### Net Sales
```
Net Sales = SUM(net_sales) from transactions for [period]
```
- Source: `daily_store_stats.total_net_sales`
- Excludes discounts, refunds. Includes GST.

### Gross Sales
```
Gross Sales = SUM(gross_sales) from transactions for [period]
```
- Source: `daily_store_stats.total_gross_sales`
- Pre-discount, pre-refund amounts.

### Cafe / Retail Net Sales
```
Cafe Net Sales = SUM(net_sales) WHERE category side = 'Cafe'
Retail Net Sales = SUM(net_sales) WHERE category side = 'Retail'
```
- Source: `get_category_daily()` RPC → groups by `category_mappings.side`

### Average Sale
```
Avg Sale = Total Net Sales / Total Transactions
```
- Source: Computed client-side from `aggregateStats()`

---

## 2. Transaction Metrics

### Total Transactions
```
Total Transactions = SUM(total_transactions) from daily_store_stats for [period]
```

### Unique Customers
```
Unique Customers = SUM(total_unique_customers) from daily_store_stats for [period]
```

---

## 3. Profit & Margin Metrics

### Avg Profit Margin (Inventory-based)
```
Avg Profit Margin = (Retail Value - Stock Value) / Retail Value × 100
```
- Uses inventory cost (GST-inclusive) vs retail price
- Source: Computed at category level from `fetchCategorySalesTotals()`

### Real Profit Margin
```
Real Profit Margin = Avg Profit Margin - Labour Cost %
```
- Combines inventory margin with labour burden

### Real Profit ($)
```
Real Profit = Net Sales × (Real Profit Margin / 100)
```

### Category Margin (per-category)
```
Category Margin = (Avg Selling Price - Unit Cost) / Avg Selling Price × 100
```
- `Avg Selling Price = total_net_sales / total_qty` (from transactions)
- `Unit Cost = default_unit_cost × 1.10` (if GST-applicable, source: `tax_gst_10 = 'Y'`)

---

## 4. Labour Metrics

### Labour Cost
```
Labour Cost = SUM(labour_cost) from staff_shifts for [period]
```
- Source: `staff_shifts.labour_cost` (pre-computed from hours × rate)
- Rates applied: weekday, Saturday, Sunday, Public Holiday

### Labour vs Sales %
```
Labour % = Total Labour Cost / Total Net Sales × 100
```
- Denominator is total store net sales, not cafe or retail alone

### Labour Cost Split (Cafe / Retail)
```
Cafe Labour = SUM(labour_cost) WHERE business_side = 'Cafe'
Retail Labour = SUM(labour_cost) WHERE business_side = 'Retail'
```
- 80/20 Barista split: Default 80% Cafe, 20% Retail for Barista role

---

## 5. Member Metrics

### Active Members
```
Active Members = COUNT(DISTINCT customer_id) from transactions WHERE customer_id IS NOT NULL for [period]
```

### Member Revenue %
```
Member Revenue % = member_net_sales / total_net_sales × 100
```
- Source: `daily_store_stats.member_sales_ratio` (pre-computed)

### Avg Spend per Visit
```
Avg Spend/Visit = member_net_sales / member_transactions
```

### Member Status Classification
```
Active:  days_since_last_visit ≤ 14
Cooling: 14 < days_since_last_visit ≤ 30
At Risk: 30 < days_since_last_visit ≤ 45
Churned: days_since_last_visit > 45
```

### Spend Trend (30d vs All-time)
```
Spend Drop % = (alltime_avg_spend - last30_avg_spend) / alltime_avg_spend × 100
```
- Positive = spending decreased, Negative = spending increased

---

## 6. Inventory Metrics

### Stock Value (GST inc.)
```
Stock Value = SUM(qty × unit_cost) for positive-stock items
Unit Cost = default_unit_cost × 1.10 (if GST applicable)
```

### Retail Value
```
Retail Value = SUM(qty × retail_price) for positive-stock items
```

### Sales Velocity
```
Sales Velocity = units_sold_30d / 30 (units per day)
```
- Source: `inventory_intelligence.sales_velocity`

### Days of Stock
```
Days of Stock = current_quantity / sales_velocity
```

### Sell Through %
```
Sell Through = units_sold / (units_sold + current_quantity) × 100
```

### Reorder Alert Classification
```
CRITICAL: days_of_stock < 3 AND sales_velocity > 0
LOW:      days_of_stock < 7 AND sales_velocity > 0
WATCH:    days_of_stock < 14 AND sales_velocity > 0
OVERSTOCK: days_of_stock > 90
DEAD:     sales_velocity = 0 AND current_quantity > 0 AND last_sold > 30 days ago
OK:       all other cases
```

---

## 7. Comparison Period Logic

### Prior Period
```
Duration = endDate - startDate + 1 days
Prior End = startDate - 1
Prior Start = Prior End - Duration + 1
```

### Same Period Last Year (SPLY)
```
SPLY Start = startDate - 1 year
SPLY End = endDate - 1 year
```

### Prior FY
```
Prior FY Start = July 1 of (current FY year - 1)
Prior FY End = June 30 of current FY year
```

### Change Calculation
```
Change % = (current - comparison) / comparison × 100
```
- When comparison = 0: returns null (N/A badge)
- For cost ratios (Labour %): colors are inverted (increase = red)

---

## 8. Chart Metrics

### Moving Average (3-month / 90-day)
```
3mo Avg = SUM(values in trailing 90-day window) / COUNT(values in window)
```
- Uses 6-month historical lookback data
- Warm-up period: suppressed before 2025-11-20 (90 days after opening)

### Linear Trend
```
Trend = Linear regression (least squares) across all data points in the period
```
- Extrapolates the best-fit line from data points
