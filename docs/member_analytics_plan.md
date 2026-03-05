# Member Analytics & SMS Marketing — Implementation Plan

> **Status**: ✅ Code pushed. SQL + backfill needed.

## 1. Enhanced `members` Table (SMS Marketing Ready)

Currently stored: `square_customer_id`, `first_name`, `last_name`, `email_address`, `phone_number`, `creation_date`, `customer_note`, `reference_id`

### New columns to add from Square API:

| Column | Source | SMS Use |
|--------|--------|---------|
| `birthday` | `customer.birthday` | Birthday promos 🎂 |
| `company_name` | `customer.company_name` | B2B segmentation |
| `address_line_1` | `customer.address.address_line_1` | Local vs tourist |
| `locality` | `customer.address.locality` | Suburb targeting |
| `postal_code` | `customer.address.postal_code` | Geo campaigns |
| `creation_source` | `customer.creation_source` | How they signed up |
| `group_ids` | `customer.group_ids` | Square groups |
| `segment_ids` | `customer.segment_ids` | Square segments |
| `updated_at` | `customer.updated_at` | Track freshness |

## 2. New Table: `member_daily_stats` (Behavioral Time Series)

One row per member per day. Updated daily by the sync job.

| Column | Type | Description |
|--------|------|-------------|
| `square_customer_id` | text | FK to members |
| `date` | text | YYYY-MM-DD |
| `total_spent` | real | Cumulative $ spent since first visit |
| `total_items` | integer | Cumulative items purchased |
| `total_visits` | integer | Cumulative visit count (unique dates with a purchase) |
| `total_transactions` | integer | Cumulative transaction count |
| `day_spent` | real | $ spent on this specific day |
| `day_items` | integer | Items purchased this specific day |
| `day_transactions` | integer | Transactions on this specific day |
| `avg_spend_per_visit` | real | total_spent / total_visits |
| `avg_items_per_visit` | real | total_items / total_visits |
| `days_since_last_visit` | integer | Calendar days since previous visit |
| `visit_frequency_30d` | real | Visits in last 30 days |
| `spend_trend_30d` | real | Avg daily spend over last 30 days |

### Why daily snapshots?

- **Temporal vision**: See if a member is coming more/less often over time
- **Trend detection**: `visit_frequency_30d` dropping = churn risk
- **Campaign targeting**: "Hasn't visited in 14 days" → send SMS
- **Charts**: Line charts showing member behavior evolution

### Estimated size:
- ~2,000 members × 365 days = **730K rows/year**
- Each row ~200 bytes = **~146 MB/year** (well within Supabase free tier)

## 3. New Table: `daily_store_stats` (Member vs Non-Member Ratios)

One row per day. Tracks store-wide member vs non-member split.

| Column | Type | Description |
|--------|------|-------------|
| `date` | text PK | YYYY-MM-DD |
| `total_transactions` | integer | All transactions |
| `total_net_sales` | real | All net sales |
| `total_items` | integer | All items sold |
| `member_transactions` | integer | Transactions with Customer ID |
| `member_net_sales` | real | Net sales from members |
| `member_items` | integer | Items from members |
| `member_unique_customers` | integer | Unique members that day |
| `non_member_transactions` | integer | Walk-in transactions |
| `non_member_net_sales` | real | Walk-in net sales |
| `non_member_items` | integer | Walk-in items |
| `member_tx_ratio` | real | member_tx / total_tx |
| `member_sales_ratio` | real | member_sales / total_sales |
| `member_items_ratio` | real | member_items / total_items |

## 4. Charts Enabled by This Data

### Member vs Non-Member Ratios (from `daily_store_stats`)
| Chart | Description |
|-------|-------------|
| **Member Transaction Ratio** | Line: % of transactions from members over time |
| **Member Sales Ratio** | Line: % of net sales from members over time |
| **Member Items Ratio** | Line: % of items from members over time |
| **Member Growth** | Line: unique member customers per day |

### Per-Member Insights (from `member_daily_stats`)
| Chart | Description |
|-------|-------------|
| **Member Lifetime Value** | Line: cumulative spend per member |
| **Visit Frequency Trend** | Are members coming more/less? |
| **Churn Early Warning** | Members where `days_since_last_visit` is growing |
| **Top Members Dashboard** | Ranked by total_spent with trend arrows |
| **Spend Trend** | 30-day rolling avg spend across members |

### SMS Marketing (from enhanced `members`)
| Chart | Description |
|-------|-------------|
| **Birthday Calendar** | Upcoming birthdays for promos 🎂 |
| **Campaign ROI** | Compare behaviour before/after SMS blast |
| **Geo Map** | Members by suburb/postcode |

## 5. Implementation Steps

1. **Alter `members` table** — add new columns (SQL)
2. **Update `sync_customers()`** — pull all fields from Square API
3. **Create `member_daily_stats` table** (SQL)
4. **Create backfill script** — compute stats from historical transactions
5. **Update `square_sync`** — auto-update stats after each sync
6. **Build charts** (future)
