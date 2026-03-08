"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import KpiCard from "@/components/kpi-card";
import PeriodSelector from "@/components/period-selector";
import { MemberMetricChart, type MemberDailyRow } from "@/components/charts/member-metric-chart";
import { SortableTable, type ColumnDef } from "@/components/sortable-table";
import {
    fetchMembers,
    fetchMemberLoyalty,
    fetchLatestMemberStats,
    fetchMemberRevenueSeries,
    fetchMemberPeriodKPIs,
    fetchLoyaltyPeriodKPIs,
    fetchMemberPeriodTable,
    buildPeriodMembers,
    aggregateLoyaltyInsights,
    type MemberPeriodKPIs,
    type LoyaltyPeriodKPIs,
} from "@/lib/queries/members";
import { fetchDailyStats } from "@/lib/queries/overview";
import {
    type PeriodType,
    type ComparisonType,
    resolvePeriodRange,
    resolveComparisonRange,
} from "@/lib/dates";
import {
    formatCurrency,
    formatPercent,
    formatNumber,
    calcChange,
} from "@/lib/format";

// ── Member row type for sortable table ──────────────────────────

interface MemberRow {
    [key: string]: unknown;
    customerId: string;
    name: string;
    totalSpent: number;
    visits: number;
    avgSpend: number;
    points: number;
    lifetimePoints: number;
    pointsRedeemed: number;
    daysSinceLastVisit: number;
    status: "Active" | "Cooling" | "At Risk" | "Churned";
}

// ── Status badge ────────────────────────────────────────────────

const statusColors: Record<string, string> = {
    Active: "bg-positive text-white",
    Cooling: "bg-warning text-white",
    "At Risk": "bg-coral-light text-coral-dark",
    Churned: "bg-muted text-muted-foreground",
};

function StatusBadge({ status }: { status: string }) {
    return (
        <span className={`inline-block text-xs font-semibold px-2.5 py-0.5 rounded-full ${statusColors[status] || "bg-muted text-muted-foreground"}`}>
            {status}
        </span>
    );
}

// ── Table column definitions ────────────────────────────────────

const MEMBER_COLUMNS: ColumnDef<MemberRow>[] = [
    {
        key: "name",
        label: "Name",
        align: "left",
        sortValue: (r) => r.name.toLowerCase(),
        render: (r) => <span className="font-medium text-foreground">{r.name}</span>,
    },
    {
        key: "totalSpent",
        label: "Total Spent",
        align: "right",
        sortValue: (r) => r.totalSpent,
        render: (r) => <span className="tabular-nums text-foreground">{formatCurrency(r.totalSpent)}</span>,
    },
    {
        key: "visits",
        label: "Visits",
        align: "right",
        sortValue: (r) => r.visits,
        render: (r) => <span className="tabular-nums text-foreground">{formatNumber(r.visits)}</span>,
    },
    {
        key: "avgSpend",
        label: "Avg Spend",
        align: "right",
        sortValue: (r) => r.avgSpend,
        render: (r) => <span className="tabular-nums text-foreground">{formatCurrency(r.avgSpend)}</span>,
    },
    {
        key: "lifetimePoints",
        label: "Total Pts",
        align: "right",
        sortValue: (r) => r.lifetimePoints,
        render: (r) => <span className="tabular-nums text-foreground">{formatNumber(r.lifetimePoints)}</span>,
    },
    {
        key: "pointsRedeemed",
        label: "Redeemed",
        align: "right",
        sortValue: (r) => r.pointsRedeemed,
        render: (r) => <span className="tabular-nums text-foreground">{formatNumber(r.pointsRedeemed)}</span>,
    },
    {
        key: "points",
        label: "Available",
        align: "right",
        sortValue: (r) => r.points,
        render: (r) => <span className="tabular-nums font-medium text-olive">{formatNumber(r.points)}</span>,
    },
    {
        key: "daysSinceLastVisit",
        label: "Last Visit",
        align: "right",
        sortValue: (r) => r.daysSinceLastVisit,
        render: (r) => <span className="text-text-body">{r.daysSinceLastVisit}d ago</span>,
    },
    {
        key: "status",
        label: "Status",
        align: "center",
        sortValue: (r) => {
            const order = { Active: 0, Cooling: 1, "At Risk": 2, Churned: 3 };
            return order[r.status] ?? 4;
        },
        render: (r) => <StatusBadge status={r.status} />,
    },
];

// ── Page component ──────────────────────────────────────────────

export default function MembersPage() {
    const [period, setPeriod] = useState<PeriodType>("this_week");
    const [comparison, setComparison] = useState<ComparisonType>("prior_period");
    const [customStart, setCustomStart] = useState("");
    const [customEnd, setCustomEnd] = useState("");
    const [loading, setLoading] = useState(true);

    // Period-aware KPIs
    const [kpis, setKpis] = useState<MemberPeriodKPIs | null>(null);
    const [compKpis, setCompKpis] = useState<MemberPeriodKPIs | null>(null);
    // Loyalty — period-aware from events + snapshot
    const [loyaltyKpis, setLoyaltyKpis] = useState<LoyaltyPeriodKPIs | null>(null);
    const [compLoyaltyKpis, setCompLoyaltyKpis] = useState<LoyaltyPeriodKPIs | null>(null);
    const [totalLoyaltyPoints, setTotalLoyaltyPoints] = useState(0);
    const [totalEnrolled, setTotalEnrolled] = useState(0);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [loyaltyInsights, setLoyaltyInsights] = useState<any>(null);
    // Members table
    const [allMembers, setAllMembers] = useState<MemberRow[]>([]);
    // Chart data
    const [dailyMemberData, setDailyMemberData] = useState<MemberDailyRow[]>([]);
    const [compDailyMemberData, setCompDailyMemberData] = useState<MemberDailyRow[]>([]);

    const loadData = useCallback(async () => {
        setLoading(true);
        try {
            const range = resolvePeriodRange(period, customStart, customEnd);
            const compRange = resolveComparisonRange(range, comparison, period);

            const [
                members,
                loyalty,
                stats,
                periodKpis,
                compPeriodKpis,
                loyaltyPeriod,
                compLoyaltyPeriod,
                periodTableStats,
                dailyStats,
                compDailyStats,
                series,
                compSeries,
            ] = await Promise.all([
                fetchMembers(),
                fetchMemberLoyalty(),
                fetchLatestMemberStats(),
                fetchMemberPeriodKPIs(range.startDate, range.endDate),
                fetchMemberPeriodKPIs(compRange.startDate, compRange.endDate),
                fetchLoyaltyPeriodKPIs(range.startDate, range.endDate),
                fetchLoyaltyPeriodKPIs(compRange.startDate, compRange.endDate),
                fetchMemberPeriodTable(range.startDate, range.endDate),
                fetchDailyStats(range.startDate, range.endDate),
                fetchDailyStats(compRange.startDate, compRange.endDate),
                fetchMemberRevenueSeries(range.startDate, range.endDate),
                fetchMemberRevenueSeries(compRange.startDate, compRange.endDate),
            ]);

            // Period-aware KPIs
            setKpis(periodKpis);
            setCompKpis(compPeriodKpis);

            // Loyalty — period-aware + snapshot
            setLoyaltyKpis(loyaltyPeriod);
            setCompLoyaltyKpis(compLoyaltyPeriod);
            const pts = loyalty.reduce((s, l) => s + l.balance, 0);
            setTotalLoyaltyPoints(pts);
            setTotalEnrolled(loyalty.length);
            setLoyaltyInsights(aggregateLoyaltyInsights(loyalty));

            // Members table — period-specific spending + lifetime loyalty
            setAllMembers(buildPeriodMembers(members, periodTableStats, loyalty, stats) as MemberRow[]);

            // Daily chart data — merge daily_store_stats with revenue series
            const dsMap = new Map(dailyStats.map((d) => [d.date, d]));
            setDailyMemberData(
                series.map((s) => {
                    const ds = dsMap.get(s.date);
                    return {
                        date: s.date,
                        member_net_sales: s.member_net_sales || 0,
                        non_member_net_sales: s.non_member_net_sales || 0,
                        member_transactions: ds?.member_transactions || 0,
                        non_member_transactions: ds?.non_member_transactions || 0,
                        member_sales_ratio: s.member_sales_ratio || 0,
                        member_tx_ratio: s.member_tx_ratio || 0,
                        member_unique_customers: ds?.total_unique_customers || 0,
                    };
                })
            );

            const compDsMap = new Map(compDailyStats.map((d) => [d.date, d]));
            setCompDailyMemberData(
                compSeries.map((s) => {
                    const ds = compDsMap.get(s.date);
                    return {
                        date: s.date,
                        member_net_sales: s.member_net_sales || 0,
                        non_member_net_sales: s.non_member_net_sales || 0,
                        member_transactions: ds?.member_transactions || 0,
                        non_member_transactions: ds?.non_member_transactions || 0,
                        member_sales_ratio: s.member_sales_ratio || 0,
                        member_tx_ratio: s.member_tx_ratio || 0,
                        member_unique_customers: ds?.total_unique_customers || 0,
                    };
                })
            );
        } catch (err: unknown) {
            const msg = err instanceof Error
                ? err.message
                : typeof err === 'object' && err !== null
                    ? JSON.stringify(err)
                    : String(err);
            console.error("Failed to load members data:", msg, err);
        } finally {
            setLoading(false);
        }
    }, [period, comparison, customStart, customEnd]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    // ── Comparison logic — match Overview pattern ──

    // No comparison data if comp period has zero transactions
    const noCompData = !compKpis || compKpis.totalTransactions === 0;

    return (
        <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="space-y-8"
        >
            <div className="flex items-center justify-between">
                <h1 className="text-[28px] font-bold text-foreground">Members</h1>
            </div>

            {/* Period Selector — with comparison enabled */}
            <PeriodSelector
                period={period}
                comparison={comparison}
                customStart={customStart}
                customEnd={customEnd}
                onPeriodChange={setPeriod}
                onComparisonChange={setComparison}
                onCustomRangeChange={(s, e) => {
                    setCustomStart(s);
                    setCustomEnd(e);
                }}
            />

            {/* KPI Cards — period-aware with comparison badges + Staff-style subtitles */}
            {kpis && (
                <div className="grid grid-cols-3 gap-5">
                    <KpiCard
                        label="Active Members"
                        value={kpis.uniqueMembers}
                        formatter={(n) => formatNumber(n)}
                        change={noCompData ? null : calcChange(kpis.uniqueMembers, compKpis!.uniqueMembers)}
                        noCompData={noCompData}
                        subtitle={`Repeat: ${formatNumber(kpis.repeatMembers)} (${kpis.uniqueMembers > 0 ? Math.round(kpis.repeatMembers / kpis.uniqueMembers * 100) : 0}%) · One-off: ${formatNumber(kpis.uniqueMembers - kpis.repeatMembers)} (${kpis.uniqueMembers > 0 ? Math.round((kpis.uniqueMembers - kpis.repeatMembers) / kpis.uniqueMembers * 100) : 0}%)`}
                        delay={0}
                    />
                    <KpiCard
                        label="New Enrolments"
                        value={kpis.newEnrollments}
                        formatter={(n) => formatNumber(n)}
                        change={noCompData ? null : calcChange(kpis.newEnrollments, compKpis!.newEnrollments)}
                        noCompData={noCompData}
                        subtitle={`Total enrolled: ${formatNumber(totalEnrolled)} (${kpis.totalTransactions > 0 ? formatPercent(kpis.uniqueMembers / totalEnrolled * 100) : '0%'} active)`}
                        delay={1}
                    />
                    <KpiCard
                        label="Member Sales"
                        value={kpis.memberNetSales}
                        formatter={(n) => formatCurrency(n)}
                        change={noCompData ? null : calcChange(kpis.memberNetSales, compKpis!.memberNetSales)}
                        noCompData={noCompData}
                        subtitle={`Non-member: ${formatCurrency(kpis.nonMemberNetSales)}`}
                        delay={2}
                    />
                    <KpiCard
                        label="Member Revenue %"
                        value={kpis.memberRevenueShare}
                        formatter={(n) => formatPercent(n)}
                        change={noCompData ? null : calcChange(kpis.memberRevenueShare, compKpis!.memberRevenueShare)}
                        noCompData={noCompData}
                        subtitle={`Tx ratio: ${formatPercent(kpis.memberTxRatio)}`}
                        delay={3}
                    />
                    <KpiCard
                        label="Avg Spend / Visit"
                        value={kpis.avgSpendPerVisit}
                        formatter={(n) => formatCurrency(n)}
                        change={noCompData ? null : calcChange(kpis.avgSpendPerVisit, compKpis!.avgSpendPerVisit)}
                        noCompData={noCompData}
                        subtitle={`Member Tx: ${formatNumber(kpis.memberTransactions)} · Non-m: ${formatNumber(kpis.nonMemberTransactions)}`}
                        delay={4}
                    />
                    <KpiCard
                        label="Points Earned"
                        value={loyaltyKpis?.pointsEarned ?? 0}
                        formatter={(n) => formatNumber(n)}
                        change={
                            noCompData || !compLoyaltyKpis?.pointsEarned
                                ? null
                                : calcChange(loyaltyKpis?.pointsEarned ?? 0, compLoyaltyKpis.pointsEarned)
                        }
                        noCompData={noCompData || !compLoyaltyKpis?.pointsEarned}
                        subtitle={`Redeemed: ${formatNumber(loyaltyKpis?.pointsRedeemed ?? 0)} · Balance: ${formatNumber(totalLoyaltyPoints)}`}
                        delay={5}
                    />
                </div>
            )}

            {/* Member Metric Time-Series Chart */}
            <section>
                <MemberMetricChart
                    data={dailyMemberData}
                    compData={compDailyMemberData}
                />
            </section>

            {/* Sortable Members List */}
            <section>
                <SortableTable<MemberRow>
                    title="Members List"
                    columns={MEMBER_COLUMNS}
                    data={allMembers}
                    defaultSortKey="totalSpent"
                    defaultSortDir="desc"
                />
            </section>

            {/* Loyalty Insights */}
            {loyaltyInsights && (
                <div className="grid grid-cols-3 gap-5">
                    <div className="bg-card rounded-xl border border-border p-5" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                        <h4 className="text-sm font-semibold text-foreground mb-3">Lifetime Points</h4>
                        <div className="space-y-2 text-sm">
                            <div className="flex justify-between"><span className="text-text-muted">Min</span><span className="font-medium tabular-nums">{formatNumber(loyaltyInsights.lifetimeMin)}</span></div>
                            <div className="flex justify-between"><span className="text-text-muted">Max</span><span className="font-medium tabular-nums">{formatNumber(loyaltyInsights.lifetimeMax)}</span></div>
                            <div className="flex justify-between"><span className="text-text-muted">Avg</span><span className="font-medium tabular-nums">{formatNumber(loyaltyInsights.lifetimeAvg)}</span></div>
                        </div>
                    </div>
                    <div className="bg-card rounded-xl border border-border p-5" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                        <h4 className="text-sm font-semibold text-foreground mb-3">Points Redeemed</h4>
                        <div className="space-y-2 text-sm">
                            <div className="flex justify-between"><span className="text-text-muted">Min</span><span className="font-medium tabular-nums">{formatNumber(loyaltyInsights.redeemedMin)}</span></div>
                            <div className="flex justify-between"><span className="text-text-muted">Max</span><span className="font-medium tabular-nums">{formatNumber(loyaltyInsights.redeemedMax)}</span></div>
                            <div className="flex justify-between"><span className="text-text-muted">Avg</span><span className="font-medium tabular-nums">{formatNumber(loyaltyInsights.redeemedAvg)}</span></div>
                        </div>
                    </div>
                    <div className="bg-card rounded-xl border border-border p-5" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                        <h4 className="text-sm font-semibold text-foreground mb-3">Redemption Behaviour</h4>
                        <p className="text-2xl font-bold text-olive tabular-nums">{formatPercent(loyaltyInsights.redemptionPct)}</p>
                        <p className="text-xs text-text-muted mb-3">have redeemed</p>
                        <div className="space-y-1 text-sm">
                            <div className="flex justify-between"><span className="text-text-muted">Never</span><span className="font-medium tabular-nums">{formatNumber(loyaltyInsights.neverRedeemed)}</span></div>
                            <div className="flex justify-between"><span className="text-text-muted">Once</span><span className="font-medium tabular-nums">{formatNumber(loyaltyInsights.redeemedOnce)}</span></div>
                            <div className="flex justify-between"><span className="text-text-muted">2+ times</span><span className="font-medium tabular-nums">{formatNumber(loyaltyInsights.redeemed2Plus)}</span></div>
                        </div>
                    </div>
                </div>
            )}

            {loading && (
                <div className="fixed inset-0 ml-[220px] bg-background/80 flex items-center justify-center z-40">
                    <div className="flex items-center gap-3 text-muted-foreground">
                        <div className="w-5 h-5 border-2 border-olive/30 border-t-olive rounded-full animate-spin" />
                        <span className="text-sm">Loading members data...</span>
                    </div>
                </div>
            )}
        </motion.div>
    );
}
