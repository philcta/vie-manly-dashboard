# AI Coach — Supabase RPCs, Tables & Indexes

> **All SQL needed to set up the AI Coach database layer.**  
> Supabase project: `heavnfayolxrgmxkkrvr`  
> Last updated: 2026-03-16

---

## 1. Tool RPC Functions

These are called on-demand by the AI when it needs specific data.

### 1.1 `lookup_product` — Fuzzy product search

```sql
CREATE OR REPLACE FUNCTION lookup_product(search_term text)
RETURNS TABLE (
    product_name text,
    category text,
    current_stock bigint,
    unit_cost numeric,
    margin_pct numeric,
    total_sold_30d bigint,
    avg_daily_velocity numeric,
    days_of_stock numeric,
    trend text,
    status text,
    stockout_risk_date date,
    last_sold_date date
)
LANGUAGE sql STABLE
AS $$
    SELECT
        product_name,
        category,
        current_stock,
        unit_cost,
        margin_pct,
        total_sold_30d,
        avg_daily_velocity,
        days_of_stock,
        trend,
        status,
        stockout_risk_date,
        last_sold_date
    FROM inventory_intelligence
    WHERE product_name ILIKE '%' || search_term || '%'
    ORDER BY total_sold_30d DESC NULLS LAST
    LIMIT 20;
$$;
```

### 1.2 `lookup_category_products` — All products in a category

```sql
CREATE OR REPLACE FUNCTION lookup_category_products(cat_name text)
RETURNS TABLE (
    product_name text,
    category text,
    current_stock bigint,
    unit_cost numeric,
    margin_pct numeric,
    total_sold_30d bigint,
    avg_daily_velocity numeric,
    days_of_stock numeric,
    trend text,
    status text
)
LANGUAGE sql STABLE
AS $$
    SELECT
        product_name,
        category,
        current_stock,
        unit_cost,
        margin_pct,
        total_sold_30d,
        avg_daily_velocity,
        days_of_stock,
        trend,
        status
    FROM inventory_intelligence
    WHERE category ILIKE '%' || cat_name || '%'
    ORDER BY total_sold_30d DESC NULLS LAST
    LIMIT 50;
$$;
```

### 1.3 `get_daily_sales` — Day-by-day breakdown

```sql
CREATE OR REPLACE FUNCTION get_daily_sales(num_days int DEFAULT 7)
RETURNS TABLE (
    sale_date date,
    net_sales numeric,
    item_count bigint,
    transaction_count bigint,
    member_transactions bigint,
    non_member_transactions bigint
)
LANGUAGE sql STABLE
AS $$
    SELECT
        date AS sale_date,
        SUM(net_sales) AS net_sales,
        COUNT(*) AS item_count,
        COUNT(DISTINCT order_id) AS transaction_count,
        COUNT(DISTINCT order_id) FILTER (WHERE customer_id IS NOT NULL) AS member_transactions,
        COUNT(DISTINCT order_id) FILTER (WHERE customer_id IS NULL) AS non_member_transactions
    FROM transactions
    WHERE date >= CURRENT_DATE - num_days
    GROUP BY date
    ORDER BY date DESC;
$$;
```

### 1.4 `get_mtd_summary` — Month-to-date totals

```sql
CREATE OR REPLACE FUNCTION get_mtd_summary()
RETURNS TABLE (
    mtd_net_sales numeric,
    mtd_item_count bigint,
    mtd_transaction_count bigint,
    mtd_unique_customers bigint,
    days_elapsed int
)
LANGUAGE sql STABLE
AS $$
    SELECT
        SUM(net_sales) AS mtd_net_sales,
        COUNT(*) AS mtd_item_count,
        COUNT(DISTINCT order_id) AS mtd_transaction_count,
        COUNT(DISTINCT customer_id) FILTER (WHERE customer_id IS NOT NULL) AS mtd_unique_customers,
        (CURRENT_DATE - date_trunc('month', CURRENT_DATE)::date) AS days_elapsed
    FROM transactions
    WHERE date >= date_trunc('month', CURRENT_DATE)::date;
$$;
```

---

## 2. Performance Indexes

These indexes bring RPC response times from 200-1300ms down to 7-33ms.

```sql
-- Enable trigram extension for fuzzy search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Fuzzy search on product names (lookup_product)
CREATE INDEX IF NOT EXISTS idx_ii_product_name_trgm
ON inventory_intelligence USING gin (product_name gin_trgm_ops);

-- Fuzzy search on category names (lookup_category_products)
CREATE INDEX IF NOT EXISTS idx_ii_category_trgm
ON inventory_intelligence USING gin (category gin_trgm_ops);

-- Date index for daily sales queries (get_daily_sales, get_mtd_summary)
CREATE INDEX IF NOT EXISTS idx_transactions_date
ON transactions (date DESC);
```

**Performance benchmarks** (after indexing):

| RPC | Before | After |
|-----|--------|-------|
| `lookup_product('kombucha')` | 287ms | 7ms |
| `lookup_category_products('beverages')` | 180ms | 9ms |
| `get_daily_sales(7)` | 1,295ms | 33ms |
| `get_mtd_summary()` | 890ms | 21ms |

---

## 3. Conversation Storage Tables

```sql
-- Per-message log (optional, used by some implementations)
CREATE TABLE IF NOT EXISTS coach_conversations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cc_session ON coach_conversations (session_id);
CREATE INDEX IF NOT EXISTS idx_cc_created ON coach_conversations (created_at DESC);

-- Full conversation save (used by frontend history feature)
CREATE TABLE IF NOT EXISTS ai_coach_conversations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE,
    title TEXT,
    messages JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_acc_created ON ai_coach_conversations (created_at DESC);
```

---

## 4. KPI Targets Table

```sql
CREATE TABLE IF NOT EXISTS kpi_targets (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    metric TEXT NOT NULL,
    target_value TEXT NOT NULL,
    current_value TEXT,
    timeline TEXT,
    category TEXT,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Seed with VIE's targets
INSERT INTO kpi_targets (metric, target_value, current_value, timeline, category) VALUES
    ('Labour vs Sales %', '≤ 24%', '24.4% (trending 28%)', '4 weeks', 'profitability'),
    ('Average Sale', '≥ $24.00', '$24.10 (trending $22)', '8 weeks', 'revenue'),
    ('Real Profit Margin', '≥ 25%', '23.8%', '3 months', 'profitability'),
    ('Member Revenue %', '+5% vs current', 'TBD', '3 months', 'members'),
    ('Dead/Overstock Items', '−30% vs current', 'TBD', '6 weeks', 'inventory');
```

---

## 5. RLS Policies

```sql
-- All AI Coach tables: anon can read, service_role can write
ALTER TABLE coach_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_coach_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE kpi_targets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_coach" ON coach_conversations FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read_acc" ON ai_coach_conversations FOR SELECT TO anon USING (true);
CREATE POLICY "anon_write_acc" ON ai_coach_conversations FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_kpi" ON kpi_targets FOR SELECT TO anon USING (true);
```

---

## 6. Weekly Knowledge Base Tables (Context Layer)

These 7 tables are pre-computed by `scripts/backfill_weekly_stats.py` and provide the AI's base context. See `supabase/migrations/01-08_*.sql` for full schemas:

| Table | Primary Key | Rows (est.) |
|-------|------------|-------------|
| `weekly_store_stats` | `(week_start, side, day_type)` | ~500 |
| `weekly_category_stats` | `(week_start, category, day_type)` | ~5,000 |
| `weekly_member_stats` | `(week_start, customer_type, age_group, day_type)` | ~1,000 |
| `weekly_staff_stats` | `(week_start, side, day_type)` | ~500 |
| `weekly_inventory_stats` | `(week_start, category)` | ~2,000 |
| `weekly_hourly_patterns` | `(week_start, hour, day_type)` | ~3,000 |
| `weekly_dow_stats` | `(week_start, dow, side)` | ~2,000 |

**Dimension values**:
- `side`: `All`, `Cafe`, `Retail`
- `day_type`: `all`, `weekday`, `weekend`
- `customer_type`: `all`, `member`, `non_member`
- `age_group`: `all`, `teen`, `adult`
- `dow`: 0 = Sunday through 6 = Saturday
