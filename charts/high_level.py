import streamlit as st
import pandas as pd
import plotly.express as px
import math
import numpy as np
from services.category_rules import is_bar_category

def safe_fmt(x, digits=2, default="—"):
    try:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return default
        return f"{float(x):.{digits}f}"
    except Exception:
        return default

def _safe_sum(df, col):
    if df is None or df.empty or col not in df.columns:
        return 0.0
    s = df[col]
    if pd.api.types.is_numeric_dtype(s):
        return float(pd.to_numeric(s, errors="coerce").sum(skipna=True))
    s = (
        s.astype(str)
        .str.replace(r"[^0-9\.\-]", "", regex=True)
        .replace("", pd.NA)
    )
    return float(pd.to_numeric(s, errors="coerce").sum(skipna=True) or 0.0)


def proper_round(x):
    """标准的四舍五入方法，处理浮点数精度问题"""
    if pd.isna(x):
        return x
    # 处理浮点数精度问题
    x_rounded = round(x, 10)  # 先舍入到10位小数消除精度误差
    return math.floor(x_rounded + 0.5)


def persisting_multiselect(label, options, key, default=None, width_chars=None):
    if key not in st.session_state:
        st.session_state[key] = default or []

    # === 修改：添加自定义宽度参数 ===
    if width_chars is None:
        # 默认宽度为标签长度+1字符
        label_width = len(label)
        min_width = label_width + 1
    else:
        # 使用自定义宽度
        min_width = width_chars

    st.markdown(f"""
    <style>
        /* 强制设置多选框宽度 */
        [data-testid*="{key}"] {{
            width: {min_width}ch !important;
            min-width: {min_width}ch !important;
        }}
        [data-testid*="{key}"] > div {{
            width: {min_width}ch !important;
            min-width: {min_width}ch !important;
        }}
        [data-testid*="{key}"] [data-baseweb="select"] {{
            width: {min_width}ch !important;
            min-width: {min_width}ch !important;
        }}
        [data-testid*="{key}"] [data-baseweb="select"] > div {{
            width: {min_width}ch !important;
            min-width: {min_width}ch !important;
        }}
    </style>
    """, unsafe_allow_html=True)

    return st.multiselect(label, options, default=st.session_state[key], key=key)


# === 预加载所有数据 ===


@st.cache_data(ttl=600, show_spinner=False)
def _prepare_inventory_grouped(inv: pd.DataFrame):
    if inv is None or inv.empty:
        return pd.DataFrame(), None

    df = inv.copy()

    if "source_date" in df.columns:
        df["date"] = pd.to_datetime(df["source_date"], errors="coerce")
        # === 修复：过滤掉转换失败的日期 ===
        df = df[df["date"].notna()]
    else:
        return pd.DataFrame(), None

    # Category 列
    if "Categories" in df.columns:
        df["Category"] = df["Categories"].astype(str)
    elif "Category" in df.columns:
        df["Category"] = df["Category"].astype(str)
    else:
        df["Category"] = "Unknown"

    # === 用 catalogue 现算 - 应用新的inventory value计算逻辑 ===
    # 1. 过滤掉 Current Quantity Vie Market & Bar 为负数或0的行
    df["Quantity"] = pd.to_numeric(df["Current Quantity Vie Market & Bar"], errors="coerce")
    mask = (df["Quantity"] > 0)  # 只保留正数
    df = df[mask].copy()

    if df.empty:
        return pd.DataFrame(), None

    # 2. 把 Default Unit Cost 为空的值补为0
    df["UnitCost"] = pd.to_numeric(df["Default Unit Cost"], errors="coerce").fillna(0)

    # 3. 计算 inventory value: Default Unit Cost * Current Quantity Vie Market & Bar
    df["Inventory Value"] = df["UnitCost"] * df["Quantity"]

    # 四舍五入保留整数
    df["Inventory Value"] = df["Inventory Value"].apply(lambda x: proper_round(x) if not pd.isna(x) else 0)

    # 保留其他计算（如果需要）
    df["Price"] = pd.to_numeric(df.get("Price", 0), errors="coerce").fillna(0)

    # 修复：检查 TaxFlag 列是否存在，如果不存在则创建默认值
    if "TaxFlag" not in df.columns:
        df["TaxFlag"] = "N"  # 默认值，假设不含税

    def calc_retail(row):
        try:
            O, AA, tax = row["Price"], row["Quantity"], row["TaxFlag"]
            return (O / 11 * 10) * AA if tax == "Y" else O * AA
        except KeyError:
            # 如果列不存在，直接计算 Price * Quantity
            return row["Price"] * row["Quantity"]

    df["Retail Total"] = df.apply(calc_retail, axis=1)
    df["Profit"] = df["Retail Total"] - df["Inventory Value"]

    # 聚合
    g = (
        df.groupby(["date", "Category"], as_index=False)[["Inventory Value", "Profit"]]
        .sum(min_count=1)
    )

    latest_date = g["date"].max() if not g.empty else None
    return g, latest_date

BAD_DATES = set(pd.to_datetime([
    "2025-08-18",
    "2025-08-19",
    "2025-08-20",
]))

# === 预加载所有数据 ===
def preload_all_data(tx_df):
    """预加载所有需要的数据 — pure pandas, no SQL"""
    if tx_df is None or tx_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    tx = tx_df.copy()

    # Ensure Datetime is datetime type
    tx["Datetime"] = pd.to_datetime(tx["Datetime"], errors="coerce")
    tx["date"] = tx["Datetime"].dt.normalize()
    tx["Net Sales"] = pd.to_numeric(tx["Net Sales"], errors="coerce").fillna(0)
    tx["Qty"] = pd.to_numeric(tx["Qty"], errors="coerce").fillna(0)

    # ── daily aggregation (replaces daily_sql) ──
    txn_agg = tx.groupby(["date", "Transaction ID"]).agg(
        total_net_sales=("Net Sales", "sum"),
        total_qty=("Qty", "sum")
    ).reset_index()

    daily = txn_agg.groupby("date").agg(
        net_sales=("total_net_sales", "sum"),
        transactions=("Transaction ID", "nunique"),
        qty=("total_qty", "sum")
    ).reset_index()
    daily["avg_txn"] = daily.apply(
        lambda r: r["net_sales"] / r["transactions"] if r["transactions"] > 0 else 0, axis=1
    )

    # ── category aggregation (replaces category_sql) ──
    tx["Category"] = tx["Category"].fillna("None").replace("", "None").str.strip()
    tx.loc[tx["Category"] == "", "Category"] = "None"

    cat_txn_agg = tx.groupby(["date", "Category", "Transaction ID"]).agg(
        cat_net_sales=("Net Sales", "sum"),
        cat_qty=("Qty", "sum")
    ).reset_index()

    category = cat_txn_agg.groupby(["date", "Category"]).agg(
        net_sales=("cat_net_sales", "sum"),
        transactions=("Transaction ID", "nunique"),
        qty=("cat_qty", "sum")
    ).reset_index()
    category["avg_txn"] = category.apply(
        lambda r: r["net_sales"] / r["transactions"] if r["transactions"] > 0 else 0, axis=1
    )

    # ── post-processing (same as before) ──
    if not daily.empty:
        daily["date_raw"] = daily["date"]
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()

        invalid_mask = daily["date"].isna()
        if invalid_mask.any():
            print("⚠️ High level: invalid date rows:", daily.loc[invalid_mask, "date_raw"].unique()[:5])

        daily = daily.sort_values("date")
        daily["_is_bad_date"] = daily["date"].isin(BAD_DATES)
        daily["3M_Avg_Rolling"] = daily["net_sales"].rolling(window=90, min_periods=1, center=False).mean()
        daily["6M_Avg_Rolling"] = daily["net_sales"].rolling(window=180, min_periods=1, center=False).mean()

    if not category.empty:
        category["date"] = pd.to_datetime(category["date"], errors="coerce")
        category = category[category["date"].notna()]
        category = category.sort_values(["Category", "date"])

        category_with_rolling = []
        for cat in category["Category"].unique():
            cat_data = category[category["Category"] == cat].copy()
            cat_data = cat_data.sort_values("date")
            cat_data["3M_Avg_Rolling"] = cat_data["net_sales"].rolling(window=90, min_periods=1, center=False).mean()
            cat_data["6M_Avg_Rolling"] = cat_data["net_sales"].rolling(window=180, min_periods=1, center=False).mean()
            category_with_rolling.append(cat_data)

        category = pd.concat(category_with_rolling, ignore_index=True)

    return daily, category


@st.cache_data(ttl=300, max_entries=50, show_spinner=False)
def prepare_chart_data_fast(daily, category_tx, inv_grouped, time_range, data_sel, cats_sel,
                            custom_dates_selected=False, t1=None, t2=None):
    """快速准备图表数据 - 优化缓存稳定性"""

    # 检查 daily 数据是否存在且不为空
    if daily is not None and not daily.empty and 'date' in daily.columns:
        daily_dates = daily['date'].dropna()  # 过滤掉 NaT 值
        if not daily_dates.empty:
            print(f"daily data date range: {daily_dates.min()} to {daily_dates.max()}")
        else:
            print("daily data date range: No valid dates after filtering NaT")
    else:
        print("daily data date range: No date column or empty dataframe")

    # 稳定缓存键 - 对列表参数排序确保缓存键一致
    time_range = list(dict.fromkeys(time_range))  # 去重但保持用户选择顺序
    data_sel = sorted(data_sel) if data_sel else []
    cats_sel = sorted(cats_sel) if cats_sel else []

    if not time_range or not data_sel or not cats_sel:
        return None

    # 应用时间范围筛选到daily数据
    daily_filtered = daily.copy()

    # === 修复：确保日期列是 datetime 类型并过滤 NaT ===
    if 'date' in daily_filtered.columns:
        daily_filtered['date'] = pd.to_datetime(daily_filtered['date'], errors='coerce')
        daily_filtered = daily_filtered[daily_filtered['date'].notna()]  # 过滤掉 NaT 值

    grouped_tx = category_tx.copy()
    if 'date' in grouped_tx.columns:
        grouped_tx['date'] = pd.to_datetime(grouped_tx['date'], errors='coerce')
        grouped_tx = grouped_tx[grouped_tx['date'].notna()]  # 过滤掉 NaT 值

    # === 优化：统一定义时间边界 ===
    today = pd.Timestamp.today().normalize()
    start_of_week = today - pd.Timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)

    # === 修复：重新设计时间筛选逻辑 ===
    # 如果选择了"Custom date"，则只使用自定义日期范围，忽略其他时间范围
    if "Custom date" in time_range and t1 and t2:
        print("=== DEBUG: Using CUSTOM DATE RANGE ===")
        t1_ts = pd.to_datetime(t1)
        t2_ts = pd.to_datetime(t2)

        daily_filtered = daily_filtered[
            (daily_filtered["date"] >= t1_ts) & (daily_filtered["date"] <= t2_ts)]
        grouped_tx = grouped_tx[
            (grouped_tx["date"] >= t1_ts) & (grouped_tx["date"] <= t2_ts)]

    elif any(x in time_range for x in ["WTD", "MTD", "YTD"]):
        # 如果没有选择自定义日期，则使用其他时间范围选项
        print("=== DEBUG: Using STANDARD TIME RANGES ===")

        # === 修复：重置索引以避免布尔索引对齐问题 ===
        daily_filtered = daily_filtered.reset_index(drop=True)
        grouped_tx = grouped_tx.reset_index(drop=True)

        # 应用多个时间范围筛选（WTD、MTD、YTD可以同时选择）
        date_filters = []

        if "WTD" in time_range:
            # 使用 .values 来避免索引对齐问题
            date_filters.append(daily_filtered["date"].values >= start_of_week)
            print("Applied WTD filter")

        if "MTD" in time_range:
            date_filters.append(daily_filtered["date"].values >= start_of_month)
            print("Applied MTD filter")

        if "YTD" in time_range:
            date_filters.append(daily_filtered["date"].values >= start_of_year)
            print("Applied YTD filter")

        # 如果有多个时间范围筛选条件，使用 OR 逻辑合并
        if date_filters:
            combined_filter = date_filters[0]
            for filter_condition in date_filters[1:]:
                combined_filter = combined_filter | filter_condition

            daily_filtered = daily_filtered[combined_filter]

            # ✅ 对 grouped_tx 单独计算过滤条件
            if date_filters:
                grouped_tx_filters = []
                if "WTD" in time_range:
                    grouped_tx_filters.append(grouped_tx["date"].values >= start_of_week)
                if "MTD" in time_range:
                    grouped_tx_filters.append(grouped_tx["date"].values >= start_of_month)
                if "YTD" in time_range:
                    grouped_tx_filters.append(grouped_tx["date"].values >= start_of_year)

                if grouped_tx_filters:
                    combined_tx_filter = grouped_tx_filters[0]
                    for fcond in grouped_tx_filters[1:]:
                        combined_tx_filter = combined_tx_filter | fcond
                    grouped_tx = grouped_tx[combined_tx_filter]

    # === 添加过滤后的日期范围验证 ===
    if daily_filtered is not None and not daily_filtered.empty and 'date' in daily_filtered.columns:
        filtered_dates = daily_filtered['date'].dropna()
        if not filtered_dates.empty:
            print(f"daily_filtered date range: {filtered_dates.min()} to {filtered_dates.max()}")
            print(f"daily_filtered dates count: {len(filtered_dates)}")
            print(f"Sample dates: {sorted(filtered_dates.unique())[:5]}")  # 显示前5个日期
        else:
            print("daily_filtered date range: No valid dates after filtering")
    else:
        print("daily_filtered date range: No date column or empty dataframe after filtering")

    # === 优化：对库存数据应用相同的时间范围筛选 ===
    grouped_inv = inv_grouped.copy()
    if not grouped_inv.empty:
        if "Custom date" in time_range and t1 and t2:
            grouped_inv = grouped_inv[
                (grouped_inv["date"] >= pd.to_datetime(t1)) & (grouped_inv["date"] <= pd.to_datetime(t2))]
        elif any(x in time_range for x in ["WTD", "MTD", "YTD"]):
            inv_filters = []

            if "WTD" in time_range:
                inv_filters.append(grouped_inv["date"] >= start_of_week)
            if "MTD" in time_range:
                inv_filters.append(grouped_inv["date"] >= start_of_month)
            if "YTD" in time_range:
                inv_filters.append(grouped_inv["date"] >= start_of_year)

            if inv_filters:
                combined_inv_filter = inv_filters[0]
                for filter_condition in inv_filters[1:]:
                    combined_inv_filter = combined_inv_filter | filter_condition
                grouped_inv = grouped_inv[combined_inv_filter]

    # === 修复：同步库存数据与销售数据的日期范围 ===
    if not daily_filtered.empty and not grouped_inv.empty:
        min_date, max_date = daily_filtered["date"].min(), daily_filtered["date"].max()
        grouped_inv = grouped_inv[
            (grouped_inv["date"] >= min_date) & (grouped_inv["date"] <= max_date)
        ]

    # === 修复：确保grouped_tx有Category列 ===
    if "Category" not in grouped_tx.columns:
        grouped_tx["Category"] = "Unknown"

    bar_cats = {
        "Cafe Drinks",
        "Smoothie Bar",
        "Soups",
        "Sweet Treats",
        "Wraps & Salads",
        "Breakfast Bowls",
        "Chia Bowls",  # ✅ 新增
    }

    # 修复：过滤掉没有数据的分类，避免重复显示
    small_cats = []
    for c in cats_sel:
        if c not in ("bar", "retail", "total"):
            small_cats.append(c)

    parts_tx = []
    # NEW: customers lookup table (date + Category -> daily_customers)
    customers_by_group = st.session_state.get("customers_by_group")
    if customers_by_group is not None and not customers_by_group.empty:
        customers_by_group = customers_by_group.copy()
        customers_by_group["date"] = pd.to_datetime(customers_by_group["date"], errors="coerce").dt.normalize()
        customers_by_group["Category"] = customers_by_group["Category"].astype(str)


    if small_cats:
        # 为小类数据添加滚动平均值
        small_cats_data = grouped_tx[grouped_tx["Category"].isin(small_cats)].copy()

        # 修复：按日期和分类重新计算 net_sales
        for cat in small_cats:
            cat_mask = small_cats_data["Category"] == cat
            if cat not in bar_cats:  # 非bar分类使用 net_sales 列
                # 按日期分组计算每个日期的 net_sales 总和
                daily_net_sales = small_cats_data[cat_mask].groupby("date")["net_sales"].sum().reset_index()
                # 结果四舍五入保留整数
                daily_net_sales["net_sales"] = daily_net_sales["net_sales"].apply(
                    lambda x: proper_round(x) if not pd.isna(x) else 0
                )

                # 更新原始数据中的 net_sales
                for _, row in daily_net_sales.iterrows():
                    date_mask = (small_cats_data["date"] == row["date"]) & (small_cats_data["Category"] == cat)
                    small_cats_data.loc[date_mask, "net_sales"] = row["net_sales"]
        # NEW: merge daily_customers for each Category
        if customers_by_group is not None and not customers_by_group.empty:
            small_cats_data = small_cats_data.merge(
                customers_by_group[customers_by_group["Category"].isin(small_cats)],
                on=["date", "Category"],
                how="left"
            )
            small_cats_data["daily_customers"] = small_cats_data["daily_customers"].fillna(0)


        parts_tx.append(small_cats_data)

    # 处理bar分类 - 重新计算bar的滚动平均（改为使用pure net sale）
    if "bar" in cats_sel:
        bar_tx = grouped_tx[grouped_tx["Category"].apply(is_bar_category)].copy()
        if not bar_tx.empty:
            # 改为使用 net_sales 列（纯净净销售额）
            bar_daily_agg = bar_tx.groupby("date").agg({
                "net_sales": "sum",
                "transactions": "sum",
                "qty": "sum"
            }).reset_index()

            # 同时把新列名统一为 net_sales，以兼容下游绘图逻辑
            #bar_daily_agg["net_sales"] = bar_daily_agg["net_sales"]

            # 计算bar的平均交易额
            bar_daily_agg["avg_txn"] = bar_daily_agg.apply(
                lambda x: x["net_sales"] / x["transactions"] if x["transactions"] > 0 else 0,
                axis=1
            )

            bar_daily_agg["3M_Avg_Rolling"] = np.nan
            bar_daily_agg["6M_Avg_Rolling"] = np.nan

            bar_daily_agg["Category"] = "bar"
            # NEW: merge bar daily_customers
            if customers_by_group is not None and not customers_by_group.empty:
                bar_daily_agg = bar_daily_agg.merge(
                    customers_by_group[customers_by_group["Category"] == "bar"][["date", "daily_customers"]],
                    on="date",
                    how="left"
                )
                bar_daily_agg["daily_customers"] = bar_daily_agg["daily_customers"].fillna(0)

            parts_tx.append(bar_daily_agg)

    # 处理retail分类 = total - bar
    if "retail" in cats_sel:
        # 获取每日total数据
        total_daily = daily_filtered.copy()
        total_daily = total_daily.rename(columns={
            "net_sales": "total_net_sales",
            "transactions": "total_transactions",
            "avg_txn": "total_avg_txn",
            "qty": "total_qty"
        })

        # 获取每日bar数据
        bar_daily = grouped_tx[grouped_tx["Category"].apply(is_bar_category)].groupby("date").agg({
            "net_sales": "sum",
            "transactions": "sum",
            "qty": "sum"
        }).reset_index()
        bar_daily = bar_daily.rename(columns={
            "net_sales": "bar_net_sales",
            "transactions": "bar_transactions",
            "qty": "bar_qty"
        })

        # === Retail 独立计算 ===
        retail_tx = grouped_tx[~grouped_tx["Category"].apply(is_bar_category)].copy()

        # 确保 txn_id 列存在
        if "txn_id" not in retail_tx.columns:
            # 如果 txn_id 不存在，我们需要创建一个
            # 检查是否有 transactions 列可以作为替代
            if "transactions" in retail_tx.columns:
                # 使用 transactions 列的值来创建唯一标识符
                retail_tx["txn_id"] = retail_tx.index.astype(str) + "_" + retail_tx["transactions"].astype(str)
            else:
                # 否则使用索引
                retail_tx["txn_id"] = retail_tx.index.astype(str)

        retail_daily = retail_tx.groupby("date").agg({
            "net_sales": "sum",
            "qty": "sum",
            "txn_id": "nunique"
        }).reset_index()

        retail_daily = retail_daily.rename(columns={"txn_id": "transactions"})

        # ✅ 关键修复：补全 retail 的日期（否则 category_tx 缺前段日期时图就只显示后段）
        # 以 daily_filtered 的日期做基准（它已按 Custom dates 过滤过）
        full_dates = pd.DataFrame({"date": daily_filtered["date"].drop_duplicates().sort_values()})

        retail_daily = full_dates.merge(retail_daily, on="date", how="left")
        retail_daily["net_sales"] = retail_daily["net_sales"].fillna(0)
        retail_daily["qty"] = retail_daily["qty"].fillna(0)
        retail_daily["transactions"] = retail_daily["transactions"].fillna(0).astype(int)

        # === 保持变量名结构不变：retail_data 用于后续 rolling & avg_tx 计算 ===
        retail_data = retail_daily.copy()
        # NEW: merge retail daily_customers
        if customers_by_group is not None and not customers_by_group.empty:
            retail_data = retail_data.merge(
                customers_by_group[customers_by_group["Category"] == "retail"][["date", "daily_customers"]],
                on="date",
                how="left"
            )
            retail_data["daily_customers"] = retail_data["daily_customers"].fillna(0)


        # === 修复：只在选择了3M/6M Avg时才计算滚动平均 ===
        retail_data["3M_Avg_Rolling"] = 0
        retail_data["6M_Avg_Rolling"] = 0

        # 计算平均交易额
        retail_data["avg_txn"] = retail_data.apply(
            lambda x: x["net_sales"] / x["transactions"] if x["transactions"] > 0 else 0,
            axis=1
        )

        # 只保留需要的列
        retail_tx = retail_data[
            ["date", "net_sales", "transactions", "avg_txn", "qty",
             "daily_customers",  # ✅ 加这一列
             "3M_Avg_Rolling", "6M_Avg_Rolling"]
        ].copy()

        retail_tx["Category"] = "retail"
        parts_tx.append(retail_tx)

    if "total" in cats_sel:
        total_tx = daily_filtered.copy()
        total_tx["Category"] = "total"
        parts_tx.append(total_tx)

    if not parts_tx:
        return None

    df_plot = pd.concat(parts_tx, ignore_index=True)
    df_plot["__is_weekly__"] = False
    df_plot["__source__"] = "tx"  # 默认都当交易来源

    if "daily_customers" not in df_plot.columns:
        df_plot["daily_customers"] = 0
    else:
        df_plot["daily_customers"] = pd.to_numeric(df_plot["daily_customers"], errors="coerce").fillna(0)

    # === 计算 Monthly Net Sales（每个月1号显示当月净销售额） ===
    if "Monthly Net Sales" in data_sel:
        # 先创建列，默认 0
        df_plot["monthly_net_sales"] = 0.0

        for cat in df_plot["Category"].unique():
            cat_data = df_plot[df_plot["Category"] == cat].copy()
            if cat_data.empty:
                continue

            # 按月汇总该分类的 net_sales
            cat_data = cat_data.set_index("date").sort_index()
            monthly_agg = (
                cat_data["net_sales"]
                .resample("MS")              # Month Start，每月1号
                .sum()
                .reset_index()
            )

            # 把每个月的总额写回 df_plot 对应那个月1号的行
            for _, row in monthly_agg.iterrows():
                month_start = row["date"]
                value = row["net_sales"]
                mask = (df_plot["Category"] == cat) & (df_plot["date"] == month_start)
                df_plot.loc[mask, "monthly_net_sales"] = value

    # ✅ 兜底：用户只勾 3M/6M Avg 时也不会 KeyError
    if "monthly_net_sales" not in df_plot.columns:
        df_plot["monthly_net_sales"] = 0.0

    # === Monthly Net Sales rolling (3M / 6M) ===
    if ("Monthly Net Sales 3M Avg" in data_sel) or ("Monthly Net Sales 6M Avg" in data_sel):

        # 先初始化列，避免后面出现 _x / _y
        df_plot["monthly_net_sales_3M_Avg"] = np.nan
        df_plot["monthly_net_sales_6M_Avg"] = np.nan

        for cat in df_plot["Category"].unique():
            # 只取“每月1号有值”的行
            m = df_plot[
                (df_plot["Category"] == cat) &
                (df_plot["monthly_net_sales"] > 0)
                ][["date", "monthly_net_sales"]].copy()

            if m.empty:
                continue

            m = m.sort_values("date")

            m["monthly_net_sales_3M_Avg"] = (
                m["monthly_net_sales"].rolling(window=3, min_periods=1).mean()
            )
            m["monthly_net_sales_6M_Avg"] = (
                m["monthly_net_sales"].rolling(window=6, min_periods=1).mean()
            )

            # 写回 df_plot —— 只写 month_start 那些行
            for _, r in m.iterrows():
                mask = (df_plot["Category"] == cat) & (df_plot["date"] == r["date"])
                df_plot.loc[mask, "monthly_net_sales_3M_Avg"] = r["monthly_net_sales_3M_Avg"]
                df_plot.loc[mask, "monthly_net_sales_6M_Avg"] = r["monthly_net_sales_6M_Avg"]

    data_map_extended = {
        "Daily Net Sales": "net_sales",
        "Weekly Net Sales": "weekly_net_sales",
        "Monthly Net Sales": "monthly_net_sales",  # ⭐ 新增
        "Daily Number of Customers": "daily_customers",  # ✅ 新增
        "Daily Transactions": "transactions",
        "Avg Transaction": "avg_txn",
        "Items Sold": "qty",
        "Inventory Value": "inventory_value",
        "Profit (Amount)": "profit_amount",
        # 为每个数据类型添加对应的3M和6M Avg
        "Daily Net Sales 3M Avg": "3M_Avg_Rolling",
        "Daily Net Sales 6M Avg": "6M_Avg_Rolling",
        "Weekly Net Sales 3M Avg": "weekly_net_sales_3M_Avg",
        "Weekly Net Sales 6M Avg": "weekly_net_sales_6M_Avg",
        "Daily Transactions 3M Avg": "transactions_3M_Avg",
        "Daily Transactions 6M Avg": "transactions_6M_Avg",
        "Avg Transaction 3M Avg": "avg_txn_3M_Avg",
        "Avg Transaction 6M Avg": "avg_txn_6M_Avg",
        "Items Sold 3M Avg": "qty_3M_Avg",
        "Items Sold 6M Avg": "qty_6M_Avg",
        "Daily Number of Customers": "daily_customers",
        "Daily Number of Customers 3M Avg": "customers_3M_Avg",
        "Daily Number of Customers 6M Avg": "customers_6M_Avg",
        # Monthly Net Sales
        "Monthly Net Sales 3M Avg": "monthly_net_sales_3M_Avg",
        "Monthly Net Sales 6M Avg": "monthly_net_sales_6M_Avg",

        # Inventory Value（如果你要做）
        "Inventory Value 3M Avg": "inventory_value_3M_Avg",
        "Inventory Value 6M Avg": "inventory_value_6M_Avg",

        # Profit（如果你要做）
        "Profit (Amount) 3M Avg": "profit_amount_3M_Avg",
        "Profit (Amount) 6M Avg": "profit_amount_6M_Avg",

    }

    # === 修复：只在选择了3M/6M Avg时才计算滚动平均，并且基于筛选后的数据计算 ===
    if any("3M Avg" in data_type or "6M Avg" in data_type for data_type in data_sel):
        print("=== DEBUG: Calculating rolling averages ===")

        # 为每个分类计算基于筛选后数据的滚动平均值
        for category in df_plot['Category'].unique():
            cat_mask = df_plot['Category'] == category

            # 为当前分类的数据按日期排序
            cat_data = df_plot[cat_mask].sort_values('date').copy()

            # === rolling: 不足窗口长度就 NaN（但不删任何日期） ===
            if "Daily Net Sales 3M Avg" in data_sel or "Daily Net Sales 6M Avg" in data_sel:
                df_plot.loc[cat_mask, "3M_Avg_Rolling"] = cat_data["net_sales"].rolling(
                    window=90, min_periods=1, center=False
                ).mean()
                df_plot.loc[cat_mask, "6M_Avg_Rolling"] = cat_data["net_sales"].rolling(
                    window=180, min_periods=1, center=False
                ).mean()

            # === Daily Number of Customers rolling ===
            if (
                    "Daily Number of Customers 3M Avg" in data_sel
                    or "Daily Number of Customers 6M Avg" in data_sel
            ):
                df_plot.loc[cat_mask, "customers_3M_Avg"] = cat_data["daily_customers"].rolling(
                    window=90, min_periods=1
                ).mean()

                df_plot.loc[cat_mask, "customers_6M_Avg"] = cat_data["daily_customers"].rolling(
                    window=180, min_periods=1
                ).mean()

            if "Daily Transactions 3M Avg" in data_sel or "Daily Transactions 6M Avg" in data_sel:
                df_plot.loc[cat_mask, "transactions_3M_Avg"] = cat_data["transactions"].rolling(
                    window=90, min_periods=1, center=False
                ).mean()
                df_plot.loc[cat_mask, "transactions_6M_Avg"] = cat_data["transactions"].rolling(
                    window=180, min_periods=1, center=False
                ).mean()

            if "Avg Transaction 3M Avg" in data_sel or "Avg Transaction 6M Avg" in data_sel:
                df_plot.loc[cat_mask, "avg_txn_3M_Avg"] = cat_data["avg_txn"].rolling(
                    window=90, min_periods=1, center=False
                ).mean()
                df_plot.loc[cat_mask, "avg_txn_6M_Avg"] = cat_data["avg_txn"].rolling(
                    window=180, min_periods=1, center=False
                ).mean()

            if "Items Sold 3M Avg" in data_sel or "Items Sold 6M Avg" in data_sel:
                df_plot.loc[cat_mask, "qty_3M_Avg"] = cat_data["qty"].rolling(
                    window=90, min_periods=1, center=False
                ).mean()
                df_plot.loc[cat_mask, "qty_6M_Avg"] = cat_data["qty"].rolling(
                    window=180, min_periods=1, center=False
                ).mean()

    # 处理库存数据
    if any(data in ["Inventory Value", "Profit (Amount)"] for data in data_sel):
        if not grouped_inv.empty:
            grouped_inv_plot = grouped_inv.copy()
            grouped_inv_plot = grouped_inv_plot.rename(columns={
                "Inventory Value": "inventory_value",
                "Profit": "profit_amount"
            })
            # 添加缺失的列
            for col in ["net_sales", "transactions", "avg_txn", "qty", "3M_Avg_Rolling", "6M_Avg_Rolling"]:
                grouped_inv_plot[col] = 0

            # 合并库存数据
            if small_cats:
                inv_small = grouped_inv_plot[grouped_inv_plot["Category"].isin(small_cats)].copy()
                inv_small["__source__"] = "inv"  # ✅ 加这里
                df_plot = pd.concat([df_plot, inv_small], ignore_index=True)

            if "bar" in cats_sel:
                bar_inv = grouped_inv_plot[grouped_inv_plot["Category"].apply(is_bar_category)].copy()
                if not bar_inv.empty:
                    bar_inv["Category"] = "bar"
                    bar_inv["__source__"] = "inv"  # ✅ 加这里
                    df_plot = pd.concat([df_plot, bar_inv], ignore_index=True)

            if "retail" in cats_sel:
                retail_inv = grouped_inv_plot[grouped_inv_plot["Category"] == "Retail"].copy()
                if not retail_inv.empty:
                    retail_inv["Category"] = "retail"
                    retail_inv["__source__"] = "inv"  # ✅ 加这里
                    df_plot = pd.concat([df_plot, retail_inv], ignore_index=True)

            if "total" in cats_sel:
                total_inv = grouped_inv_plot.copy()
                total_inv_sum = total_inv.groupby("date").agg({
                    "inventory_value": "sum",
                    "profit_amount": "sum"
                }).reset_index()
                total_inv_sum["Category"] = "total"
                for col in ["net_sales", "transactions", "avg_txn", "qty", "3M_Avg_Rolling", "6M_Avg_Rolling"]:
                    total_inv_sum[col] = 0
                total_inv_sum["__source__"] = "inv"  # ✅ 加这里（在 concat 前）
                df_plot = pd.concat([df_plot, total_inv_sum], ignore_index=True)

    # ============================
    # ✅ Inventory / Profit rolling（必须在 concat 之后）
    # ============================
    if any(x in data_sel for x in [
        "Inventory Value 3M Avg", "Inventory Value 6M Avg",
        "Profit (Amount) 3M Avg", "Profit (Amount) 6M Avg"
    ]):
        # 初始化列（防止 data_map 检查时报 KeyError）
        for col in [
            "inventory_value_3M_Avg", "inventory_value_6M_Avg",
            "profit_amount_3M_Avg", "profit_amount_6M_Avg"
        ]:
            if col not in df_plot.columns:
                df_plot[col] = np.nan

        # 只处理 inventory source
        inv_all = df_plot[df_plot["__source__"] == "inv"].copy()
        if not inv_all.empty:
            for cat in inv_all["Category"].unique():
                mask = (df_plot["__source__"] == "inv") & (df_plot["Category"] == cat)
                inv_data = df_plot.loc[mask].sort_values("date").copy()

                if inv_data.empty:
                    continue

                if "Inventory Value 3M Avg" in data_sel and "inventory_value" in inv_data.columns:
                    df_plot.loc[mask, "inventory_value_3M_Avg"] = (
                        inv_data["inventory_value"].rolling(90, min_periods=1).mean().values
                    )

                if "Inventory Value 6M Avg" in data_sel and "inventory_value" in inv_data.columns:
                    df_plot.loc[mask, "inventory_value_6M_Avg"] = (
                        inv_data["inventory_value"].rolling(180, min_periods=1).mean().values
                    )

                if "Profit (Amount) 3M Avg" in data_sel and "profit_amount" in inv_data.columns:
                    df_plot.loc[mask, "profit_amount_3M_Avg"] = (
                        inv_data["profit_amount"].rolling(90, min_periods=1).mean().values
                    )

                if "Profit (Amount) 6M Avg" in data_sel and "profit_amount" in inv_data.columns:
                    df_plot.loc[mask, "profit_amount_6M_Avg"] = (
                        inv_data["profit_amount"].rolling(180, min_periods=1).mean().values
                    )

    # 确保所有需要的列都存在
    for col_name in data_map_extended.values():
        if col_name not in df_plot.columns:
            df_plot[col_name] = 0

    # 添加库存数据列
    if "inventory_value" not in df_plot.columns:
        df_plot["inventory_value"] = 0
    if "profit_amount" not in df_plot.columns:
        df_plot["profit_amount"] = 0

    # === Weekly Net Sales 计算（避免口径重复风险） ===
    if "Weekly Net Sales" in data_sel or any("Weekly Net Sales" in dt for dt in data_sel):
        weekly_base_data = []

        # ✅ 用 cats_sel（用户选择的分类）做 loop，更稳定；不要用 df_plot.unique()
        for category in cats_sel:
            # 1) 选择“周汇总”的数据源（关键：避免从 df_plot 这种混合口径再反推）
            if category == "total":
                # total 只从 daily_filtered 算
                cat_data = daily_filtered[["date", "net_sales", "transactions", "qty"]].copy()
                cat_data["Category"] = "total"

            elif category == "bar":
                # bar 从 grouped_tx 算（按 bar 规则聚合）
                cat_data = grouped_tx[grouped_tx["Category"].apply(is_bar_category)][
                    ["date", "net_sales", "transactions", "qty"]
                ].copy()
                cat_data["Category"] = "bar"

            elif category == "retail":
                # retail 从 grouped_tx 算（非 bar）
                cat_data = grouped_tx[~grouped_tx["Category"].apply(is_bar_category)][
                    ["date", "net_sales", "transactions", "qty"]
                ].copy()
                cat_data["Category"] = "retail"

            else:
                # 小分类从 grouped_tx 直接拿
                cat_data = grouped_tx[grouped_tx["Category"] == category][
                    ["date", "net_sales", "transactions", "qty"]
                ].copy()
                cat_data["Category"] = category

            if cat_data.empty:
                continue

            # 2) 按周汇总（周一为周起点）
            cat_data["year_week"] = cat_data["date"].dt.strftime("%Y-%W")

            weekly_agg = (
                cat_data.groupby("year_week", as_index=False)
                .agg({"net_sales": "sum", "transactions": "sum", "qty": "sum"})
            )

            # 只保留有销售的周
            weekly_agg = weekly_agg[weekly_agg["net_sales"] > 0]
            if weekly_agg.empty:
                continue

            weekly_agg["date"] = pd.to_datetime(weekly_agg["year_week"] + "-1", format="%Y-%W-%w")
            weekly_agg["Category"] = category

            weekly_agg = weekly_agg.sort_values("date")

            weekly_agg["weekly_net_sales_3M_Avg"] = weekly_agg["net_sales"].rolling(
                window=min(13, len(weekly_agg)), min_periods=1
            ).mean()
            weekly_agg["weekly_net_sales_6M_Avg"] = weekly_agg["net_sales"].rolling(
                window=min(26, len(weekly_agg)), min_periods=1
            ).mean()

            weekly_agg = weekly_agg.rename(columns={"net_sales": "weekly_net_sales"})
            weekly_agg["__is_weekly__"] = True

            # 兜底列
            for col in [
                "inventory_value", "profit_amount",
                "transactions_3M_Avg", "transactions_6M_Avg",
                "avg_txn_3M_Avg", "avg_txn_6M_Avg",
                "qty_3M_Avg", "qty_6M_Avg",
                "3M_Avg_Rolling", "6M_Avg_Rolling",
                "avg_txn"
            ]:
                if col not in weekly_agg.columns:
                    weekly_agg[col] = 0

            weekly_base_data.append(weekly_agg)

        if weekly_base_data:
            weekly_combined = pd.concat(weekly_base_data, ignore_index=True)

            keep_columns = [
                "date", "Category",
                "weekly_net_sales", "weekly_net_sales_3M_Avg", "weekly_net_sales_6M_Avg",
                "transactions", "avg_txn", "qty",
                "3M_Avg_Rolling", "6M_Avg_Rolling",
                "inventory_value", "profit_amount",
                "transactions_3M_Avg", "transactions_6M_Avg",
                "avg_txn_3M_Avg", "avg_txn_6M_Avg",
                "qty_3M_Avg", "qty_6M_Avg",
                "__is_weekly__"
            ]

            for col in keep_columns:
                if col not in weekly_combined.columns:
                    weekly_combined[col] = 0

            weekly_combined = weekly_combined[keep_columns]
            weekly_combined["__source__"] = "tx"  # ✅ 加在这里（concat 进 df_plot 之前）

            # ✅ 只 concat 一次
            df_plot = pd.concat([df_plot, weekly_combined], ignore_index=True)

            # 清理临时列
            if "year_week" in df_plot.columns:
                df_plot = df_plot.drop(columns=["year_week"])

            # ✅ 关键：把 weekly 行按 date+Category 聚合到唯一一行（避免同周重复点）
            weekly_mask = df_plot.get("__is_weekly__", False) == True
            if weekly_mask is not False and weekly_mask.any():
                weekly_df = df_plot.loc[weekly_mask].copy()
                non_weekly_df = df_plot.loc[~weekly_mask].copy()

                weekly_df = (
                    weekly_df
                    .groupby(["date", "Category"], as_index=False)
                    .agg({
                        "weekly_net_sales": "sum",
                        "weekly_net_sales_3M_Avg": "max",
                        "weekly_net_sales_6M_Avg": "max",
                        "transactions": "sum",
                        "qty": "sum",
                        # 兜底列（不重要但避免丢）
                        "inventory_value": "sum",
                        "profit_amount": "sum",
                    })
                )
                weekly_df["__is_weekly__"] = True
                weekly_df["__source__"] = "tx"
                df_plot = pd.concat([non_weekly_df, weekly_df], ignore_index=True)

    # === 在这里添加调试代码 ===
    print("=== DEBUG INFO ===")
    print("Available columns in df_plot:", sorted(df_plot.columns.tolist()))
    print("Data types selected:", data_sel)
    print("--- Column existence check ---")
    for data_type in data_sel:
        col_name = data_map_extended.get(data_type)
        exists = col_name in df_plot.columns if col_name else False
        print(f"Data type: {data_type:25} | Column: {col_name:30} | Exists: {exists}")
    print("=== END DEBUG ===")

    # === 新增：Weekly Net Sales 列检查 ===
    print("=== DEBUG: Weekly Net Sales Columns ===")
    print("weekly_net_sales in columns:", 'weekly_net_sales' in df_plot.columns)
    print("weekly_net_sales_3M_Avg in columns:", 'weekly_net_sales_3M_Avg' in df_plot.columns)
    print("weekly_net_sales_6M_Avg in columns:", 'weekly_net_sales_6M_Avg' in df_plot.columns)

    if 'weekly_net_sales' in df_plot.columns:
        weekly_data_exists = (df_plot['weekly_net_sales'] > 0).any()
        print("Weekly data exists:", weekly_data_exists)
        if weekly_data_exists:
            sample_weekly = df_plot[df_plot['weekly_net_sales'] > 0].head(3)
            print("Sample weekly data:")
            print(sample_weekly[
                      ['date', 'Category', 'weekly_net_sales', 'weekly_net_sales_3M_Avg', 'weekly_net_sales_6M_Avg']])

    melted_dfs = []

    def _is_inv_type(dt: str) -> bool:
        return dt.startswith("Inventory Value") or dt.startswith("Profit (Amount)")

    for data_type in data_sel:
        col_name = data_map_extended.get(data_type)
        if not col_name or col_name not in df_plot.columns:
            continue

        if _is_inv_type(data_type):
            # Inventory / Profit 只来自 inv
            base = df_plot[df_plot["__source__"] == "inv"]

        elif data_type.startswith("Weekly"):
            # Weekly 只来自 weekly 行
            base = df_plot[df_plot["__is_weekly__"] == True]

        else:
            # ✅ 所有“交易型指标”（Avg Txn / Items Sold / Customers / Daily / Monthly）
            # 只允许：tx + 非 weekly
            base = df_plot[
                (df_plot["__source__"] == "tx") &
                (df_plot.get("__is_weekly__", False) != True)
                ]

        temp_df = base[["date", "Category", col_name]].copy()
        temp_df = temp_df.rename(columns={col_name: "value"})
        temp_df["data_type"] = data_type
        # 仅对 Avg Transaction 和 Items Sold 保留两位小数
        if data_type in [
            "Avg Transaction",
            "Avg Transaction 3M Avg",
            "Avg Transaction 6M Avg",
            "Items Sold",
            "Items Sold 3M Avg",
            "Items Sold 6M Avg",
        ]:
            temp_df["value"] = (
                pd.to_numeric(temp_df["value"], errors="coerce")
                .round(2)
            )

        # === 修改：对 Daily Net Sales 和 Weekly Net Sales 进行四舍五入取整 ===
        if data_type in ["Daily Net Sales", "Weekly Net Sales"]:
            temp_df["value"] = (
                pd.to_numeric(temp_df["value"], errors="coerce")
                .fillna(0)
                .apply(proper_round)
            )

        if data_type in ["Weekly Net Sales", "Weekly Net Sales 3M Avg", "Weekly Net Sales 6M Avg"]:
            temp_df = temp_df[temp_df["value"] > 0]

        # ⭐ 新增 Monthly 的过滤：去掉 0 值（这样只在每月1号有值）
        if data_type == "Monthly Net Sales":
            temp_df = temp_df[temp_df["value"] > 0]

        # 放宽过滤条件
        temp_df = temp_df[temp_df["value"].notna()]
        if not temp_df.empty:
            melted_dfs.append(temp_df)

    if melted_dfs:
        combined_df = pd.concat(melted_dfs, ignore_index=True)
        combined_df["series"] = combined_df["Category"] + " - " + combined_df["data_type"]

        # ✅ 只在“展示层”过滤 Daily，不影响 Weekly
        combined_df = combined_df[
            ~(
                    combined_df["date"].isin(BAD_DATES)
                    & combined_df["data_type"].str.contains("Daily", case=False)
            )
        ]

        return combined_df

    return None

def show_high_level(tx: pd.DataFrame, mem: pd.DataFrame, inv: pd.DataFrame):
    # === 全局样式：消除顶部标题间距 ===
    st.markdown("""
    <style>
    /* 去掉 Vie Manly Dashboard 与 High Level Report 之间的空白 */
    div.block-container h1, 
    div.block-container h2, 
    div.block-container h3, 
    div.block-container p {
        margin-top: 0rem !important;
        margin-bottom: 0rem !important;
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
    }

    /* 更强力地压缩 Streamlit 自动插入的 vertical space */
    div.block-container > div {
        margin-top: 0rem !important;
        margin-bottom: 0rem !important;
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
    }

    /* 消除标题和选择框之间空隙 */
    div[data-testid="stVerticalBlock"] > div {
        margin-top: 0rem !important;
        margin-bottom: 0rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # === 保留标题 ===
    st.markdown("<h2 style='font-size:24px; font-weight:700;'>📊 High Level Report</h2>", unsafe_allow_html=True)

    # 在现有的样式后面添加：
    st.markdown("""
    <style>
    /* 让多选框列更紧凑 */
    div[data-testid="column"] {
        padding: 0 8px !important;
    }
    div[data-baseweb="select"] {
        min-width: 12ch !important;
        max-width: 20ch !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # 预加载所有数据
    with st.spinner("Loading data..."):
        daily, category_tx = preload_all_data(tx)
        inv_grouped, inv_latest_date = _prepare_inventory_grouped(inv)

    # 初始化分类选择的 session state
    if "hl_cats" not in st.session_state:
        st.session_state["hl_cats"] = []
    if "hl_time" not in st.session_state:
        st.session_state["hl_time"] = ["MTD"]

    if "hl_data_base" not in st.session_state:
        st.session_state["hl_data_base"] = ["Daily Net Sales"]

    if "hl_cats" not in st.session_state or not st.session_state["hl_cats"]:
        st.session_state["hl_cats"] = ["total"]

    # === 计算每日客户数，写入 daily（用于 Daily Number of Customers 曲线） ===
    if "Datetime" in tx.columns and "Card Brand" in tx.columns and "PAN Suffix" in tx.columns:
        tx_customers = tx.copy()
        # 规范日期 & 卡信息
        tx_customers["date"] = pd.to_datetime(tx_customers["Datetime"], errors="coerce").dt.normalize()
        tx_customers = tx_customers.dropna(subset=["date", "Card Brand", "PAN Suffix"])
        tx_customers["Card Brand"] = tx_customers["Card Brand"].str.title()
        tx_customers["PAN Suffix"] = tx_customers["PAN Suffix"].astype(str).str.split(".").str[0]

        # 每天唯一 (Card Brand, PAN Suffix) 组合数量 = 当天客户数
        unique_pairs = tx_customers[["date", "Card Brand", "PAN Suffix"]].drop_duplicates()
        daily_cust = (
            unique_pairs.groupby("date")
            .size()
            .reset_index(name="daily_customers")
        )

        # 把 daily_customers merge 到 daily
        if "date" in daily.columns:
            # 两边都强制转成同一种 datetime 类型（并归一到日期）
            daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
            daily_cust["date"] = pd.to_datetime(daily_cust["date"], errors="coerce").dt.normalize()

            # 过滤掉无效日期
            daily = daily[daily["date"].notna()]
            daily_cust = daily_cust[daily_cust["date"].notna()]

            daily = daily.merge(daily_cust, on="date", how="left")
            daily["daily_customers"] = daily["daily_customers"].fillna(0)
            # =========================
            # NEW: 计算按 Category / bar / retail 拆分的 daily_customers
            # =========================

            # 先确保 Category 存在
            if "Category" in tx_customers.columns:
                tx_customers["Category"] = tx_customers["Category"].fillna("None").astype(str).str.strip()
            else:
                tx_customers["Category"] = "None"

            # 1) 每个 Category 的 daily_customers
            unique_pairs_cat = tx_customers[["date", "Category", "Card Brand", "PAN Suffix"]].drop_duplicates()
            cust_by_cat = (
                unique_pairs_cat.groupby(["date", "Category"])
                .size()
                .reset_index(name="daily_customers")
            )

            # 2) bar daily_customers
            # bar 的判定逻辑复用 is_bar_category()
            unique_pairs_cat["__is_bar__"] = unique_pairs_cat["Category"].apply(is_bar_category)

            cust_bar = (
                unique_pairs_cat[unique_pairs_cat["__is_bar__"]]
                .groupby("date")
                .size()
                .reset_index(name="daily_customers")
            )
            cust_bar["Category"] = "bar"

            # 3) retail daily_customers
            cust_retail = (
                unique_pairs_cat[~unique_pairs_cat["__is_bar__"]]
                .groupby("date")
                .size()
                .reset_index(name="daily_customers")
            )
            cust_retail["Category"] = "retail"

            # 4) 把 total 也做成同结构，方便后面统一 merge
            cust_total = daily_cust.copy()
            cust_total["Category"] = "total"

            # 5) 合并为一张“customers 维表”，后面 prepare_chart_data_fast 用
            customers_by_group = pd.concat([cust_by_cat, cust_bar, cust_retail, cust_total], ignore_index=True)

            # 放到 session_state（最少侵入式，不改函数签名）
            st.session_state["customers_by_group"] = customers_by_group

    if daily.empty:
        st.warning("No transaction data available. Please upload data first.")
        return

    # === 特定日期选择 ===
    # 改为两列布局：时间范围选择 + 日期选择
    col_time_range, col_date, _ = st.columns([1, 1, 5])

    # === 添加空白行确保水平对齐 ===
    # st.markdown("<div style='margin-top: 0.5rem;'></div>", unsafe_allow_html=True)

    st.markdown("""
    <style>

    /* 让多选框列更紧凑 */
    div[data-testid="column"] {
        padding: 0 8px !important;
    }

    /* 精确控制 summary_time_range 下拉框宽度 */
    div[data-testid*="summary_time_range"] > div[data-baseweb="select"] {
        width: 14ch !important;
        min-width: 14ch !important;
        max-width: 14ch !important;
    }

    /* 日期选择框容器 - 精确宽度 */
    div[data-testid*="stSelectbox"] {
        width: 18ch !important;
        min-width: 18ch !important;
        max-width: 18ch !important;
        display: inline-block !important;
    }

    /* 日期选择框标签 */
    div[data-testid*="stSelectbox"] label {
        white-space: nowrap !important;
        font-size: 0.9rem !important;
        width: 100% !important;
    }

    /* 下拉菜单 */
    div[data-testid*="stSelectbox"] [data-baseweb="select"] {
        width: 18ch !important;
        min-width: 18ch !important;
        max-width: 18ch !important;
    }

    /* 下拉选项容器 */
    div[role="listbox"] {
        min-width: 18ch !important;
        max-width: 18ch !important;
    }

    /* 隐藏多余的下拉箭头空间 */
    div[data-testid*="stSelectbox"] [data-baseweb="select"] > div {
        padding-right: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    with col_time_range:
        # === 移除空白标签，现在用CSS控制 ===
        summary_time_options = ["Daily", "WTD", "MTD", "YTD", "Custom date"]
        summary_time_range = st.selectbox(
            "Choose time range",
            summary_time_options,
            key="summary_time_range"
        )

    with col_date:
        if summary_time_range == "Daily":
            # 保证 Datetime → date 列存在
            if "Datetime" in daily.columns:
                daily["date"] = pd.to_datetime(daily["Datetime"]).dt.date

            # 过滤有效日期，直接用 date 对象，不要再 .date()
            available_dates = sorted([
                pd.to_datetime(d).date() for d in daily["date"].unique()
                if pd.notna(d)
            ], reverse=True)

            if available_dates:  # 确保有可用的日期
                available_dates_formatted = [date.strftime('%d/%m/%Y') for date in available_dates]

                date_width = 18
                selectbox_width = date_width + 1

                selected_date_formatted = st.selectbox("Choose date", available_dates_formatted)

                # 将选择的日期转换回日期对象
                selected_date = pd.to_datetime(selected_date_formatted, format='%d/%m/%Y').date()
            else:
                # 如果没有可用日期，使用今天
                selected_date = pd.Timestamp.today().date()
                selected_date_formatted = selected_date.strftime('%d/%m/%Y')
                st.warning("No valid dates available, using today's date")
        else:
            # 对于非Daily选项，设置一个默认日期（使用最新日期）
            # === 修复：同样过滤掉 NaT ===
            valid_dates = daily["date"].dropna()
            if not valid_dates.empty:
                selected_date = valid_dates.max().date()
            else:
                selected_date = pd.Timestamp.today().date()
            selected_date_formatted = selected_date.strftime('%d/%m/%Y')

    # === 自定义日期范围选择（仅当选择Custom date时显示） ===
    summary_custom_dates_selected = False
    summary_t1 = None
    summary_t2 = None

    if summary_time_range == "Custom date":
        summary_custom_dates_selected = True
        st.markdown("<h4 style='font-size:16px; font-weight:700;'>📅 Custom Date Range for Summary</h4>",
                    unsafe_allow_html=True)

        col_from, col_to, _ = st.columns([1, 1, 5])

        with col_from:
            summary_t1 = st.date_input(
                "From",
                value=pd.Timestamp.today().normalize() - pd.Timedelta(days=7),
                key="summary_date_from",
                format="DD/MM/YYYY"
            )

        with col_to:
            summary_t2 = st.date_input(
                "To",
                value=pd.Timestamp.today().normalize(),
                key="summary_date_to",
                format="DD/MM/YYYY"
            )

    def filter_data_by_time_range(data, time_range, selected_date, custom_dates_selected=False, t1=None, t2=None):
        """根据时间范围筛选数据"""
        if data.empty:
            return data

        data_filtered = data.copy()

        # 获取当前日期
        today = pd.Timestamp.today().normalize()

        # 计算时间范围筛选条件
        start_of_week = today - pd.Timedelta(days=today.weekday())
        start_of_month = today.replace(day=1)
        start_of_year = today.replace(month=1, day=1)

        # 检查数据框是否有date列，如果没有则使用Datetime列
        if 'date' in data_filtered.columns:
            date_col = 'date'
        elif 'Datetime' in data_filtered.columns:
            date_col = 'Datetime'
            # 确保Datetime列是datetime类型
            data_filtered[date_col] = pd.to_datetime(data_filtered[date_col])
        else:
            # 如果没有日期列，返回原始数据
            return data_filtered

        # 确保日期列为 datetime 类型
        data_filtered[date_col] = pd.to_datetime(data_filtered[date_col], errors="coerce")

        # === 修复：优先处理 Custom date ===
        if custom_dates_selected and t1 and t2:
            t1_ts = pd.to_datetime(t1)
            t2_ts = pd.to_datetime(t2)
            data_filtered = data_filtered[
                (data_filtered[date_col] >= t1_ts) & (data_filtered[date_col] <= t2_ts)
                ]
        elif "WTD" in time_range:
            data_filtered = data_filtered[data_filtered[date_col] >= start_of_week]
        elif "MTD" in time_range:
            data_filtered = data_filtered[data_filtered[date_col] >= start_of_month]
        elif "YTD" in time_range:
            data_filtered = data_filtered[data_filtered[date_col] >= start_of_year]
        elif "Daily" in time_range:
            data_filtered = data_filtered[data_filtered[date_col].dt.date == selected_date]

        return data_filtered

    # 筛选daily数据
    df_selected_date = filter_data_by_time_range(
        daily, summary_time_range, selected_date,
        summary_custom_dates_selected, summary_t1, summary_t2
    )

    # 转换 selected_date 为 Timestamp 用于比较
    selected_date_ts = pd.Timestamp(selected_date)

    def calculate_transactions_from_tx(tx_df, time_range, selected_date,
                                       custom_dates_selected=False, t1=None, t2=None):
        if tx_df is None or tx_df.empty:
            return 0

        df = tx_df.copy()
        df["date"] = pd.to_datetime(df["Datetime"], errors="coerce").dt.date
        df = df[df["date"].notna()]

        df = filter_data_by_time_range(
            df, time_range, selected_date,
            custom_dates_selected, t1, t2
        )

        return df["Transaction ID"].nunique()

    # === 计算客户数量 ===
    def calculate_customer_count(tx_df, time_range, selected_date, custom_dates_selected=False, t1=None, t2=None):
        if tx_df is None or tx_df.empty:
            return 0
        if 'Datetime' not in tx_df.columns:
            return 0

        # 根据时间范围筛选交易数据
        tx_df_filtered = filter_data_by_time_range(
            tx_df, time_range, selected_date, custom_dates_selected, t1, t2
        )

        if tx_df_filtered.empty:
            return 0

        if 'Card Brand' not in tx_df_filtered.columns or 'PAN Suffix' not in tx_df_filtered.columns:
            return 0

        filtered_tx = tx_df_filtered.dropna(subset=['Card Brand', 'PAN Suffix'])
        if filtered_tx.empty:
            return 0

        filtered_tx['Card Brand'] = filtered_tx['Card Brand'].str.title()
        filtered_tx['PAN Suffix'] = filtered_tx['PAN Suffix'].astype(str).str.split('.').str[0]
        unique_customers = filtered_tx[['Card Brand', 'PAN Suffix']].drop_duplicates()

        return len(unique_customers)

    def calculate_bar_retail_data(category_tx, time_range, selected_date, daily_data, custom_dates_selected=False,
                                  t1=None, t2=None):
        """计算bar和retail在选定时间范围的数据"""

        bar_cats = {
            "Cafe Drinks",
            "Smoothie Bar",
            "Soups",
            "Sweet Treats",
            "Wraps & Salads",
            "Breakfast Bowls",
            "Chia Bowls",  # ✅ 新增
        }

        # 用原始交易表 tx 来算"笔数"，避免分类重复计数
        tx_filtered = filter_data_by_time_range(
            tx, time_range, selected_date, custom_dates_selected, t1, t2
        )

        # 根据时间范围筛选分类数据
        category_filtered = filter_data_by_time_range(
            category_tx, time_range, selected_date, custom_dates_selected, t1, t2
        )

        # === 计算bar数据 ===
        bar_data = category_filtered[category_filtered["Category"].apply(is_bar_category)].copy()
        bar_net_sales_raw = bar_data["net_sales"].sum()
        bar_net_sales = proper_round(bar_net_sales_raw)

        # 按 Transaction ID 去重统计 bar 笔数
        bar_tx_ids = tx_filtered[tx_filtered["Category"].apply(is_bar_category)]
        bar_transactions = bar_tx_ids["Transaction ID"].nunique()

        bar_avg_txn = bar_net_sales_raw / bar_transactions if bar_transactions > 0 else 0
        bar_qty = bar_data["qty"].sum()

        # === 计算retail数据 ===
        retail_data = category_filtered[~category_filtered["Category"].apply(is_bar_category)].copy()
        retail_net_sales_raw = pd.to_numeric(retail_data["net_sales"], errors="coerce").sum()
        retail_net_sales = proper_round(retail_net_sales_raw)

        # 按 Transaction ID 去重统计 retail 笔数
        retail_tx_ids = tx_filtered[~tx_filtered["Category"].apply(is_bar_category)]
        retail_transactions = retail_tx_ids["Transaction ID"].nunique()

        retail_avg_txn = retail_net_sales_raw / retail_transactions if retail_transactions > 0 else 0
        retail_qty = retail_data["qty"].sum()

        # === 关键修复：确保 total transactions 等于 bar + retail ===
        # 直接从筛选后的交易数据计算总笔数
        total_transactions = tx_filtered["Transaction ID"].nunique()

        # 验证：bar + retail 应该等于 total
        bar_retail_sum_transactions = bar_transactions + retail_transactions
        if bar_retail_sum_transactions != total_transactions:
            # 如果不等，重新分配以确保一致性
            # 按比例重新分配
            if bar_retail_sum_transactions > 0:
                bar_transactions = int(total_transactions * (bar_transactions / bar_retail_sum_transactions))
                retail_transactions = total_transactions - bar_transactions
            else:
                # 如果都没有交易，平均分配（理论上不会发生）
                bar_transactions = total_transactions // 2
                retail_transactions = total_transactions - bar_transactions

        # 重新计算平均交易额以确保一致性
        bar_avg_txn = bar_net_sales_raw / bar_transactions if bar_transactions > 0 else 0
        retail_avg_txn = retail_net_sales_raw / retail_transactions if retail_transactions > 0 else 0

        # === 其他计算保持不变 ===
        bar_all = category_tx[category_tx["Category"].apply(is_bar_category)].copy()
        bar_all = bar_all.sort_values("date")

        selected_date_ts = pd.Timestamp(selected_date)
        bar_recent_3m = bar_all[bar_all["date"] >= (selected_date_ts - pd.Timedelta(days=90))]
        bar_recent_6m = bar_all[bar_all["date"] >= (selected_date_ts - pd.Timedelta(days=180))]

        bar_3m_avg = proper_round(bar_recent_3m["net_sales"].sum() / 90) if not bar_recent_3m.empty else 0
        bar_6m_avg = proper_round(bar_recent_6m["net_sales"].sum() / 180) if not bar_recent_6m.empty else 0

        retail_all = category_tx[~category_tx["Category"].apply(is_bar_category)].copy()
        retail_all = retail_all.sort_values("date")

        retail_recent_3m = retail_all[retail_all["date"] >= (selected_date_ts - pd.Timedelta(days=90))]
        retail_recent_6m = retail_all[retail_all["date"] >= (selected_date_ts - pd.Timedelta(days=180))]

        retail_3m_avg = proper_round(retail_recent_3m["net_sales"].sum() / 90) if not retail_recent_3m.empty else 0
        retail_6m_avg = proper_round(retail_recent_6m["net_sales"].sum() / 180) if not retail_recent_6m.empty else 0

        # ✅ 正确：total Daily Net Sales = 原始 transactions 逐行求和
        tx_day = tx.copy()
        tx_day["date"] = pd.to_datetime(tx_day["Datetime"], errors="coerce").dt.date

        total_net_sales_raw = (
            tx_day.loc[tx_day["date"] == selected_date, "Net Sales"]
            .astype(float)
            .sum()
        )

        total_net_sales = proper_round(total_net_sales_raw)

        total_qty = category_filtered["qty"].sum()

        # === 客户数保持按交易比例分配 ===
        total_customers = calculate_customer_count(tx, time_range, selected_date, custom_dates_selected, t1, t2)
        bar_customers = int(total_customers * (bar_transactions / total_transactions)) if total_transactions > 0 else 0
        retail_customers = total_customers - bar_customers

        return {
            "bar": {
                "Daily Net Sales": bar_net_sales,
                "Daily Transactions": bar_transactions,
                "# of Customers": bar_customers,
                "Avg Transaction": bar_avg_txn,
                "3M Avg": bar_3m_avg,
                "6M Avg": bar_6m_avg,
                "Items Sold": bar_qty
            },
            "retail": {
                "Daily Net Sales": retail_net_sales,
                "Daily Transactions": retail_transactions,
                "# of Customers": retail_customers,
                "Avg Transaction": retail_avg_txn,
                "3M Avg": retail_3m_avg,
                "6M Avg": retail_6m_avg,
                "Items Sold": retail_qty
            },
            "total": {
                "Daily Net Sales": total_net_sales,
                "Daily Transactions": total_transactions,  # 现在这个应该等于 bar + retail
                "# of Customers": total_customers,
                "Avg Transaction": total_net_sales / total_transactions if total_transactions > 0 else 0,
                "3M Avg": bar_3m_avg + retail_3m_avg,
                "6M Avg": bar_6m_avg + retail_6m_avg,
                "Items Sold": total_qty
            }
        }

    # === KPI（交易，口径按小票） ===
    kpis_main = {
        "Daily Net Sales": proper_round(df_selected_date["net_sales"].sum()),
        "Daily Transactions": calculate_transactions_from_tx(
        tx, summary_time_range, selected_date,
        summary_custom_dates_selected, summary_t1, summary_t2
        ),

        "# of Customers": calculate_customer_count(tx, summary_time_range, selected_date, summary_custom_dates_selected,
                                                   summary_t1, summary_t2),
        "Avg Transaction": df_selected_date["avg_txn"].mean(),
        "3M Avg": proper_round(daily["3M_Avg_Rolling"].iloc[-1]),
        "6M Avg": proper_round(daily["6M_Avg_Rolling"].iloc[-1]),
        "Items Sold": df_selected_date["qty"].sum(),
    }

    # === KPI（库存派生，catalogue-only） ===
    inv_value_latest = 0.0
    profit_latest = 0.0
    if inv_grouped is not None and not inv_grouped.empty and inv_latest_date is not None:
        sub = inv_grouped[inv_grouped["date"] == inv_latest_date]
        inv_value_latest = float(pd.to_numeric(sub["Inventory Value"], errors="coerce").sum())
        profit_latest = float(pd.to_numeric(sub["Profit"], errors="coerce").sum())

    # 计算bar和retail数据
    bar_retail_data = calculate_bar_retail_data(
        category_tx, summary_time_range, selected_date, daily,
        summary_custom_dates_selected, summary_t1, summary_t2
    )

    # 显示选定日期（字体加大）
    st.markdown(
        f"<h3 style='font-size:18px; font-weight:700;'>Selected Date: {selected_date.strftime('%d/%m/%Y')}</h3>",
        unsafe_allow_html=True)

    # ===== 组装三行数据 =====
    total_row = [
        f"${proper_round(bar_retail_data['total']['Daily Net Sales']):,}",
        f"{proper_round(bar_retail_data['total']['Daily Transactions']):,}",
        f"{proper_round(bar_retail_data['total']['# of Customers']):,}",
        f"${safe_fmt(bar_retail_data['total']['Avg Transaction'])}",
        f"${proper_round(bar_retail_data['total']['3M Avg']):,}",
        f"${proper_round(bar_retail_data['total']['6M Avg']):,}",
        f"{proper_round(bar_retail_data['total']['Items Sold']):,}",
        f"${proper_round(inv_value_latest):,} <br><span style='font-size:10px; color:#666;'>as of {pd.to_datetime(inv_latest_date).strftime('%d/%m/%Y') if inv_latest_date else '-'}</span>"
    ]

    bar_row = [
        f"${proper_round(bar_retail_data['bar']['Daily Net Sales']):,}",
        f"{proper_round(bar_retail_data['bar']['Daily Transactions']):,}",
        f"{proper_round(bar_retail_data['bar']['# of Customers']):,}",
        f"${safe_fmt(bar_retail_data['bar']['Avg Transaction'])}",
        f"${proper_round(bar_retail_data['bar']['3M Avg']):,}",
        f"${proper_round(bar_retail_data['bar']['6M Avg']):,}",
        f"{proper_round(bar_retail_data['bar']['Items Sold']):,}",
        "-"
    ]

    retail_row = [
        f"${proper_round(bar_retail_data['retail']['Daily Net Sales']):,}",
        f"{proper_round(bar_retail_data['retail']['Daily Transactions']):,}",
        f"{proper_round(bar_retail_data['retail']['# of Customers']):,}",
        f"${safe_fmt(bar_retail_data['retail']['Avg Transaction'])}",
        f"${proper_round(bar_retail_data['retail']['3M Avg']):,}",
        f"${proper_round(bar_retail_data['retail']['6M Avg']):,}",
        f"{proper_round(bar_retail_data['retail']['Items Sold']):,}",
        "-"
    ]

    # ===== 渲染成 HTML 表格 =====
    # === 新增：Summary Table列宽配置 ===
    column_widths = {
        "label": "110px",
        "Percentage": "80px",
        "Daily Net Sales": "130px",
        "Daily Transactions": "140px",
        "# of Customers": "140px",
        "Avg Transaction": "125px",
        "3M Avg": "115px",
        "6M Avg": "115px",
        "Items Sold": "115px",
        "Inventory Value": "140px"
    }
    display_bar = bar_retail_data['bar']['Daily Net Sales']
    display_retail = bar_retail_data['retail']['Daily Net Sales']
    display_total = display_bar + display_retail
    # 创建数据框
    summary_data = {
        'Category': ['Bar', 'Retail', 'Total'],

        'Percentage': [
            f"{safe_fmt(display_bar / display_total * 100, digits=1)}%" if display_total > 0 else "0.0%",
            f"{safe_fmt(display_retail / display_total * 100, digits=1)}%" if display_total > 0 else "0.0%",
            "-"
        ],
        'Daily Net Sales': [
            f"${proper_round(bar_retail_data['bar']['Daily Net Sales']):,}",
            f"${proper_round(bar_retail_data['retail']['Daily Net Sales']):,}",
            f"${proper_round(bar_retail_data['bar']['Daily Net Sales'] + bar_retail_data['retail']['Daily Net Sales']):,}"
        ],
        'Daily Transactions': [
            f"{proper_round(bar_retail_data['bar']['Daily Transactions']):,}",
            f"{proper_round(bar_retail_data['retail']['Daily Transactions']):,}",
            f"{proper_round(kpis_main['Daily Transactions']):,}"
        ],
        '# of Customers': [
            f"{proper_round(bar_retail_data['bar']['# of Customers']):,}",
            f"{proper_round(bar_retail_data['retail']['# of Customers']):,}",
            f"{proper_round(kpis_main['# of Customers']):,}"
        ],
        'Avg Transaction': [
            f"${safe_fmt(bar_retail_data['bar']['Avg Transaction'])}",
            f"${safe_fmt(bar_retail_data['retail']['Avg Transaction'])}",
            f"${safe_fmt(kpis_main['Avg Transaction'])}"
        ],
        '3M Avg': [
            f"${proper_round(bar_retail_data['bar']['3M Avg']):,}",
            f"${proper_round(bar_retail_data['retail']['3M Avg']):,}",
            f"${proper_round(kpis_main['3M Avg']):,}"
        ],
        '6M Avg': [
            f"${proper_round(bar_retail_data['bar']['6M Avg']):,}",
            f"${proper_round(bar_retail_data['retail']['6M Avg']):,}",
            f"${proper_round(kpis_main['6M Avg']):,}"
        ],
        'Items Sold': [
            f"{proper_round(bar_retail_data['bar']['Items Sold']):,}",
            f"{proper_round(bar_retail_data['retail']['Items Sold']):,}",
            f"{proper_round(kpis_main['Items Sold']):,}"
        ],
        'Inventory Value': [
            "-", "-",
            f"${proper_round(inv_value_latest):,} (as of {pd.to_datetime(inv_latest_date).strftime('%d/%m/%Y') if inv_latest_date else '-'})"
        ]

    }

    df_summary = pd.DataFrame(summary_data)

    # 设置列配置
    column_config = {
        'Category': st.column_config.Column(width=80),
        'Percentage': st.column_config.Column(width=80),
        'Daily Net Sales': st.column_config.Column(width=100),
        'Daily Transactions': st.column_config.Column(width=120),
        '# of Customers': st.column_config.Column(width=100),
        'Avg Transaction': st.column_config.Column(width=105),
        '3M Avg': st.column_config.Column(width=55),
        '6M Avg': st.column_config.Column(width=55),
        'Items Sold': st.column_config.Column(width=75),
        'Inventory Value': st.column_config.Column(width=105),
    }
    # 显示表格
    st.markdown("<h4 style='font-size:16px; font-weight:700; margin-top:1rem;'>Summary Table</h4>",
                unsafe_allow_html=True)
    st.dataframe(
        df_summary,
        column_config=column_config,
        hide_index=True,
        width=875
    )

    st.markdown("---")

    # === 交互选择 ===
    st.markdown("<h4 style='font-size:16px; font-weight:700;'>🔍 Select Parameters</h4>", unsafe_allow_html=True)

    # 分类选择
    if category_tx is None or category_tx.empty:
        st.info("No category breakdown available.")
        return

    # 过滤掉没有数据的分类 - 修复重复显示问题
    category_tx["Category"] = category_tx["Category"].astype(str).str.strip()
    all_cats_tx = (
        category_tx["Category"]
        .fillna("Unknown")
        .drop_duplicates()
        .sort_values()
        .tolist()
    )

    # 只保留有实际数据的分类
    valid_cats = []
    seen_cats = set()
    for cat in all_cats_tx:
        if cat not in seen_cats:
            seen_cats.add(cat)
            cat_data = category_tx[category_tx["Category"] == cat]
            if not cat_data.empty and cat_data["net_sales"].sum() > 0:
                valid_cats.append(cat)

    special_cats = ["bar", "retail", "total"]
    all_cats_extended = special_cats + sorted([c for c in valid_cats if c not in special_cats])

    # === 四个多选框一行显示（使用 columns，等宽且靠左） ===

    # 定义每个框的宽度比例
    col1, col2, col3, col4, _ = st.columns([1.0, 1.2, 0.8, 1.5, 2.5])

    with col1:
        time_range = persisting_multiselect(
            "Choose time range",
            ["Custom date", "WTD", "MTD", "YTD"],
            key="hl_time",
            width_chars=15
        )

    with col2:
        data_sel_base = persisting_multiselect(
            "Choose data types",
            [
                "Daily Net Sales",
                "Weekly Net Sales",
                "Monthly Net Sales",  # ⭐ 新增
                "Daily Transactions",
                "Daily Number of Customers",  # ⭐ 新增
                "Avg Transaction",
                "Items Sold",
                "Inventory Value"
            ],
            key="hl_data_base",
            width_chars=22
        )

    with col3:
        data_sel_avg = persisting_multiselect(
            "Choose averages",
            ["3M Avg", "6M Avg"],
            key="hl_data_avg",
            width_chars=8
        )

    with col4:
        # 为分类选择创建表单，避免立即 rerun
        with st.form(key="categories_form"):
            cats_sel = st.multiselect(
                "Choose categories",
                all_cats_extended,
                default=st.session_state.get("hl_cats", []),
                key="hl_cats_widget"
            )

            # 应用按钮
            submitted = st.form_submit_button("Apply", type="primary")

            if submitted:
                st.session_state["hl_cats"] = cats_sel
                st.rerun()

        # 从 session state 获取最终的选择
        cats_sel = st.session_state.get("hl_cats", [])

        # 显示当前选择状态
        if cats_sel:
            st.caption(f"✅ Selected: {len(cats_sel)} categories")
        else:
            st.caption("ℹ️ No categories selected")

    # 加一小段 CSS，让四个框左对齐、间距最小
    st.markdown("""
    <style>
    div[data-testid="column"] {
        padding: 0 4px !important;
    }
    div[data-baseweb="select"] {
        min-width: 5ch !important;
        max-width: 35ch !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # 合并数据类型选择
    data_sel = data_sel_base.copy()

    # 如果选择了平均值，为每个选择的基础数据类型添加对应的平均值
    for avg_type in data_sel_avg:
        for base_type in data_sel_base:
            if base_type in [
                "Daily Net Sales",
                "Weekly Net Sales",
                "Monthly Net Sales",  # ✅ 新增
                "Daily Transactions",
                "Daily Number of Customers",  # ✅ 新增
                "Avg Transaction",
                "Items Sold",
                # 如果你也想给库存做 avg，就加：
                "Inventory Value",  # ✅ 可选
                "Profit (Amount)"  # ✅ 可选
            ]:
                data_sel.append(f"{base_type} {avg_type}")


    # 如果没有选择任何基础数据类型但有平均值，默认使用Daily Net Sales
    if not data_sel_base and data_sel_avg:
        for avg_type in data_sel_avg:
            data_sel.append(f"Daily Net Sales {avg_type}")

    # === 自定义日期范围选择 ===
    custom_dates_selected = False

    # 初始化 session_state 中的日期（如果还没有）
    if "hl_date_from" not in st.session_state:
        st.session_state["hl_date_from"] = pd.Timestamp.today().normalize() - pd.Timedelta(days=7)
    if "hl_date_to" not in st.session_state:
        st.session_state["hl_date_to"] = pd.Timestamp.today().normalize()

    t1 = st.session_state["hl_date_from"]
    t2 = st.session_state["hl_date_to"]

    if "Custom date" in time_range:
        custom_dates_selected = True
        st.markdown("<h4 style='font-size:16px; font-weight:700;'>📅 Custom Date Range</h4>", unsafe_allow_html=True)

        col_from, col_to, _ = st.columns([1, 1, 5])

        with col_from:
            # ✅ 不使用 key，直接获取返回值
            t1 = st.date_input(
                "From",
                value=st.session_state["hl_date_from"],
                key="hl_date_from",
                format="DD/MM/YYYY"
            )

        with col_to:
            # ✅ 不使用 key，直接获取返回值
            t2 = st.date_input(
                "To",
                value=st.session_state["hl_date_to"],
                key="hl_date_to",
                format="DD/MM/YYYY"
            )

    # 修改1：检查三个多选框是否都有选择
    has_time_range = bool(time_range)
    has_data_sel = bool(data_sel)
    has_cats_sel = bool(cats_sel)

    # 对于 Custom date，需要确保日期已选择
    if "Custom date" in time_range:
        has_valid_custom_dates = (t1 is not None and t2 is not None)
    else:
        has_valid_custom_dates = True

    # 实时计算图表数据 - 修改1：只有三个多选框都选择了才展示
    if has_time_range and has_data_sel and has_cats_sel and has_valid_custom_dates:
        with st.spinner("Generating chart..."):

            # === 修复：第一次进入 dashboard，Custom date 必须按用户选择生效 ===
            if "Custom date" in time_range:
                t1_final = t1
                t2_final = t2
            else:
                t1_final = None
                t2_final = None

            combined_df = prepare_chart_data_fast(
                daily, category_tx, inv_grouped, time_range, data_sel, cats_sel,
                custom_dates_selected=("Custom date" in time_range),
                t1=t1_final,
                t2=t2_final
            )

        if combined_df is not None and not combined_df.empty:
            # 修复：确保图表中的日期按正确顺序显示
            combined_df = combined_df.sort_values("date")

            # 立即显示图表
            fig = px.line(
                combined_df,
                x="date",
                y="value",
                color="series",
                title="All Selected Data Types by Category",
                labels={"date": "Date", "value": "Value", "series": "Series"}
            )

            # === 智能加 marker：只有一个点的 series 才加 marker ===
            series_counts = combined_df.groupby("series")["date"].nunique().to_dict()

            for trace in fig.data:
                name = trace.name
                if name in series_counts and series_counts[name] == 1:
                    trace.update(mode="markers", marker=dict(size=5))  # 只有一个点 → 放大显示
                else:
                    trace.update(mode="lines")  # 正常多点 → 保持线图

            # 改为欧洲日期格式
            fig.update_layout(
                xaxis=dict(tickformat="%d/%m/%Y"),
                hovermode="x unified",
                height=600
            )

            # ✅ 强制 X 轴显示完整自定义日期范围（避免 Plotly 自动缩放只显示末段）
            if "Custom date" in time_range and t1_final is not None and t2_final is not None:
                t1_ts = pd.to_datetime(t1_final)
                t2_ts = pd.to_datetime(t2_final)
                week_start = t1_ts - pd.Timedelta(days=t1_ts.weekday())  # 回到周一
                fig.update_xaxes(range=[week_start, t2_ts])

            st.plotly_chart(
                fig,
                config={
                    "responsive": True,
                    "displayModeBar": True
                }
            )

            st.markdown("""
            <style>
            div[data-testid="stExpander"] > div:first-child {
                width: fit-content !important;
                max-width: 95% !important;
            }
            div[data-testid="stDataFrame"] {
                width: fit-content !important;
            }
            </style>
            """, unsafe_allow_html=True)

            # 显示数据表格 - 直接展示，去掉下拉框
            st.markdown("#### 📊 Combined Data for All Selected Types")
            display_df = combined_df.copy()

            # === 修改：为 Weekly Net Sales 显示周区间 ===
            def format_weekly_date(row):
                if "Weekly Net Sales" in row["data_type"]:
                    # 计算周的起始和结束日期（周一到周日）
                    week_start = row["date"]
                    week_end = week_start + pd.Timedelta(days=6)
                    # 确保周区间不重叠：如果起始日期不是周一，调整为周一
                    if week_start.weekday() != 0:  # 0 代表周一
                        week_start = week_start - pd.Timedelta(days=week_start.weekday())
                        week_end = week_start + pd.Timedelta(days=6)
                    return f"{week_start.strftime('%d/%m/%Y')}-{week_end.strftime('%d/%m/%Y')}"
                else:
                    return row["date"].strftime("%d/%m/%Y")

            display_df["date"] = display_df.apply(format_weekly_date, axis=1)

            # === 修改：对表格中的 Daily Net Sales 和 Weekly Net Sales 也进行四舍五入取整 ===
            display_df.loc[display_df["data_type"].isin(["Daily Net Sales", "Weekly Net Sales"]), "value"] = \
                display_df.loc[
                    display_df["data_type"].isin(["Daily Net Sales", "Weekly Net Sales"]), "value"
                ].apply(lambda x: proper_round(x) if not pd.isna(x) else 0)

            display_df = display_df.rename(columns={
                "date": "Date",
                "Category": "Category",
                "data_type": "Data Type",
                "value": "Value"
            })

            # 修复：按日期正确排序（需要创建一个临时日期列用于排序）
            def get_sort_date(row):
                if "Weekly Net Sales" in row["Data Type"]:
                    # 从周区间中提取起始日期
                    start_date_str = row["Date"].split('-')[0]
                    return pd.to_datetime(start_date_str, format='%d/%m/%Y')
                else:
                    return pd.to_datetime(row["Date"], format='%d/%m/%Y')

            display_df["Date_dt"] = display_df.apply(get_sort_date, axis=1)
            display_df = display_df.sort_values(["Date_dt", "Category", "Data Type"])
            display_df = display_df.drop("Date_dt", axis=1)

            # === 修改1：表格容器宽度跟随表格内容 ===
            # 计算表格总宽度
            total_width = 0
            for column in display_df.columns:
                header_len = len(str(column))
                # 估算列宽：标题长度+数据最大长度+2字符边距
                data_len = display_df[column].astype(str).str.len().max()
                col_width = max(header_len, data_len) + 2
                total_width += col_width

            # 设置表格容器样式
            st.markdown(f"""
            <style>
            /* 表格容器 - 宽度跟随内容 */
            [data-testid="stExpander"] {{
                width: auto !important;
                min-width: {total_width}ch !important;
                max-width: 100% !important;
            }}
            /* 让表格左右可滚动 */
            [data-testid="stDataFrame"] div[role="grid"] {{
                overflow-x: auto !important;
                width: auto !important;
            }}
            /* 自动列宽，不强制占满 */
            [data-testid="stDataFrame"] table {{
                table-layout: auto !important;
                width: auto !important;
            }}
            /* 所有单元格左对齐 */
            [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th {{
                text-align: left !important;
                justify-content: flex-start !important;
            }}
            /* 防止省略号 */
            [data-testid="stDataFrame"] td {{
                white-space: nowrap !important;
            }}
            </style>
            """, unsafe_allow_html=True)

            # === 新逻辑：列宽根据标题字符串长度设置 ===
            column_config = {}
            for column in display_df.columns:
                header_len = len(str(column))
                column_config[column] = st.column_config.Column(
                    column,
                    width=f"{header_len + 2}ch"
                )

            # 对3M/6M平均值列四舍五入保留两位小数
            avg_mask = display_df["Data Type"].str.contains("3M Avg|6M Avg", case=False, na=False)
            display_df.loc[avg_mask, "Value"] = display_df.loc[avg_mask, "Value"].apply(
                lambda x: round(x, 2) if pd.notna(x) else x
            )

            # 新增：对 Weekly Net Sales 也进行四舍五入取整
            weekly_mask = display_df["Data Type"].str.contains("Weekly Net Sales", case=False, na=False) & ~display_df[
                "Data Type"].str.contains("Avg", case=False, na=False)
            display_df.loc[weekly_mask, "Value"] = display_df.loc[weekly_mask, "Value"].apply(
                lambda x: proper_round(x) if not pd.isna(x) else 0
            )

            st.dataframe(display_df, column_config=column_config)

        else:
            st.warning("No data available for the selected combination.")

