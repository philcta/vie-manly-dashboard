# SMS Campaigns — Data Model & Tracking Plan

## Database Schema

### `sms_campaigns` — Campaign definitions
| Column | Type | Purpose |
|--------|------|---------|
| name | TEXT | e.g., "Win Back Lapsed" |
| status | TEXT | draft / active / paused / completed |
| criteria | JSONB | Auto-enrollment rules (see below) |
| message_template | TEXT | SMS body with variables |
| send_at | TIMESTAMPTZ | Schedule time |
| recurrence | TEXT | once / weekly / monthly |
| impact_window_days | INT | Default 28 (4 weeks) |

### `sms_campaign_enrollments` — Per-member tracking
| Column | Type | Purpose |
|--------|------|---------|
| campaign_id | UUID | → sms_campaigns |
| member_id | TEXT | Square loyalty member ID |
| sms_status | TEXT | pending / sent / delivered / failed / opted_out |
| points_at_enrollment | INT | Snapshot for comparison |
| redeemable_points_at_enrollment | INT | Snapshot |
| transactions_after | INT | Purchases within 4-week window |
| net_sales_after | NUMERIC | Revenue within window |
| points_redeemed_after | INT | Redemptions within window |
| discount_given_after | NUMERIC | Discount value from redemptions |

### Views
- **`sms_campaign_summary`** — Per-campaign: enrolled, sent, return rate %, net sales, ROI
- **`member_sms_history`** — Per-member: campaigns enrolled, texts received, attributed sales

## Auto-Enrollment Criteria (JSONB)

```json
{
  "min_redeemable_points": 100,
  "max_redeemable_points": null,
  "never_redeemed": true,
  "inactive_days": 30,
  "min_lifetime_points": 500,
  "segments": ["at_risk", "lapsed"]
}
```

## Impact Tracking Flow

```
1. Campaign created with criteria
2. Members matching criteria auto-enrolled
3. SMS sent via mobilemessage.com.au API
4. Delivery status tracked (sent/delivered/failed)
5. Over next 4 weeks, a scheduled job:
   - Counts transactions by enrolled members
   - Sums net sales (after redeem discounts)
   - Tracks points redeemed
6. Campaign summary shows ROI
```

## SMS Provider

- **API**: mobilemessage.com.au (to be integrated)
- **Tracking**: delivery_response JSONB stores API response
- **Message limit**: 160 chars per SMS
