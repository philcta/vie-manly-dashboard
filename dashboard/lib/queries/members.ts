/**
 * Members page data queries.
 * KPIs are now fully period-aware:
 * - Active Members: COUNT(DISTINCT customer_id) from transactions in period
 * - Member Revenue %: member_sales / total_sales × 100 from daily_store_stats
 * - Avg Spend/Visit: member_sales / member_transactions
 * - Member Transactions: SUM(member_transactions) from daily_store_stats
 * - Loyalty Points: snapshot from member_loyalty (no historical tracking)
 */
import { supabase } from "@/lib/supabase";

export interface MemberPeriodKPIs {
    uniqueMembers: number;
    repeatMembers: number;
    newEnrollments: number;
    memberTransactions: number;
    nonMemberTransactions: number;
    memberNetSales: number;
    nonMemberNetSales: number;
    totalTransactions: number;
    totalNetSales: number;
    memberRevenueShare: number;
    memberTxRatio: number;
    avgSpendPerVisit: number;
}

/** Fetch period-specific member KPIs via RPC for accurate comparisons */
export async function fetchMemberPeriodKPIs(
    startDate: string,
    endDate: string
): Promise<MemberPeriodKPIs> {
    const { data, error } = await supabase.rpc("get_member_period_kpis", {
        start_date: startDate,
        end_date: endDate,
    });

    if (error) throw error;

    const d = data || {};
    const memberSales = Number(d.member_net_sales) || 0;
    const totalSales = Number(d.total_net_sales) || 0;
    const memberTx = Number(d.member_transactions) || 0;
    const totalTx = Number(d.total_transactions) || 0;

    return {
        uniqueMembers: Number(d.unique_members) || 0,
        repeatMembers: Number(d.repeat_members) || 0,
        newEnrollments: Number(d.new_enrollments) || 0,
        memberTransactions: memberTx,
        nonMemberTransactions: Number(d.non_member_transactions) || 0,
        memberNetSales: memberSales,
        nonMemberNetSales: Number(d.non_member_net_sales) || 0,
        totalTransactions: totalTx,
        totalNetSales: totalSales,
        memberRevenueShare: totalSales > 0 ? (memberSales / totalSales) * 100 : 0,
        memberTxRatio: totalTx > 0 ? (memberTx / totalTx) * 100 : 0,
        avgSpendPerVisit: memberTx > 0 ? memberSales / memberTx : 0,
    };
}

export interface LoyaltyPeriodKPIs {
    pointsEarned: number;
    pointsRedeemed: number;
    pointsAdjusted: number;
    earnEvents: number;
    redeemEvents: number;
    netPoints: number;
}

/** Fetch period-specific loyalty KPIs from the loyalty_events ledger */
export async function fetchLoyaltyPeriodKPIs(
    startDate: string,
    endDate: string
): Promise<LoyaltyPeriodKPIs> {
    const { data, error } = await supabase.rpc("get_loyalty_period_kpis", {
        start_date: startDate,
        end_date: endDate,
    });

    if (error) throw error;

    const d = data || {};
    const earned = Number(d.points_earned) || 0;
    const redeemed = Number(d.points_redeemed) || 0; // stored positive (CREATE_REWARD)
    const adjusted = Number(d.points_adjusted) || 0;

    return {
        pointsEarned: earned,
        pointsRedeemed: redeemed,
        pointsAdjusted: adjusted,
        earnEvents: Number(d.earn_events) || 0,
        redeemEvents: Number(d.redeem_events) || 0,
        netPoints: earned - redeemed + adjusted,
    };
}

/** Per-member spending aggregated within a date range */
export interface MemberPeriodRow {
    customer_id: string;
    total_spent: number;
    visits: number;
    avg_spend: number;
}

/** Fetch period-specific per-member spending from transactions via RPC */
export async function fetchMemberPeriodTable(
    startDate: string,
    endDate: string
): Promise<MemberPeriodRow[]> {
    const { data, error } = await supabase.rpc("get_member_period_table", {
        start_date: startDate,
        end_date: endDate,
    });

    if (error) throw error;

    return (data || []).map((r: Record<string, unknown>) => ({
        customer_id: String(r.customer_id || ""),
        total_spent: Number(r.total_spent) || 0,
        visits: Number(r.visits) || 0,
        avg_spend: Number(r.avg_spend) || 0,
    }));
}

/** Build members table with period-specific spending + lifetime loyalty */
export function buildPeriodMembers(
    members: Member[],
    periodStats: MemberPeriodRow[],
    loyalty: MemberLoyalty[],
    latestStats: MemberDailyStats[],
) {
    const memberMap = new Map(members.map((m) => [m.square_customer_id, m]));
    const loyaltyMap = new Map(loyalty.map((l) => [l.customer_id, l]));

    // Build latest-stats map for days_since_last_visit
    const latestByMember = new Map<string, MemberDailyStats>();
    for (const s of latestStats) {
        const existing = latestByMember.get(s.square_customer_id);
        if (!existing || s.date > existing.date) {
            latestByMember.set(s.square_customer_id, s);
        }
    }

    return periodStats
        .sort((a, b) => b.total_spent - a.total_spent)
        .map((s) => {
            const member = memberMap.get(s.customer_id);
            const loy = loyaltyMap.get(s.customer_id);
            const latest = latestByMember.get(s.customer_id);
            const daysSince = latest?.days_since_last_visit ?? 999;

            let status: "Active" | "Cooling" | "At Risk" | "Churned" = "Active";
            if (daysSince > 45) status = "Churned";
            else if (daysSince > 30) status = "At Risk";
            else if (daysSince > 14) status = "Cooling";

            return {
                customerId: s.customer_id,
                name: member
                    ? `${member.first_name || ""} ${member.last_name || ""}`.trim() || "Unknown"
                    : "Unknown",
                totalSpent: s.total_spent,
                visits: s.visits,
                avgSpend: s.avg_spend,
                points: loy?.balance ?? 0,
                lifetimePoints: loy?.lifetime_points ?? 0,
                pointsRedeemed: loy?.points_redeemed ?? 0,
                daysSinceLastVisit: daysSince,
                status,
            };
        });
}

export interface Member {
    id: number;
    square_customer_id: string;
    first_name: string | null;
    last_name: string | null;
    email_address: string | null;
    phone_number: string | null;
    creation_date: string | null;
    birthday: string | null;
}

export interface MemberLoyalty {
    customer_id: string;
    balance: number;
    lifetime_points: number;
    points_redeemed: number | null;
    enrolled_at: string | null;
}

export interface MemberDailyStats {
    square_customer_id: string;
    date: string;
    total_spent: number;
    total_items: number;
    total_visits: number;
    total_transactions: number;
    day_spent: number;
    days_since_last_visit: number;
    visit_frequency_30d: number;
}

/** Fetch all members */
export async function fetchMembers(): Promise<Member[]> {
    const { data, error } = await supabase
        .from("members")
        .select("*")
        .order("first_name", { ascending: true });

    if (error) throw error;
    return data || [];
}

/** Fetch member loyalty data */
export async function fetchMemberLoyalty(): Promise<MemberLoyalty[]> {
    const { data, error } = await supabase
        .from("member_loyalty")
        .select("customer_id, balance, lifetime_points, points_redeemed, enrolled_at");

    if (error) throw error;
    return (data || []).map((l) => ({
        ...l,
        points_redeemed: l.points_redeemed ?? 0,
    }));
}

/** Fetch member daily stats for recent date (latest available) */
export async function fetchLatestMemberStats(): Promise<MemberDailyStats[]> {
    const { data, error } = await supabase
        .from("member_daily_stats")
        .select("*")
        .order("date", { ascending: false })
        .limit(5000);

    if (error) throw error;
    return data || [];
}

/** Fetch daily store stats for member/non-member ratio charts */
export async function fetchMemberRevenueSeries(
    startDate: string,
    endDate: string
) {
    const { data, error } = await supabase
        .from("daily_store_stats")
        .select(
            "date, member_net_sales, non_member_net_sales, member_tx_ratio, member_sales_ratio, member_items_ratio"
        )
        .gte("date", startDate)
        .lte("date", endDate)
        .order("date", { ascending: true });

    if (error) throw error;
    return data || [];
}

/** Aggregate member KPIs */
export function aggregateMemberKPIs(
    stats: MemberDailyStats[],
    loyalty: MemberLoyalty[],
    memberSales: number,
    totalSales: number,
    activeThresholdDays: number = 7
) {
    // Get the latest stats per member (most recent date)
    const latestByMember = new Map<string, MemberDailyStats>();
    for (const s of stats) {
        const existing = latestByMember.get(s.square_customer_id);
        if (!existing || s.date > existing.date) {
            latestByMember.set(s.square_customer_id, s);
        }
    }

    const latestStats = Array.from(latestByMember.values());
    const activeMembers = latestStats.filter(
        (s) => s.days_since_last_visit <= activeThresholdDays
    );

    const totalLifetimeSpent = latestStats.reduce((s, m) => s + m.total_spent, 0);
    const avgLifetimeValue =
        latestStats.length > 0 ? totalLifetimeSpent / latestStats.length : 0;

    const totalPoints = loyalty.reduce((s, l) => s + l.balance, 0);
    const totalEnrolled = loyalty.length;

    const memberRevenueShare =
        totalSales > 0 ? (memberSales / totalSales) * 100 : 0;

    return {
        activeMembers: activeMembers.length,
        totalMembers: latestStats.length,
        memberRevenueShare,
        avgLifetimeValue,
        totalPoints,
        totalEnrolled,
    };
}

/** Build members table data (all members, sorted by total spent) */
export function buildAllMembers(
    members: Member[],
    stats: MemberDailyStats[],
    loyalty: MemberLoyalty[],
) {
    const latestByMember = new Map<string, MemberDailyStats>();
    for (const s of stats) {
        const existing = latestByMember.get(s.square_customer_id);
        if (!existing || s.date > existing.date) {
            latestByMember.set(s.square_customer_id, s);
        }
    }

    const memberMap = new Map(
        members.map((m) => [m.square_customer_id, m])
    );
    const loyaltyMap = new Map(loyalty.map((l) => [l.customer_id, l]));

    return Array.from(latestByMember.values())
        .sort((a, b) => b.total_spent - a.total_spent)
        .map((s) => {
            const member = memberMap.get(s.square_customer_id);
            const loy = loyaltyMap.get(s.square_customer_id);

            let status: "Active" | "Cooling" | "At Risk" | "Churned" = "Active";
            if (s.days_since_last_visit > 45) status = "Churned";
            else if (s.days_since_last_visit > 30) status = "At Risk";
            else if (s.days_since_last_visit > 14) status = "Cooling";

            return {
                customerId: s.square_customer_id,
                name: member
                    ? `${member.first_name || ""} ${member.last_name || ""}`.trim() || "Unknown"
                    : "Unknown",
                totalSpent: s.total_spent,
                visits: s.total_visits,
                avgSpend: s.total_visits > 0 ? s.total_spent / s.total_visits : 0,
                points: loy?.balance ?? 0,
                lifetimePoints: loy?.lifetime_points ?? 0,
                pointsRedeemed: loy?.points_redeemed ?? 0,
                daysSinceLastVisit: s.days_since_last_visit,
                status,
            };
        });
}

/** Aggregate loyalty insights */
export function aggregateLoyaltyInsights(loyalty: MemberLoyalty[]) {
    if (loyalty.length === 0) {
        return {
            lifetimeMin: 0, lifetimeMax: 0, lifetimeAvg: 0,
            redeemedMin: 0, redeemedMax: 0, redeemedAvg: 0,
            redemptionPct: 0, neverRedeemed: 0, redeemedOnce: 0, redeemed2Plus: 0,
        };
    }

    const lifetimes = loyalty.map((l) => l.lifetime_points);
    const redeemed = loyalty.map((l) => l.points_redeemed ?? 0);

    const withRedemptions = loyalty.filter((l) => (l.points_redeemed ?? 0) > 0);

    return {
        lifetimeMin: Math.min(...lifetimes),
        lifetimeMax: Math.max(...lifetimes),
        lifetimeAvg: Math.round(lifetimes.reduce((a, b) => a + b, 0) / lifetimes.length),
        redeemedMin: Math.min(...redeemed),
        redeemedMax: Math.max(...redeemed),
        redeemedAvg: Math.round(redeemed.reduce((a, b) => a + b, 0) / redeemed.length),
        redemptionPct: (withRedemptions.length / loyalty.length) * 100,
        neverRedeemed: loyalty.length - withRedemptions.length,
        redeemedOnce: withRedemptions.filter((l) => (l.points_redeemed ?? 0) <= 200).length,
        redeemed2Plus: withRedemptions.filter((l) => (l.points_redeemed ?? 0) > 200).length,
    };
}
