-- ============================================
-- 1. ALTER members table — add Square API fields
-- ============================================

ALTER TABLE members ADD COLUMN IF NOT EXISTS birthday TEXT;
ALTER TABLE members ADD COLUMN IF NOT EXISTS company_name TEXT;
ALTER TABLE members ADD COLUMN IF NOT EXISTS address_line_1 TEXT;
ALTER TABLE members ADD COLUMN IF NOT EXISTS locality TEXT;
ALTER TABLE members ADD COLUMN IF NOT EXISTS postal_code TEXT;
ALTER TABLE members ADD COLUMN IF NOT EXISTS creation_source TEXT;
ALTER TABLE members ADD COLUMN IF NOT EXISTS group_ids TEXT;      -- JSON array as text
ALTER TABLE members ADD COLUMN IF NOT EXISTS segment_ids TEXT;    -- JSON array as text
ALTER TABLE members ADD COLUMN IF NOT EXISTS updated_at TEXT;


-- ============================================
-- 2. member_daily_stats — per-member daily snapshot
-- ============================================

CREATE TABLE IF NOT EXISTS member_daily_stats (
    id BIGSERIAL PRIMARY KEY,
    square_customer_id TEXT NOT NULL,
    date TEXT NOT NULL,

    -- Cumulative totals (since first visit)
    total_spent REAL NOT NULL DEFAULT 0,
    total_items INTEGER NOT NULL DEFAULT 0,
    total_visits INTEGER NOT NULL DEFAULT 0,
    total_transactions INTEGER NOT NULL DEFAULT 0,

    -- This day only
    day_spent REAL NOT NULL DEFAULT 0,
    day_items INTEGER NOT NULL DEFAULT 0,
    day_transactions INTEGER NOT NULL DEFAULT 0,

    -- Computed averages
    avg_spend_per_visit REAL NOT NULL DEFAULT 0,
    avg_items_per_visit REAL NOT NULL DEFAULT 0,

    -- Recency / trend
    days_since_last_visit INTEGER NOT NULL DEFAULT 0,
    visit_frequency_30d REAL NOT NULL DEFAULT 0,
    spend_trend_30d REAL NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'member_daily_stats_unique'
    ) THEN
        ALTER TABLE member_daily_stats
        ADD CONSTRAINT member_daily_stats_unique UNIQUE (square_customer_id, date);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_member_daily_stats_date
ON member_daily_stats (date);

CREATE INDEX IF NOT EXISTS idx_member_daily_stats_customer
ON member_daily_stats (square_customer_id);

ALTER TABLE member_daily_stats ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all" ON member_daily_stats;
CREATE POLICY "service_role_all" ON member_daily_stats
    FOR ALL USING (true) WITH CHECK (true);


-- ============================================
-- 3. daily_store_stats — store-level daily aggregates
--    (member vs non-member split)
-- ============================================

CREATE TABLE IF NOT EXISTS daily_store_stats (
    id BIGSERIAL PRIMARY KEY,
    date TEXT NOT NULL UNIQUE,

    -- Total store
    total_transactions INTEGER NOT NULL DEFAULT 0,
    total_net_sales REAL NOT NULL DEFAULT 0,
    total_items INTEGER NOT NULL DEFAULT 0,
    total_unique_customers INTEGER NOT NULL DEFAULT 0,

    -- Member split
    member_transactions INTEGER NOT NULL DEFAULT 0,
    member_net_sales REAL NOT NULL DEFAULT 0,
    member_items INTEGER NOT NULL DEFAULT 0,
    member_unique_customers INTEGER NOT NULL DEFAULT 0,

    -- Non-member split
    non_member_transactions INTEGER NOT NULL DEFAULT 0,
    non_member_net_sales REAL NOT NULL DEFAULT 0,
    non_member_items INTEGER NOT NULL DEFAULT 0,

    -- Ratios (precomputed for fast charting)
    member_tx_ratio REAL NOT NULL DEFAULT 0,       -- member_transactions / total_transactions
    member_sales_ratio REAL NOT NULL DEFAULT 0,    -- member_net_sales / total_net_sales
    member_items_ratio REAL NOT NULL DEFAULT 0,    -- member_items / total_items

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_store_stats_date
ON daily_store_stats (date);

ALTER TABLE daily_store_stats ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all" ON daily_store_stats;
CREATE POLICY "service_role_all" ON daily_store_stats
    FOR ALL USING (true) WITH CHECK (true);
