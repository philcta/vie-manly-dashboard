CREATE TABLE IF NOT EXISTS weekly_inventory_stats (
    week_start date NOT NULL,
    week_label text NOT NULL,
    category text NOT NULL,
    side text NOT NULL DEFAULT 'Retail',
    total_skus integer DEFAULT 0,
    in_stock_skus integer DEFAULT 0,
    zero_stock_skus integer DEFAULT 0,
    stock_value_gst real DEFAULT 0,
    stock_value_ex_gst real DEFAULT 0,
    retail_value real DEFAULT 0,
    units_sold_7d real DEFAULT 0,
    units_sold_30d real DEFAULT 0,
    units_sold_90d real DEFAULT 0,
    revenue_30d real DEFAULT 0,
    sales_velocity real DEFAULT NULL,
    days_of_stock real DEFAULT NULL,
    sell_through_pct real DEFAULT NULL,
    critical_count integer DEFAULT 0,
    low_count integer DEFAULT 0,
    watch_count integer DEFAULT 0,
    overstock_count integer DEFAULT 0,
    dead_count integer DEFAULT 0,
    category_margin_pct real DEFAULT NULL,
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (week_start, category)
);

CREATE INDEX IF NOT EXISTS idx_winv_week ON weekly_inventory_stats (week_start);

ALTER TABLE weekly_inventory_stats ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_winv" ON weekly_inventory_stats FOR SELECT TO anon USING (true);
