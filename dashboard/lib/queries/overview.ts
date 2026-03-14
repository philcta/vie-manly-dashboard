/**
 * Overview page data queries.
 * Fetches from: daily_store_stats, transactions, daily_item_summary, staff_shifts
 *
 * Formulas Reference (docs/formulas_reference.md):
 * - Net Sales: SUM(net_sales) from transactions for [period]
 * - Transactions: COUNT(DISTINCT transaction_id)
 * - Gross Sales: SUM(gross_sales)
 * - Average Sale: Net Sales / Transactions
 * - Labour Cost: SUM(labour_cost) from staff_shifts
 * - Labour Cost vs Sales Profit %: Labour Cost / Net Sales × 100
 * - Hourly bars: SUM(net_sales) grouped by HOUR(datetime)
 */
import { supabase } from "@/lib/supabase";
import { classifySide } from "@/lib/category-rules";

export interface DailyStats {
    date: string;
    total_transactions: number;
    total_net_sales: number;
    total_gross_sales: number;
    total_items: number;
    total_unique_customers: number;
    member_transactions: number;
    member_net_sales: number;
    non_member_transactions: number;
    non_member_net_sales: number;
    member_tx_ratio: number;
    member_sales_ratio: number;
    is_closed: boolean;
}

export interface HourlyData {
    hour: number;
    net_sales: number;
    transactions: number;
}

export interface CategoryDailyData {
    date: string;
    category: string;
    total_net_sales: number;
    total_gross_sales: number;
    total_qty: number;
    transaction_count: number;
}

/** Fetch daily store stats for a date range.
 *  Excludes days flagged as is_closed (public holidays, etc.) */
export async function fetchDailyStats(
    startDate: string,
    endDate: string
): Promise<DailyStats[]> {
    const { data, error } = await supabase
        .from("daily_store_stats")
        .select("*")
        .gte("date", startDate)
        .lte("date", endDate)
        .eq("is_closed", false)
        .order("date", { ascending: true });

    if (error) throw error;
    return data || [];
}

/** Fetch a single day's aggregated stats */
export async function fetchDayStats(date: string): Promise<DailyStats | null> {
    const { data, error } = await supabase
        .from("daily_store_stats")
        .select("*")
        .eq("date", date)
        .single();

    if (error && error.code !== "PGRST116") throw error;
    return data;
}

/**
 * Fetch hourly breakdown from transactions for a specific date.
 * Groups by hour of datetime.
 */
export async function fetchHourlyData(date: string): Promise<HourlyData[]> {
    // Query transactions using the date text field (avoids full table scan)
    // Use 'time' column (TEXT, Sydney local time) instead of 'datetime'
    // because datetime stores Sydney time with +00 offset, causing
    // double-conversion when parsed by JS Date().
    const { data: txns, error: txErr } = await supabase
        .from("transactions")
        .select("time, net_sales, gross_sales, transaction_id")
        .eq("date", date)
        .limit(5000);

    if (txErr) {
        console.error("Hourly data query failed:", txErr);
        return [];
    }

    const hourMap = new Map<number, { net_sales: number; gross_sales: number; txIds: Set<string> }>();
    for (const t of txns || []) {
        if (!t.time) continue;
        // time is "HH:MM:SS" in Sydney local time
        const hour = parseInt(t.time.split(":")[0], 10);
        if (isNaN(hour)) continue;
        if (!hourMap.has(hour)) {
            hourMap.set(hour, { net_sales: 0, gross_sales: 0, txIds: new Set() });
        }
        const entry = hourMap.get(hour)!;
        entry.net_sales += t.net_sales || 0;
        entry.gross_sales += t.gross_sales || 0;
        if (t.transaction_id) entry.txIds.add(t.transaction_id);
    }

    return Array.from(hourMap.entries())
        .map(([hour, val]) => ({
            hour,
            net_sales: Math.round(val.net_sales * 100) / 100,
            transactions: val.txIds.size,
        }))
        .sort((a, b) => a.hour - b.hour);
}

/** Fetch daily category totals for Cafe vs Retail charts.
 *  Uses an RPC that pre-aggregates by date+category in SQL,
 *  avoiding Supabase's default 1000-row limit on long date ranges. */
export async function fetchCategoryDaily(
    startDate: string,
    endDate: string
): Promise<CategoryDailyData[]> {
    const { data, error } = await supabase
        .rpc("get_category_daily", {
            start_date: startDate,
            end_date: endDate,
        })
        .limit(100000);

    if (error) throw error;
    return (data || []) as CategoryDailyData[];
}

/** Fetch per-category (granular) daily stats for category filter on charts.
 *  Returns individual categories (e.g. "Cafe Drinks", "Bread & Bakery") not sides.
 *  Uses v2 RPC returning JSON to bypass PostgREST's 1000-row limit. */
export async function fetchCategoryDetailDaily(
    startDate: string,
    endDate: string
): Promise<CategoryDailyData[]> {
    const { data, error } = await supabase
        .rpc("get_category_detail_daily_v2", {
            start_date: startDate,
            end_date: endDate,
        });

    if (error) throw error;
    return (data as unknown as CategoryDailyData[]) || [];
}

/** Fetch total labour cost for a date range from staff_shifts */
export async function fetchLabourCost(
    startDate: string,
    endDate: string
): Promise<number> {
    const { data, error } = await supabase
        .from("staff_shifts")
        .select("labour_cost")
        .gte("shift_date", startDate)
        .lte("shift_date", endDate);

    if (error) throw error;
    return (data || []).reduce((sum, s) => sum + (Number(s.labour_cost) || 0), 0);
}

/** Fetch labour cost split by business_side (Cafe vs Retail) */
export async function fetchLabourCostBySide(
    startDate: string,
    endDate: string
): Promise<{ cafe: number; retail: number }> {
    const { data, error } = await supabase
        .from("staff_shifts")
        .select("labour_cost, business_side")
        .gte("shift_date", startDate)
        .lte("shift_date", endDate);

    if (error) throw error;
    let cafe = 0;
    let retail = 0;
    for (const s of data || []) {
        const cost = Number(s.labour_cost) || 0;
        // business_side values: "Bar" (cafe), "Retail", "Overhead" (treated as cafe)
        if (s.business_side === "Retail") retail += cost;
        else cafe += cost; // "Bar" + "Overhead" = cafe side
    }
    return { cafe, retail };
}

export interface DailyLabour {
    date: string;
    labour_cost: number;
}

/** Fetch daily labour costs for a date range, grouped by day */
export async function fetchDailyLabour(
    startDate: string,
    endDate: string
): Promise<DailyLabour[]> {
    const { data, error } = await supabase
        .from("staff_shifts")
        .select("shift_date, labour_cost")
        .gte("shift_date", startDate)
        .lte("shift_date", endDate);

    if (error) throw error;

    // Group by date
    const map = new Map<string, number>();
    for (const row of data || []) {
        const d = row.shift_date;
        map.set(d, (map.get(d) || 0) + (Number(row.labour_cost) || 0));
    }

    return Array.from(map.entries())
        .map(([date, labour_cost]) => ({ date, labour_cost: Math.round(labour_cost * 100) / 100 }))
        .sort((a, b) => a.date.localeCompare(b.date));
}

export interface CategorySalesTotal {
    category: string;
    net_sales: number;
}

/** Fetch per-category net sales totals from raw transactions.
 *  Returns the original Square category names (e.g. "Tea", "Cafe Drinks")
 *  NOT the pre-classified "Cafe"/"Retail" from the RPC. */
export async function fetchCategorySalesTotals(
    startDate: string,
    endDate: string
): Promise<CategorySalesTotal[]> {
    const { data, error } = await supabase
        .from("transactions")
        .select("category, net_sales")
        .gte("date", startDate)
        .lte("date", endDate);

    if (error) throw error;

    // Aggregate net_sales per category
    const map = new Map<string, number>();
    for (const row of data || []) {
        const cat = row.category || "(Uncategorized)";
        map.set(cat, (map.get(cat) || 0) + (Number(row.net_sales) || 0));
    }

    return Array.from(map.entries())
        .map(([category, net_sales]) => ({ category, net_sales }));
}

/**
 * Aggregate period KPIs from daily_store_stats.
 * Handles single day or range.
 */
export function aggregateStats(rows: DailyStats[]) {
    // Safety: filter out any closed days that weren't caught at query level
    const open = rows.filter(r => !r.is_closed);
    const totalNetSales = open.reduce((s, r) => s + r.total_net_sales, 0);
    const totalGrossSales = open.reduce((s, r) => s + (r.total_gross_sales || 0), 0);
    const totalTransactions = open.reduce((s, r) => s + r.total_transactions, 0);
    const totalItems = open.reduce((s, r) => s + r.total_items, 0);
    const totalCustomers = open.reduce((s, r) => s + (r.total_unique_customers || 0), 0);
    const memberTx = open.reduce((s, r) => s + r.member_transactions, 0);
    const memberSales = open.reduce((s, r) => s + r.member_net_sales, 0);
    const avgSale = totalTransactions > 0 ? totalNetSales / totalTransactions : 0;

    return {
        netSales: totalNetSales,
        grossSales: totalGrossSales,
        transactions: totalTransactions,
        avgSale,
        totalItems,
        totalCustomers,
        memberTx,
        memberSales,
        memberTxRatio: totalTransactions > 0 ? (memberTx / totalTransactions) * 100 : 0,
        memberSalesRatio: totalNetSales > 0 ? (memberSales / totalNetSales) * 100 : 0,
    };
}

/**
 * Aggregate category data for period KPIs.
 * The RPC returns rows pre-classified as "Cafe" or "Retail".
 */
export function aggregateCategoryStats(rows: CategoryDailyData[]) {
    let cafeNetSales = 0;
    let retailNetSales = 0;
    let cafeGrossSales = 0;
    let retailGrossSales = 0;
    let cafeTransactions = 0;
    let retailTransactions = 0;

    for (const r of rows) {
        if (r.category === "Cafe") {
            cafeNetSales += r.total_net_sales;
            cafeGrossSales += r.total_gross_sales;
            cafeTransactions += r.transaction_count;
        } else {
            retailNetSales += r.total_net_sales;
            retailGrossSales += r.total_gross_sales;
            retailTransactions += r.transaction_count;
        }
    }

    return {
        cafeNetSales,
        retailNetSales,
        cafeGrossSales,
        retailGrossSales,
        cafeTransactions,
        retailTransactions,
    };
}

