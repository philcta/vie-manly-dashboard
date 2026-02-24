import streamlit as st

import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
from services.analytics import (
    member_flagged_transactions,
    member_frequency_stats,
    non_member_overview,
    category_counts,
    heatmap_pivot,
    top_categories_for_customer,
    recommend_similar_categories,
    ltv_timeseries_for_customer,
    recommend_bundles_for_customer,
    churn_signals_for_member,
)

@st.cache_data(show_spinner=False)
def get_customer_search_options(_tx, _members):
    """
    高效缓存所有搜索选项，减少重复计算
    """
    options = []

    if "Customer Name" not in _tx.columns:
        return options

    # 使用字典来存储每个 Customer Name 的最新 Customer ID
    customer_latest_id = {}

    # 按 Customer Name 和 Datetime 排序，获取最新的 Customer ID
    if "Datetime" in _tx.columns and "Customer ID" in _tx.columns:
        # 按时间降序排序，这样第一个就是最新的
        sorted_tx = _tx.sort_values("Datetime", ascending=False)

        # 遍历找到每个 Customer Name 的最新 Customer ID
        for _, row in sorted_tx.iterrows():
            name = row["Customer Name"]
            customer_id = row["Customer ID"]

            if pd.notna(name) and pd.notna(customer_id):
                if name not in customer_latest_id:
                    customer_latest_id[name] = str(customer_id)

    # 获取所有唯一的 Customer Name
    unique_names = _tx["Customer Name"].dropna().unique()

    # 预计算 enrolled 状态（使用集合提高查找速度）
    if not _members.empty and "Square Customer ID" in _members.columns:
        enrolled_ids = set(_members["Square Customer ID"].dropna().astype(str))
    else:
        enrolled_ids = set()

    # 构建选项列表
    for name in unique_names:
        # 获取 Customer ID
        customer_id = customer_latest_id.get(name, f"NO_ID_{name}")

        # 检查 enrolled 状态
        is_enrolled = "Yes" if customer_id in enrolled_ids else "No"

        options.append({
            "Customer Name": name,
            "Customer ID": customer_id,
            "is_enrolled": is_enrolled
        })

    return options


@st.cache_data(show_spinner=False)
def cached_member_flagged_transactions(tx, members):
    """
    对 member_flagged_transactions 结果做缓存
    """
    return member_flagged_transactions(tx, members)

@st.cache_data(show_spinner=False)
def cached_segmentation_preprocess(tx, members):
    """
    将 segmentation 页面最耗时的预处理全部缓存起来
    """
    import pandas as pd

    # === Prepare Datetime ===
    tx = tx.copy()
    tx["Datetime"] = pd.to_datetime(tx.get("Datetime"), errors="coerce", utc=True).dt.tz_localize(None)

    # === member flag ===
    from services.analytics import member_flagged_transactions
    df = member_flagged_transactions(tx, members)

    # === unify Customer ID ===
    if "Customer Name" in df.columns and "Customer ID" in df.columns:
        df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce", utc=True).dt.tz_localize(None)
        latest_ids = (
            df.dropna(subset=["Customer Name", "Customer ID", "Datetime"])
            .sort_values("Datetime")
            .groupby("Customer Name")
            .tail(1)[["Customer Name", "Customer ID"]]
        )
        df = df.drop(columns=["Customer ID"]).merge(latest_ids, on="Customer Name", how="left")

    return df

@st.cache_data(show_spinner=False)
def cached_heatmap_pivot(df, metric, time_col, net_col):
    """
    计算 heatmap 所需的数据并缓存：
    - groupby day-of-week + hour
    - pivot 成二维矩阵
    """
    t = pd.to_datetime(df[time_col], errors="coerce")
    base = df.assign(_date=t)
    base["_hour"] = base["_date"].dt.hour
    base["_dow"] = base["_date"].dt.day_name()

    if metric == "net sales" and net_col:
        agg = base.groupby(["_dow", "_hour"])[net_col].sum().reset_index(name="value")
    else:
        txn_col2 = "Transaction ID" if "Transaction ID" in base.columns else None
        if txn_col2:
            agg = base.groupby(["_dow", "_hour"])[txn_col2].nunique().reset_index(name="value")
        else:
            agg = base.groupby(["_dow", "_hour"]).size().reset_index(name="value")

    pv = agg.pivot(index="_dow", columns="_hour", values="value").fillna(0)
    return pv

def format_phone_number(phone):
    """
    格式化手机号：移除61之前的所有字符，确保以61开头
    """
    if pd.isna(phone) or phone is None:
        return ""

    phone_str = str(phone).strip()

    # 移除所有非数字字符
    digits_only = re.sub(r'\D', '', phone_str)

    # 查找61的位置
    if '61' in digits_only:
        # 找到61第一次出现的位置
        start_index = digits_only.find('61')
        # 返回从61开始的部分
        formatted = digits_only[start_index:]

        # 确保长度合理（手机号通常10-12位）
        if len(formatted) >= 10 and len(formatted) <= 12:
            return formatted
        else:
            # 如果长度不合适，返回原始数字
            return digits_only
    else:
        # 如果没有61，返回原始数字
        return digits_only


def persisting_multiselect(label, options, key, default=None, width_chars=None, format_func=None):
    """
    保持选择状态的多选框函数 - 统一宽度和箭头显示（增强版）
    """
    if key not in st.session_state:
        st.session_state[key] = default or []

    if width_chars is None:
        min_width = 30  # 全局默认 30ch
    else:
        min_width = width_chars

    st.markdown(f"""
    <style>
    /* === 强制覆盖 stMultiSelect 宽度（仅限当前 key） === */
    div[data-testid="stMultiSelect"][data-testid*="{key}"],
    [data-testid*="{key}"][data-testid="stMultiSelect"] {{
        width: {min_width}ch !important;
        min-width: {min_width}ch !important;
        max-width: {min_width}ch !important;
        flex: 0 0 {min_width}ch !important;
        box-sizing: border-box !important;
    }}

    /* === 下拉框主体 === */
    div[data-testid="stMultiSelect"][data-testid*="{key}"] [data-baseweb="select"],
    div[data-testid="stMultiSelect"][data-testid*="{key}"] [data-baseweb="select"] > div {{
        width: 100% !important;
        min-width: 100% !important;
        max-width: 100% !important;
        box-sizing: border-box !important;
    }}

    /* === 输入框 === */
    div[data-testid="stMultiSelect"][data-testid*="{key}"] input {{
        width: 100% !important;
        box-sizing: border-box !important;
    }}

    /* === 下拉菜单 === */
    div[role="listbox"] {{
        width: {min_width}ch !important;
        min-width: {min_width}ch !important;
        max-width: {min_width}ch !important;
        box-sizing: border-box !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    # 确保所有选项都是字符串类型
    options = [str(opt) for opt in options]

    # 确保默认值也是字符串类型
    default_values = [str(val) for val in st.session_state[key]]

    # 创建一个安全的 format_func，确保返回字符串
    def safe_format_func(x):
        result = format_func(x) if format_func else x
        return str(result)

    if format_func:
        return st.multiselect(label, options, default=default_values, key=key, format_func=safe_format_func)
    else:
        return st.multiselect(label, options, default=default_values, key=key)


def is_phone_number(name):
    """
    判断字符串是否为手机号（包含数字和特定字符）
    """
    if pd.isna(name) or name is None:
        return False

    name_str = str(name).strip()

    # 如果字符串只包含数字、空格、括号、加号、连字符，则认为是手机号
    if re.match(r'^[\d\s\(\)\+\-]+$', name_str):
        return True

    # 如果字符串长度在8-15之间且主要包含数字，也认为是手机号
    if 8 <= len(name_str) <= 15 and sum(c.isdigit() for c in name_str) >= 7:
        return True

    return False

def get_enrollment_status_for_table(customer_id, members_data):
    """判断客户是否enrolled，用于表格显示"""
    if pd.isna(customer_id) or customer_id == "":
        return "No"

    customer_id_str = str(customer_id)
    if "Square Customer ID" in members_data.columns:
        # 检查customer_id是否在members的Square Customer ID列中
        is_enrolled = any(
            str(member_id) == customer_id_str
            for member_id in members_data["Square Customer ID"].dropna()
        )
        return "Yes" if is_enrolled else "No"
    return "No"

def show_customer_segmentation(tx, members):
    # === 全局样式：参考 inventory 的样式设置 ===
    st.markdown("""
    <style>
    /* 去掉标题之间的空白 */
    div.block-container h1, 
    div.block-container h2, 
    div.block-container h3, 
    div.block-container h4,
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

    /* 让多选框列更紧凑 */
    div[data-testid="column"] {
        padding: 0 8px !important;
    }
    /* 让表格文字左对齐 */
    [data-testid="stDataFrame"] table {
        text-align: left !important;
    }
    [data-testid="stDataFrame"] th {
        text-align: left !important;
    }
    [data-testid="stDataFrame"] td {
        text-align: left !important;
    }

    /* 统一多选框和输入框的垂直对齐 */
    div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] {
        align-items: start !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <style>
    [data-testid="stDataEditor"] table {
        table-layout: fixed !important;
    }
    [data-testid="stDataEditor"] td, 
    [data-testid="stDataEditor"] th {
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        white-space: nowrap !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h2 style='font-size:24px; font-weight:700;'>👥 Customer Segmentation & Personalization</h2>",
                unsafe_allow_html=True)

    if tx.empty:
        st.info("No transaction data available.")
        return

    # always use latest uploaded data
    tx = tx.copy()
    from services.analytics import member_flagged_transactions
    members = members.copy()

    # === Prepare Datetime column ===
    tx["Datetime"] = pd.to_datetime(tx.get("Datetime", pd.NaT), errors="coerce", utc=True).dt.tz_localize(None)
    today = pd.Timestamp.today().normalize()
    four_weeks_ago = today - pd.Timedelta(weeks=4)

    # --- 给交易数据打上 is_member 标记（使用缓存版本）
    df = cached_segmentation_preprocess(tx, members)

    # === 新增：统一 Customer Name 与最新 Customer ID ===
    if "Customer Name" in df.columns and "Customer ID" in df.columns and "Datetime" in df.columns:
        # 确保 Datetime 为时间格式
        df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce", utc=True).dt.tz_localize(None)

        # 找到每个 Customer Name 最近一次交易对应的 Customer ID
        latest_ids = (df.dropna(subset=["Customer Name", "Customer ID", "Datetime"])
                      .sort_values("Datetime")
                      .groupby("Customer Name")
                      .tail(1)[["Customer Name", "Customer ID"]]
                      .drop_duplicates("Customer Name"))

        # 更新 df 中的 Customer ID
        df = df.drop(columns=["Customer ID"]).merge(latest_ids, on="Customer Name", how="left")

    # =========================
    # 👑 前置功能（User Analysis 之前）
    # =========================

    # ======================
    # 📅 Time Range (same layout as Sales Report)
    # ======================
    st.markdown(
        "<h4 style='font-size:18px; font-weight:700; margin-bottom:4px;'>📅 Time Range</h4>",
        unsafe_allow_html=True
    )

    col_range, col_spacer = st.columns([1, 5])
    with col_range:
        range_opt = st.selectbox(
            "Select range",
            ["Custom dates", "WTD", "MTD", "YTD"],
            key="seg_range",
            label_visibility="visible"
        )

    today = pd.Timestamp.today().normalize()

    # default init
    start_date = df["Datetime"].min().date()
    end_date = df["Datetime"].max().date()

    # Apply preset ranges
    if range_opt == "WTD":
        start_date = (today - pd.Timedelta(days=today.weekday())).date()
        end_date = today.date()
    elif range_opt == "MTD":
        start_date = today.replace(day=1).date()
        end_date = today.date()
    elif range_opt == "YTD":
        start_date = today.replace(month=1, day=1).date()
        end_date = today.date()

    # Custom dates (two inputs side-by-side)
    if range_opt == "Custom dates":
        col_from, col_to, _ = st.columns([1, 1, 5])

        with col_from:
            start_date = st.date_input("From", value=start_date, format="DD/MM/YYYY")
        with col_to:
            end_date = st.date_input("To", value=end_date, format="DD/MM/YYYY")
    else:
        # Show disabled date boxes for clarity (same as Sales Report)
        col_from, col_to, _ = st.columns([1, 1, 5])
        with col_from:
            st.date_input("From", value=start_date, disabled=True, format="DD/MM/YYYY")
        with col_to:
            st.date_input("To", value=end_date, disabled=True, format="DD/MM/YYYY")

    # Convert to timestamp
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    # Final filtering
    df = df[(df["Datetime"] >= start_date) & (df["Datetime"] <= end_date)]

    # === Overview add-ons ===
    st.markdown("<h3 style='font-size:20px; font-weight:700;'>✨ Overview add-ons</h3>", unsafe_allow_html=True)

    # 使用 df（已经 member_flag + 最新 ID）做过滤
    df_filtered = df[(df["Datetime"] >= start_date) & (df["Datetime"] <= end_date)].copy()

    # 🔥 修复：先计算每笔交易的总金额，再去重
    if "Transaction ID" in df_filtered.columns and "Net Sales" in df_filtered.columns:
        # 确保 Net Sales 是数值
        df_filtered["Net Sales"] = pd.to_numeric(df_filtered["Net Sales"], errors="coerce")

        # 按 Transaction ID 聚合，计算每笔交易的总金额
        transaction_summary = df_filtered.groupby("Transaction ID").agg({
            "Net Sales": "sum",
            "is_member": "first",  # 取第一个 is_member 值
            "Customer ID": "first",
            "Customer Name": "first"
        }).reset_index()

        df_unique = transaction_summary
    else:
        # 没有 Transaction ID，直接使用原始数据
        df_unique = df_filtered.copy()
        df_unique["Net Sales"] = pd.to_numeric(df_unique["Net Sales"], errors="coerce")

    # ====== 关键修复：使用正确的 is_member 标记 ======
    enrolled = df_unique[df_unique["is_member"] == True]
    non_enrolled = df_unique[df_unique["is_member"] == False]

    # ====== 计算平均消费 ======
    # 对于 enrolled：总消费额 / 交易数
    if len(enrolled) > 0:
        total_spend_member = enrolled["Net Sales"].sum()
        num_trans_member = len(enrolled)
        avg_spend_member = total_spend_member / num_trans_member if num_trans_member > 0 else 0
    else:
        avg_spend_member = None

    # 对于 non_enrolled：总消费额 / 交易数
    if len(non_enrolled) > 0:
        total_spend_non_member = non_enrolled["Net Sales"].sum()
        num_trans_non_member = len(non_enrolled)
        avg_spend_non_member = total_spend_non_member / num_trans_non_member if num_trans_non_member > 0 else 0
    else:
        avg_spend_non_member = None

    # 对于 non_enrolled：总消费额 / 交易数
    if len(non_enrolled) > 0:
        total_spend_non_member = non_enrolled["Net Sales"].sum()
        num_trans_non_member = len(non_enrolled)
        avg_spend_non_member = total_spend_non_member / num_trans_non_member if num_trans_non_member > 0 else 0
    else:
        avg_spend_non_member = None

    # ====== 输出 Summary ======
    summary_table_data = {
        "Metric": ["Avg Spend (Enrolled)", "Avg Spend (Not Enrolled)"],
        "Value": [
            "-" if pd.isna(avg_spend_member) else f"${avg_spend_member:,.2f}",
            "-" if pd.isna(avg_spend_non_member) else f"${avg_spend_non_member:,.2f}",
        ],
    }

    df_summary = pd.DataFrame(summary_table_data)

    column_config = {
        "Metric": st.column_config.Column(width=150),
        "Value": st.column_config.Column(width=80),
    }

    st.data_editor(
        df_summary,
        column_config=column_config,
        use_container_width=False,
        hide_index=True,
        disabled=True,
    )

    st.divider()

    # [2] 两个柱状预测 - 放在同一行
    st.markdown("<h3 style='font-size:20px; font-weight:700;'>📊 Customer Behavior Predictions</h3>",
                unsafe_allow_html=True)

    # 使用两列布局将两个预测图表放在同一行
    col1, col2 = st.columns(2)

    time_col = next((c for c in ["Datetime", "Date", "date", "Transaction Time"] if c in df.columns), None)
    if time_col:
        with col1:
            t = pd.to_datetime(df[time_col], errors="coerce")
            day_df = df.assign(_dow=t.dt.day_name())
            dow_counts = day_df.dropna(subset=["_dow"]).groupby("_dow").size().reset_index(
                name="Predicted Transactions")
            cat_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            dow_counts["_dow"] = pd.Categorical(dow_counts["_dow"], categories=cat_order, ordered=True)

            fig_dow = px.bar(
                dow_counts.sort_values("_dow"),
                x="_dow",
                y="Predicted Transactions",
                title="Shopping Days Prediction"
            )
            fig_dow.update_layout(
                width=500,
                height=420,
                margin=dict(l=40, r=20, t=60, b=80),
                xaxis_title=None,
                yaxis_title="Predicted Transactions",
                uniformtext_minsize=10,
                uniformtext_mode="hide",
                autosize=False
            )

            st.plotly_chart(fig_dow, config={"responsive": True, "displayModeBar": True})

    # 修改：使用分类而不是具体商品名称
    category_col = next((c for c in ["Category", "Item Category", "Product Category"] if c in df.columns), None)
    qty_col = "Qty" if "Qty" in df.columns else None
    if category_col:
        with col2:
            if qty_col:
                top_categories = df.groupby(category_col)[qty_col].sum().reset_index().sort_values(qty_col,
                                                                                                   ascending=False).head(
                    15)
                # 设置柱形图宽度为更紧凑
                fig_categories = px.bar(top_categories, x=category_col, y=qty_col,
                                        title="Top Categories Prediction (Top 15)")
                fig_categories.update_layout(
                    width=500,
                    height=420,
                    margin=dict(l=40, r=20, t=60, b=80),
                    xaxis_tickangle=-30,
                    uniformtext_minsize=10,
                    uniformtext_mode="hide",
                    autosize=False,
                    xaxis_title=None
                )

                st.plotly_chart(fig_categories, config={"responsive": True, "displayModeBar": True})
            else:
                top_categories = df[category_col].value_counts().reset_index().rename(
                    columns={"index": "Category", category_col: "Count"}).head(15)
                # 设置柱形图宽度为更紧凑
                fig_categories = px.bar(top_categories, x="Category", y="Count",
                                        title="Top Categories Prediction (Top 15)")
                fig_categories.update_layout(
                    width=420,
                    height=420,
                    margin=dict(l=40, r=20, t=60, b=80),
                    xaxis_tickangle=-30,
                    uniformtext_minsize=10,
                    uniformtext_mode="hide"
                )
                st.plotly_chart(fig_categories, config={"responsive": True, "displayModeBar": True})
    else:
        # 如果没有分类列，使用商品名称但只显示大类（通过截取或分组）
        item_col = next((c for c in ["Item", "Item Name", "Variation Name", "SKU Name"] if c in df.columns), None)
        if item_col:
            with col2:
                # 尝试从商品名称中提取分类（取第一个单词或特定分隔符前的部分）
                df_with_category = df.copy()
                # 简单的分类提取：取第一个单词或特定分隔符前的部分
                df_with_category['_category'] = df_with_category[item_col].astype(str).str.split().str[0]

                if qty_col:
                    top_categories = df_with_category.groupby('_category')[qty_col].sum().reset_index().sort_values(
                        qty_col, ascending=False).head(15)
                    fig_categories = px.bar(top_categories, x='_category', y=qty_col,
                                            title="Top Categories Prediction (Top 15)")
                    fig_categories.update_layout(
                        width=420,
                        height=420,
                        margin=dict(l=40, r=20, t=60, b=80),
                        xaxis_tickangle=-30,
                        uniformtext_minsize=10,
                        uniformtext_mode="hide"
                    )
                    st.plotly_chart(fig_categories, config={"responsive": True, "displayModeBar": True})
                else:
                    top_categories = df_with_category['_category'].value_counts().reset_index().rename(
                        columns={"index": "Category", '_category': "Count"}).head(15)
                    fig_categories = px.bar(top_categories, x="Category", y="Count",
                                            title="Top Categories Prediction (Top 15)")
                    fig_categories.update_layout(
                        width=420,
                        height=420,
                        margin=dict(l=40, r=20, t=60, b=80),
                        xaxis_tickangle=-30,
                        uniformtext_minsize=10,
                        uniformtext_mode="hide"
                    )
                    st.plotly_chart(fig_categories, config={"responsive": True, "displayModeBar": True})

    st.divider()

    # [3] Top20 churn 风险（基于 Customer Name 计算）
    st.markdown("<h3 style='font-size:20px; font-weight:700;'>👥 Customer Churn Analysis</h3>",
                unsafe_allow_html=True)
    if time_col and "Customer Name" in df.columns:
        t = pd.to_datetime(df[time_col], errors="coerce")
        df["_ts"] = t

        # === 使用正确的日期范围计算 ===
        today = pd.Timestamp.today().normalize()
        if df["_ts"].dropna().empty:
            st.info("No customers found in this date range.")
            return

        # 第一个期间：从数据的实际第一天到四周前（28天前）
        data_start_date = df["_ts"].min().normalize()  # 使用数据的实际开始日期
        period1_end = today - pd.Timedelta(days=28)  # 四周前

        # 第二个期间：过去四周（今天往前推28天）
        period2_start = today - pd.Timedelta(days=28)
        period2_end = today

        # 检查日期范围是否有效
        if period1_end < data_start_date:
            period1_end = period2_start - pd.Timedelta(days=1)

        # === 直接按日期过滤 ===
        base = df.dropna(subset=["Customer Name"])

        # 第一个期间：历史数据（从数据开始到四周前）
        mask_period1 = (base["_ts"] >= data_start_date) & (base["_ts"] <= period1_end)
        period1_data = base[mask_period1]

        # 第二个期间：最近四周
        mask_period2 = (base["_ts"] >= period2_start) & (base["_ts"] <= period2_end)
        period2_data = base[mask_period2]

        # 获取第一个期间的客户（历史常客）
        if not period1_data.empty:
            # 计算历史访问频率（按天去重）
            period1_visits = (period1_data.dropna(subset=["Customer Name", "Transaction ID"])
                              .groupby(["Customer Name", period1_data["_ts"].dt.date])["Transaction ID"]
                              .nunique()
                              .reset_index(name="daily_visits"))

            # === 修改：计算平均每月来访次数（仅对有来访的月份取平均） ===
            period1_visits["_month"] = pd.to_datetime(period1_visits["_ts"]).dt.to_period("M")

            # 每个客户在每个月的访问次数（去重按天或交易）
            monthly_visits = (period1_visits.groupby(["Customer Name", "_month"])
                              ["daily_visits"].sum()
                              .reset_index(name="monthly_visits"))

            # 对每个客户计算平均每月来访次数（仅统计有来访的月份）
            customer_avg_visits = (monthly_visits.groupby("Customer Name")["monthly_visits"]
                                   .mean()
                                   .reset_index(name="Average Visit"))
            customer_avg_visits["Average Visit"] = customer_avg_visits["Average Visit"].round(2)

            # 过滤常客（平均访问次数 >= 2）
            regular_customers = customer_avg_visits[customer_avg_visits["Average Visit"] >= 2]

        else:
            regular_customers = pd.DataFrame(columns=["Customer Name", "Average Visit"])
            st.warning("No data found in Period 1. This might be because the data only started recently.")

        # === New integer-only inputs, same behavior as Inventory Current Quantity ===
        col_l, col_r, _ = st.columns([1.0, 1.0, 5.0])

        with col_l:
            months_raw = st.text_input(
                "Select last months",
                value="1",
                key="churn_months_input",
                help="Please enter an integer"
            )
            # integer check
            if not months_raw.isdigit():
                st.warning("Please enter an integer")
                months = 1
            else:
                months = int(months_raw)
                months = max(1, min(months, 12))  # limit 1–12

        with col_r:
            top_n_raw = st.text_input(
                "Show Top N users",
                value="20",
                key="churn_topn_input",
                help="Please enter an integer"
            )
            if not top_n_raw.isdigit():
                st.warning("Please enter an integer")
                top_n = 20
            else:
                top_n = int(top_n_raw)
                top_n = max(1, min(top_n, 200))  # Limit 1–200

        # ---- Compute date ranges ----
        today = pd.Timestamp.today().normalize()
        period2_start = today - pd.DateOffset(months=int(months))
        period2_end = today

        # period2 = 最近 N 个月的来访客户
        period2_data = df[
            (df["Datetime"] >= period2_start) &
            (df["Datetime"] <= period2_end)
            ].copy()

        period2_customers = period2_data["Customer Name"].dropna().unique().tolist()

        # ---- Lost regulars: appear in regular_customers but NOT in period2 ----
        if not regular_customers.empty:
            churn_candidates = regular_customers[
                ~regular_customers["Customer Name"].isin(period2_customers)
            ].copy()

            churn_candidates["Last Visit (months)"] = int(months)

            churn_tag_final = (
                churn_candidates.sort_values("Average Visit", ascending=False)
                .head(int(top_n))
            )
        else:
            churn_tag_final = pd.DataFrame(columns=["Customer Name", "Average Visit", "Last Visit (months)"])

        # ---- Add Customer ID + Phone + Enrolled Status ----
        if not churn_tag_final.empty:
            # 添加Customer ID
            if "Customer ID" in df.columns:
                id_mapping = df[["Customer Name", "Customer ID"]].drop_duplicates()
                churn_tag_final = churn_tag_final.merge(id_mapping, on="Customer Name", how="left")
            else:
                churn_tag_final["Customer ID"] = ""

            # 添加Phone
            if "Square Customer ID" in members.columns:
                phone_map = (
                    members.rename(columns={"Square Customer ID": "Customer ID", "Phone Number": "Phone"})
                    [["Customer ID", "Phone"]]
                    .dropna(subset=["Customer ID"])
                    .drop_duplicates("Customer ID")
                )
                churn_tag_final = churn_tag_final.merge(phone_map, on="Customer ID", how="left")
            else:
                churn_tag_final["Phone"] = ""

            # 添加Enrolled状态
            churn_tag_final["Enrolled"] = churn_tag_final["Customer ID"].apply(
                lambda x: get_enrollment_status_for_table(x, members)
            )


        if churn_tag_final.empty:
            st.info("No customers found.")
        else:
            # 更新表格列配置，添加Enrolled列
            column_config = {
                'Customer Name': st.column_config.Column(width=105),
                'Customer ID': st.column_config.Column(width=100),
                'Phone': st.column_config.Column(width=90),
                'Enrolled': st.column_config.Column(width=80),
                'Average Visit': st.column_config.Column(width=90),
                'Last Visit (months)': st.column_config.Column(width=110),
            }

            st.data_editor(
                churn_tag_final[
                    ["Customer Name", "Customer ID", "Phone", "Enrolled", "Average Visit", "Last Visit (months)"]
                ],
                column_config=column_config,
                use_container_width=False,
                hide_index=True,
                disabled=True
            )

    st.divider()

    # [4] 姓名/ID 搜索（显示所有客户，包括enrolled和not enrolled）
    # ✅ 使用缓存版本获取搜索选项
    options = get_customer_search_options(tx, members)

    # 🔹 使用三列布局缩短下拉框宽度
    col_search, _ = st.columns([1.6, 5.4])
    with col_search:
        if options:  # 只有有选项时才显示
            # 创建选项映射
            option_dict = {}
            for opt in options:
                status_symbol = "✓" if opt["is_enrolled"] == "Yes" else "✗"
                display_name = f"{opt['Customer Name']} [{status_symbol}]"
                option_dict[opt["Customer Name"]] = display_name

            # 使用Customer Name作为选项值
            customer_options = [opt["Customer Name"] for opt in options]

            # 初始化session state
            if "customer_search_names" not in st.session_state:
                st.session_state["customer_search_names"] = []

            # 为分类选择创建表单，避免立即rerun
            with st.form(key="customer_search_form"):
                # ✅ 使用空的 default 值，避免重新计算
                # 获取当前已选择的值
                current_selection = st.session_state.get("customer_search_names", [])

                # 过滤掉不存在的选项（防止错误）
                valid_selection = [name for name in current_selection if name in customer_options]

                sel_names = st.multiselect(
                    "🔎 Search customers",
                    options=customer_options,
                    default=valid_selection,
                    format_func=lambda x: option_dict.get(x, x),
                    key="customer_search_widget",
                    placeholder="Select customers..."
                )

                # 应用按钮
                submitted = st.form_submit_button("Apply", type="primary")

                if submitted:
                    # 更新session state
                    st.session_state["customer_search_names"] = sel_names
                    st.rerun()

            # 从session state获取最终的选择
            sel_names = st.session_state.get("customer_search_names", [])

            # 显示当前选择状态
            if sel_names:
                st.caption(f"✅ Selected: {len(sel_names)} customers")
            else:
                st.caption("ℹ️ No customers selected")
        else:
            st.caption("ℹ️ No customer data available for search")
            sel_names = []

    # ✅ 使用缓存的客户数据来显示选中的客户交易
    if sel_names:
        # 创建一个映射字典，加速查找
        name_to_info = {opt["Customer Name"]: opt for opt in options}

        # 为选中的客户创建ID映射
        selected_customer_ids = []
        for name in sel_names:
            if name in name_to_info:
                selected_customer_ids.append(name_to_info[name]["Customer ID"])

        # 过滤交易数据（使用原始数据，因为这是用户选择后才需要计算的）
        if "Customer ID" in tx.columns:
            # 先过滤有Customer ID的记录
            mask = tx["Customer ID"].astype(str).isin(selected_customer_ids)
        else:
            # 回退到使用Customer Name过滤
            mask = tx["Customer Name"].isin(sel_names)

        chosen = tx[mask].copy()

        # 添加Enrolled列（使用缓存的enrolled状态）
        chosen["Enrolled"] = chosen["Customer Name"].apply(
            lambda x: name_to_info.get(x, {}).get("is_enrolled", "No")
        )

        st.markdown("<h3 style='font-size:20px; font-weight:700;'>All transactions for selected customers</h3>",
                    unsafe_allow_html=True)

        # 更新列配置，添加Enrolled列
        column_config = {
            "Datetime": st.column_config.Column(width=120),
            "Customer Name": st.column_config.Column(width=120),
            "Enrolled": st.column_config.Column(width=80),
            "Customer ID": st.column_config.Column(width=140),
            "Category": st.column_config.Column(width=140),
            "Item": st.column_config.Column(width=250),
            "Qty": st.column_config.Column(width=40),
            "Net Sales": st.column_config.Column(width=80),
        }

        # ✅ 显示指定列（包括Enrolled）
        display_cols = ["Datetime", "Customer Name", "Enrolled", "Category", "Item", "Qty", "Net Sales"]
        existing_cols = [c for c in display_cols if c in chosen.columns]

        if "Datetime" in chosen.columns:
            chosen = chosen.sort_values("Datetime", ascending=False)

        # ✅ 只显示前100条记录，提高渲染速度
        display_data = chosen.head(100) if len(chosen) > 100 else chosen

        if len(chosen) > 100:
            st.caption(f"⚠️ Showing 100 of {len(chosen)} total transactions. Use filters to narrow down.")

        st.data_editor(
            display_data[existing_cols],
            column_config=column_config,
            use_container_width=False,
            hide_index=True,
            disabled=True
        )

    st.divider()

    # [5] Heatmap 可切换
    st.markdown("<h3 style='font-size:20px; font-weight:700;'>Heatmap (selectable metric)</h3>",
                unsafe_allow_html=True)

    # 🔹 使用三列布局缩短下拉框宽度，与 inventory.py 保持一致
    col_metric, _ = st.columns([1, 6])
    with col_metric:
        # === 修改：设置选择框宽度 ===
        st.markdown("""
        <style>
        div[data-testid*="stSelectbox"][aria-label="Metric"],
        div[data-testid*="stSelectbox"][data-baseweb="select"][aria-label="Metric"] {
            width: 15ch !important;
            min-width: 15ch !important;
            max-width: 15ch !important;
        }
        </style>
        """, unsafe_allow_html=True)

        metric = st.selectbox("Metric", ["net sales", "number of transactions"], index=0, key="heatmap_metric")

    if time_col:
        # 找到 Net Sales 列
        net_col = next((c for c in ["Net Sales", "Net_Sales", "NetSales"] if c in df.columns), None)

        # ✅ 使用缓存版本计算 heatmap 数据
        pv = cached_heatmap_pivot(df, metric, time_col, net_col)

        # 画图
        fig_heatmap = px.imshow(pv, aspect="auto", title=f"Heatmap by {metric.title()} (Hour x Day)")
        fig_heatmap.update_layout(width=600)  # 设置图表宽度
        st.plotly_chart(fig_heatmap, config={"responsive": True, "displayModeBar": True})
