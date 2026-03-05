√M# Database Schema Reference

## Entity Relationship Diagram

```
auth.users (Supabase built-in)
    ‚îÇ
    ‚îú‚îÄ‚îÄ‚îÄ‚îÄ 1:1 ‚îÄ‚îÄ‚îÄ‚îÄ‚ñ∂ profiles (role, first_name, last_name)
    ‚îÇ
    ‚îú‚îÄ‚îÄ‚îÄ‚îÄ 1:N ‚îÄ‚îÄ‚îÄ‚îÄ‚ñ∂ favourites ‚óÄ‚îÄ‚îÄ‚îÄ‚îÄ N:1 ‚îÄ‚îÄ‚îÄ‚îÄ deals
    ‚îÇ
    ‚îú‚îÄ‚îÄ‚îÄ‚îÄ 1:N ‚îÄ‚îÄ‚îÄ‚îÄ‚ñ∂ enquiries ‚óÄ‚îÄ‚îÄ‚îÄ‚îÄ N:1 ‚îÄ‚îÄ‚îÄ‚îÄ deals
    ‚îÇ
    ‚îî‚îÄ‚îÄ‚îÄ‚îÄ 1:N ‚îÄ‚îÄ‚îÄ‚îÄ‚ñ∂ audit_log
                              deals
                                ‚îÇ
                                ‚îî‚îÄ‚îÄ‚îÄ‚îÄ 1:N ‚îÄ‚îÄ‚îÄ‚îÄ‚ñ∂ deal_media
```

---

## Tables

### `profiles`
Extends Supabase auth with app-specific user data.

> **Note:** Passwords are handled by Supabase Auth (`auth.users`) ‚Äî never stored here.

| Column      | Type         | Constraints                          |
|-------------|--------------|--------------------------------------|
| id          | uuid         | PK, references auth.users(id)       |
| role        | text         | CHECK (role in ('admin','investor')) |
| first_name  | text         |                                      |
| last_name   | text         |                                      |
| phone       | text         |                                      |
| created_at  | timestamptz  | DEFAULT now()                        |

### `deals`
Core listings ‚Äî investment properties.

| Column                  | Type           | Constraints / Notes                                  |
|-------------------------|----------------|------------------------------------------------------|
| id                      | uuid           | PK, DEFAULT gen_random_uuid()                        |
| title                   | text           | NOT NULL                                             |
| suburb                  | text           |                                                      |
| state                   | text           |                                                      |
| postcode                | text           |                                                      |
| price                   | int            |                                                      |
| rent_week               | int            |                                                      |
| gross_yield             | numeric(5,2)   |                                                      |
| strategy_tags           | text[]         | e.g., {cashflow,growth,SMSF}                        |
| highlights              | text[]         | Bullet point features                                |
| description             | text           |                                                      |
| status                  | text           | CHECK (status in ('draft','published','archived'))   |
| published_at            | timestamptz    |                                                      |
| created_by              | uuid           | references auth.users(id)                            |
| created_at              | timestamptz    | DEFAULT now()                                        |
| updated_at              | timestamptz    | DEFAULT now()                                        |
| **Property details**    |                |                                                      |
| bedrooms                | int            | Number of bedrooms                                   |
| car_spaces              | int            | Number of car spaces                                 |
| area_sqm                | numeric(10,2)  | Property area in square metres                       |
| **Suburb demographics** |                |                                                      |
| population_change_5y    | numeric(5,2)   | 5-year population change %                           |
| suburb_occupancy_rate   | numeric(5,2)   | Occupancy rate %                                     |
| **Suburb yields**       |                |                                                      |
| suburb_yield_h          | numeric(5,2)   | House yield %                                        |
| suburb_yield_u          | numeric(5,2)   | Unit yield %                                         |
| **Suburb growth (1yr)** |                |                                                      |
| suburb_1y_growth_h      | numeric(6,2)   | House 1-year growth %                                |
| suburb_1y_growth_u      | numeric(6,2)   | Unit 1-year growth %                                 |
| **Suburb growth (10yr)**|                |                                                      |
| suburb_10y_growth_h     | numeric(6,2)   | House 10-year total growth %                         |
| suburb_10y_growth_u     | numeric(6,2)   | Unit 10-year total growth %                          |
| suburb_10y_growth_avg_h | numeric(6,2)   | House 10-year avg annual growth %                    |
| suburb_10y_growth_avg_u | numeric(6,2)   | Unit 10-year avg annual growth %                     |

**Indexes:**
- `deals(status, published_at DESC)`
- `deals(state, suburb)`
- `GIN(strategy_tags)`

**Computed (virtual):** `is_new = published_at > now() - interval '14 days'`

### `deal_media`
Photos and documents attached to deals.

| Column       | Type         | Constraints                               |
|--------------|--------------|-------------------------------------------|
| id           | uuid         | PK, DEFAULT gen_random_uuid()             |
| deal_id      | uuid         | references deals(id) ON DELETE CASCADE    |
| kind         | text         | CHECK (kind in ('image','pdf'))           |
| storage_path | text         | NOT NULL                                  |
| caption      | text         |                                           |
| sort_order   | int          | DEFAULT 0                                 |
| created_at   | timestamptz  | DEFAULT now()                             |

**Indexes:**
- `deal_media(deal_id, sort_order)`

### `favourites`
Investor saved/bookmarked deals.

| Column     | Type         | Constraints                            |
|------------|--------------|----------------------------------------|
| user_id    | uuid         | references auth.users(id)              |
| deal_id    | uuid         | references deals(id) ON DELETE CASCADE |
| created_at | timestamptz  | DEFAULT now()                          |

**Primary Key:** `(user_id, deal_id)` ‚Äî composite

### `enquiries`
Investor questions/interest in a deal.

| Column     | Type         | Constraints                                     |
|------------|--------------|--------------------------------------------------|
| id         | uuid         | PK, DEFAULT gen_random_uuid()                    |
| deal_id    | uuid         | references deals(id)                             |
| user_id    | uuid         | references auth.users(id)                        |
| message    | text         |                                                  |
| status     | text         | CHECK (status in ('new','contacted','closed'))   |
| created_at | timestamptz  | DEFAULT now()                                    |

**Indexes:**
- `enquiries(deal_id, created_at DESC)`

### `audit_log`
Track admin actions for accountability.

| Column     | Type         | Constraints                  |
|------------|--------------|------------------------------|
| id         | uuid         | PK, DEFAULT gen_random_uuid()|
| actor_id   | uuid         |                              |
| entity     | text         | 'deal', 'media', 'enquiry'  |
| entity_id  | uuid         |                              |
| action     | text         | 'create','update','delete','publish' |
| diff       | jsonb        | Before/after changes         |
| created_at | timestamptz  | DEFAULT now()                |

### `market_data`
Scraped property market data (from Python scrapers).

| Column       | Type         | Constraints                     |
|--------------|--------------|---------------------------------|
| id           | uuid         | PK, DEFAULT gen_random_uuid()   |
| source       | text         | NOT NULL ('proptrack','cotality','propertyvalue') |
| report_date  | date         | NOT NULL                        |
| category     | text         | 'dwellings','houses','units','indices' |
| region       | text         | NOT NULL                        |
| metrics      | jsonb        | NOT NULL (flexible key/value)   |
| created_at   | timestamptz  | DEFAULT now()                   |

**Indexes:**
- `market_data(source, report_date DESC)`
- `market_data(region)`

**Example `metrics` JSONB:**
```json
{
  "monthly_growth_pct": 0.2,
  "annual_growth_pct": 8.4,
  "median_value": 883000
}
```

---

## RLS Policies Summary

| Table       | Investor (SELECT) | Investor (INSERT) | Admin (ALL) |
|-------------|-------------------|--------------------|-------------|
| profiles    | Own row only      | ‚Äî                  | ‚úÖ           |
| deals       | Published only    | ‚Äî                  | ‚úÖ           |
| deal_media  | Published deals   | ‚Äî                  | ‚úÖ           |
| favourites  | Own rows          | Own rows           | ‚úÖ           |
| enquiries   | Own rows          | Own rows           | ‚úÖ           |
| audit_log   | ‚Äî                 | ‚Äî                  | ‚úÖ           |
| market_data | All (read-only)   | ‚Äî                  | ‚úÖ           |

---

## Storage Buckets

### `deal-media` (private)

```
deal-media/
‚îî‚îÄ‚îÄ deals/
    ‚îî‚îÄ‚îÄ <deal_id>/
        ‚îú‚îÄ‚îÄ images/
        ‚îÇ   ‚îú‚îÄ‚îÄ <uuid>.jpg
        ‚îÇ   ‚îî‚îÄ‚îÄ <uuid>.jpg
        ‚îî‚îÄ‚îÄ docs/
            ‚îî‚îÄ‚îÄ <uuid>.pdf
```

Access via signed URLs (generated server-side or via Supabase client with auth).
® *cascade08®≥*cascade08≥¥ *cascade08¥∑*cascade08∑Ω *cascade08Ωô*cascade08ô∑ *cascade08∑˝*cascade08˝˛ *cascade08˛Å	*cascade08Å	ƒ	 *cascade08ƒ	ã
*cascade08ã
õ *cascade08õ•*cascade08•ƒ *cascade08ƒ≈*cascade08≈∆ *cascade08∆À*cascade08ÀÒ *cascade08ÒÛ*cascade08ÛÇ *cascade08Çä*cascade08äŸ *cascade08Ÿ‚*cascade08‚Ó *cascade08ÓÔ*cascade08Ô¡ *cascade08¡…*cascade08…“ *cascade08“‘*cascade08‘ß *cascade08ß≠*cascade08≠µ *cascade08µπ*cascade08πã *cascade08ãê*cascade08êô *cascade08ôû*cascade08ûÛ *cascade08Û˝*cascade08˝’ *cascade08’ﬂ*cascade08ﬂ√ *cascade08√Õ*cascade08Õ® *cascade08®≤*cascade08≤ç *cascade08çó*cascade08óÌ *cascade08Ì˜*cascade08˜” *cascade08”›*cascade08›ª *cascade08ª≈*cascade08≈† *cascade08†™*cascade08™Ö *cascade08Öè*cascade08èÍ *cascade08ÍÙ*cascade08Ùœ *cascade08œŸ*cascade08Ÿ˘ *cascade08˘˙*cascade08˙ç *cascade08ç¶'*cascade08¶'√M *cascade0823file:///f:/phil/antigravity/docs/database_schema.md