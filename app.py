import streamlit as st
from datetime import datetime, timedelta, date
import pandas as pd

from services.logger import init_logging, LOG_FILE, log_info, log_warning, log_error

st.set_page_config(
    page_title="Vie Manly Analytics",
    layout="wide",
    initial_sidebar_state="auto"
)
init_logging()


import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
import os
import numpy as np

# === Cloud imports (Supabase) ===
from services.db_supabase import (
    get_db, get_supabase_client, load_all, load_transactions,
    load_inventory, load_members, init_database,
    get_table_row_count, reset_db_connection
)
from init_db import init_db

from charts.high_level import show_high_level
from charts.sales_report import show_sales_report
from charts.inventory import show_inventory
from charts.product_mix_only import show_product_mix_only
from charts.customer_segmentation import show_customer_segmentation

# Load dotenv for local development
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not needed on Streamlit Cloud (uses secrets.toml)


def check_memory():
    try:
        import psutil
        mem = psutil.virtual_memory()
        used_gb = mem.used / (1024 ** 3)
        total_gb = mem.total / (1024 ** 3)
        usage_ratio = used_gb / total_gb

        if usage_ratio > 0.85:
            st.warning(f"⚠️ Memory usage high ({usage_ratio*100:.1f}%). Please refresh occasionally.")
    except ImportError:
        pass  # psutil not required on cloud


# 关闭文件监控，避免 Streamlit Cloud 报 inotify 错误
os.environ["WATCHDOG_DISABLE_FILE_WATCH"] = "true"

# ✅ Ensure Supabase tables exist (no-op — tables managed via Supabase dashboard)
init_db()


st.markdown("<h1 style='font-size:26px; font-weight:700;'>📊 Vie Manly Dashboard</h1>", unsafe_allow_html=True)

@st.cache_data(ttl=300, show_spinner="Loading data from cloud...")
def load_db_cached(_cache_key):
    """Load all data from Supabase. Cached for 5 minutes."""
    return load_all()

def reload_db_cache():
    """Force reload data from Supabase."""
    st.session_state.pop("db_cache", None)
    load_db_cached.clear()
    cache_key = datetime.now().isoformat()
    st.session_state.db_cache = load_db_cached(cache_key)

BAD_DATES = {
    date(2025, 8, 18),
    date(2025, 8, 19),
    date(2025, 8, 20),
}
def check_missing_data(tx, inv):
    """
    分开检查交易和库存的缺失日期：

    - 交易（transactions）：
        * 从固定的起始日期 tx_start_date 开始（你可以根据需要改）
        * 到今天为止，每一天如果在数据库里完全没有交易记录，就标记为缺失

    - 库存（inventory）：
        * 从固定的起始日期 inv_start_date 开始（你明确说要从 2025-11-01）
        * 到今天为止，每一天如果在数据库里没有任何 inventory 记录，就标记为缺失
    """
    missing_info = {
        "transaction_dates": [],
        "inventory_dates": [],
    }

    today = datetime.now().date()

    # ===== 1. 交易缺失检查 =====
    tx_start_date = date(2024, 1, 1)

    if tx is not None and not tx.empty and "Datetime" in tx.columns:
        tx_dates_series = pd.to_datetime(tx["Datetime"], errors="coerce").dt.date
        tx_dates = set(d for d in tx_dates_series.dropna())

        if tx_start_date <= today:
            all_days = [
                tx_start_date + timedelta(days=i)
                for i in range((today - tx_start_date).days + 1)
            ]
            missing_tx = [
                d for d in all_days
                if d not in tx_dates and d not in BAD_DATES
            ]

            missing_info["transaction_dates"] = missing_tx

    # ===== 2. 库存缺失检查 =====
    inv_start_date = date(2025, 11, 1)

    if inv is not None and not inv.empty and "source_date" in inv.columns:
        inv_dates_series = pd.to_datetime(inv["source_date"], errors="coerce").dt.date
        inv_dates = set(d for d in inv_dates_series.dropna())

        if inv_start_date <= today:
            all_days = [
                inv_start_date + timedelta(days=i)
                for i in range((today - inv_start_date).days + 1)
            ]
            missing_inv = [d for d in all_days if d not in inv_dates]
            missing_info["inventory_dates"] = missing_inv

    return missing_info

if "db_auto_reloaded" not in st.session_state:
    reload_db_cache()
    st.session_state.db_auto_reloaded = True

tx, mem, inv = st.session_state.db_cache


# === Sidebar ===
st.sidebar.header("⚙️ Settings")

# === 数据缺失预警 ===
missing_data = check_missing_data(tx, inv)

if missing_data['transaction_dates'] or missing_data['inventory_dates']:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚠️ Data missing warning")

    if missing_data['transaction_dates']:
        st.sidebar.error("**Missing transaction date:**")
        # 显示最近7天的缺失日期，其他的折叠显示
        recent_missing = sorted(missing_data['transaction_dates'])[-7:]
        for d in recent_missing:
            st.sidebar.write(f"📅 {d.strftime('%Y-%m-%d')}")

        if len(missing_data['transaction_dates']) > 7:
            with st.sidebar.expander(f"check all {len(missing_data['transaction_dates'])} missing dates"):
                for d in sorted(missing_data['transaction_dates']):
                    st.write(f"📅 {d.strftime('%Y-%m-%d')}")

    if missing_data['inventory_dates']:
        st.sidebar.warning("**Missing inventory date:**")
        # 显示最近7天的缺失日期，其他的折叠显示
        recent_missing = sorted(missing_data['inventory_dates'])[-7:]
        for d in recent_missing:
            st.sidebar.write(f"📦 {d.strftime('%Y-%m-%d')}")

        if len(missing_data['inventory_dates']) > 7:
            with st.sidebar.expander(f"check all {len(missing_data['inventory_dates'])} missing dates"):
                for d in sorted(missing_data['inventory_dates']):
                    st.write(f"📦 {d.strftime('%Y-%m-%d')}")


# ===============================
# 🛠️ Database maintenance
# ===============================
st.sidebar.markdown("---")
st.sidebar.subheader("🛠️ Database")

# --- 1) Sync from Square (replaces Clear & Rebuild) ---
if st.sidebar.button("🔄 Sync from Square"):
    try:
        from services.square_sync import run_smart_sync
        with st.spinner("Detecting data gap and syncing from Square..."):
            result = run_smart_sync()
            reload_db_cache()
            gap = result.get('gap_info', '')
            st.sidebar.success(f"✅ Sync complete: {result.get('transactions', 0)} transactions synced ({gap})")
            st.rerun()
    except ImportError:
        st.sidebar.warning("⚠️ Square sync not configured yet. Set SQUARE_ACCESS_TOKEN in .env")
    except Exception as e:
        st.sidebar.error(f"❌ Sync failed: {e}")
        log_error(f"Square sync failed: {e}")


# --- 2) Refresh (cache only) ---
if st.sidebar.button("🔄 Refresh data"):
    reload_db_cache()
    st.sidebar.success("Reloading data…")
    st.rerun()


# --- 3) Debug Snapshot ---
if st.sidebar.button("Debug Snapshot"):
    try:
        log_info("🧪 DEBUG SNAPSHOT (Supabase)")
        log_info(f"🌐 Connected to Supabase")

        tx_count = get_table_row_count("transactions")
        inv_count = get_table_row_count("inventory")
        mem_count = get_table_row_count("members")

        log_info(f"📊 transactions: {tx_count} rows")
        log_info(f"📦 inventory: {inv_count} rows")
        log_info(f"👥 members: {mem_count} rows")

        # Show date ranges from loaded data
        if tx is not None and not tx.empty and "Datetime" in tx.columns:
            tx_dates = pd.to_datetime(tx["Datetime"], errors="coerce")
            log_info(
                f"📊 transactions: min_date={tx_dates.min()}, "
                f"max_date={tx_dates.max()}, "
                f"distinct_days={tx_dates.dt.date.nunique()}"
            )

        if inv is not None and not inv.empty and "source_date" in inv.columns:
            log_info(
                f"📦 inventory: min_date={inv['source_date'].min()}, "
                f"max_date={inv['source_date'].max()}, "
                f"distinct_days={inv['source_date'].nunique()}"
            )

        st.sidebar.success("Debug snapshot written to log.")

    except Exception as e:
        log_error(f"❌ DEBUG SNAPSHOT failed: {e}")
        st.sidebar.error("Debug snapshot failed. Check logs.")


with st.sidebar.expander("🪵 Logs"):
    st.caption(f"Log file: {LOG_FILE}")
    try:
        log_text = LOG_FILE.read_text(encoding="utf-8")
    except Exception:
        log_text = ""
    tail = "\n".join(log_text.splitlines()[-60:])
    st.text_area("Latest log lines", tail, height=220)
    st.download_button("Download app.log", log_text, file_name="app.log", mime="text/plain")


# === 单位选择 ===
st.sidebar.subheader("📏 Units")

if inv is not None and not inv.empty and "Unit" in inv.columns:
    units_available = sorted(inv["Unit"].dropna().unique().tolist())
else:
    units_available = ["Gram 1.000", "Kilogram 1.000", "Milligram 1.000"]

# Load units from Supabase
try:
    client = get_supabase_client()
    response = client.table("units").select("name").execute()
    db_units = [r["name"] for r in response.data] if response.data else []
except Exception:
    db_units = []

all_units = sorted(list(set(units_available + db_units)))
unit = st.sidebar.selectbox("Choose unit", all_units)

new_unit = st.sidebar.text_input("Add new unit")
if st.sidebar.button("➕ Add Unit"):
    if new_unit and new_unit not in all_units:
        try:
            client = get_supabase_client()
            client.table("units").upsert(
                {"name": new_unit}, on_conflict="name"
            ).execute()
            st.sidebar.success(f"✅ Added new unit: {new_unit}")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"❌ Failed to add unit: {e}")

# === Section 选择 ===
section = st.sidebar.radio("📂 Sections", [
    "High Level report",
    "Sales report by category",
    "Inventory",
    "product mix",
    "Customers insights"
])

# === 主体展示 ===
if section == "High Level report":
    show_high_level(tx, mem, inv)
elif section == "Sales report by category":
    show_sales_report(tx, inv)
elif section == "Inventory":
    show_inventory(tx, inv)
elif section == "product mix":
    show_product_mix_only(tx, inv)
elif section == "Customers insights":
    show_customer_segmentation(tx, mem)