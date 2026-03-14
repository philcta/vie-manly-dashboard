"""
backfill_weekly_stats.py — Populate weekly knowledge-base tables from existing data.

Reads from: transactions, daily_store_stats, daily_category_stats, staff_shifts,
            inventory_intelligence, member_daily_stats, loyalty_events, members,
            category_mappings, inventory_margins

Writes to:  weekly_store_stats, weekly_category_stats, weekly_member_stats,
            weekly_staff_stats, weekly_inventory_stats, weekly_hourly_patterns,
            weekly_dow_stats

Can be run standalone OR imported by scheduled_sync:
    python scripts/backfill_weekly_stats.py                # Full backfill
    python scripts/backfill_weekly_stats.py --weeks 4      # Last 4 weeks only
    from scripts.backfill_weekly_stats import run_weekly_stats_update  # Import
"""
import sys, os, json, urllib.request, time, math
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from collections import defaultdict
from datetime import datetime, timedelta, date

SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

HEADERS = {
    "apikey": SUPA_KEY,
    "Authorization": f"Bearer {SUPA_KEY}",
    "Content-Type": "application/json",
}

STORE_OPENING_DATE = "2025-08-20"

DOW_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


# ── Supabase helpers ──────────────────────────────────────────────────

def supa_get(endpoint):
    url = f"{SUPA_URL}/rest/v1/{endpoint}"
    req = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=120)
    return json.loads(resp.read())


def supa_get_all(endpoint):
    """GET with pagination to bypass 1000-row limit."""
    all_rows = []
    page_size = 5000
    offset = 0
    while True:
        sep = "&" if "?" in endpoint else "?"
        data = supa_get(f"{endpoint}{sep}limit={page_size}&offset={offset}")
        all_rows.extend(data)
        if len(data) < page_size:
            break
        offset += page_size
    return all_rows


def supa_post(endpoint, data, extra_headers=None):
    url = f"{SUPA_URL}/rest/v1/{endpoint}"
    hdrs = dict(HEADERS)
    if extra_headers:
        hdrs.update(extra_headers)
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    resp = urllib.request.urlopen(req, timeout=120)
    return resp.status


def upsert_batch(table, records, conflict_cols, label=""):
    batch_size = 500
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        status = supa_post(
            f"{table}?on_conflict={conflict_cols}",
            batch,
            extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )
        total += len(batch)
        print(f"    {label} batch {i // batch_size + 1}: {len(batch)} rows → HTTP {status}")
    return total


# ── Week helpers ──────────────────────────────────────────────────────

def get_week_start(d):
    """Return Monday of the week containing date d."""
    if isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d").date()
    return d - timedelta(days=d.weekday())  # weekday(): Mon=0


def week_label(ws):
    """e.g. '2026-W11 (Mar 9–15)'"""
    we = ws + timedelta(days=6)
    iso = ws.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d} ({ws.strftime('%b %-d' if os.name != 'nt' else '%b %#d')}–{we.strftime('%-d' if os.name != 'nt' else '%#d')})"


def get_day_type(d):
    """Return 'weekday' or 'weekend'."""
    if isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d").date()
    return "weekend" if d.weekday() >= 5 else "weekday"


def get_dow(d):
    """Return day-of-week 0=Sunday..6=Saturday (JS-style)."""
    if isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d").date()
    return (d.weekday() + 1) % 7  # Python Mon=0 → JS Sun=0


# ── Data Loading ──────────────────────────────────────────────────────

def load_daily_store_stats(start_date=None):
    ep = "daily_store_stats?select=*&order=date"
    if start_date:
        ep += f"&date=gte.{start_date}"
    return supa_get_all(ep)


def load_daily_category_stats(start_date=None):
    ep = "daily_category_stats?select=*&order=date"
    if start_date:
        ep += f"&date=gte.{start_date}"
    return supa_get_all(ep)


def load_staff_shifts(start_date=None):
    ep = "staff_shifts?select=shift_date,staff_name,team_member_id,job_title,business_side,effective_hours,labour_cost,is_teen&order=shift_date"
    if start_date:
        ep += f"&shift_date=gte.{start_date}"
    return supa_get_all(ep)


def load_transactions_hourly(start_date=None):
    """Load transactions with hour extracted for hourly patterns."""
    ep = "transactions?select=date,time,net_sales,transaction_id,customer_id&order=id"
    if start_date:
        ep += f"&date=gte.{start_date}"
    return supa_get_all(ep)


def load_member_daily_stats_latest():
    """Load latest stats per member for churn classification."""
    ep = "rpc/get_latest_member_stats"
    try:
        url = f"{SUPA_URL}/rest/v1/{ep}"
        req = urllib.request.Request(url, data=b"{}", headers=HEADERS, method="POST")
        resp = urllib.request.urlopen(req, timeout=120)
        return json.loads(resp.read())
    except Exception:
        return []


def load_loyalty_events(start_date=None):
    ep = "loyalty_events?select=event_type,points,created_at&order=created_at"
    if start_date:
        ep += f"&created_at=gte.{start_date}T00:00:00"
    return supa_get_all(ep)


def load_member_loyalty():
    return supa_get_all("member_loyalty?select=balance,lifetime_points")


def load_category_mappings():
    data = supa_get("category_mappings?select=category,side")
    return {r["category"]: r["side"] for r in data}


def load_inventory_margins():
    data = supa_get("inventory_margins?select=scope,margin_pct&scope_type=eq.category")
    return {r["scope"]: float(r.get("margin_pct") or 0) for r in data}


def load_inventory_intelligence():
    return supa_get_all(
        "inventory_intelligence?select=product_name,current_quantity,sales_velocity,"
        "days_of_stock,sell_through_pct,reorder_alert,units_sold_7d,units_sold_30d,"
        "units_sold_90d,revenue_30d"
    )


# ── Table 1: weekly_store_stats ───────────────────────────────────────

def build_weekly_store_stats(dss_rows, shifts, cat_stats, margins, side_map):
    print("  Building weekly_store_stats...")
    # Group daily_store_stats by week
    by_week = defaultdict(list)
    for r in dss_rows:
        ws = get_week_start(r["date"])
        by_week[ws].append(r)

    # Group shifts by week
    shifts_by_week = defaultdict(list)
    for s in shifts:
        ws = get_week_start(s["shift_date"])
        shifts_by_week[ws].append(s)

    # Group cat_stats by week for margin calculation
    cat_by_week = defaultdict(list)
    for c in cat_stats:
        ws = get_week_start(c["date"])
        cat_by_week[ws].append(c)

    records = []
    for ws in sorted(by_week.keys()):
        wl = week_label(ws)
        days = by_week[ws]
        week_shifts = shifts_by_week.get(ws, [])
        week_cats = cat_by_week.get(ws, [])

        # For each (side, day_type) combo + 'All'/'all'
        for side_filter in ["All", "Cafe", "Retail"]:
            for dt_filter in ["all", "weekday", "weekend"]:
                # Filter days by day_type
                filtered_days = days
                if dt_filter != "all":
                    filtered_days = [d for d in days if get_day_type(d["date"]) == dt_filter]
                if not filtered_days:
                    continue

                total_net = sum(float(d.get("total_net_sales") or 0) for d in filtered_days)
                total_tx = sum(int(d.get("total_transactions") or 0) for d in filtered_days)
                total_items = sum(float(d.get("total_items") or 0) for d in filtered_days)
                member_tx = sum(int(d.get("member_transactions") or 0) for d in filtered_days)
                member_sales = sum(float(d.get("member_net_sales") or 0) for d in filtered_days)
                nonmember_tx = sum(int(d.get("non_member_transactions") or 0) for d in filtered_days)
                nonmember_sales = sum(float(d.get("non_member_net_sales") or 0) for d in filtered_days)
                unique_cust = sum(int(d.get("total_unique_customers") or 0) for d in filtered_days)
                trading_days = len(filtered_days)

                # Side-specific sales from cat_stats
                if side_filter != "All":
                    side_cats = [c for c in week_cats
                                 if get_day_type(c["date"]) == dt_filter or dt_filter == "all"]
                    side_cats = [c for c in side_cats if c.get("side") == side_filter]
                    total_net = sum(float(c.get("total_net_sales") or 0) for c in side_cats)
                    total_tx = sum(int(c.get("transaction_count") or 0) for c in side_cats)
                    total_items = sum(float(c.get("total_qty") or 0) for c in side_cats)

                # Labour from shifts
                filtered_shifts = week_shifts
                if dt_filter != "all":
                    filtered_shifts = [s for s in week_shifts if get_day_type(s["shift_date"]) == dt_filter]

                # Map business_side: Bar/Overhead → Cafe
                def map_side(bs):
                    return "Cafe" if bs in ("Bar", "Overhead") else "Retail"

                if side_filter != "All":
                    filtered_shifts = [s for s in filtered_shifts if map_side(s.get("business_side", "")) == side_filter]

                total_labour = sum(float(s.get("labour_cost") or 0) for s in filtered_shifts)
                total_hours = sum(float(s.get("effective_hours") or 0) for s in filtered_shifts)
                unique_staff_ids = set(s.get("team_member_id") for s in filtered_shifts if s.get("team_member_id"))

                # 4-way split (only for All side)
                adult_cafe_cost = sum(float(s.get("labour_cost") or 0) for s in week_shifts
                                      if not s.get("is_teen") and map_side(s.get("business_side", "")) == "Cafe"
                                      and (dt_filter == "all" or get_day_type(s["shift_date"]) == dt_filter))
                adult_cafe_hours = sum(float(s.get("effective_hours") or 0) for s in week_shifts
                                       if not s.get("is_teen") and map_side(s.get("business_side", "")) == "Cafe"
                                       and (dt_filter == "all" or get_day_type(s["shift_date"]) == dt_filter))
                adult_retail_cost = sum(float(s.get("labour_cost") or 0) for s in week_shifts
                                        if not s.get("is_teen") and map_side(s.get("business_side", "")) == "Retail"
                                        and (dt_filter == "all" or get_day_type(s["shift_date"]) == dt_filter))
                adult_retail_hours = sum(float(s.get("effective_hours") or 0) for s in week_shifts
                                         if not s.get("is_teen") and map_side(s.get("business_side", "")) == "Retail"
                                         and (dt_filter == "all" or get_day_type(s["shift_date"]) == dt_filter))
                teen_cafe_cost = sum(float(s.get("labour_cost") or 0) for s in week_shifts
                                     if s.get("is_teen") and map_side(s.get("business_side", "")) == "Cafe"
                                     and (dt_filter == "all" or get_day_type(s["shift_date"]) == dt_filter))
                teen_cafe_hours = sum(float(s.get("effective_hours") or 0) for s in week_shifts
                                      if s.get("is_teen") and map_side(s.get("business_side", "")) == "Cafe"
                                      and (dt_filter == "all" or get_day_type(s["shift_date"]) == dt_filter))
                teen_retail_cost = sum(float(s.get("labour_cost") or 0) for s in week_shifts
                                       if s.get("is_teen") and map_side(s.get("business_side", "")) == "Retail"
                                       and (dt_filter == "all" or get_day_type(s["shift_date"]) == dt_filter))
                teen_retail_hours = sum(float(s.get("effective_hours") or 0) for s in week_shifts
                                        if s.get("is_teen") and map_side(s.get("business_side", "")) == "Retail"
                                        and (dt_filter == "all" or get_day_type(s["shift_date"]) == dt_filter))

                # Margin: weighted avg from category sales
                relevant_cats = week_cats if side_filter == "All" else [c for c in week_cats if c.get("side") == side_filter]
                if dt_filter != "all":
                    relevant_cats = [c for c in relevant_cats if get_day_type(c["date"]) == dt_filter]
                weighted_margin = None
                if relevant_cats and margins:
                    total_cat_sales = sum(float(c.get("total_net_sales") or 0) for c in relevant_cats)
                    if total_cat_sales > 0:
                        wm = 0
                        for c in relevant_cats:
                            cs = float(c.get("total_net_sales") or 0)
                            m = margins.get(c.get("category"), 0) or 0
                            wm += cs * m
                        weighted_margin = round(wm / total_cat_sales, 2)

                has_labour = bool(week_shifts) and ws.isoformat() >= STORE_OPENING_DATE
                labour_pct = round(total_labour / total_net * 100, 2) if total_net > 0 and has_labour else None
                real_profit_pct = round(weighted_margin - labour_pct, 2) if weighted_margin is not None and labour_pct is not None else None
                real_profit_dollars = round(total_net * real_profit_pct / 100, 2) if real_profit_pct is not None else None

                # Cafe/Retail labour for All side
                all_cafe_shifts = [s for s in week_shifts if map_side(s.get("business_side", "")) == "Cafe"
                                   and (dt_filter == "all" or get_day_type(s["shift_date"]) == dt_filter)]
                all_retail_shifts = [s for s in week_shifts if map_side(s.get("business_side", "")) == "Retail"
                                     and (dt_filter == "all" or get_day_type(s["shift_date"]) == dt_filter)]
                cafe_labour = sum(float(s.get("labour_cost") or 0) for s in all_cafe_shifts)
                retail_labour = sum(float(s.get("labour_cost") or 0) for s in all_retail_shifts)

                # Cafe/Retail sales for side-specific labour %
                cafe_cat_sales = sum(float(c.get("total_net_sales") or 0) for c in week_cats
                                     if c.get("side") == "Cafe" and (dt_filter == "all" or get_day_type(c["date"]) == dt_filter))
                retail_cat_sales = sum(float(c.get("total_net_sales") or 0) for c in week_cats
                                       if c.get("side") == "Retail" and (dt_filter == "all" or get_day_type(c["date"]) == dt_filter))

                rec = {
                    "week_start": ws.isoformat(),
                    "week_label": wl,
                    "side": side_filter,
                    "day_type": dt_filter,
                    "total_net_sales": round(total_net, 2),
                    "total_gross_sales": round(total_net, 2),  # gross ≈ net for weekly summary
                    "total_transactions": total_tx,
                    "total_items": round(total_items, 1),
                    "trading_days": trading_days,
                    "avg_daily_sales": round(total_net / trading_days, 2) if trading_days > 0 else 0,
                    "avg_transaction_value": round(total_net / total_tx, 2) if total_tx > 0 else 0,
                    "avg_daily_transactions": round(total_tx / trading_days, 2) if trading_days > 0 else 0,
                    "member_transactions": member_tx if side_filter == "All" else 0,
                    "member_net_sales": round(member_sales, 2) if side_filter == "All" else 0,
                    "non_member_transactions": nonmember_tx if side_filter == "All" else 0,
                    "non_member_net_sales": round(nonmember_sales, 2) if side_filter == "All" else 0,
                    "member_sales_ratio": round(member_sales / total_net, 4) if total_net > 0 and side_filter == "All" else 0,
                    "member_tx_ratio": round(member_tx / total_tx, 4) if total_tx > 0 and side_filter == "All" else 0,
                    "unique_customers": unique_cust if side_filter == "All" else 0,
                    "total_labour_cost": round(total_labour, 2) if has_labour else None,
                    "labour_pct": labour_pct,
                    "cafe_labour_cost": round(cafe_labour, 2) if has_labour and side_filter == "All" else None,
                    "retail_labour_cost": round(retail_labour, 2) if has_labour and side_filter == "All" else None,
                    "cafe_labour_pct": round(cafe_labour / cafe_cat_sales * 100, 2) if cafe_cat_sales > 0 and has_labour and side_filter == "All" else None,
                    "retail_labour_pct": round(retail_labour / retail_cat_sales * 100, 2) if retail_cat_sales > 0 and has_labour and side_filter == "All" else None,
                    "adult_cafe_cost": round(adult_cafe_cost, 2) if has_labour else None,
                    "adult_cafe_hours": round(adult_cafe_hours, 2) if has_labour else None,
                    "adult_retail_cost": round(adult_retail_cost, 2) if has_labour else None,
                    "adult_retail_hours": round(adult_retail_hours, 2) if has_labour else None,
                    "teen_cafe_cost": round(teen_cafe_cost, 2) if has_labour else None,
                    "teen_cafe_hours": round(teen_cafe_hours, 2) if has_labour else None,
                    "teen_retail_cost": round(teen_retail_cost, 2) if has_labour else None,
                    "teen_retail_hours": round(teen_retail_hours, 2) if has_labour else None,
                    "weighted_margin_pct": weighted_margin,
                    "real_profit_pct": real_profit_pct,
                    "real_profit_dollars": real_profit_dollars,
                    "unique_staff": len(unique_staff_ids) if has_labour else None,
                    "total_hours": round(total_hours, 2) if has_labour else None,
                    "revenue_per_hour": round(total_net / total_hours, 2) if total_hours > 0 and has_labour else None,
                }
                records.append(rec)

    print(f"    → {len(records)} weekly_store_stats rows")
    return records


# ── Table 2: weekly_category_stats ────────────────────────────────────

def build_weekly_category_stats(cat_stats, margins):
    print("  Building weekly_category_stats...")
    records = []
    # Group by (week, category, day_type)
    agg = defaultdict(lambda: {"net": 0, "gross": 0, "qty": 0, "txns": 0, "side": "Retail"})
    week_totals = defaultdict(float)  # (week, day_type) → total sales

    for c in cat_stats:
        ws = get_week_start(c["date"])
        dt = get_day_type(c["date"])
        cat = c.get("category", "(Uncategorized)")
        for dt_val in ["all", dt]:
            key = (ws, cat, dt_val)
            a = agg[key]
            a["net"] += float(c.get("total_net_sales") or 0)
            a["gross"] += float(c.get("total_gross_sales") or 0)
            a["qty"] += float(c.get("total_qty") or 0)
            a["txns"] += int(c.get("transaction_count") or 0)
            a["side"] = c.get("side", "Retail")
            week_totals[(ws, dt_val)] += float(c.get("total_net_sales") or 0)

    # Previous week for WoW
    prev_week_sales = {}
    for (ws, cat, dt), a in agg.items():
        prev_ws = ws - timedelta(days=7)
        prev_key = (prev_ws, cat, dt)
        if prev_key in agg:
            prev_week_sales[(ws, cat, dt)] = agg[prev_key]["net"]

    for (ws, cat, dt), a in sorted(agg.items()):
        total_sales = week_totals.get((ws, dt), 0)
        side_total = sum(v["net"] for (w, c, d), v in agg.items()
                         if w == ws and d == dt and v["side"] == a["side"])
        margin = margins.get(cat)
        prev_sales = prev_week_sales.get((ws, cat, dt))
        wow = round((a["net"] - prev_sales) / prev_sales * 100, 2) if prev_sales and prev_sales > 0 else None

        records.append({
            "week_start": ws.isoformat(),
            "week_label": week_label(ws),
            "category": cat,
            "side": a["side"],
            "day_type": dt,
            "total_net_sales": round(a["net"], 2),
            "total_gross_sales": round(a["gross"], 2),
            "total_qty": round(a["qty"], 2),
            "transaction_count": a["txns"],
            "pct_of_total_sales": round(a["net"] / total_sales * 100, 2) if total_sales > 0 else 0,
            "pct_of_side_sales": round(a["net"] / side_total * 100, 2) if side_total > 0 else 0,
            "category_margin_pct": margin,
            "estimated_gross_profit": round(a["net"] * margin / 100, 2) if margin else None,
            "wow_sales_change_pct": wow,
        })

    # Compute rank_by_sales per (week, day_type)
    from itertools import groupby
    records.sort(key=lambda r: (r["week_start"], r["day_type"], -r["total_net_sales"]))
    for _, group in groupby(records, key=lambda r: (r["week_start"], r["day_type"])):
        for rank, rec in enumerate(group, 1):
            rec["rank_by_sales"] = rank

    print(f"    → {len(records)} weekly_category_stats rows")
    return records


# ── Table 3: weekly_member_stats ──────────────────────────────────────

def build_weekly_member_stats(dss_rows, transactions, loyalty_events):
    print("  Building weekly_member_stats...")
    # Group daily_store_stats by week for member/non-member splits
    by_week = defaultdict(list)
    for r in dss_rows:
        ws = get_week_start(r["date"])
        by_week[ws].append(r)

    # Group transactions by week for unique member counting
    tx_by_week = defaultdict(list)
    for t in transactions:
        if t.get("date"):
            ws = get_week_start(t["date"])
            tx_by_week[ws].append(t)

    # Group loyalty events by week
    loy_by_week = defaultdict(list)
    for le in loyalty_events:
        ca = le.get("created_at", "")
        if ca:
            d = ca[:10]  # YYYY-MM-DD
            ws = get_week_start(d)
            loy_by_week[ws].append(le)

    records = []
    for ws in sorted(by_week.keys()):
        wl = week_label(ws)
        days = by_week[ws]
        week_txns = tx_by_week.get(ws, [])
        week_loy = loy_by_week.get(ws, [])

        for dt_filter in ["all", "weekday", "weekend"]:
            filtered_days = days if dt_filter == "all" else [d for d in days if get_day_type(d["date"]) == dt_filter]
            filtered_txns = week_txns if dt_filter == "all" else [t for t in week_txns if get_day_type(t["date"]) == dt_filter]
            if not filtered_days:
                continue

            total_net = sum(float(d.get("total_net_sales") or 0) for d in filtered_days)
            total_tx = sum(int(d.get("total_transactions") or 0) for d in filtered_days)
            member_tx = sum(int(d.get("member_transactions") or 0) for d in filtered_days)
            member_sales = sum(float(d.get("member_net_sales") or 0) for d in filtered_days)

            # Unique members this week
            member_ids = set(t.get("customer_id") for t in filtered_txns if t.get("customer_id"))
            unique_members = len(member_ids)

            # Loyalty events
            pts_earned = sum(int(le.get("points") or 0) for le in week_loy if le.get("event_type") == "ACCUMULATE_POINTS")
            pts_redeemed = sum(abs(int(le.get("points") or 0)) for le in week_loy if le.get("event_type") == "REDEEM_REWARD")
            rewards_created = sum(1 for le in week_loy if le.get("event_type") == "CREATE_REWARD")

            for ct_filter in ["all", "member", "non_member"]:
                if ct_filter == "member":
                    ct_tx = member_tx
                    ct_sales = member_sales
                    ct_customers = unique_members
                elif ct_filter == "non_member":
                    ct_tx = total_tx - member_tx
                    ct_sales = total_net - member_sales
                    ct_customers = 0  # Can't count non-member unique
                else:
                    ct_tx = total_tx
                    ct_sales = total_net
                    ct_customers = unique_members

                rec = {
                    "week_start": ws.isoformat(),
                    "week_label": wl,
                    "customer_type": ct_filter,
                    "age_group": "all",
                    "day_type": dt_filter,
                    "unique_customers": ct_customers,
                    "total_visits": ct_tx,
                    "total_transactions": ct_tx,
                    "total_net_sales": round(ct_sales, 2),
                    "avg_spend_per_visit": round(ct_sales / ct_tx, 2) if ct_tx > 0 else 0,
                    "avg_visits_per_customer": round(ct_tx / ct_customers, 2) if ct_customers > 0 else 0,
                    "member_revenue_share": round(member_sales / total_net * 100, 2) if total_net > 0 and ct_filter == "all" else None,
                    "member_tx_share": round(member_tx / total_tx * 100, 2) if total_tx > 0 and ct_filter == "all" else None,
                    "total_points_earned": pts_earned if ct_filter in ("all", "member") else None,
                    "total_points_redeemed": pts_redeemed if ct_filter in ("all", "member") else None,
                    "rewards_created": rewards_created if ct_filter in ("all", "member") else None,
                    "redemption_rate_pct": round(pts_redeemed / pts_earned * 100, 2) if pts_earned > 0 and ct_filter in ("all", "member") else None,
                }
                records.append(rec)

    print(f"    → {len(records)} weekly_member_stats rows")
    return records


# ── Table 4: weekly_staff_stats ───────────────────────────────────────

def build_weekly_staff_stats(shifts):
    print("  Building weekly_staff_stats...")
    records = []

    def map_side(bs):
        return "Cafe" if bs in ("Bar", "Overhead") else "Retail"

    by_week = defaultdict(list)
    for s in shifts:
        ws = get_week_start(s["shift_date"])
        by_week[ws].append(s)

    for ws in sorted(by_week.keys()):
        wl = week_label(ws)
        week_shifts = by_week[ws]

        for side_filter in ["All", "Cafe", "Retail"]:
            for dt_filter in ["all", "weekday", "weekend"]:
                filtered = week_shifts
                if dt_filter != "all":
                    filtered = [s for s in filtered if get_day_type(s["shift_date"]) == dt_filter]
                if side_filter != "All":
                    filtered = [s for s in filtered if map_side(s.get("business_side", "")) == side_filter]
                if not filtered:
                    continue

                total_cost = sum(float(s.get("labour_cost") or 0) for s in filtered)
                total_hrs = sum(float(s.get("effective_hours") or 0) for s in filtered)
                teen_shifts = [s for s in filtered if s.get("is_teen")]
                adult_shifts = [s for s in filtered if not s.get("is_teen")]

                # Day-type breakdown
                wd = [s for s in filtered if get_day_type(s["shift_date"]) == "weekday"]
                we = [s for s in filtered if get_day_type(s["shift_date"]) == "weekend"]
                # Approximate sat/sun split from weekend
                sat = [s for s in filtered if datetime.strptime(s["shift_date"], "%Y-%m-%d").date().weekday() == 5]
                sun = [s for s in filtered if datetime.strptime(s["shift_date"], "%Y-%m-%d").date().weekday() == 6]

                records.append({
                    "week_start": ws.isoformat(),
                    "week_label": wl,
                    "side": side_filter,
                    "day_type": dt_filter,
                    "total_shifts": len(filtered),
                    "total_hours": round(total_hrs, 2),
                    "total_labour_cost": round(total_cost, 2),
                    "teen_cost": round(sum(float(s.get("labour_cost") or 0) for s in teen_shifts), 2),
                    "teen_hours": round(sum(float(s.get("effective_hours") or 0) for s in teen_shifts), 2),
                    "adult_cost": round(sum(float(s.get("labour_cost") or 0) for s in adult_shifts), 2),
                    "adult_hours": round(sum(float(s.get("effective_hours") or 0) for s in adult_shifts), 2),
                    "weekday_cost": round(sum(float(s.get("labour_cost") or 0) for s in wd), 2),
                    "weekday_hours": round(sum(float(s.get("effective_hours") or 0) for s in wd), 2),
                    "saturday_cost": round(sum(float(s.get("labour_cost") or 0) for s in sat), 2),
                    "saturday_hours": round(sum(float(s.get("effective_hours") or 0) for s in sat), 2),
                    "sunday_cost": round(sum(float(s.get("labour_cost") or 0) for s in sun), 2),
                    "sunday_hours": round(sum(float(s.get("effective_hours") or 0) for s in sun), 2),
                    "unique_staff": len(set(s.get("team_member_id") for s in filtered if s.get("team_member_id"))),
                })

    print(f"    → {len(records)} weekly_staff_stats rows")
    return records


# ── Table 5: weekly_inventory_stats (snapshot-based, latest only) ─────

def build_weekly_inventory_stats(inv_intel, side_map, margins):
    print("  Building weekly_inventory_stats (latest snapshot)...")
    # Group by category
    by_cat = defaultdict(list)
    for item in inv_intel:
        # Try to find category from product name via side_map keys
        pname = item.get("product_name", "")
        cat = None
        for c in side_map:
            if c.lower() in pname.lower():
                cat = c
                break
        if not cat:
            cat = "(Uncategorized)"
        by_cat[cat].append(item)

    # Only produce one snapshot for current week
    ws = get_week_start(date.today())
    wl = week_label(ws)
    records = []

    for cat, items in by_cat.items():
        in_stock = sum(1 for i in items if (float(i.get("current_quantity") or 0)) > 0)
        zero_stock = sum(1 for i in items if (float(i.get("current_quantity") or 0)) <= 0)
        alerts = defaultdict(int)
        for i in items:
            alerts[i.get("reorder_alert", "OK")] += 1

        records.append({
            "week_start": ws.isoformat(),
            "week_label": wl,
            "category": cat,
            "side": side_map.get(cat, "Retail"),
            "total_skus": len(items),
            "in_stock_skus": in_stock,
            "zero_stock_skus": zero_stock,
            "units_sold_7d": round(sum(float(i.get("units_sold_7d") or 0) for i in items), 1),
            "units_sold_30d": round(sum(float(i.get("units_sold_30d") or 0) for i in items), 1),
            "units_sold_90d": round(sum(float(i.get("units_sold_90d") or 0) for i in items), 1),
            "revenue_30d": round(sum(float(i.get("revenue_30d") or 0) for i in items), 2),
            "critical_count": alerts.get("CRITICAL", 0),
            "low_count": alerts.get("LOW", 0),
            "watch_count": alerts.get("WATCH", 0),
            "overstock_count": alerts.get("OVERSTOCK", 0),
            "dead_count": alerts.get("DEAD", 0),
            "category_margin_pct": margins.get(cat),
        })

    print(f"    → {len(records)} weekly_inventory_stats rows")
    return records


# ── Table 6: weekly_hourly_patterns ───────────────────────────────────

def build_weekly_hourly_patterns(transactions):
    print("  Building weekly_hourly_patterns...")
    # Group transactions by (week, hour, day_type)
    # key: (week_start, hour, day_type) → {total_net, total_tx, days: set}
    agg = defaultdict(lambda: {"net": 0, "tx_ids": set(), "days": set()})

    for t in transactions:
        d = t.get("date")
        tm = t.get("time", "")
        if not d or not tm:
            continue
        try:
            hour = int(tm.split(":")[0])
        except (ValueError, IndexError):
            continue

        ws = get_week_start(d)
        dt = get_day_type(d)
        net = float(t.get("net_sales") or 0)
        tid = t.get("transaction_id", "")

        for dt_val in ["all", dt]:
            key = (ws, hour, dt_val)
            a = agg[key]
            a["net"] += net
            if tid:
                a["tx_ids"].add(f"{d}_{tid}")
            a["days"].add(d)

    # Build records
    records = []
    # Compute daily totals per (week, day_type) for pct_of_daily_total
    week_daily_totals = defaultdict(float)
    for (ws, hour, dt), a in agg.items():
        week_daily_totals[(ws, dt)] += a["net"]

    for (ws, hour, dt), a in sorted(agg.items()):
        days_in_sample = len(a["days"])
        total_tx = len(a["tx_ids"])
        total_net = a["net"]
        daily_total = week_daily_totals.get((ws, dt), 0)

        records.append({
            "week_start": ws.isoformat(),
            "week_label": week_label(ws),
            "hour": hour,
            "day_type": dt,
            "avg_transactions": round(total_tx / days_in_sample, 2) if days_in_sample > 0 else 0,
            "avg_net_sales": round(total_net / days_in_sample, 2) if days_in_sample > 0 else 0,
            "total_transactions": total_tx,
            "total_net_sales": round(total_net, 2),
            "days_in_sample": days_in_sample,
            "pct_of_daily_total": round(total_net / daily_total * 100, 2) if daily_total > 0 else 0,
        })

    # Mark peaks per (week, day_type)
    from itertools import groupby
    records.sort(key=lambda r: (r["week_start"], r["day_type"], -r["total_net_sales"]))
    for _, group in groupby(records, key=lambda r: (r["week_start"], r["day_type"])):
        group_list = list(group)
        if group_list:
            max_sales = group_list[0]["total_net_sales"]
            for rec in group_list:
                rec["is_peak"] = rec["total_net_sales"] >= max_sales * 0.8 and rec["total_net_sales"] > 0

    print(f"    → {len(records)} weekly_hourly_patterns rows")
    return records


# ── Table 7: weekly_dow_stats ─────────────────────────────────────────

def build_weekly_dow_stats(dss_rows, cat_stats, shifts, side_map):
    print("  Building weekly_dow_stats...")

    def map_side(bs):
        return "Cafe" if bs in ("Bar", "Overhead") else "Retail"

    # Index by (week, date)
    dss_by_date = {}
    for r in dss_rows:
        dss_by_date[r["date"]] = r

    cat_by_date = defaultdict(list)
    for c in cat_stats:
        cat_by_date[c["date"]].append(c)

    shifts_by_date = defaultdict(list)
    for s in shifts:
        shifts_by_date[s["shift_date"]].append(s)

    # Collect all dates per week
    weeks = defaultdict(list)
    for r in dss_rows:
        ws = get_week_start(r["date"])
        weeks[ws].append(r["date"])

    records = []
    for ws in sorted(weeks.keys()):
        wl = week_label(ws)
        week_dates = weeks[ws]

        # Calculate week total for pct
        week_total_net = sum(float(dss_by_date[d].get("total_net_sales") or 0) for d in week_dates if d in dss_by_date)

        for d in week_dates:
            dss = dss_by_date.get(d)
            if not dss:
                continue
            dt = datetime.strptime(d, "%Y-%m-%d").date()
            dow = get_dow(d)
            day_cats = cat_by_date.get(d, [])
            day_shifts = shifts_by_date.get(d, [])

            for side_filter in ["All", "Cafe", "Retail"]:
                if side_filter == "All":
                    net = float(dss.get("total_net_sales") or 0)
                    gross = net
                    tx = int(dss.get("total_transactions") or 0)
                    items = float(dss.get("total_items") or 0)
                    cust = int(dss.get("total_unique_customers") or 0)
                    m_net = float(dss.get("member_net_sales") or 0)
                    m_tx = int(dss.get("member_transactions") or 0)
                else:
                    side_cats = [c for c in day_cats if c.get("side") == side_filter]
                    net = sum(float(c.get("total_net_sales") or 0) for c in side_cats)
                    gross = sum(float(c.get("total_gross_sales") or 0) for c in side_cats)
                    tx = sum(int(c.get("transaction_count") or 0) for c in side_cats)
                    items = sum(float(c.get("total_qty") or 0) for c in side_cats)
                    cust = 0
                    m_net = 0
                    m_tx = 0

                # Labour
                if side_filter == "All":
                    f_shifts = day_shifts
                else:
                    f_shifts = [s for s in day_shifts if map_side(s.get("business_side", "")) == side_filter]
                labour_cost = sum(float(s.get("labour_cost") or 0) for s in f_shifts) if f_shifts else None
                hours = sum(float(s.get("effective_hours") or 0) for s in f_shifts) if f_shifts else None

                has_labour = bool(day_shifts) and d >= STORE_OPENING_DATE
                records.append({
                    "week_start": ws.isoformat(),
                    "week_label": wl,
                    "dow": dow,
                    "dow_name": DOW_NAMES[dow],
                    "side": side_filter,
                    "total_net_sales": round(net, 2),
                    "total_gross_sales": round(gross, 2),
                    "total_transactions": tx,
                    "total_items": round(items, 1),
                    "avg_transaction_value": round(net / tx, 2) if tx > 0 else 0,
                    "unique_customers": cust,
                    "member_net_sales": round(m_net, 2),
                    "member_transactions": m_tx,
                    "member_sales_ratio": round(m_net / net, 4) if net > 0 else 0,
                    "total_labour_cost": round(labour_cost, 2) if labour_cost and has_labour else None,
                    "labour_pct": round(labour_cost / net * 100, 2) if labour_cost and net > 0 and has_labour else None,
                    "total_hours": round(hours, 2) if hours and has_labour else None,
                    "pct_of_weekly_sales": round(net / week_total_net * 100, 2) if week_total_net > 0 else 0,
                })

    # Rank by sales within (week, side)
    from itertools import groupby
    records.sort(key=lambda r: (r["week_start"], r["side"], -r["total_net_sales"]))
    for _, group in groupby(records, key=lambda r: (r["week_start"], r["side"])):
        for rank, rec in enumerate(group, 1):
            rec["rank_by_sales"] = rank

    print(f"    → {len(records)} weekly_dow_stats rows")
    return records


# ── Main Entry Points ─────────────────────────────────────────────────

def run_weekly_stats_update(weeks_back=None):
    """
    Callable entry point for scheduled_sync.
    If weeks_back is None, does full backfill. Otherwise only last N weeks.
    """
    t0 = time.time()
    result = {"status": "success", "tables": {}}

    start_date = None
    if weeks_back:
        start_date = (date.today() - timedelta(weeks=weeks_back)).isoformat()
        print(f"  Weekly stats: last {weeks_back} weeks (from {start_date})")
    else:
        print("  Weekly stats: full historical backfill")

    try:
        # Load source data
        print("\n  Loading source data...")
        dss = load_daily_store_stats(start_date)
        print(f"    daily_store_stats: {len(dss)} rows")
        cat_stats = load_daily_category_stats(start_date)
        print(f"    daily_category_stats: {len(cat_stats)} rows")
        shifts = load_staff_shifts(start_date)
        print(f"    staff_shifts: {len(shifts)} rows")
        txns = load_transactions_hourly(start_date)
        print(f"    transactions (hourly): {len(txns)} rows")
        loyalty = load_loyalty_events(start_date)
        print(f"    loyalty_events: {len(loyalty)} rows")
        side_map = load_category_mappings()
        print(f"    category_mappings: {len(side_map)} entries")
        margins = load_inventory_margins()
        print(f"    inventory_margins: {len(margins)} entries")
        inv_intel = load_inventory_intelligence()
        print(f"    inventory_intelligence: {len(inv_intel)} items")

        # Build and upsert each table
        print("\n  Building weekly tables...")

        # 1. weekly_store_stats
        wss = build_weekly_store_stats(dss, shifts, cat_stats, margins, side_map)
        if wss:
            n = upsert_batch("weekly_store_stats", wss, "week_start,side,day_type", "wss")
            result["tables"]["weekly_store_stats"] = n

        # 2. weekly_category_stats
        wcs = build_weekly_category_stats(cat_stats, margins)
        if wcs:
            n = upsert_batch("weekly_category_stats", wcs, "week_start,category,day_type", "wcs")
            result["tables"]["weekly_category_stats"] = n

        # 3. weekly_member_stats
        wms = build_weekly_member_stats(dss, txns, loyalty)
        if wms:
            n = upsert_batch("weekly_member_stats", wms, "week_start,customer_type,age_group,day_type", "wms")
            result["tables"]["weekly_member_stats"] = n

        # 4. weekly_staff_stats
        wstaff = build_weekly_staff_stats(shifts)
        if wstaff:
            n = upsert_batch("weekly_staff_stats", wstaff, "week_start,side,day_type", "wstaff")
            result["tables"]["weekly_staff_stats"] = n

        # 5. weekly_inventory_stats
        winv = build_weekly_inventory_stats(inv_intel, side_map, margins)
        if winv:
            n = upsert_batch("weekly_inventory_stats", winv, "week_start,category", "winv")
            result["tables"]["weekly_inventory_stats"] = n

        # 6. weekly_hourly_patterns
        whp = build_weekly_hourly_patterns(txns)
        if whp:
            n = upsert_batch("weekly_hourly_patterns", whp, "week_start,hour,day_type", "whp")
            result["tables"]["weekly_hourly_patterns"] = n

        # 7. weekly_dow_stats
        wdow = build_weekly_dow_stats(dss, cat_stats, shifts, side_map)
        if wdow:
            n = upsert_batch("weekly_dow_stats", wdow, "week_start,dow,side", "wdow")
            result["tables"]["weekly_dow_stats"] = n

        elapsed = time.time() - t0
        total_rows = sum(result["tables"].values())
        print(f"\n  ✅ Weekly stats complete: {total_rows} total rows in {elapsed:.1f}s")
        result["total_rows"] = total_rows

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print(f"  ❌ Weekly stats failed: {e}")
        import traceback
        traceback.print_exc()

    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Backfill weekly knowledge-base tables")
    parser.add_argument("--weeks", type=int, default=None, help="Only backfill last N weeks (default: all)")
    args = parser.parse_args()

    print("=" * 60)
    print("WEEKLY KNOWLEDGE BASE — Backfill")
    print("=" * 60)

    result = run_weekly_stats_update(weeks_back=args.weeks)

    print(f"\n{'=' * 60}")
    print("RESULTS:")
    for table, count in result.get("tables", {}).items():
        print(f"  {table}: {count} rows")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
