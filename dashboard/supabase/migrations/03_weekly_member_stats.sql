CREATE TABLE IF NOT EXISTS weekly_member_stats (
    week_start date NOT NULL,
    week_label text NOT NULL,
    customer_type text NOT NULL DEFAULT 'all',
    age_group text NOT NULL DEFAULT 'all',
    day_type text NOT NULL DEFAULT 'all',
    unique_customers integer NOT NULL DEFAULT 0,
    total_visits integer NOT NULL DEFAULT 0,
    total_transactions integer NOT NULL DEFAULT 0,
    total_net_sales real NOT NULL DEFAULT 0,
    active_members integer DEFAULT NULL,
    repeat_members integer DEFAULT NULL,
    one_off_members integer DEFAULT NULL,
    new_enrollments integer DEFAULT NULL,
    avg_spend_per_visit real NOT NULL DEFAULT 0,
    avg_visits_per_customer real NOT NULL DEFAULT 0,
    member_revenue_share real DEFAULT NULL,
    member_tx_share real DEFAULT NULL,
    total_points_earned integer DEFAULT NULL,
    total_points_redeemed integer DEFAULT NULL,
    rewards_created integer DEFAULT NULL,
    total_loyalty_balance integer DEFAULT NULL,
    redemption_rate_pct real DEFAULT NULL,
    active_count integer DEFAULT NULL,
    cooling_count integer DEFAULT NULL,
    at_risk_count integer DEFAULT NULL,
    churned_count integer DEFAULT NULL,
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (week_start, customer_type, age_group, day_type)
);

CREATE INDEX IF NOT EXISTS idx_wms_week ON weekly_member_stats (week_start);

ALTER TABLE weekly_member_stats ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_wms" ON weekly_member_stats FOR SELECT TO anon USING (true);
