CREATE TABLE IF NOT EXISTS weekly_staff_stats (
    week_start date NOT NULL,
    week_label text NOT NULL,
    side text NOT NULL DEFAULT 'All',
    day_type text NOT NULL DEFAULT 'all',
    total_shifts integer NOT NULL DEFAULT 0,
    total_hours real NOT NULL DEFAULT 0,
    total_labour_cost real NOT NULL DEFAULT 0,
    teen_cost real DEFAULT 0,
    teen_hours real DEFAULT 0,
    adult_cost real DEFAULT 0,
    adult_hours real DEFAULT 0,
    weekday_cost real DEFAULT 0,
    weekday_hours real DEFAULT 0,
    saturday_cost real DEFAULT 0,
    saturday_hours real DEFAULT 0,
    sunday_cost real DEFAULT 0,
    sunday_hours real DEFAULT 0,
    public_holiday_cost real DEFAULT 0,
    public_holiday_hours real DEFAULT 0,
    labour_cost_ratio real DEFAULT NULL,
    revenue_per_hour real DEFAULT NULL,
    unique_staff integer NOT NULL DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (week_start, side, day_type)
);

CREATE INDEX IF NOT EXISTS idx_wstaff_week ON weekly_staff_stats (week_start);

ALTER TABLE weekly_staff_stats ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_wstaff" ON weekly_staff_stats FOR SELECT TO anon USING (true);
