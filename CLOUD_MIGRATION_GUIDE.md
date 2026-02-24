# ☁️ Vie Manly Dashboard — Cloud Migration Guide

> **Goal**: Move from local SQLite + CSV uploads → Supabase (PostgreSQL) + Square API + Streamlit Cloud
>
> **Date**: February 2026

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Step 1: Supabase Setup](#2-step-1-supabase-setup)
3. [Step 2: Square Developer Setup](#3-step-2-square-developer-setup)
4. [Step 3: Project Environment Setup](#4-step-3-project-environment-setup)
5. [Step 4: Database Migration (SQLite → Supabase)](#5-step-4-database-migration)
6. [Step 5: Deploy to Streamlit Cloud](#6-step-5-deploy-to-streamlit-cloud)

---

## 1. Architecture Overview

```
┌──────────────┐    Cron (hourly)     ┌───────────────┐
│  Square API  │ ──────────────────►  │   Supabase    │
│   (POS)      │                     │  (PostgreSQL)  │
└──────────────┘                     └───────┬───────┘
                                             │
                                             │  SQL queries
                                             ▼
                                     ┌───────────────┐
                                     │   Streamlit    │
                                     │  Community     │
                                     │  Cloud (Free)  │
                                     └───────────────┘
```

**Data flow:**
1. Square API provides transactions, inventory, and customer data
2. A sync job (GitHub Actions or Supabase Edge Function) runs **hourly** to pull fresh data
3. Data is stored in Supabase PostgreSQL (replaces your local SQLite)
4. Streamlit dashboard reads directly from Supabase
5. Manual CSV upload remains as a **fallback** option

---

## 2. Step 1: Supabase Setup

### 2.1 Create a Supabase Account & Project

1. Go to **[https://supabase.com](https://supabase.com)**
2. Click **"Start your project"** → Sign in with GitHub (recommended)
3. Click **"New Project"**
4. Fill in:
   - **Name**: `vie-manly-dashboard`
   - **Database Password**: Generate a strong password → **⚠️ SAVE THIS, you'll need it later**
   - **Region**: Choose `Southeast Asia (Singapore)` — closest to Sydney
   - **Plan**: Free tier is fine (500MB database, 50,000 monthly active users)
5. Click **"Create new project"** — wait ~2 minutes for provisioning

### 2.2 Get Your Supabase Credentials

Once the project is created, go to **Settings → API** (left sidebar):

You need these 3 values:

| Setting | Where to find it | Example |
|---------|-------------------|---------|
| **Project URL** | Settings → API → Project URL | `https://xyzcompany.supabase.co` |
| **Anon Key** | Settings → API → Project API keys → `anon` `public` | `eyJhbGciOiJIUzI1NiIs...` |
| **Service Role Key** | Settings → API → Project API keys → `service_role` `secret` | `eyJhbGciOiJIUzI1NiIs...` |

Also get the **direct database connection string**:

1. Go to **Settings → Database**
2. Under **Connection string** → select **URI**
3. Copy it — it looks like:
   ```
   postgresql://postgres.[project-ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
   ```

> ⚠️ **Important**: Replace `[YOUR-PASSWORD]` with the database password you set earlier.

### 2.3 Create Database Tables

Go to **SQL Editor** (left sidebar) and run this SQL:

```sql
-- ============================================
-- Vie Manly Dashboard — Supabase Schema
-- ============================================

-- 1) Transactions table
CREATE TABLE IF NOT EXISTS transactions (
    id BIGSERIAL PRIMARY KEY,
    datetime TIMESTAMPTZ,
    category TEXT,
    item TEXT,
    qty REAL,
    net_sales REAL,
    gross_sales REAL,
    discounts REAL,
    customer_id TEXT,
    transaction_id TEXT,
    tax TEXT,
    card_brand TEXT,
    pan_suffix TEXT,
    date TEXT,
    time TEXT,
    time_zone TEXT,
    modifiers_applied TEXT,
    row_key TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2) Inventory table
CREATE TABLE IF NOT EXISTS inventory (
    id BIGSERIAL PRIMARY KEY,
    product_id TEXT,
    product_name TEXT,
    sku TEXT,
    categories TEXT,
    price REAL,
    tax_gst_10 TEXT,
    current_quantity REAL,
    default_unit_cost REAL,
    unit TEXT,
    source_date TEXT,
    stock_on_hand REAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3) Members table
CREATE TABLE IF NOT EXISTS members (
    id BIGSERIAL PRIMARY KEY,
    square_customer_id TEXT UNIQUE,
    first_name TEXT,
    last_name TEXT,
    email_address TEXT,
    phone_number TEXT,
    creation_date TEXT,
    customer_note TEXT,
    reference_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4) Units table
CREATE TABLE IF NOT EXISTS units (
    id BIGSERIAL PRIMARY KEY,
    name TEXT UNIQUE
);

-- 5) Ingestion log
CREATE TABLE IF NOT EXISTS ingestion_log (
    source_file TEXT PRIMARY KEY,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6) Sync log (for Square API sync tracking)
CREATE TABLE IF NOT EXISTS sync_log (
    id BIGSERIAL PRIMARY KEY,
    sync_type TEXT,           -- 'transactions', 'inventory', 'customers'
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    records_synced INTEGER,
    status TEXT,              -- 'success', 'error'
    error_message TEXT
);

-- ============================================
-- Indexes (matching your existing SQLite indexes)
-- ============================================
CREATE INDEX IF NOT EXISTS idx_txn_datetime ON transactions(datetime);
CREATE INDEX IF NOT EXISTS idx_txn_transaction_id ON transactions(transaction_id);
CREATE INDEX IF NOT EXISTS idx_txn_row_key ON transactions(row_key);
CREATE INDEX IF NOT EXISTS idx_member_square ON members(square_customer_id);
CREATE INDEX IF NOT EXISTS idx_member_ref ON members(reference_id);
CREATE INDEX IF NOT EXISTS idx_inv_sku ON inventory(sku);
CREATE INDEX IF NOT EXISTS idx_inv_categories ON inventory(categories);
CREATE INDEX IF NOT EXISTS idx_inv_source_date ON inventory(source_date);

-- ============================================
-- Row Level Security (optional but recommended)
-- ============================================
-- For now, we'll use the service_role key which bypasses RLS
-- If you want to add RLS later for public access:
-- ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE inventory ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE members ENABLE ROW LEVEL SECURITY;
```

### 2.4 Verify Tables Were Created

In the Supabase dashboard:
1. Go to **Table Editor** (left sidebar)
2. You should see all 6 tables: `transactions`, `inventory`, `members`, `units`, `ingestion_log`, `sync_log`

✅ **Supabase is now ready!**

---

## 3. Step 2: Square Developer Setup

### 3.1 Create a Square Developer Account

1. Go to **[https://developer.squareup.com](https://developer.squareup.com)**
2. Click **"Get started"** → Sign in with your **existing Square account** (the one you use for Vie Manly POS)
3. You'll land on the **Developer Dashboard**

### 3.2 Create an Application

1. Click **"+" or "Create Application"**
2. **Application Name**: `Vie Manly Dashboard`
3. Click **"Save"**

### 3.3 Get Your API Credentials

On the application page:

1. Click on your app **"Vie Manly Dashboard"**
2. You'll see two tabs at the top: **Sandbox** and **Production**
3. **⚠️ Switch to the "Production" tab** (Sandbox has test data only)
4. You need these values:

| Setting | Where to find it |
|---------|-------------------|
| **Application ID** | On the Credentials page |
| **Access Token** | Production → Access Token → **"Show"** |

> ⚠️ **CRITICAL**: The **Production Access Token** has full access to your live Square data. Treat it like a password. Never commit it to Git.

### 3.4 Required API Permissions

Your access token needs these permissions (they should be enabled by default):

| Permission | Used For |
|------------|----------|
| `ORDERS_READ` | Reading transaction/order data |
| `ITEMS_READ` | Reading catalog/inventory items |
| `INVENTORY_READ` | Reading stock counts |
| `CUSTOMERS_READ` | Reading customer/member data |

To verify permissions:
1. Go to your app → **OAuth** tab
2. Under **Production**, check that the above scopes are listed

### 3.5 Get Your Location ID

You need the Square **Location ID** for your Vie Manly store:

1. Go to **[https://developer.squareup.com/explorer/square/locations-api/list-locations](https://developer.squareup.com/explorer/square/locations-api/list-locations)**
2. Switch to **Production** mode
3. Click **"Run"**
4. In the response, find your location — it will have:
   ```json
   {
     "id": "LXXXXXXXXXXXXXXXXX",
     "name": "Vie Market & Bar",
     ...
   }
   ```
5. Copy the `id` value — this is your **Location ID**

✅ **Square Developer is now ready!**

---

## 4. Step 3: Project Environment Setup

### 4.1 Summary of All Credentials Needed

Create a `.env` file with these values (we'll set up the file structure next):

```env
# === Supabase ===
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIs...
SUPABASE_DB_URL=postgresql://postgres.[ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres

# === Square API ===
SQUARE_ACCESS_TOKEN=EAAAl...
SQUARE_APPLICATION_ID=sq0idp-...
SQUARE_LOCATION_ID=LXXXXXXXXXXXXXXXXX
SQUARE_ENVIRONMENT=production

# === App Settings ===
SYNC_INTERVAL_MINUTES=60
```

### 4.2 Project Structure (Cloud Version)

The new project structure will be:

```
App24-cloud/
├── .streamlit/
│   ├── config.toml          # Streamlit theme/settings
│   └── secrets.toml         # Credentials (for Streamlit Cloud)
├── .github/
│   └── workflows/
│       └── sync_square.yml  # Hourly sync via GitHub Actions
├── app.py                   # Main dashboard (modified)
├── charts/                  # Your existing charts (minimal changes)
│   ├── high_level.py
│   ├── sales_report.py
│   ├── inventory.py
│   ├── product_mix_only.py
│   └── customer_segmentation.py
├── services/
│   ├── db.py                # NEW: Supabase connector (replaces SQLite)
│   ├── analytics.py         # Your existing analytics (minimal changes)
│   ├── category_rules.py    # Your existing rules
│   ├── ingestion.py         # MODIFIED: Square API ingestion
│   ├── square_sync.py       # NEW: Square API sync service
│   └── logger.py            # Your existing logger
├── scripts/
│   ├── migrate_sqlite_to_supabase.py  # One-time migration script
│   └── sync_now.py          # Manual sync trigger
├── .env.example             # Template for environment variables
├── .gitignore
├── requirements.txt         # Updated dependencies
└── README.md
```

---

## 5. Step 4: Database Migration (SQLite → Supabase)

Once you have Supabase set up, we'll run a one-time migration script to transfer your ~377MB of historical data from SQLite to Supabase.

The migration script will:
1. Read all data from your local `manlyfarm.db`
2. Map SQLite column names to PostgreSQL column names (snake_case)
3. Upload in batches (1000 rows at a time) to Supabase
4. Verify row counts match

**Column name mapping** (SQLite → Supabase):
| SQLite Column | Supabase Column |
|---------------|-----------------|
| `Datetime` | `datetime` |
| `Net Sales` | `net_sales` |
| `Gross Sales` | `gross_sales` |
| `Customer ID` | `customer_id` |
| `Transaction ID` | `transaction_id` |
| `Card Brand` | `card_brand` |
| `PAN Suffix` | `pan_suffix` |
| `Time Zone` | `time_zone` |
| `Modifiers Applied` | `modifiers_applied` |
| `Product ID` | `product_id` |
| `Product Name` | `product_name` |
| `Tax - GST (10%)` | `tax_gst_10` |
| `Current Quantity Vie Market & Bar` | `current_quantity` |
| `Default Unit Cost` | `default_unit_cost` |
| `Stock on Hand` | `stock_on_hand` |
| `Square Customer ID` | `square_customer_id` |
| `First Name` | `first_name` |
| `Last Name` | `last_name` |
| `Email Address` | `email_address` |
| `Phone Number` | `phone_number` |
| `Creation Date` | `creation_date` |
| `Customer Note` | `customer_note` |
| `Reference ID` | `reference_id` |

---

## 6. Step 5: Deploy to Streamlit Cloud

### 6.1 Push to GitHub

1. Create a new **private** GitHub repository: `vie-manly-dashboard`
2. Push the cloud version of the code

### 6.2 Deploy on Streamlit Cloud

1. Go to **[https://share.streamlit.io](https://share.streamlit.io)**
2. Sign in with GitHub
3. Click **"New app"**
4. Select:
   - **Repository**: `your-username/vie-manly-dashboard`
   - **Branch**: `main`
   - **Main file path**: `app.py`
5. Under **Advanced settings** → **Secrets**, paste your credentials:
   ```toml
   [supabase]
   url = "https://your-project.supabase.co"
   key = "your-service-role-key"

   [square]
   access_token = "EAAAl..."
   location_id = "LXXXXXXXXXXXXXXXXX"
   ```
6. Click **"Deploy!"**

### 6.3 Set Up Hourly Sync

Option A: **GitHub Actions** (recommended — free)
- A workflow file runs every hour, calling the Square API and writing to Supabase

Option B: **Supabase Edge Functions**
- A serverless function inside Supabase that runs on a schedule

---

## Next Steps

Once you've completed Steps 1 & 2 (Supabase + Square setup), let me know and I'll:

1. ✅ Create the cloud version of `services/db.py` (Supabase connector)
2. ✅ Create `services/square_sync.py` (Square API integration)
3. ✅ Create the migration script
4. ✅ Update `app.py` for cloud deployment
5. ✅ Set up GitHub Actions for hourly sync

**Estimated time to complete migration**: 2-3 hours of development work once credentials are ready.
