# services/analytics.py
import pandas as pd
import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from datetime import timedelta
from services.db import get_db
import pandas as pd



# === 工具函数 ===
def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.drop_duplicates()
    df = df.dropna(how="all")
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])
    return df


def _to_numeric(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.replace(r"[^0-9\.\-]", "", regex=True)
        .replace("", np.nan)
        .astype(float)
    )


# === 数据加载 ===
def load_transactions(db, days=365, time_from=None, time_to=None):
    if time_from and time_to:
        start, end = pd.to_datetime(time_from), pd.to_datetime(time_to)
    else:
        end = pd.Timestamp.today()
        start = end - pd.Timedelta(days=days)

    # 转成 SQLite 可识别的字符串
    start_str = start.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end.strftime("%Y-%m-%d %H:%M:%S")

    query = """
        SELECT Datetime, Category, Item, Qty, [Net Sales], [Gross Sales],
               Discounts, [Customer ID], [Transaction ID]
        FROM transactions
        WHERE Datetime BETWEEN ? AND ?
    """
    df = pd.read_sql(query, db, params=[start_str, end_str])
    if not df.empty:
        df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce")
    return df


def load_inventory(db) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM inventory", db)
    return _clean_df(df)


def load_members(db) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM members", db)
    return _clean_df(df)


def compute_inventory_profit(df: pd.DataFrame) -> pd.DataFrame:
    """
    修改后的inventory value计算公式：
    - Tax - GST (10%)列如果是N: inventory value = Current Quantity Vie Market & Bar * Default Unit Cost
    - Tax - GST (10%)列如果是Y: inventory value = Current Quantity Vie Market & Bar * (Default Unit Cost/11*10)
    - 过滤掉Current Quantity Vie Market & Bar或者Default Unit Cost为空的行
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    for col in ["Tax - GST (10%)", "Price", "Current Quantity Vie Market & Bar", "Default Unit Cost"]:
        if col not in df.columns:
            df[col] = np.nan

    # 过滤掉空值行
    mask = (~df["Current Quantity Vie Market & Bar"].isna()) & (~df["Default Unit Cost"].isna())
    df = df[mask].copy()

    if df.empty:
        return df

    price = _to_numeric(df["Price"])
    qty = _to_numeric(df["Current Quantity Vie Market & Bar"])
    unit_cost = _to_numeric(df["Default Unit Cost"])
    tax_flag = df["Tax - GST (10%)"].astype(str)

    # 计算 retail_total
    retail_total = pd.Series(0.0, index=df.index)
    retail_total.loc[tax_flag.eq("N")] = (price * qty).loc[tax_flag.eq("N")]
    retail_total.loc[tax_flag.eq("Y")] = ((price / 11.0 * 10.0) * qty).loc[tax_flag.eq("Y")]

    # 修改：计算 inventory_value
    inventory_value = pd.Series(0.0, index=df.index)
    inventory_value.loc[tax_flag.eq("N")] = (unit_cost * qty).loc[tax_flag.eq("N")]
    inventory_value.loc[tax_flag.eq("Y")] = ((unit_cost / 11.0 * 10.0) * qty).loc[tax_flag.eq("Y")]

    profit = retail_total - inventory_value

    df["retail_total"] = retail_total
    df["inventory_value"] = inventory_value
    df["profit"] = profit

    return df


def load_all(db=None, time_from=None, time_to=None, days=None):
    conn = db or get_db()

    tx = pd.read_sql("SELECT * FROM transactions", conn)
    inv = pd.read_sql("SELECT * FROM inventory", conn)

    try:
        mem = pd.read_sql("SELECT * FROM members", conn)
    except Exception:
        mem = pd.DataFrame()

    # ✅ 每次都重新计算 inventory_value / profit，保证口径一致
    if not inv.empty:
        inv = compute_inventory_profit(inv)

    return tx, mem, inv


# === 日报表 ===
def daily_summary(transactions: pd.DataFrame) -> pd.DataFrame:
    if transactions.empty:
        return pd.DataFrame()
    transactions["date"] = pd.to_datetime(transactions["Datetime"], errors="coerce").dt.normalize()


    # 👉 确保关键列为数值，避免 groupby 后求和/均值时出错
    for col in ["Net Sales", "Gross Sales", "Qty"]:
        if col in transactions.columns:
            transactions[col] = (
                transactions[col]
                .astype(str)
                .str.replace(r"[^0-9\.\-]", "", regex=True)
                .replace("", pd.NA)
            )
            transactions[col] = pd.to_numeric(transactions[col], errors="coerce")

    summary = (
        transactions.groupby("date")
        .agg(
            net_sales=("Net Sales", "sum"),
            transactions=("Datetime", "count"),
            avg_txn=("Net Sales", "mean"),
            gross=("Gross Sales", "sum"),
            qty=("Qty", "sum"),
        )
        .reset_index()
    )
    summary["profit"] = summary["gross"] - summary["net_sales"]
    return summary


# === 销售预测 ===
def forecast_sales(transactions: pd.DataFrame, periods: int = 30) -> pd.DataFrame:
    if transactions.empty:
        return pd.DataFrame()
    transactions["date"] = pd.to_datetime(transactions["Datetime"]).dt.normalize()

    daily_sales = transactions.groupby("date")["Net Sales"].sum()
    if len(daily_sales) < 10:
        return pd.DataFrame()
    model = ExponentialSmoothing(daily_sales, trend="add", seasonal=None)
    fit = model.fit()
    forecast = fit.forecast(periods)
    return pd.DataFrame({
        "date": pd.date_range(start=daily_sales.index[-1] + timedelta(days=1), periods=periods),
        "forecast": forecast.values
    })


# === 高消费客户 ===
def forecast_top_consumers(transactions: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    if transactions.empty or "Customer ID" not in transactions.columns:
        return pd.DataFrame()
    return (
        transactions.groupby("Customer ID")["Net Sales"]
        .sum()
        .reset_index()
        .sort_values("Net Sales", ascending=False)
        .head(top_n)
    )


# === SKU 消耗时序 ===
def sku_consumption_timeseries(transactions: pd.DataFrame, sku: str) -> pd.DataFrame:
    if transactions.empty or "Item" not in transactions.columns:
        return pd.DataFrame()
    df = transactions[transactions["Item"] == sku].copy()
    if df.empty:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["Datetime"]).dt.normalize()

    return df.groupby("date")["Qty"].sum().reset_index()


# === 会员相关分析 ===
def member_flagged_transactions(transactions: pd.DataFrame, members: pd.DataFrame) -> pd.DataFrame:
    """
    会员识别逻辑：
    1. 如果客户在会员表中，且交易日期 >= 会员开始日期 → enrolled
    2. 否则 → not enrolled
    3. 对于没有 First Visit 或 Creation Date 的客户，使用 First Visit 中的最大日期作为默认值
    """

    df = transactions.copy()

    # 没有 member 表 → 全部是非会员
    if members is None or members.empty:
        df["is_member"] = False
        return df

    # 确保 Datetime 是 datetime 类型
    df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce")

    # 🔥 关键：使用 First Visit 中的最大日期作为默认值
    DEFAULT_MEMBER_DATE = None

    if "First Visit" in members.columns:
        # 提取所有有效的 First Visit 日期
        first_visit_dates = pd.to_datetime(members["First Visit"], errors="coerce").dropna()

        if not first_visit_dates.empty:
            # 使用 First Visit 中的最大日期作为默认值
            DEFAULT_MEMBER_DATE = first_visit_dates.max()
            print(f"DEBUG: 使用 First Visit 最大日期作为默认值: {DEFAULT_MEMBER_DATE.date()}")

    # 如果没有 First Visit，使用今天
    if DEFAULT_MEMBER_DATE is None:
        DEFAULT_MEMBER_DATE = pd.Timestamp.today().normalize()
        print(f"DEBUG: 没有 First Visit 数据，使用今天作为默认值: {DEFAULT_MEMBER_DATE.date()}")

    # === 为每个客户确定会员开始日期 ===
    customer_member_dates = {}

    # 处理 Square Customer ID
    if "Square Customer ID" in members.columns:
        for idx, row in members.iterrows():
            customer_id = str(row.get("Square Customer ID", "")).strip().lower()
            if not customer_id:
                continue

            # 确定会员开始日期
            member_start_date = None

            # 1. 优先使用 First Visit
            if "First Visit" in row:
                member_start_date = pd.to_datetime(row["First Visit"], errors="coerce")

            # 2. 其次使用 Creation Date
            if pd.isna(member_start_date) and "Creation Date" in row:
                member_start_date = pd.to_datetime(row["Creation Date"], errors="coerce")

            # 3. 🔥 关键修改：如果都没有，使用上面计算的默认日期
            if pd.isna(member_start_date):
                member_start_date = DEFAULT_MEMBER_DATE

            # 存储映射（如果有重复，取最早的日期）
            if customer_id not in customer_member_dates:
                customer_member_dates[customer_id] = member_start_date
            else:
                customer_member_dates[customer_id] = min(customer_member_dates[customer_id], member_start_date)

    # 处理 Reference ID
    if "Reference ID" in members.columns:
        for idx, row in members.iterrows():
            ref_id = str(row.get("Reference ID", "")).strip().lower()
            if not ref_id:
                continue

            # 确定会员开始日期（同上逻辑）
            member_start_date = None
            if "First Visit" in row:
                member_start_date = pd.to_datetime(row["First Visit"], errors="coerce")
            if pd.isna(member_start_date) and "Creation Date" in row:
                member_start_date = pd.to_datetime(row["Creation Date"], errors="coerce")

            # 🔥 使用默认日期
            if pd.isna(member_start_date):
                member_start_date = DEFAULT_MEMBER_DATE

            if ref_id not in customer_member_dates:
                customer_member_dates[ref_id] = member_start_date
            else:
                customer_member_dates[ref_id] = min(customer_member_dates[ref_id], member_start_date)

    # === 标记交易 ===
    df["clean_customer_id"] = df["Customer ID"].astype(str).str.strip().str.lower()
    df["is_member"] = False

    for idx, row in df.iterrows():
        customer_id = row.get("clean_customer_id", "")
        transaction_date = row["Datetime"]

        if not customer_id or pd.isna(transaction_date):
            continue

        if customer_id in customer_member_dates:
            member_start_date = customer_member_dates[customer_id]

            # 交易日期在会员开始日期之后（或当天）才算是会员消费
            if pd.notna(member_start_date) and transaction_date >= member_start_date:
                df.at[idx, "is_member"] = True

    # 清理临时列
    df = df.drop(columns=["clean_customer_id"], errors="ignore")

    # 添加调试信息
    print(f"DEBUG: 总客户数: {len(customer_member_dates)}")

    # 统计使用默认日期的客户数
    default_date_count = 0
    specific_date_count = 0

    for customer_id, date in customer_member_dates.items():
        if pd.notna(date):
            if date == DEFAULT_MEMBER_DATE:
                default_date_count += 1
            else:
                specific_date_count += 1

    print(f"DEBUG: 使用特定日期的客户数: {specific_date_count}")
    print(f"DEBUG: 使用默认日期的客户数: {default_date_count}")
    print(f"DEBUG: 默认日期值: {DEFAULT_MEMBER_DATE.date()}")
    print(f"DEBUG: 会员交易数: {df['is_member'].sum()}")
    print(f"DEBUG: 非会员交易数: {(df['is_member'] == False).sum()}")

    # 检查一些示例客户的会员开始日期
    if customer_member_dates:
        sample_customers = list(customer_member_dates.items())[:3]
        print(f"DEBUG: 示例客户会员开始日期:")
        for customer_id, date in sample_customers:
            date_str = date.date() if pd.notna(date) else "NaN"
            print(f"  - {customer_id}: {date_str}")

    return df

def member_frequency_stats(transactions: pd.DataFrame, members: pd.DataFrame) -> pd.DataFrame:
    if transactions.empty or members.empty:
        return pd.DataFrame()
    df = transactions.copy()
    df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce")
    df = df.dropna(subset=["Datetime"])
    stats = (
        df.groupby("Customer ID")["Datetime"]
        .agg(["count", "min", "max"])
        .reset_index()
        .rename(columns={"count": "txn_count", "min": "first_txn", "max": "last_txn"})
    )
    # ✅ 用新的列名来计算
    stats["days_active"] = (stats["last_txn"] - stats["first_txn"]).dt.days.clip(lower=1)
    stats["avg_days_between"] = stats["days_active"] / stats["txn_count"]
    return stats


def non_member_overview(transactions: pd.DataFrame, members: pd.DataFrame) -> pd.DataFrame:
    if transactions.empty:
        return pd.DataFrame()
    member_ids = set(members["Square Customer ID"].unique()) if not members.empty else set()
    df = transactions[~transactions["Customer ID"].isin(member_ids)].copy()
    return df.groupby("Customer ID")["Net Sales"].sum().reset_index()


# === 分类与推荐分析 ===
def category_counts(transactions: pd.DataFrame) -> pd.DataFrame:
    if transactions.empty or "Category" not in transactions.columns:
        return pd.DataFrame()
    return transactions["Category"].value_counts().reset_index().rename(
        columns={"index": "Category", "Category": "count"})


def heatmap_pivot(transactions: pd.DataFrame) -> pd.DataFrame:
    if transactions.empty or "Category" not in transactions.columns:
        return pd.DataFrame()
    return pd.pivot_table(
        transactions, values="Net Sales", index="Customer ID", columns="Category", aggfunc="sum", fill_value=0
    )


def top_categories_for_customer(transactions: pd.DataFrame, customer_id: str, top_n: int = 3) -> pd.DataFrame:
    df = transactions[transactions["Customer ID"] == customer_id]
    if df.empty:
        return pd.DataFrame()
    return (
        df.groupby("Category")["Net Sales"]
        .sum()
        .reset_index()
        .sort_values("Net Sales", ascending=False)
        .head(top_n)
    )


def recommend_similar_categories(transactions: pd.DataFrame, category: str, top_n: int = 3) -> pd.DataFrame:
    if transactions.empty or "Category" not in transactions.columns:
        return pd.DataFrame()
    other_cats = transactions["Category"].value_counts().reset_index()
    other_cats = other_cats[other_cats["index"] != category]
    return other_cats.head(top_n)


def ltv_timeseries_for_customer(transactions: pd.DataFrame, customer_id: str) -> pd.DataFrame:
    df = transactions[transactions["Customer ID"] == customer_id]
    if df.empty:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["Datetime"]).dt.normalize()

    return df.groupby("date")["Net Sales"].sum().cumsum().reset_index()


def recommend_bundles_for_customer(transactions: pd.DataFrame, customer_id: str, top_n: int = 3) -> pd.DataFrame:
    df = transactions[transactions["Customer ID"] == customer_id]
    if df.empty or "Item" not in df.columns:
        return pd.DataFrame()
    return df["Item"].value_counts().reset_index().head(top_n)


def churn_signals_for_member(transactions: pd.DataFrame, members: pd.DataFrame,
                             days_threshold: int = 30) -> pd.DataFrame:
    if transactions.empty or members.empty:
        return pd.DataFrame()
    df = transactions[transactions["Customer ID"].isin(members["Square Customer ID"].unique())]
    if df.empty:
        return pd.DataFrame()
    df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce")
    last_seen = df.groupby("Customer ID")["Datetime"].max().reset_index()
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_threshold)
    last_seen["churn_flag"] = last_seen["Datetime"] < cutoff
    return last_seen