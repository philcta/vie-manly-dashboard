CREATE TABLE IF NOT EXISTS weekly_hourly_patterns (
    week_start date NOT NULL,
    week_label text NOT NULL,
    hour integer NOT NULL,
    day_type text NOT NULL DEFAULT 'all',
    avg_transactions real NOT NULL DEFAULT 0,
    avg_net_sales real NOT NULL DEFAULT 0,
    total_transactions integer NOT NULL DEFAULT 0,
    total_net_sales real NOT NULL DEFAULT 0,
    days_in_sample integer NOT NULL DEFAULT 0,
    is_peak boolean DEFAULT false,
    pct_of_daily_total real DEFAULT NULL,
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (week_start, hour, day_type)
);

CREATE INDEX IF NOT EXISTS idx_whp_week ON weekly_hourly_patterns (week_start);

ALTER TABLE weekly_hourly_patterns ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_whp" ON weekly_hourly_patterns FOR SELECT TO anon USING (true);
