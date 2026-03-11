"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import KpiCard from "@/components/kpi-card";
import PeriodSelector from "@/components/period-selector";
import { MemberMetricChart, type MemberDailyRow } from "@/components/charts/member-metric-chart";
import { SortableTable, type ColumnDef } from "@/components/sortable-table";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import {
    fetchMembers,
    fetchMemberLoyalty,
    fetchLatestMemberStats,
    fetchMemberRevenueSeries,
    fetchMemberHistoricalSeries,
    fetchMemberPeriodKPIs,
    fetchLoyaltyPeriodKPIs,
    fetchMemberSpendingPatterns,
    buildPeriodMembers,
    aggregateLoyaltyInsights,
    type MemberPeriodKPIs,
    type LoyaltyPeriodKPIs,
} from "@/lib/queries/members";

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
    phone: string | null;
    totalSpent: number;
    visits: number;
    avgSpend: number;
    avgSpendCafe: number;
    avgSpendRetail: number;
    last30AvgSpend: number;
    last30CafeAvg: number;
    last30RetailAvg: number;
    last30Visits: number;
    spendDropPct: number;
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

function formatPhone(phone: string | null): string {
    if (!phone) return "—";
    // Normalise: strip leading +61, 61, replace with 0
    let p = phone.replace(/\s/g, "");
    if (p.startsWith("+61")) p = "0" + p.slice(3);
    else if (p.startsWith("61") && p.length > 9) p = "0" + p.slice(2);
    // Format as 0XXX XXX XXX
    if (p.length === 10) return `${p.slice(0, 4)} ${p.slice(4, 7)} ${p.slice(7)}`;
    return p;
}

const MEMBER_COLUMNS: ColumnDef<MemberRow>[] = [
    {
        key: "name",
        label: "Name",
        align: "left",
        sortValue: (r) => r.name.toLowerCase(),
        render: (r) => <span className="font-medium text-foreground">{r.name}</span>,
    },
    {
        key: "phone",
        label: "Phone",
        align: "left",
        sortValue: (r) => r.phone || "",
        render: (r) => <span className="tabular-nums text-text-muted text-xs">{formatPhone(r.phone)}</span>,
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
    // ── Avg Spend group (expandable → Café, Retail) ──
    {
        key: "avgSpend",
        label: "Avg Spend",
        align: "right",
        sortValue: (r) => r.avgSpend,
        render: (r) => <span className="tabular-nums font-medium text-foreground">{formatCurrency(r.avgSpend)}</span>,
        group: "Avg Breakdown",
        groupParent: true,
    },
    {
        key: "avgSpendCafe",
        label: "☕ Café",
        align: "right",
        sortValue: (r) => r.avgSpendCafe,
        render: (r) => <span className="tabular-nums text-olive">{formatCurrency(r.avgSpendCafe)}</span>,
        group: "Avg Breakdown",
    },
    {
        key: "avgSpendRetail",
        label: "🛍 Retail",
        align: "right",
        sortValue: (r) => r.avgSpendRetail,
        render: (r) => <span className="tabular-nums text-[#B07242]">{formatCurrency(r.avgSpendRetail)}</span>,
        group: "Avg Breakdown",
    },
    // ── Last 30d Avg group (expandable → Café 30d, Retail 30d) ──
    {
        key: "last30AvgSpend",
        label: "30d Avg",
        align: "right",
        sortValue: (r) => r.last30AvgSpend,
        render: (r) => {
            if (r.last30Visits === 0) {
                return <span className="text-muted-foreground italic text-xs">No visits</span>;
            }
            return <span className="tabular-nums font-medium text-foreground">{formatCurrency(r.last30AvgSpend)}</span>;
        },
        group: "30d Breakdown",
        groupParent: true,
    },
    {
        key: "last30CafeAvg",
        label: "☕ 30d",
        align: "right",
        sortValue: (r) => r.last30CafeAvg,
        render: (r) => <span className="tabular-nums text-olive">{formatCurrency(r.last30CafeAvg)}</span>,
        group: "30d Breakdown",
    },
    {
        key: "last30RetailAvg",
        label: "🛍 30d",
        align: "right",
        sortValue: (r) => r.last30RetailAvg,
        render: (r) => <span className="tabular-nums text-[#B07242]">{formatCurrency(r.last30RetailAvg)}</span>,
        group: "30d Breakdown",
    },
    {
        key: "last30Visits",
        label: "30d Visits",
        align: "right",
        sortValue: (r) => r.last30Visits,
        render: (r) => <span className="tabular-nums text-text-body">{r.last30Visits}</span>,
        group: "30d Breakdown",
    },
    // ── Spending trend alert ──
    {
        key: "spendDropPct",
        label: "Trend",
        align: "center",
        sortValue: (r) => r.spendDropPct,
        render: (r) => {
            const drop = r.spendDropPct;
            if (r.last30Visits === 0) {
                return (
                    <span className="inline-flex items-center gap-0.5 text-xs font-semibold px-2 py-0.5 rounded-full bg-red-50 text-red-600">
                        Inactive
                    </span>
                );
            }
            if (drop >= 50) {
                return (
                    <span className="inline-flex items-center gap-0.5 text-xs font-semibold px-2 py-0.5 rounded-full bg-red-50 text-red-600 animate-pulse">
                        {drop.toFixed(0)}%
                    </span>
                );
            }
            if (drop >= 25) {
                return (
                    <span className="inline-flex items-center gap-0.5 text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700">
                        {drop.toFixed(0)}%
                    </span>
                );
            }
            if (drop < 0) {
                return (
                    <span className="inline-flex items-center gap-0.5 text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700">
                        +{Math.abs(drop).toFixed(0)}%
                    </span>
                );
            }
            return (
                <span className="text-xs text-muted-foreground">
                    —
                </span>
            );
        },
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
        render: (r) => (
            <span className={r.daysSinceLastVisit >= 999 ? "text-text-muted italic" : r.daysSinceLastVisit > 90 ? "text-coral-dark" : "text-text-body"}>
                {r.daysSinceLastVisit >= 999 ? "Never" : `${r.daysSinceLastVisit}d ago`}
            </span>
        ),
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
    const [period, setPeriod] = useState<PeriodType>("this_month");
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
    // Filters
    const [hideUnknown, setHideUnknown] = useState(true);
    const [activityFilter, setActivityFilter] = useState<"all" | "no_1m" | "no_3m">("all");
    // Chart data
    const [dailyMemberData, setDailyMemberData] = useState<MemberDailyRow[]>([]);
    const [compDailyMemberData, setCompDailyMemberData] = useState<MemberDailyRow[]>([]);
    const [historicalMemberData, setHistoricalMemberData] = useState<MemberDailyRow[]>([]);

    const loadData = useCallback(async () => {
        setLoading(true);
        try {
            const range = resolvePeriodRange(period, customStart, customEnd);
            const compRange = resolveComparisonRange(range, comparison, period);

            // 6-month lookback for moving averages
            const histStart = new Date(range.startDate);
            histStart.setMonth(histStart.getMonth() - 6);
            const historicalStartDate = histStart.toISOString().slice(0, 10);

            const [
                members,
                loyalty,
                stats,
                periodKpis,
                compPeriodKpis,
                loyaltyPeriod,
                compLoyaltyPeriod,
                series,
                compSeries,
                historicalSeries,
                spendingPatterns,
            ] = await Promise.all([
                fetchMembers(),
                fetchMemberLoyalty(),
                fetchLatestMemberStats(),
                fetchMemberPeriodKPIs(range.startDate, range.endDate),
                fetchMemberPeriodKPIs(compRange.startDate, compRange.endDate),
                fetchLoyaltyPeriodKPIs(range.startDate, range.endDate),
                fetchLoyaltyPeriodKPIs(compRange.startDate, compRange.endDate),
                fetchMemberRevenueSeries(range.startDate, range.endDate),
                fetchMemberRevenueSeries(compRange.startDate, compRange.endDate),
                fetchMemberHistoricalSeries(historicalStartDate, range.endDate),
                fetchMemberSpendingPatterns(),
            ]);

            // Derive all-time per-member stats from latestMemberStats
            // (already has total_spent, total_visits pre-aggregated — no extra query needed)
            const allTimeStats = stats.map(s => ({
                customer_id: s.square_customer_id,
                total_spent: s.total_spent || 0,
                visits: s.total_visits || 0,
                avg_spend: s.total_visits > 0 ? (s.total_spent || 0) / s.total_visits : 0,
            }));

            // Derive transacting member IDs from stats (any member in member_daily_stats has transacted)
            const txMemberIds = new Set(stats.map(s => s.square_customer_id));

            // Filter out members who never purchased (374 loyalty-only / phone-only)
            const activeMembers = members.filter(m => txMemberIds.has(m.square_customer_id));
            const activeLoyalty = loyalty.filter(l => txMemberIds.has(l.customer_id));

            // Period-aware KPIs
            setKpis(periodKpis);
            setCompKpis(compPeriodKpis);

            // Loyalty — period-aware + snapshot (only active members)
            setLoyaltyKpis(loyaltyPeriod);
            setCompLoyaltyKpis(compLoyaltyPeriod);
            const pts = activeLoyalty.reduce((s, l) => s + l.balance, 0);
            setTotalLoyaltyPoints(pts);
            setTotalEnrolled(activeLoyalty.length);
            setLoyaltyInsights(aggregateLoyaltyInsights(activeLoyalty));

            // Members table — ALL-TIME spending + lifetime loyalty (not period-filtered)
            setAllMembers(buildPeriodMembers(activeMembers, allTimeStats, activeLoyalty, stats, spendingPatterns) as MemberRow[]);

            // Build MemberDailyRow from series data (all pre-computed in Supabase)
            const toRow = (s: typeof series[0]): MemberDailyRow => ({
                date: s.date,
                member_net_sales: s.member_net_sales || 0,
                non_member_net_sales: s.non_member_net_sales || 0,
                member_transactions: s.member_transactions || 0,
                non_member_transactions: s.non_member_transactions || 0,
                member_sales_ratio: s.member_sales_ratio || 0,
                member_tx_ratio: s.member_tx_ratio || 0,
                member_unique_customers: s.member_unique_customers || 0,
            });

            setDailyMemberData(series.map(toRow));
            setCompDailyMemberData(compSeries.map(toRow));
            setHistoricalMemberData(historicalSeries.map(toRow));
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
        // eslint-disable-next-line react-hooks/exhaustive-deps
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
            className="space-y-8 relative min-h-[80vh]"
        >
            {loading ? (
                <div className="absolute inset-0 flex items-center justify-center z-40 bg-background">
                    <div className="flex flex-col items-center gap-3 text-muted-foreground">
                        <div className="w-8 h-8 border-2 border-olive/30 border-t-olive rounded-full animate-spin" />
                        <span className="text-sm font-medium">Loading members data...</span>
                    </div>
                </div>
            ) : (
                <>
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
                        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
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

                    {/* Row 3: Loyalty Insights */}
                    {loyaltyInsights && (() => {
                        const total = loyaltyInsights.neverRedeemed + loyaltyInsights.redeemedOnce + loyaltyInsights.redeemed2Plus;
                        const neverPct = total > 0 ? ((loyaltyInsights.neverRedeemed / total) * 100).toFixed(1) : "0";
                        const oncePct = total > 0 ? ((loyaltyInsights.redeemedOnce / total) * 100).toFixed(1) : "0";
                        const twoPlusPct = total > 0 ? ((loyaltyInsights.redeemed2Plus / total) * 100).toFixed(1) : "0";
                        const frequentNonRedeemers = allMembers.filter(
                            (m) => m.visits >= 5 && (m.points as number) > 0 && (m.pointsRedeemed as number) === 0 && m.name !== "Unknown"
                        );
                        return (
                            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                                <div className="bg-card rounded-xl border border-border p-5" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                                    <h4 className="text-sm font-semibold text-foreground mb-3">Points Overview</h4>
                                    <div className="space-y-2 text-sm">
                                        <div className="flex justify-between"><span className="text-text-muted">Total available</span><span className="font-medium tabular-nums">{formatNumber(totalLoyaltyPoints)}</span></div>
                                        <div className="flex justify-between"><span className="text-text-muted">Avg balance / member</span><span className="font-medium tabular-nums">{formatNumber(loyaltyInsights.lifetimeAvg > 0 ? Math.round(totalLoyaltyPoints / totalEnrolled) : 0)}</span></div>
                                        <div className="flex justify-between"><span className="text-text-muted">Avg redeemed / member</span><span className="font-medium tabular-nums">{formatNumber(loyaltyInsights.redeemedAvg)}</span></div>
                                        <div className="flex justify-between"><span className="text-text-muted">Max lifetime</span><span className="font-medium tabular-nums">{formatNumber(loyaltyInsights.lifetimeMax)}</span></div>
                                    </div>
                                </div>
                                <div className="bg-card rounded-xl border border-border p-5" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                                    <h4 className="text-sm font-semibold text-foreground mb-3">Redemption Behaviour</h4>
                                    <p className="text-2xl font-bold text-olive tabular-nums">{formatPercent(loyaltyInsights.redemptionPct)}</p>
                                    <p className="text-xs text-text-muted mb-3">have redeemed at least once</p>
                                    <div className="space-y-1.5 text-sm">
                                        <div className="flex justify-between items-center">
                                            <span className="text-text-muted">Never redeemed</span>
                                            <span className="font-medium tabular-nums">{formatNumber(loyaltyInsights.neverRedeemed)} <span className="text-text-muted text-xs">({neverPct}%)</span></span>
                                        </div>
                                        <div className="flex justify-between items-center">
                                            <span className="text-text-muted">Redeemed once</span>
                                            <span className="font-medium tabular-nums">{formatNumber(loyaltyInsights.redeemedOnce)} <span className="text-text-muted text-xs">({oncePct}%)</span></span>
                                        </div>
                                        <div className="flex justify-between items-center">
                                            <span className="text-text-muted">Redeemed 2+ times</span>
                                            <span className="font-medium tabular-nums">{formatNumber(loyaltyInsights.redeemed2Plus)} <span className="text-text-muted text-xs">({twoPlusPct}%)</span></span>
                                        </div>
                                    </div>
                                </div>
                                <div className="bg-card rounded-xl border border-border p-5" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                                    <h4 className="text-sm font-semibold text-foreground mb-3">🎯 Re-engagement Opportunity</h4>
                                    <p className="text-2xl font-bold text-coral-dark tabular-nums">{frequentNonRedeemers.length}</p>
                                    <p className="text-xs text-text-muted mb-3">frequent visitors (5+ visits) who never redeemed</p>
                                    <div className="space-y-1 text-xs max-h-[100px] overflow-y-auto">
                                        {frequentNonRedeemers.slice(0, 8).map((m, i) => (
                                            <div key={i} className="flex justify-between items-center py-0.5">
                                                <span className="text-text-body truncate mr-2">{m.name}</span>
                                                <span className="font-medium tabular-nums text-olive whitespace-nowrap">{formatNumber(m.points as number)} pts</span>
                                            </div>
                                        ))}
                                        {frequentNonRedeemers.length > 8 && (
                                            <p className="text-text-muted italic pt-1">+ {frequentNonRedeemers.length - 8} more</p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        );
                    })()}

                    {/* Member Metric Time-Series Chart */}
                    <section>
                        <MemberMetricChart
                            data={dailyMemberData}
                            compData={compDailyMemberData}
                            historicalData={historicalMemberData}
                        />
                    </section>

                    {/* Filter Toggles */}
                    <section className="flex flex-wrap items-center gap-3">
                        <button
                            onClick={() => setHideUnknown(!hideUnknown)}
                            className={`text-xs font-semibold px-3 py-1.5 rounded-full border transition-all ${hideUnknown
                                ? "bg-olive/10 text-olive border-olive/30"
                                : "bg-card text-text-muted border-border hover:border-olive/30"
                                }`}
                        >
                            {hideUnknown ? "✓ Hiding unnamed" : "Show all members"}
                        </button>
                        <div className="h-4 w-px bg-border" />
                        <span className="text-xs text-text-muted font-medium">Activity:</span>
                        {[
                            { key: "all" as const, label: "All", tip: "Show all members" },
                            { key: "no_1m" as const, label: "No visit 1 month", tip: "Last visited 30–89 days ago" },
                            { key: "no_3m" as const, label: "No visit 3 months", tip: "Last visited 90+ days ago" },
                        ].map((opt) => (
                            <Tooltip key={opt.key}>
                                <TooltipTrigger asChild>
                                    <button
                                        onClick={() => setActivityFilter(opt.key)}
                                        className={`text-xs font-semibold px-3 py-1.5 rounded-full border transition-all cursor-pointer ${activityFilter === opt.key
                                            ? opt.key === "no_3m" ? "bg-red-500/10 text-red-600 border-red-500/30"
                                                : opt.key === "no_1m" ? "bg-orange-500/10 text-orange-600 border-orange-500/30"
                                                    : "bg-olive/10 text-olive border-olive/30"
                                            : "bg-card text-text-muted border-border hover:border-olive/30"
                                            }`}
                                    >
                                        {opt.label}
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent side="bottom" sideOffset={6}>
                                    {opt.tip}
                                </TooltipContent>
                            </Tooltip>
                        ))}
                    </section>

                    {/* Sortable Members List */}
                    <section>
                        <SortableTable<MemberRow>
                            title="Members List"
                            columns={MEMBER_COLUMNS}
                            data={allMembers.filter((m) => {
                                // Hide unnamed members if toggled
                                if (hideUnknown && m.name === "Unknown") return false;
                                // Exclusive activity filters:
                                // "no_1m" = 30–89 days (visited within 3mo but not within 1mo)
                                // "no_3m" = 90+ days (haven't been back in 3+ months)
                                if (activityFilter === "no_1m" && (m.daysSinceLastVisit < 30 || m.daysSinceLastVisit >= 90)) return false;
                                if (activityFilter === "no_3m" && m.daysSinceLastVisit < 90) return false;
                                return true;
                            })}
                            defaultSortKey="totalSpent"
                            defaultSortDir="desc"
                            searchKeys={["name", "phone"]}
                            searchPlaceholder="Search by name or phone…"
                        />
                    </section>

                </>
            )}
        </motion.div>
    );
}
