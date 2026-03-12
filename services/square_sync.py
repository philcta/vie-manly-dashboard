"""
services/square_sync.py — Square API → Supabase sync service

Pulls data from Square POS API and writes to Supabase:
- Transactions (via Orders API)
- Inventory (via Catalog + Inventory API)
- Customers/Members (via Customers API)

Can be run as:
- Standalone script: python -m services.square_sync
- GitHub Actions cron job
- Called from the dashboard UI
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
import streamlit as st

try:
    from square import Square as SquareClient
except ImportError:
    print("⚠️ squareup package not installed. Run: pip install squareup")
    SquareClient = None


# ============================================
# Square Client Setup
# ============================================

def _get_square_config():
    """Get Square config from Streamlit secrets or environment variables."""
    # Try Streamlit secrets first
    try:
        return {
            "access_token": st.secrets["square"]["access_token"],
            "environment": st.secrets["square"].get("environment", "production"),
            "location_id": st.secrets["square"]["location_id"],
        }
    except Exception:
        pass

    # Fall back to environment variables
    token = os.getenv("SQUARE_ACCESS_TOKEN")
    if not token:
        raise ValueError("Square access token not found. Set SQUARE_ACCESS_TOKEN in .env")

    return {
        "access_token": token,
        "environment": os.getenv("SQUARE_ENVIRONMENT", "production"),
        "location_id": os.getenv("SQUARE_LOCATION_ID"),
    }


def get_square_client() -> "SquareClient":
    """Create a Square API client (v44+ SDK)."""
    if SquareClient is None:
        raise ImportError("squareup package not installed. Run: pip install squareup")

    config = _get_square_config()
    # v44 SDK uses Square(token=...) and environment is set via base_url
    env = config["environment"]
    if env == "production":
        return SquareClient(token=config["access_token"])
    else:
        return SquareClient(
            token=config["access_token"],
            environment=env,
        )


def get_location_id() -> str:
    """Get the Square location ID."""
    config = _get_square_config()
    loc_id = config.get("location_id")
    if loc_id:
        return loc_id

    # Auto-discover: get the first active location (v44 SDK)
    client = get_square_client()
    result = client.locations.list()
    if result.locations:
        active = [l for l in result.locations if l.status == "ACTIVE"]
        if active:
            return active[0].id
    raise ValueError("No Square location found. Set SQUARE_LOCATION_ID in .env")


# ============================================
# Category Mapping (from Square Catalog API)
# ============================================

def build_catalog_map():
    """Build item_name -> category_name map from the Square Catalog API.
    
    Uses item_data.reporting_category.id to resolve the single reporting
    category for each item. This field is populated for virtually all items,
    unlike the deprecated category_id.
    
    Returns:
        catalog_map: dict  lowercase item_name -> category_name
    """
    client = get_square_client()
    
    # Step 1: Get all CATEGORY objects -> id:name map (SyncPager auto-paginates)
    cat_names = {}
    for obj in client.catalog.list(types="CATEGORY"):
        cat_names[obj.id] = getattr(obj.category_data, "name", "") if obj.category_data else ""
    
    # Step 2: Build item name -> category map using reporting_category
    catalog_map = {}
    for obj in client.catalog.list(types="ITEM"):
        item_data = obj.item_data
        if not item_data:
            continue
        name = item_data.name or ""
        if not name:
            continue
        
        # Use reporting_category (always populated, single value)
        reporting = item_data.reporting_category
        if reporting:
            cat_name = cat_names.get(reporting.id, "")
        else:
            cat_name = ""
        
        if cat_name:
            catalog_map[name.lower()] = cat_name
            for var in (item_data.variations or []):
                v_data = var.item_variation_data
                v_name = v_data.name if v_data else ""
                if v_name and v_name != name:
                    catalog_map[f"{name} - {v_name}".lower()] = cat_name
    
    print(f"Category map: {len(catalog_map)} items from {len(cat_names)} categories")
    return catalog_map


def _lookup_category(display_name, item_name, catalog_map):
    """Look up category from catalog map.
    Tries display_name first (e.g. 'Coffee - Long Black'), then base name.
    Returns category name or empty string.
    """
    return (
        catalog_map.get(display_name.strip().lower()) or
        catalog_map.get(item_name.strip().lower()) or
        ""
    )


# ============================================
# Sync Transactions (Orders API)
# ============================================

def sync_transactions(hours_back: int = 2, start_from: Optional[datetime] = None) -> pd.DataFrame:
    """
    Fetch recent transactions from Square Orders API with proper category mapping.

    Args:
        hours_back: How many hours of data to fetch (default: 2 for hourly cron with overlap)
        start_from: If provided, fetch from this datetime instead of using hours_back

    Returns:
        DataFrame with transaction rows in the dashboard's expected format
    """
    client = get_square_client()
    location_id = get_location_id()

    # Build catalog map for category enrichment
    try:
        catalog_map = build_catalog_map()
    except Exception as e:
        print(f"Warning: Could not build catalog map: {e}")
        catalog_map = {}

    now = datetime.now(timezone.utc)
    if start_from is not None:
        # Ensure it's timezone-aware (UTC)
        if start_from.tzinfo is None:
            start_time = start_from.replace(tzinfo=timezone.utc)
        else:
            start_time = start_from
    else:
        start_time = now - timedelta(hours=hours_back)

    all_orders = []
    cursor = None

    while True:
        # v44 SDK: keyword args instead of body=dict
        result = client.orders.search(
            location_ids=[location_id],
            cursor=cursor,
            query={
                "filter": {
                    "date_time_filter": {
                        "closed_at": {
                            "start_at": start_time.isoformat(),
                            "end_at": now.isoformat(),
                        }
                    },
                    "state_filter": {
                        "states": ["COMPLETED"]
                    }
                },
                "sort": {
                    "sort_field": "CLOSED_AT",
                    "sort_order": "ASC"
                }
            },
            limit=500,
        )

        if result.errors:
            print(f"Square Orders API error: {result.errors}")
            break

        orders = result.orders or []
        all_orders.extend(orders)

        cursor = result.cursor
        if not cursor:
            break

    # Convert orders to transaction rows with proper category mapping
    rows = []
    matched = 0
    unmatched = 0
    
    for order in all_orders:
        order_id = order.id or ""
        closed_at = order.closed_at or order.created_at or ""
        customer_id = order.customer_id or ""

        # Parse tenders (payment info)
        tenders = order.tenders or []
        card_brand = ""
        pan_suffix = ""
        if tenders:
            card_details = tenders[0].card_details
            if card_details and card_details.card:
                card_brand = card_details.card.card_brand or ""
                pan_suffix = card_details.card.last4 or ""

        # Parse line items
        line_items = order.line_items or []
        for idx, item in enumerate(line_items):
            item_name = item.name or ""
            qty = float(item.quantity or "0")

            # Amounts are in cents (smallest currency unit) — v44 uses pydantic Money objects
            total_money = int(item.total_money.amount if item.total_money else 0) / 100
            total_tax = int(item.total_tax_money.amount if item.total_tax_money else 0) / 100
            total_discount = int(item.total_discount_money.amount if item.total_discount_money else 0) / 100

            # Use Square's gross_sales_money for accuracy (matches their dashboard)
            gross_sales = int(item.gross_sales_money.amount if item.gross_sales_money else 0) / 100
            net_sales = total_money - total_tax

            # Parse modifiers
            modifiers = item.modifiers or []
            modifier_names = [m.name or "" for m in modifiers]
            modifiers_str = ", ".join(modifier_names) if modifier_names else ""

            # Get variation name for better item identification
            variation_name = item.variation_name or ""
            if variation_name and variation_name != item_name:
                display_name = f"{item_name} - {variation_name}"
            else:
                display_name = item_name

            # Category lookup from catalog
            category = _lookup_category(display_name, item_name, catalog_map)
            if category:
                matched += 1
            else:
                unmatched += 1

            # Parse datetime — use closed_at to match Square's "Bills Closed" logic
            try:
                dt = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
                # Convert to Sydney time
                from zoneinfo import ZoneInfo
                dt_local = dt.astimezone(ZoneInfo("Australia/Sydney"))
                date_str = dt_local.strftime("%Y-%m-%d")
                time_str = dt_local.strftime("%H:%M:%S")
                datetime_str = dt_local.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                date_str = ""
                time_str = ""
                datetime_str = closed_at

            # Build deterministic row_key — MUST match rebuild_from_square.py format
            row_key = f"{order_id}-LI-{idx}"

            rows.append({
                "Datetime": datetime_str,
                "Category": category,
                "Item": display_name,
                "Qty": qty,
                "Net Sales": round(net_sales, 2),
                "Gross Sales": round(gross_sales, 2),
                "Discounts": round(total_discount, 2),
                "Customer ID": customer_id,
                "Transaction ID": order_id,
                "Tax": str(round(total_tax, 2)),
                "Card Brand": card_brand,
                "PAN Suffix": pan_suffix,
                "Date": date_str,
                "Time": time_str,
                "Time Zone": "Australia/Sydney",
                "Modifiers Applied": modifiers_str,
                "__row_key": row_key,
            })

    df = pd.DataFrame(rows)
    total = matched + unmatched
    pct = (matched / total * 100) if total else 0
    print(f"Fetched {len(df)} transactions. Categories: {matched}/{total} matched ({pct:.1f}%)")
    return df


# ============================================
# Sync Inventory (Catalog + Inventory Count API)
# ============================================

def sync_inventory() -> pd.DataFrame:
    """
    Fetch current inventory from Square Catalog API + Inventory Counts API.

    Returns:
        DataFrame with inventory rows matching the dashboard's expected format
    """
    client = get_square_client()
    location_id = get_location_id()

    # --- Step 1: Get all catalog items (SyncPager auto-paginates) ---
    all_items = list(client.catalog.list(types="ITEM"))

    # --- Step 1b: Fetch all vendors from Square Vendors API ---
    import requests as _requests
    _sq_token = os.getenv("SQUARE_ACCESS_TOKEN", "")
    _sq_headers = {
        "Authorization": f"Bearer {_sq_token}",
        "Content-Type": "application/json",
        "Square-Version": "2025-01-23",
    }
    vendor_names = {}  # vendor_id -> vendor_name
    try:
        cursor = None
        while True:
            body = {"filter": {"status": ["ACTIVE"]}}
            if cursor:
                body["cursor"] = cursor
            vr = _requests.post("https://connect.squareup.com/v2/vendors/search", headers=_sq_headers, json=body)
            vdata = vr.json()
            for v in vdata.get("vendors", []):
                vendor_names[v["id"]] = v.get("name", "")
            cursor = vdata.get("cursor")
            if not cursor:
                break
        print(f"Loaded {len(vendor_names)} vendors from Square")
    except Exception as e:
        print(f"Warning: Could not fetch vendors: {e}")

    # --- Step 2: Build item -> variation mapping ---
    variation_ids = []
    inv_catalog_map = {}  # variation_id -> {product_name, sku, category, price, ...}

    # Get all CATEGORY names for resolving reporting_category
    cat_names = {}
    for obj in client.catalog.list(types="CATEGORY"):
        cat_names[obj.id] = getattr(obj.category_data, "name", "") if obj.category_data else ""

    for item in all_items:
        item_data = item.item_data
        if not item_data:
            continue
        product_name = item_data.name or ""
        tax_ids = item_data.tax_ids or []
        has_gst = len(tax_ids) > 0  # Simplified GST detection

        # Resolve reporting_category
        reporting = item_data.reporting_category
        if reporting:
            cat_name = cat_names.get(reporting.id, "")
        else:
            cat_name = ""

        for variation in (item_data.variations or []):
            var_id = variation.id or ""
            var_data = variation.item_variation_data
            if not var_data:
                continue

            sku = var_data.sku or ""
            price_money = var_data.price_money
            price = int(price_money.amount) / 100 if price_money and price_money.amount else 0

            # Unit cost + vendor — try direct default_unit_cost first, then vendor infos
            unit_cost = 0
            vendor_name = ""
            try:
                # Direct field on variation (most reliable)
                duc = getattr(var_data, 'default_unit_cost', None)
                if duc:
                    amt = duc.amount if hasattr(duc, 'amount') else (duc.get('amount', 0) if isinstance(duc, dict) else 0)
                    if amt:
                        unit_cost = int(amt) / 100

                # Vendor info: extract vendor name + fallback cost
                vi_list = getattr(var_data, 'item_variation_vendor_infos', None) or []
                if vi_list:
                    vi = vi_list[0]
                    vi_data = vi.item_variation_vendor_info_data if hasattr(vi, 'item_variation_vendor_info_data') else vi.get('item_variation_vendor_info_data', {})
                    if vi_data:
                        # Resolve vendor name
                        vid = vi_data.vendor_id if hasattr(vi_data, 'vendor_id') else vi_data.get('vendor_id', '')
                        if vid:
                            vendor_name = vendor_names.get(vid, "")
                        # Fallback cost from vendor price
                        if unit_cost == 0:
                            pm = vi_data.price_money if hasattr(vi_data, 'price_money') else vi_data.get('price_money', {})
                            if pm:
                                amt = pm.amount if hasattr(pm, 'amount') else pm.get('amount', 0)
                                unit_cost = int(amt or 0) / 100
            except Exception:
                pass

            inv_catalog_map[var_id] = {
                "product_id": item.id or "",
                "product_name": product_name,
                "sku": sku,
                "categories": cat_name,
                "price": price,
                "tax_gst": "Y" if has_gst else "N",
                "default_unit_cost": unit_cost,
                "unit": var_data.measurement_unit_id or "",
                "default_vendor": vendor_name,
            }
            variation_ids.append(var_id)

    # --- Step 3: Get inventory counts ---
    counts_map = {}  # variation_id → quantity

    if variation_ids:
        # Batch in groups of 100
        for i in range(0, len(variation_ids), 100):
            batch_ids = variation_ids[i:i + 100]
            try:
                # v44 SDK returns SyncPager for batch_get_counts
                for count in client.inventory.batch_get_counts(
                    catalog_object_ids=batch_ids,
                    location_ids=[location_id],
                ):
                    obj_id = count.catalog_object_id or ""
                    qty = float(count.quantity or "0")
                    state = count.state or ""
                    if state == "IN_STOCK":
                        counts_map[obj_id] = counts_map.get(obj_id, 0) + qty
            except Exception as e:
                print(f"Warning: inventory batch error: {e}")

    # --- Step 5: Build inventory DataFrame ---
    today = datetime.now().strftime("%Y-%m-%d")
    rows = []

    for var_id, info in inv_catalog_map.items():
        qty = counts_map.get(var_id, 0)
        rows.append({
            "Product ID": info["product_id"],
            "Product Name": info["product_name"],
            "SKU": info["sku"],
            "Categories": info["categories"],
            "Price": info["price"],
            "Tax - GST (10%)": info["tax_gst"],
            "Current Quantity Vie Market & Bar": qty,
            "Default Unit Cost": info["default_unit_cost"],
            "Unit": info["unit"],
            "source_date": today,
            "Stock on Hand": qty,
            "Default Vendor": info["default_vendor"],
        })

    df = pd.DataFrame(rows)
    print(f"✅ Fetched {len(df)} inventory items from Square")
    return df


# ============================================
# Sync Customers/Members (Customers API)
# ============================================

def sync_customers() -> pd.DataFrame:
    """
    Fetch customers from Square Customers API — only those enrolled in loyalty.
    Non-loyalty customers (card-only transactions, orphan records) are excluded.

    Returns:
        DataFrame with member rows (loyalty-enrolled only)
    """
    from .db_supabase import get_supabase_client

    client = get_square_client()

    # 1. Get the set of customer IDs enrolled in loyalty
    supa = get_supabase_client()
    loyalty_ids = set()
    offset = 0
    page_size = 1000
    while True:
        result = supa.table_select("member_loyalty", columns="customer_id", limit=page_size, offset=offset)
        batch = result.get("data", [])
        for r in batch:
            loyalty_ids.add(r["customer_id"])
        if len(batch) < page_size:
            break
        offset += page_size
    print(f"  📋 {len(loyalty_ids)} loyalty-enrolled customer IDs loaded")

    # 2. Fetch all customers from Square (SyncPager auto-paginates)
    all_customers = list(client.customers.list(limit=100))
    print(f"  📥 {len(all_customers)} total customers in Square")

    # 3. Filter to loyalty-enrolled only
    rows = []
    for customer in all_customers:
        cid = customer.id or ""
        if cid not in loyalty_ids:
            continue
        address = customer.address or None
        rows.append({
            "Square Customer ID": cid,
            "First Name": customer.given_name or "",
            "Last Name": customer.family_name or "",
            "Email Address": customer.email_address or "",
            "Phone Number": customer.phone_number or "",
            "Creation Date": customer.created_at or "",
            "Customer Note": customer.note or "",
            "Reference ID": customer.reference_id or "",
            # New fields for SMS marketing & analytics
            "Birthday": customer.birthday or "",
            "Company Name": customer.company_name or "",
            "Address Line 1": getattr(address, "address_line_1", "") or "" if address else "",
            "Locality": getattr(address, "locality", "") or "" if address else "",
            "Postal Code": getattr(address, "postal_code", "") or "" if address else "",
            "Creation Source": customer.creation_source or "",
            "Group IDs": ",".join(customer.group_ids or []),
            "Segment IDs": ",".join(customer.segment_ids or []),
            "Updated At": customer.updated_at or "",
        })

    df = pd.DataFrame(rows)
    skipped = len(all_customers) - len(df)
    print(f"✅ Fetched {len(df)} loyalty members from Square ({skipped} non-loyalty skipped)")
    return df


# ============================================
# Category Enrichment
# ============================================

def enrich_transaction_categories(tx_df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich transactions with category names from the catalog.
    Safety net — categories should already be set during sync_transactions.
    """
    if tx_df.empty:
        return tx_df

    try:
        catalog_map = build_catalog_map()
        
        # Fill in missing categories
        mask = tx_df["Category"].isna() | (tx_df["Category"] == "")
        if mask.any():
            tx_df.loc[mask, "Category"] = tx_df.loc[mask, "Item"].apply(
                lambda item: _lookup_category(str(item), str(item), catalog_map)
            )

    except Exception as e:
        print(f"Warning: Category enrichment failed: {e}")

    return tx_df


# ============================================
# Daily Summary Maintenance
# ============================================

def _update_daily_summaries(tx_df: pd.DataFrame):
    """Recalculate daily_item_summary for all dates touched by synced transactions.
    
    For each affected date, loads ALL transactions for that date from Supabase, 
    aggregates, and upserts to ensure correctness (not just incremental).
    """
    from services.db_supabase import (
        get_supabase_client,
        load_transactions_for_date,
    )
    
    if tx_df.empty:
        return
    
    # Find unique dates in the synced transactions
    if "Date" in tx_df.columns:
        dates = tx_df["Date"].dropna().unique().tolist()
    else:
        return
    
    if not dates:
        return
    
    client = get_supabase_client()
    total_upserted = 0
    
    for date_str in dates:
        # Load ALL transactions for this date (not just the synced ones)
        day_tx = load_transactions_for_date(date_str)
        if day_tx.empty:
            continue
        
        # Aggregate by (date, category, item)
        grouped = day_tx.groupby(["Date", "Category", "Item"], dropna=False).agg(
            total_qty=("Qty", "sum"),
            total_net_sales=("Net Sales", "sum"),
            total_gross_sales=("Gross Sales", "sum"),
            total_discounts=("Discounts", "sum"),
            total_tax=("Tax", lambda x: pd.to_numeric(x, errors="coerce").sum()),
            transaction_count=("Transaction ID", "nunique"),
        ).reset_index()
        
        # Build records for upsert
        records = []
        for _, row in grouped.iterrows():
            records.append({
                "date": str(row["Date"]),
                "category": str(row["Category"]) if pd.notna(row["Category"]) else "",
                "item": str(row["Item"]) if pd.notna(row["Item"]) else "",
                "total_qty": round(float(row["total_qty"]), 2),
                "total_net_sales": round(float(row["total_net_sales"]), 2),
                "total_gross_sales": round(float(row["total_gross_sales"]), 2),
                "total_discounts": round(float(row["total_discounts"]), 2),
                "total_tax": round(float(row["total_tax"]), 2),
                "transaction_count": int(row["transaction_count"]),
            })
        
        if records:
            # Upsert in batches
            for i in range(0, len(records), 500):
                batch = records[i:i+500]
                client.table_insert(
                    "daily_item_summary",
                    batch,
                    on_conflict="date,category,item",
                )
            total_upserted += len(records)
    
    print(f"✅ Updated daily_item_summary: {total_upserted} rows for {len(dates)} date(s)")


def _register_new_categories(tx_df: pd.DataFrame):
    """Auto-register any new categories seen in synced transactions.
    
    Inserts new categories into category_mappings with side='Retail' (default).
    New categories will be flagged as unassigned (assigned_at=NULL) so the
    dashboard Settings page can show a notification to classify them.
    """
    from services.db_supabase import get_supabase_client

    if tx_df.empty or "Category" not in tx_df.columns:
        return

    # Get unique non-empty categories from the synced data
    categories = tx_df["Category"].dropna().unique().tolist()
    categories = [c for c in categories if c and str(c).strip() and str(c) not in ("nan", "Uncategorized", "None")]

    if not categories:
        return

    client = get_supabase_client()
    
    # Load existing categories
    existing = client.table("category_mappings").select("category").execute()
    existing_set = {r["category"] for r in (existing.data or [])}
    
    # Find truly new categories
    new_cats = [c for c in categories if str(c) not in existing_set]
    
    if not new_cats:
        return

    # Insert with side='Retail' default, assigned_at=NULL (flagged for review)
    records = [
        {"category": str(c), "side": "Retail", "assigned_at": None}
        for c in new_cats
    ]
    
    try:
        client.table("category_mappings").upsert(
            records, on_conflict="category"
        ).execute()
        print(f"🆕 Registered {len(new_cats)} new category(ies): {', '.join(new_cats)}")
    except Exception as e:
        print(f"⚠️ Category registration failed: {e}")


def _update_daily_store_stats(tx_df: pd.DataFrame):
    """Recalculate daily_store_stats for affected dates (member vs non-member split).
    
    Rule: any transaction with a Customer ID = member, without = non-member.
    """
    from services.db_supabase import get_supabase_client, load_transactions_for_date
    
    if tx_df.empty:
        return
    
    if "Date" not in tx_df.columns:
        return
    
    dates = tx_df["Date"].dropna().unique().tolist()
    if not dates:
        return
    
    client = get_supabase_client()
    total_upserted = 0
    
    for date_str in dates:
        day_tx = load_transactions_for_date(date_str)
        if day_tx.empty:
            continue
        
        # Member = has Customer ID
        has_cid = day_tx["Customer ID"].notna() & (day_tx["Customer ID"].astype(str).str.strip() != "")
        member_tx = day_tx[has_cid]
        nonmember_tx = day_tx[~has_cid]
        
        total_transactions = day_tx["Transaction ID"].nunique() if "Transaction ID" in day_tx.columns else len(day_tx)
        member_transactions = member_tx["Transaction ID"].nunique() if "Transaction ID" in member_tx.columns and not member_tx.empty else 0
        nonmember_transactions = nonmember_tx["Transaction ID"].nunique() if "Transaction ID" in nonmember_tx.columns and not nonmember_tx.empty else 0
        
        total_sales = pd.to_numeric(day_tx["Net Sales"], errors="coerce").sum()
        total_gross = pd.to_numeric(day_tx["Gross Sales"], errors="coerce").sum()
        member_sales = pd.to_numeric(member_tx["Net Sales"], errors="coerce").sum() if not member_tx.empty else 0
        nonmember_sales = pd.to_numeric(nonmember_tx["Net Sales"], errors="coerce").sum() if not nonmember_tx.empty else 0
        
        total_items = pd.to_numeric(day_tx["Qty"], errors="coerce").sum()
        member_items = pd.to_numeric(member_tx["Qty"], errors="coerce").sum() if not member_tx.empty else 0
        nonmember_items = pd.to_numeric(nonmember_tx["Qty"], errors="coerce").sum() if not nonmember_tx.empty else 0
        
        member_unique = member_tx["Customer ID"].nunique() if not member_tx.empty else 0
        total_unique = day_tx[has_cid]["Customer ID"].nunique() if has_cid.any() else 0
        
        record = {
            "date": date_str,
            "total_transactions": int(total_transactions),
            "total_net_sales": round(float(total_sales), 2),
            "total_gross_sales": round(float(total_gross), 2),
            "total_items": int(total_items),
            "total_unique_customers": int(total_unique),
            "member_transactions": int(member_transactions),
            "member_net_sales": round(float(member_sales), 2),
            "member_items": int(member_items),
            "member_unique_customers": int(member_unique),
            "non_member_transactions": int(nonmember_transactions),
            "non_member_net_sales": round(float(nonmember_sales), 2),
            "non_member_items": int(nonmember_items),
            "member_tx_ratio": round(member_transactions / total_transactions, 4) if total_transactions > 0 else 0,
            "member_sales_ratio": round(float(member_sales) / float(total_sales), 4) if total_sales > 0 else 0,
            "member_items_ratio": round(float(member_items) / float(total_items), 4) if total_items > 0 else 0,
        }
        
        client.table_insert("daily_store_stats", [record], on_conflict="date")
        total_upserted += 1
    
    print(f"✅ Updated daily_store_stats: {total_upserted} row(s) for {len(dates)} date(s)")


# ============================================
# Full Sync Orchestrator
# ============================================

def run_full_sync(hours_back: int = 2) -> dict:
    """
    Run a full sync: transactions + inventory + customers.

    Args:
        hours_back: Hours of transaction history to fetch

    Returns:
        dict with sync results
    """
    from services.db_supabase import (
        upsert_transactions,
        upsert_inventory,
        upsert_members,
    )

    results = {
        "started_at": datetime.now().isoformat(),
        "transactions": 0,
        "inventory": 0,
        "customers": 0,
        "errors": [],
    }

    # 1) Sync transactions
    try:
        tx_df = sync_transactions(hours_back=hours_back)
        if not tx_df.empty:
            tx_df = enrich_transaction_categories(tx_df)

            # row_key is already set in sync_transactions() as __row_key
            # using deterministic format: {order_id}-LI-{idx}

            results["transactions"] = upsert_transactions(tx_df)
            
            # Update daily_item_summary for affected dates
            try:
                _update_daily_summaries(tx_df)
            except Exception as e:
                print(f"⚠️ Daily summary update failed: {e}")
            
            # Update daily_store_stats (member vs non-member splits)
            try:
                _update_daily_store_stats(tx_df)
            except Exception as e:
                print(f"⚠️ Daily store stats update failed: {e}")
            
            # Auto-register any new categories for dashboard classification
            try:
                _register_new_categories(tx_df)
            except Exception as e:
                print(f"⚠️ Category registration failed: {e}")
    except Exception as e:
        results["errors"].append(f"Transactions: {e}")
        print(f"❌ Transaction sync failed: {e}")

    # 2) Sync inventory
    try:
        inv_df = sync_inventory()
        if not inv_df.empty:
            results["inventory"] = upsert_inventory(inv_df)
    except Exception as e:
        results["errors"].append(f"Inventory: {e}")
        print(f"❌ Inventory sync failed: {e}")

    # 3) Sync customers
    try:
        cust_df = sync_customers()
        if not cust_df.empty:
            results["customers"] = upsert_members(cust_df)
    except Exception as e:
        results["errors"].append(f"Customers: {e}")
        print(f"❌ Customer sync failed: {e}")

    results["completed_at"] = datetime.now().isoformat()
    results["status"] = "success" if not results["errors"] else "partial"

    # Log to Supabase
    try:
        from services.db_supabase import get_supabase_client
        client = get_supabase_client()
        client.table("sync_log").insert({
            "sync_type": "full",
            "started_at": results["started_at"],
            "completed_at": results["completed_at"],
            "records_synced": results["transactions"] + results["inventory"] + results["customers"],
            "status": results["status"],
            "error_message": "; ".join(results["errors"]) if results["errors"] else None,
        }).execute()
    except Exception:
        pass

    return results


# ============================================
# Smart Sync (fill missing data)
# ============================================

def run_smart_sync() -> dict:
    """
    Detect the latest transaction in Supabase, then sync only the gap
    from that point to now.  Falls back to 365 days if the table is empty.

    Returns:
        dict with sync results (same format as run_full_sync)
    """
    from services.db_supabase import get_latest_transaction_date

    latest = get_latest_transaction_date()          # e.g. "2025-06-15T23:45:00+00:00"

    if latest:
        latest_dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
        # Overlap by 2 hours to catch any edge-case duplicates (upsert handles dedup)
        start_from = latest_dt - timedelta(hours=2)
        gap = datetime.now(timezone.utc) - latest_dt
        gap_hours = round(gap.total_seconds() / 3600, 1)
        gap_days  = round(gap.total_seconds() / 86400, 1)
        print(f"📊 Latest transaction in Supabase: {latest_dt.isoformat()}")
        print(f"📊 Gap to fill: ~{gap_days} days ({gap_hours} hours)")
    else:
        # Empty database — pull last 365 days
        start_from = datetime.now(timezone.utc) - timedelta(days=365)
        print("📊 No transactions found in Supabase — pulling last 365 days")

    # Use run_full_sync but override the start_from for transactions
    from services.db_supabase import (
        upsert_transactions,
        upsert_inventory,
        upsert_members,
    )

    results = {
        "started_at": datetime.now().isoformat(),
        "transactions": 0,
        "inventory": 0,
        "customers": 0,
        "errors": [],
        "gap_info": f"from {start_from.isoformat()}",
    }

    # 1) Sync transactions from the detected gap
    try:
        tx_df = sync_transactions(start_from=start_from)
        if not tx_df.empty:
            tx_df = enrich_transaction_categories(tx_df)

            # row_key is already set in sync_transactions() as __row_key
            # using deterministic format: {order_id}-LI-{idx}

            results["transactions"] = upsert_transactions(tx_df)
            
            # Update daily summaries
            try:
                _update_daily_summaries(tx_df)
            except Exception as e:
                print(f"⚠️ Daily summary update failed: {e}")
            
            try:
                _update_daily_store_stats(tx_df)
            except Exception as e:
                print(f"⚠️ Daily store stats update failed: {e}")
            
            # Auto-register any new categories
            try:
                _register_new_categories(tx_df)
            except Exception as e:
                print(f"⚠️ Category registration failed: {e}")
    except Exception as e:
        results["errors"].append(f"Transactions: {e}")
        print(f"❌ Transaction sync failed: {e}")

    # 2) Sync inventory (always full snapshot)
    try:
        inv_df = sync_inventory()
        if not inv_df.empty:
            results["inventory"] = upsert_inventory(inv_df)
    except Exception as e:
        results["errors"].append(f"Inventory: {e}")
        print(f"❌ Inventory sync failed: {e}")

    # 3) Sync customers (always full snapshot)
    try:
        cust_df = sync_customers()
        if not cust_df.empty:
            results["customers"] = upsert_members(cust_df)
    except Exception as e:
        results["errors"].append(f"Customers: {e}")
        print(f"❌ Customer sync failed: {e}")

    results["completed_at"] = datetime.now().isoformat()
    results["status"] = "success" if not results["errors"] else "partial"

    # Log to Supabase
    try:
        from services.db_supabase import get_supabase_client
        client = get_supabase_client()
        client.table("sync_log").insert({
            "sync_type": "smart",
            "started_at": results["started_at"],
            "completed_at": results["completed_at"],
            "records_synced": results["transactions"] + results["inventory"] + results["customers"],
            "status": results["status"],
            "error_message": "; ".join(results["errors"]) if results["errors"] else None,
        }).execute()
    except Exception:
        pass

    return results


# ============================================
# CLI Entry Point
# ============================================

if __name__ == "__main__":
    """Run sync from command line (used by GitHub Actions)."""
    from dotenv import load_dotenv
    load_dotenv()

    # If --smart flag passed, use smart sync; otherwise use hours_back
    if "--smart" in sys.argv:
        print("🔄 Starting smart Square → Supabase sync (filling missing data)...")
        results = run_smart_sync()
    else:
        hours = int(sys.argv[1]) if len(sys.argv) > 1 else 2
        print(f"🔄 Starting Square → Supabase sync ({hours}h window)...")
        results = run_full_sync(hours_back=hours)

    print(f"\n{'='*50}")
    print(f"📊 Sync Results:")
    print(f"   Transactions: {results['transactions']} rows")
    print(f"   Inventory:    {results['inventory']} items")
    print(f"   Customers:    {results['customers']} members")
    print(f"   Status:       {results['status']}")
    if results.get("gap_info"):
        print(f"   Gap:          {results['gap_info']}")
    if results["errors"]:
        print(f"   Errors:       {results['errors']}")
    print(f"{'='*50}")
