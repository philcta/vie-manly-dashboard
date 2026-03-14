-- ============================================================================
-- AI Coach Knowledge Base — Weekly Pre-computed Tables
-- 8 tables for comprehensive business analytics
-- Run via Supabase SQL Editor or Python migration script
-- ============================================================================

-- ────────────────────────────────────────────────────────────────────────────
-- Table 1: weekly_store_stats
-- Core business pulse — one row per week × side × day_type
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS weekly_store_stats (
    week_start date NOT NULL,
    week_label text NOT NULL,
    side text NOT NULL DEFAULT 'All',
    day_type text NOT NULL DEFAULT 'all',

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

    -- Margin & Profit
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

    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (week_start, side, day_type)
);

CREATE INDEX IF NOT EXISTS idx_wss_week ON weekly_store_stats (week_start);


-- ────────────────────────────────────────────────────────────────────────────
-- Table 2: weekly_category_stats
-- Per-category weekly breakdown with rank and trends
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS weekly_category_stats (
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
    pct_of_side_sales real DEFAULT NULL,
    rank_by_sales integer DEFAULT NULL,

    -- Profitability
    category_margin_pct real DEFAULT NULL,
    estimated_gross_profit real DEFAULT NULL,

    -- Trend
    wow_sales_change_pct real DEFAULT NULL,

    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (week_start, category, day_type)
);

CREATE INDEX IF NOT EXISTS idx_wcs_week ON weekly_category_stats (week_start);
CREATE INDEX IF NOT EXISTS idx_wcs_category ON weekly_category_stats (category, week_start);


-- ────────────────────────────────────────────────────────────────────────────
-- Table 3: weekly_member_stats
-- Member/loyalty metrics with activity status tracking
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS weekly_member_stats (
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
    active_members integer DEFAULT NULL,
    repeat_members integer DEFAULT NULL,
    one_off_members integer DEFAULT NULL,
    new_enrollments integer DEFAULT NULL,

    -- Averages
    avg_spend_per_visit real NOT NULL DEFAULT 0,
    avg_visits_per_customer real NOT NULL DEFAULT 0,
    member_revenue_share real DEFAULT NULL,
    member_tx_share real DEFAULT NULL,

    -- Loyalty
    total_points_earned integer DEFAULT NULL,
    total_points_redeemed integer DEFAULT NULL,
    rewards_created integer DEFAULT NULL,
    total_loyalty_balance integer DEFAULT NULL,
    redemption_rate_pct real DEFAULT NULL,

    -- Churn / Activity
    active_count integer DEFAULT NULL,
    cooling_count integer DEFAULT NULL,
    at_risk_count integer DEFAULT NULL,
    churned_count integer DEFAULT NULL,

    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (week_start, customer_type, age_group, day_type)
);

CREATE INDEX IF NOT EXISTS idx_wms_week ON weekly_member_stats (week_start);


-- ────────────────────────────────────────────────────────────────────────────
-- Table 4: weekly_staff_stats
-- Labour cost analysis by side, day type, and age group
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS weekly_staff_stats (
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
    labour_cost_ratio real DEFAULT NULL,
    revenue_per_hour real DEFAULT NULL,

    -- Staff count
    unique_staff integer NOT NULL DEFAULT 0,

    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (week_start, side, day_type)
);

CREATE INDEX IF NOT EXISTS idx_wstaff_week ON weekly_staff_stats (week_start);


-- ────────────────────────────────────────────────────────────────────────────
-- Table 5: weekly_inventory_stats
-- Inventory snapshots per category per week
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS weekly_inventory_stats (
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

    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (week_start, category)
);

CREATE INDEX IF NOT EXISTS idx_winv_week ON weekly_inventory_stats (week_start);


-- ────────────────────────────────────────────────────────────────────────────
-- Table 6: weekly_hourly_patterns
-- Hourly transaction/sales patterns averaged per week
-- ────────────────────────────────────────────────────────────────────────────
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


-- ────────────────────────────────────────────────────────────────────────────
-- Table 7: weekly_dow_stats
-- Day-of-week patterns within each week
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS weekly_dow_stats (
    week_start date NOT NULL,
    week_label text NOT NULL,
    dow integer NOT NULL,           -- 0=Sunday, 1=Monday, ..., 6=Saturday
    dow_name text NOT NULL,         -- 'Monday', 'Tuesday', etc.
    side text NOT NULL DEFAULT 'All',

    -- Sales
    total_net_sales real NOT NULL DEFAULT 0,
    total_gross_sales real NOT NULL DEFAULT 0,
    total_transactions integer NOT NULL DEFAULT 0,
    total_items real NOT NULL DEFAULT 0,
    avg_transaction_value real NOT NULL DEFAULT 0,
    unique_customers integer NOT NULL DEFAULT 0,

    -- Member split
    member_net_sales real NOT NULL DEFAULT 0,
    member_transactions integer NOT NULL DEFAULT 0,
    member_sales_ratio real NOT NULL DEFAULT 0,

    -- Labour
    total_labour_cost real DEFAULT NULL,
    labour_pct real DEFAULT NULL,
    total_hours real DEFAULT NULL,

    -- Rank within week
    rank_by_sales integer DEFAULT NULL,
    pct_of_weekly_sales real DEFAULT NULL,

    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (week_start, dow, side)
);

CREATE INDEX IF NOT EXISTS idx_wdow_week ON weekly_dow_stats (week_start);
CREATE INDEX IF NOT EXISTS idx_wdow_dow ON weekly_dow_stats (dow, week_start);


-- ────────────────────────────────────────────────────────────────────────────
-- Table 8: coach_conversations
-- AI coach conversation memory
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS coach_conversations (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id text NOT NULL,
    role text NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content text NOT NULL,
    context_snapshot jsonb,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_coach_conv_session ON coach_conversations (session_id, created_at);


-- ────────────────────────────────────────────────────────────────────────────
-- RLS Policies — all tables
-- ────────────────────────────────────────────────────────────────────────────

-- weekly_store_stats
ALTER TABLE weekly_store_stats ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_wss" ON weekly_store_stats FOR SELECT TO anon USING (true);

-- weekly_category_stats
ALTER TABLE weekly_category_stats ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_wcs" ON weekly_category_stats FOR SELECT TO anon USING (true);

-- weekly_member_stats
ALTER TABLE weekly_member_stats ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_wms" ON weekly_member_stats FOR SELECT TO anon USING (true);

-- weekly_staff_stats
ALTER TABLE weekly_staff_stats ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_wstaff" ON weekly_staff_stats FOR SELECT TO anon USING (true);

-- weekly_inventory_stats
ALTER TABLE weekly_inventory_stats ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_winv" ON weekly_inventory_stats FOR SELECT TO anon USING (true);

-- weekly_hourly_patterns
ALTER TABLE weekly_hourly_patterns ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_whp" ON weekly_hourly_patterns FOR SELECT TO anon USING (true);

-- weekly_dow_stats
ALTER TABLE weekly_dow_stats ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_wdow" ON weekly_dow_stats FOR SELECT TO anon USING (true);

-- coach_conversations
ALTER TABLE coach_conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_coach" ON coach_conversations FOR SELECT TO anon USING (true);
