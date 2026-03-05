# Staff Analytics — Square Labor API → Supabase

## What Square Gives Us

### 1. Team Members (Team API)
| Field | Description |
|-------|-------------|
| `id` | Staff member ID |
| `given_name` / `family_name` | Name |
| `email_address` | Email |
| `phone_number` | Phone |
| `status` | ACTIVE / INACTIVE |
| `is_owner` | Store owner flag |
| `created_at` | When they joined |

### 2. Shifts / Timecards (Labor API)
| Field | Description |
|-------|-------------|
| `id` | Shift ID |
| `team_member_id` | Who worked |
| `start_at` / `end_at` | Clock in/out (UTC) |
| `status` | OPEN (clocked in) / CLOSED (completed) |
| `wage.title` | Job title (e.g., "Barista", "Manager") |
| `wage.hourly_rate` | Hourly pay rate |
| `breaks[]` | Break start/end/duration |
| `declared_cash_tip_money` | Cash tips declared |

### 3. Wages (Labor API)
| Field | Description |
|-------|-------------|
| `team_member_id` | Staff member |
| `title` | Job title |
| `hourly_rate` | Pay rate per hour |

---

## Supabase Tables

### `staff_members`
```sql
CREATE TABLE staff_members (
    id BIGSERIAL PRIMARY KEY,
    square_team_member_id TEXT NOT NULL UNIQUE,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    phone TEXT,
    status TEXT,           -- ACTIVE / INACTIVE
    is_owner BOOLEAN DEFAULT FALSE,
    created_at_square TEXT,
    job_title TEXT,
    hourly_rate REAL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `staff_shifts`
```sql
CREATE TABLE staff_shifts (
    id BIGSERIAL PRIMARY KEY,
    square_shift_id TEXT NOT NULL UNIQUE,
    square_team_member_id TEXT NOT NULL,
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ,
    status TEXT,            -- OPEN / CLOSED
    job_title TEXT,
    hourly_rate REAL,
    total_hours REAL,       -- computed: end - start - breaks
    total_break_minutes INTEGER DEFAULT 0,
    labor_cost REAL,        -- computed: total_hours × hourly_rate
    tips REAL DEFAULT 0,
    date TEXT,              -- YYYY-MM-DD (Sydney time)
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `daily_labor_stats` (pre-aggregated for charts)
```sql
CREATE TABLE daily_labor_stats (
    id BIGSERIAL PRIMARY KEY,
    date TEXT NOT NULL UNIQUE,
    
    -- Staff counts
    total_staff INTEGER NOT NULL DEFAULT 0,
    
    -- Hours
    total_hours REAL NOT NULL DEFAULT 0,
    avg_hours_per_staff REAL NOT NULL DEFAULT 0,
    
    -- Costs
    total_labor_cost REAL NOT NULL DEFAULT 0,
    total_tips REAL NOT NULL DEFAULT 0,
    
    -- Revenue (from daily_store_stats)
    total_net_sales REAL NOT NULL DEFAULT 0,
    
    -- Key ratios
    labor_cost_ratio REAL NOT NULL DEFAULT 0,       -- labor_cost / net_sales
    revenue_per_labor_hour REAL NOT NULL DEFAULT 0,  -- net_sales / total_hours
    cost_per_transaction REAL NOT NULL DEFAULT 0,    -- labor_cost / transactions
    transactions_per_staff REAL NOT NULL DEFAULT 0,  -- transactions / staff_count
    items_per_labor_hour REAL NOT NULL DEFAULT 0,    -- items_sold / total_hours
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Recommended Charts (React Dashboard)

### Operational Efficiency
| Chart | Type | What It Shows |
|-------|------|---------------|
| **Labor Cost Ratio** | Area chart | Labor cost as % of net sales over time (target: 25-35%) |
| **Revenue per Labor Hour** | Line chart | $/hour generated — are you getting more efficient? |
| **Cost per Transaction** | Line chart | How much staff cost per sale |

### Staffing Optimization
| Chart | Type | What It Shows |
|-------|------|---------------|
| **Staff vs Revenue Heatmap** | Calendar heatmap | Overstaffed days (high cost, low revenue) highlighted red |
| **Hourly Coverage** | Stacked bar (by hour) | Staff on floor vs transactions per hour — find gaps |
| **Peak Hour Staffing** | Overlay chart | Transaction volume vs staff count by hour of day |
| **Optimal Staff Calculator** | KPI gauge | Based on revenue/staff ratio, suggest ideal headcount |

### Team Performance
| Chart | Type | What It Shows |
|-------|------|---------------|
| **Staff Leaderboard** | Table with sparklines | Hours worked, tips earned, shifts per week |
| **Shift Pattern** | Gantt-style timeline | Who works when — visualize coverage gaps |
| **Overtime Alert** | KPI cards | Staff approaching overtime threshold |

### Trend Analysis
| Chart | Type | What It Shows |
|-------|------|---------------|
| **Labor Cost Trend** | Dual-axis line | Labor cost (bars) vs net sales (line) — divergence = problem |
| **Transactions per Staff** | Line chart | Productivity trend over time |
| **Weekend vs Weekday** | Grouped bar | Compare staffing efficiency: weekdays vs weekends |

---

## Key Metrics to Track

| Metric | Formula | Healthy Range |
|--------|---------|--------------|
| **Labor Cost Ratio** | Labor Cost ÷ Net Sales | 25-35% for café |
| **Revenue per Labor Hour** | Net Sales ÷ Total Hours | Track trend (↑ = good) |
| **Transactions per Staff** | Transactions ÷ Staff Count | Higher = more productive |
| **Items per Labor Hour** | Items Sold ÷ Total Hours | Track trend (↑ = good) |
| **Avg Shift Length** | Total Hours ÷ Shifts | Monitor consistency |

---

## Implementation Steps

1. **Create Supabase tables** (SQL above)
2. **Add `sync_labor()` to `square_sync.py`** — pull team members + shifts
3. **Backfill historical shifts** (Square keeps shift data)
4. **Compute `daily_labor_stats`** by joining with `daily_store_stats`
5. **Build charts in React** (when we migrate)

---

## Requirements

- Square API permission: `EMPLOYEES_READ`, `TIMECARDS_READ`
- Your Square account must have **Team Management** enabled
- Staff must clock in/out via Square POS for shift data to exist
