-- ============================================================
-- ENABLE ROW LEVEL SECURITY (RLS) ON ALL TABLES
-- ============================================================
-- 
-- Run this in: Supabase Dashboard > SQL Editor > New query
--
-- What this does:
-- 1. Enables RLS on every public table
-- 2. Grants SELECT to anon (dashboard can read all data)
-- 3. Grants INSERT/UPDATE/DELETE only on tables the dashboard edits
-- 4. Python sync scripts use service_role key → bypasses RLS entirely
--
-- Tables the dashboard writes to via anon key:
--   - staff_rates (toggle active, edit hourly rates)
--   - category_mappings (assign Café/Retail side)
-- ============================================================

-- ── 1. Enable RLS on all tables ──────────────────────────────

ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_item_summary ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_store_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inventory_margins ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.member_loyalty ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.member_daily_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.loyalty_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.staff_shifts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.staff_rates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.staff_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.category_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.customer_id_mapping ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sync_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sms_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sms_campaign_enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.units ENABLE ROW LEVEL SECURITY;


-- ── 2. READ-ONLY tables (dashboard can SELECT, nothing else) ──

-- Transactions & summaries
CREATE POLICY "anon_read_transactions" ON public.transactions
    FOR SELECT TO anon USING (true);

CREATE POLICY "anon_read_daily_item_summary" ON public.daily_item_summary
    FOR SELECT TO anon USING (true);

CREATE POLICY "anon_read_daily_store_stats" ON public.daily_store_stats
    FOR SELECT TO anon USING (true);

-- Inventory
CREATE POLICY "anon_read_inventory" ON public.inventory
    FOR SELECT TO anon USING (true);

CREATE POLICY "anon_read_inventory_margins" ON public.inventory_margins
    FOR SELECT TO anon USING (true);

-- Members & loyalty
CREATE POLICY "anon_read_members" ON public.members
    FOR SELECT TO anon USING (true);

CREATE POLICY "anon_read_member_loyalty" ON public.member_loyalty
    FOR SELECT TO anon USING (true);

CREATE POLICY "anon_read_member_daily_stats" ON public.member_daily_stats
    FOR SELECT TO anon USING (true);

CREATE POLICY "anon_read_loyalty_events" ON public.loyalty_events
    FOR SELECT TO anon USING (true);

-- Staff
CREATE POLICY "anon_read_staff_shifts" ON public.staff_shifts
    FOR SELECT TO anon USING (true);

CREATE POLICY "anon_read_staff_roles" ON public.staff_roles
    FOR SELECT TO anon USING (true);

-- Internal / logs
CREATE POLICY "anon_read_customer_id_mapping" ON public.customer_id_mapping
    FOR SELECT TO anon USING (true);

CREATE POLICY "anon_read_ingestion_log" ON public.ingestion_log
    FOR SELECT TO anon USING (true);

CREATE POLICY "anon_read_sync_log" ON public.sync_log
    FOR SELECT TO anon USING (true);

CREATE POLICY "anon_read_units" ON public.units
    FOR SELECT TO anon USING (true);

-- Campaigns
CREATE POLICY "anon_read_sms_campaigns" ON public.sms_campaigns
    FOR SELECT TO anon USING (true);

CREATE POLICY "anon_read_sms_campaign_enrollments" ON public.sms_campaign_enrollments
    FOR SELECT TO anon USING (true);


-- ── 3. READ + WRITE tables (dashboard edits these via UI) ────

-- staff_rates: dashboard can read, update, and upsert rates
CREATE POLICY "anon_read_staff_rates" ON public.staff_rates
    FOR SELECT TO anon USING (true);

CREATE POLICY "anon_update_staff_rates" ON public.staff_rates
    FOR UPDATE TO anon USING (true) WITH CHECK (true);

CREATE POLICY "anon_insert_staff_rates" ON public.staff_rates
    FOR INSERT TO anon WITH CHECK (true);

-- category_mappings: dashboard can read and update category sides
CREATE POLICY "anon_read_category_mappings" ON public.category_mappings
    FOR SELECT TO anon USING (true);

CREATE POLICY "anon_update_category_mappings" ON public.category_mappings
    FOR UPDATE TO anon USING (true) WITH CHECK (true);


-- ── 4. Verify ────────────────────────────────────────────────
-- After running, check Supabase Dashboard > Authentication > Policies
-- to confirm all policies are in place. The security warnings should
-- be resolved.
--
-- Note: Python scripts (scheduled_sync, smart_backfill, etc.) use
-- SUPABASE_SERVICE_ROLE_KEY which ALWAYS bypasses RLS. No changes
-- needed on the backend side.
-- ============================================================
