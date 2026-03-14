CREATE TABLE IF NOT EXISTS weekly_category_stats (
    week_start date NOT NULL,
    week_label text NOT NULL,
    category text NOT NULL,
    side text NOT NULL DEFAULT 'Retail',
    day_type text NOT NULL DEFAULT 'all',
    total_net_sales real NOT NULL DEFAULT 0,
    total_gross_sales real NOT NULL DEFAULT 0,
    total_qty real NOT NULL DEFAULT 0,
    transaction_count integer NOT NULL DEFAULT 0,
    pct_of_total_sales real DEFAULT NULL,
    pct_of_side_sales real DEFAULT NULL,
    rank_by_sales integer DEFAULT NULL,
    category_margin_pct real DEFAULT NULL,
    estimated_gross_profit real DEFAULT NULL,
    wow_sales_change_pct real DEFAULT NULL,
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (week_start, category, day_type)
);

CREATE INDEX IF NOT EXISTS idx_wcs_week ON weekly_category_stats (week_start);
CREATE INDEX IF NOT EXISTS idx_wcs_category ON weekly_category_stats (category, week_start);

ALTER TABLE weekly_category_stats ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_wcs" ON weekly_category_stats FOR SELECT TO anon USING (true);
