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

CREATE TABLE IF NOT EXISTS units (
        id BIGSERIAL PRIMARY KEY,
        name TEXT UNIQUE
    );

CREATE TABLE IF NOT EXISTS ingestion_log (
        source_file TEXT PRIMARY KEY,
        ingested_at TIMESTAMPTZ DEFAULT NOW()
    );

CREATE TABLE IF NOT EXISTS sync_log (
        id BIGSERIAL PRIMARY KEY,
        sync_type TEXT,
        started_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        records_synced INTEGER,
        status TEXT,
        error_message TEXT
    );

CREATE INDEX IF NOT EXISTS idx_txn_datetime ON transactions(datetime);
CREATE INDEX IF NOT EXISTS idx_txn_transaction_id ON transactions(transaction_id);
CREATE INDEX IF NOT EXISTS idx_txn_row_key ON transactions(row_key);
CREATE INDEX IF NOT EXISTS idx_member_square ON members(square_customer_id);
CREATE INDEX IF NOT EXISTS idx_member_ref ON members(reference_id);
CREATE INDEX IF NOT EXISTS idx_inv_sku ON inventory(sku);
CREATE INDEX IF NOT EXISTS idx_inv_categories ON inventory(categories);
CREATE INDEX IF NOT EXISTS idx_inv_source_date ON inventory(source_date);
