-- ============================================
-- daily_item_summary table
-- Pre-computed daily aggregates per item/category
-- ============================================

CREATE TABLE IF NOT EXISTS daily_item_summary (
    id BIGSERIAL PRIMARY KEY,
    date TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    item TEXT NOT NULL DEFAULT '',
    total_qty REAL NOT NULL DEFAULT 0,
    total_net_sales REAL NOT NULL DEFAULT 0,
    total_gross_sales REAL NOT NULL DEFAULT 0,
    total_discounts REAL NOT NULL DEFAULT 0,
    total_tax REAL NOT NULL DEFAULT 0,
    transaction_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Unique constraint for upserts
ALTER TABLE daily_item_summary
ADD CONSTRAINT daily_item_summary_unique
UNIQUE (date, category, item);

-- Index for fast date-range queries
CREATE INDEX IF NOT EXISTS idx_daily_item_summary_date
ON daily_item_summary (date);

-- Enable Row Level Security (match other tables)
ALTER TABLE daily_item_summary ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
CREATE POLICY "service_role_all" ON daily_item_summary
    FOR ALL USING (true) WITH CHECK (true);
