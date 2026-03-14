CREATE TABLE IF NOT EXISTS weekly_dow_stats (
    week_start date NOT NULL,
    week_label text NOT NULL,
    dow integer NOT NULL,
    dow_name text NOT NULL,
    side text NOT NULL DEFAULT 'All',
    total_net_sales real NOT NULL DEFAULT 0,
    total_gross_sales real NOT NULL DEFAULT 0,
    total_transactions integer NOT NULL DEFAULT 0,
    total_items real NOT NULL DEFAULT 0,
    avg_transaction_value real NOT NULL DEFAULT 0,
    unique_customers integer NOT NULL DEFAULT 0,
    member_net_sales real NOT NULL DEFAULT 0,
    member_transactions integer NOT NULL DEFAULT 0,
    member_sales_ratio real NOT NULL DEFAULT 0,
    total_labour_cost real DEFAULT NULL,
    labour_pct real DEFAULT NULL,
    total_hours real DEFAULT NULL,
    rank_by_sales integer DEFAULT NULL,
    pct_of_weekly_sales real DEFAULT NULL,
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (week_start, dow, side)
);

CREATE INDEX IF NOT EXISTS idx_wdow_week ON weekly_dow_stats (week_start);
CREATE INDEX IF NOT EXISTS idx_wdow_dow ON weekly_dow_stats (dow, week_start);

ALTER TABLE weekly_dow_stats ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_wdow" ON weekly_dow_stats FOR SELECT TO anon USING (true);
