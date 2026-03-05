�/# Architecture Reference

## System Overview

Property Investment Platform — a Supabase-backed system with an Expo mobile app
for investors and a Next.js admin dashboard.

## Data Flow

```
┌─────────────────────────────────┐
│   Investor Mobile App (Expo)    │
│   - Browse published deals      │
│   - Save favourites             │
│   - Submit enquiries            │
└──────────┬──────────────────────┘
           │  supabase-js
           │  (anon key + JWT)
           ▼
┌─────────────────────────────────┐
│       Supabase Auth             │
│   - Email/password login        │
│   - Magic link (optional)       │
│   - Issues JWT with user ID     │
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│                  Supabase Postgres                       │
│                                                          │
│  profiles ←── auth.users          RLS enforces:          │
│  deals ────── deal_media          - investors see        │
│  favourites                         published only       │
│  enquiries                        - admins see all       │
│  audit_log                                               │
│  market_data ←── scrapers                                │
│                                                          │
└──────────┬──────────────────────────────────────────────┘
           │                              ▲
           │                              │  supabase-js
           │                              │  (anon key + JWT)
           │                    ┌─────────┴────────────────┐
           │                    │  Admin Dashboard         │
           │                    │  (Next.js on Vercel)     │
           │                    │  - CRUD deals            │
           │                    │  - Upload media          │
           │                    │  - Manage enquiries      │
           │                    │  - View market data      │
           │                    └──────────────────────────┘
           │
           ├──▶ Supabase Storage (private bucket: deal-media)
           │     └── deals/<deal_id>/images/<uuid>.jpg
           │     └── deals/<deal_id>/docs/<uuid>.pdf
           │
           └──▶ Edge Functions
                 ├── notify-enquiry → sends email via Resend/Postmark
                 └── push-notification → Expo Push API (Phase 2)


┌─────────────────────────────────┐
│     Python Scrapers (local)     │
│   - PropTrack HPI               │
│   - PropertyValue.com.au        │
│   - Cotality indices            │
│                                  │
│   Writes to: market_data table   │
│   Using: service_role key        │
└─────────────────────────────────┘
```

## Auth & Roles

**Pattern: Database-driven roles (simple, secure)**

1. User signs up → Supabase creates `auth.users` row
2. Trigger creates `profiles` row with `role = 'investor'` (default)
3. Admin manually promotes users via Supabase Dashboard or admin UI
4. RLS checks `profiles.role` via `is_admin()` helper function
5. No custom JWT claims needed — keeps things simple

## API / Data Access Patterns

**Rule: Use `supabase-js` directly. Edge Functions only when needed.**

Use Edge Functions when:
- You need `service_role` privileges (e.g., admin-only operations)
- You're calling third-party APIs (email, push notifications)
- You need server-side validation/automation

### Example Queries

```typescript
// Deal feed (investor)
const { data } = await supabase
  .from('deals')
  .select('*')
  .eq('status', 'published')
  .order('published_at', { ascending: false })
  .limit(20)

// Filtered deals
const { data } = await supabase
  .from('deals')
  .select('*')
  .eq('status', 'published')
  .eq('state', 'QLD')
  .gte('gross_yield', 5.0)
  .contains('strategy_tags', ['smsf'])

// Deal detail with media
const { data } = await supabase
  .from('deals')
  .select('*, deal_media(*)')
  .eq('id', dealId)
  .single()

// User's favourites
const { data } = await supabase
  .from('favourites')
  .select('*, deals(*)')
  .eq('user_id', userId)

// Submit enquiry
const { data } = await supabase
  .from('enquiries')
  .insert({ deal_id: dealId, user_id: userId, message })
```

## Image Strategy

- Upload originals once to Supabase Storage
- Serve resized variants using Supabase image transformations
- Typical sizes:
  - List thumbnail: ~400–600px wide
  - Detail hero: ~1200px wide
- Prefer WebP format, JPG quality 75–85%

## CI/CD

| Target          | Pipeline                                    |
|-----------------|---------------------------------------------|
| Admin Dashboard | GitHub → Vercel (auto-deploy on push)       |
| Mobile App      | EAS Build → EAS Submit → App Stores         |
| Database        | `supabase db push` or migration files        |
| Scrapers        | Manual run or scheduled (cron / GitHub Actions) |
�/*cascade0820file:///f:/phil/antigravity/docs/architecture.md