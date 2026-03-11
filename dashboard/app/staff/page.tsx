"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { motion } from "framer-motion";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";
import KpiCard from "@/components/kpi-card";
import PeriodSelector from "@/components/period-selector";
import StaffRatesEditor from "@/components/staff-rates-editor";
import {
    type StaffShift,
    fetchStaffShifts,
    fetchStaffRates,
    aggregateStaffKPIs,
    pivotRates,
    getPayPeriod,
    fetchBiweeklyEarnings,
    fetchBreakStats,
} from "@/lib/queries/staff";
import { fetchDailyStats, aggregateStats } from "@/lib/queries/overview";
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
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip as RechartsTooltip,
    ResponsiveContainer,
    Legend,
} from "recharts";

// ── Labour split segment keys ──
type SegmentKey = "adultCafe" | "adultRetail" | "teenCafe" | "teenRetail";

const SEGMENTS: { key: SegmentKey; label: string; color: string; emoji: string }[] = [
    { key: "adultCafe", label: "Adult Café", color: "#6B7355", emoji: "☕" },
    { key: "adultRetail", label: "Adult Retail", color: "#E07A5F", emoji: "🛍" },
    { key: "teenCafe", label: "Teen Café", color: "#81B29A", emoji: "☕" },
    { key: "teenRetail", label: "Teen Retail", color: "#F2CC8F", emoji: "🛍" },
];

export default function StaffPage() {
    const [period, setPeriod] = useState<PeriodType>("this_month");
    const [comparison, setComparison] = useState<ComparisonType>("prior_period");
    const [customStart, setCustomStart] = useState("");
    const [customEnd, setCustomEnd] = useState("");
    const [loading, setLoading] = useState(true);
    const [shifts, setShifts] = useState<StaffShift[]>([]);
    const [compShifts, setCompShifts] = useState<StaffShift[]>([]);
    const [netSales, setNetSales] = useState(0);
    const [compNetSales, setCompNetSales] = useState(0);
    const [ratesTable, setRatesTable] = useState<ReturnType<typeof pivotRates>>([]);
    const [ratesFilter, setRatesFilter] = useState<"all" | "active" | "inactive">("active");
    const [earningsMap, setEarningsMap] = useState<Map<string, number>>(new Map());
    const [breakMap, setBreakMap] = useState<Map<string, number>>(new Map());
    const [payPeriod, setPayPeriod] = useState(getPayPeriod());
    const [sortCol, setSortCol] = useState<"name" | "role" | "earnings" | "weekday" | "saturday" | "sunday" | "publicHoliday" | "breaks">("name");
    const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

    // ── Chart filter: which series are visible ──
    const [activeSegments, setActiveSegments] = useState<Set<SegmentKey>>(
        new Set(["adultCafe", "adultRetail", "teenCafe", "teenRetail"])
    );
    const [segDropdownOpen, setSegDropdownOpen] = useState(false);
    const segDropdownRef = useRef<HTMLDivElement>(null);

    // Close dropdown on outside click
    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (segDropdownRef.current && !segDropdownRef.current.contains(e.target as Node)) {
                setSegDropdownOpen(false);
            }
        };
        document.addEventListener("mousedown", handler);
        return () => document.removeEventListener("mousedown", handler);
    }, []);

    const toggleSegment = (key: SegmentKey) => {
        setActiveSegments((prev) => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key);
            else next.add(key);
            return next;
        });
    };

    const loadData = useCallback(async () => {
        setLoading(true);
        try {
            const currentRange = resolvePeriodRange(period, customStart, customEnd);
            const compRange = resolveComparisonRange(currentRange, comparison, period);
            const pp = getPayPeriod();

            const [currentShifts, compShiftData, dailyStats, compDailyStats, rates, earnings, breaks] =
                await Promise.all([
                    fetchStaffShifts(currentRange.startDate, currentRange.endDate),
                    fetchStaffShifts(compRange.startDate, compRange.endDate),
                    fetchDailyStats(currentRange.startDate, currentRange.endDate),
                    fetchDailyStats(compRange.startDate, compRange.endDate),
                    fetchStaffRates(),
                    fetchBiweeklyEarnings(pp.periodStart, pp.periodEnd),
                    fetchBreakStats(pp.periodStart, pp.periodEnd),
                ]);

            setShifts(currentShifts);
            setCompShifts(compShiftData);

            const stats = aggregateStats(dailyStats);
            const compStats = aggregateStats(compDailyStats);
            setNetSales(stats.netSales);
            setCompNetSales(compStats.netSales);
            setRatesTable(pivotRates(rates));
            setEarningsMap(earnings);
            setBreakMap(breaks);
            setPayPeriod(pp);
        } catch (err) {
            console.error("Failed to load staff data:", err);
        } finally {
            setLoading(false);
        }
    }, [period, comparison, customStart, customEnd]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    const kpis = aggregateStaffKPIs(shifts, netSales);
    const compKpis = aggregateStaffKPIs(compShifts, compNetSales);

    // ── Build daily % line-chart data with 4-way split ──
    const dailyLineData = useMemo(() => {
        const dayMap = new Map<string, {
            date: string; adultCafe: number; adultRetail: number; teenCafe: number; teenRetail: number;
        }>();
        for (const s of shifts) {
            if (!dayMap.has(s.shift_date)) {
                dayMap.set(s.shift_date, { date: s.shift_date, adultCafe: 0, adultRetail: 0, teenCafe: 0, teenRetail: 0 });
            }
            const entry = dayMap.get(s.shift_date)!;
            if (!s.is_teen && s.business_side === "Bar") entry.adultCafe += s.labour_cost;
            else if (!s.is_teen && s.business_side === "Retail") entry.adultRetail += s.labour_cost;
            else if (s.is_teen && s.business_side === "Bar") entry.teenCafe += s.labour_cost;
            else entry.teenRetail += s.labour_cost;
        }
        return Array.from(dayMap.values())
            .sort((a, b) => a.date.localeCompare(b.date))
            .map((d) => {
                const total = d.adultCafe + d.adultRetail + d.teenCafe + d.teenRetail;
                return {
                    label: new Date(d.date + "T00:00:00").toLocaleDateString("en-AU", { day: "numeric", month: "short" }),
                    adultCafe: total > 0 ? +((d.adultCafe / total) * 100).toFixed(1) : 0,
                    adultRetail: total > 0 ? +((d.adultRetail / total) * 100).toFixed(1) : 0,
                    teenCafe: total > 0 ? +((d.teenCafe / total) * 100).toFixed(1) : 0,
                    teenRetail: total > 0 ? +((d.teenRetail / total) * 100).toFixed(1) : 0,
                };
            });
    }, [shifts]);

    // ── 4-way split data for right chart ──
    const fourWayData = [
        { segment: "Adult Café", hours: kpis.adultCafeHours, cost: kpis.adultCafeCost, color: "#6B7355" },
        { segment: "Adult Retail", hours: kpis.adultRetailHours, cost: kpis.adultRetailCost, color: "#E07A5F" },
        { segment: "Teen Café", hours: kpis.teenCafeHours, cost: kpis.teenCafeCost, color: "#81B29A" },
        { segment: "Teen Retail", hours: kpis.teenRetailHours, cost: kpis.teenRetailCost, color: "#F2CC8F" },
    ];
    const totalCost4way = fourWayData.reduce((s, d) => s + d.cost, 0);
    const totalHours4way = fourWayData.reduce((s, d) => s + d.hours, 0);

    // ── Tooltip state for right chart bars ──
    const [hoveredBar, setHoveredBar] = useState<string | null>(null);

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
                        <span className="text-sm font-medium">Loading staff data...</span>
                    </div>
                </div>
            ) : (
                <>
                    <div className="flex items-center justify-between">
                        <h1 className="text-[28px] font-bold text-foreground">Staff</h1>
                    </div>

                    {/* Period Selector */}
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

                    {/* KPI Cards */}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                        <KpiCard
                            label="Staff"
                            value={kpis.staffCount}
                            formatter={(n) => formatNumber(n)}
                            change={compKpis.staffCount > 0 ? calcChange(kpis.staffCount, compKpis.staffCount) : null}
                            subtitle={`Cafe: ${kpis.cafeStaffCount} · Retail: ${kpis.retailStaffCount}`}
                            delay={0}
                        />
                        <KpiCard
                            label="Total Hours"
                            value={kpis.totalHours}
                            formatter={(n) => `${n.toFixed(1)}h`}
                            change={compKpis.totalHours > 0 ? calcChange(kpis.totalHours, compKpis.totalHours) : null}
                            subtitle={`Cafe: ${kpis.cafeHours.toFixed(1)}h · Retail: ${kpis.retailHours.toFixed(1)}h`}
                            delay={1}
                        />
                        <KpiCard
                            label="Labour Cost Ratio"
                            value={kpis.labourCostRatio}
                            formatter={(n) => formatPercent(n)}
                            change={compKpis.labourCostRatio > 0 ? calcChange(kpis.labourCostRatio, compKpis.labourCostRatio) : null}
                            subtitle={`Teens: ${formatCurrency(kpis.teenCost)} · Adults: ${formatCurrency(kpis.adultCost)}`}
                            delay={2}
                        />
                        <KpiCard
                            label="Revenue per Hour"
                            value={kpis.revenuePerHour}
                            formatter={(n) => formatCurrency(n)}
                            change={compKpis.revenuePerHour > 0 ? calcChange(kpis.revenuePerHour, compKpis.revenuePerHour) : null}
                            subtitle={`Teen: ${kpis.teenHours.toFixed(1)}h · Adult: ${kpis.adultHours.toFixed(1)}h`}
                            delay={3}
                        />
                    </div>

                    {/* Charts Row */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                        {/* Left: Labour Cost % Line Chart with filter */}
                        <div className="bg-card rounded-xl border border-border p-6" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-base font-semibold text-foreground">
                                    Labour Cost %
                                </h3>
                                {/* Segment filter dropdown */}
                                <div className="relative" ref={segDropdownRef}>
                                    <button
                                        onClick={() => setSegDropdownOpen(!segDropdownOpen)}
                                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full border border-border bg-olive-surface hover:bg-olive/10 transition-colors cursor-pointer"
                                    >
                                        <span className="w-2 h-2 rounded-full bg-olive" />
                                        Segments
                                        <ChevronDown className={`w-3 h-3 transition-transform ${segDropdownOpen ? "rotate-180" : ""}`} />
                                    </button>
                                    {segDropdownOpen && (
                                        <div className="absolute right-0 top-full mt-1 w-56 bg-white rounded-xl border border-border shadow-lg z-30 py-2">
                                            {/* Select all / Clear */}
                                            <div className="flex items-center justify-between px-3 pb-2 border-b border-border mb-1">
                                                <button
                                                    onClick={() => setActiveSegments(new Set(SEGMENTS.map((s) => s.key)))}
                                                    className="text-[11px] font-medium text-olive hover:underline cursor-pointer"
                                                >
                                                    Select all
                                                </button>
                                                <span className="text-[10px] text-muted-foreground tabular-nums">
                                                    {activeSegments.size}/{SEGMENTS.length}
                                                </span>
                                                <button
                                                    onClick={() => setActiveSegments(new Set())}
                                                    className="text-[11px] font-medium text-coral hover:underline cursor-pointer"
                                                >
                                                    Clear all
                                                </button>
                                            </div>
                                            {SEGMENTS.map((seg) => (
                                                <label
                                                    key={seg.key}
                                                    className="flex items-center gap-2.5 px-3 py-1.5 hover:bg-olive-surface/50 cursor-pointer transition-colors"
                                                >
                                                    <input
                                                        type="checkbox"
                                                        checked={activeSegments.has(seg.key)}
                                                        onChange={() => toggleSegment(seg.key)}
                                                        className="w-3.5 h-3.5 rounded border-border accent-olive cursor-pointer"
                                                    />
                                                    <span
                                                        className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                                                        style={{ backgroundColor: seg.color }}
                                                    />
                                                    <span className="text-xs text-foreground">{seg.label}</span>
                                                </label>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>
                            <ResponsiveContainer width="100%" height={280}>
                                <LineChart data={dailyLineData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#F0F0EE" vertical={false} />
                                    <XAxis
                                        dataKey="label"
                                        tick={{ fill: "#8A8A8A", fontSize: 10 }}
                                        axisLine={{ stroke: "#EAEAE8" }}
                                        tickLine={false}
                                        interval="preserveStartEnd"
                                    />
                                    <YAxis
                                        tick={{ fill: "#8A8A8A", fontSize: 11 }}
                                        axisLine={false}
                                        tickLine={false}
                                        tickFormatter={(v: number) => `${v}%`}
                                        domain={[0, 100]}
                                    />
                                    <RechartsTooltip
                                        contentStyle={{
                                            background: "white",
                                            borderRadius: 12,
                                            border: "1px solid #EAEAE8",
                                            boxShadow: "0 4px 16px rgba(0,0,0,0.10)",
                                            fontSize: 13,
                                            padding: "12px 16px",
                                        }}
                                        formatter={(v: number, name: string) => {
                                            const seg = SEGMENTS.find((s) => s.key === name);
                                            return [`${v.toFixed(1)}%`, seg ? `${seg.emoji} ${seg.label}` : name];
                                        }}
                                    />
                                    <Legend
                                        formatter={(v: string) => {
                                            const seg = SEGMENTS.find((s) => s.key === v);
                                            return seg ? `${seg.emoji} ${seg.label}` : v;
                                        }}
                                        wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                                    />
                                    {SEGMENTS.map((seg) =>
                                        activeSegments.has(seg.key) ? (
                                            <Line
                                                key={seg.key}
                                                type="monotone"
                                                dataKey={seg.key}
                                                stroke={seg.color}
                                                strokeWidth={2}
                                                dot={false}
                                                strokeDasharray={seg.key.startsWith("teen") ? "6 3" : undefined}
                                            />
                                        ) : null
                                    )}
                                </LineChart>
                            </ResponsiveContainer>
                        </div>

                        {/* Right: 4-way Split Horizontal Bars */}
                        <div className="bg-card rounded-xl border border-border p-6" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                            <h3 className="text-base font-semibold text-foreground mb-4">
                                Labour Split — Teen vs Adult × Café vs Retail
                            </h3>
                            <div className="space-y-3">
                                {fourWayData.map((seg) => {
                                    const pct = totalCost4way > 0 ? (seg.cost / totalCost4way) * 100 : 0;
                                    const revPerHr = seg.hours > 0 ? netSales * (seg.hours / totalHours4way) / seg.hours : 0;
                                    const isHovered = hoveredBar === seg.segment;
                                    // Dark bars (#6B7355, #81B29A) → white text; light bars (#E07A5F, #F2CC8F) → dark text
                                    const isDarkBar = seg.color === "#6B7355" || seg.color === "#81B29A";
                                    const barTextColor = isDarkBar ? "#FFFFFF" : "#1A1A1A";

                                    return (
                                        <div key={seg.segment}>
                                            <div className="flex items-center justify-between mb-1">
                                                <span className="text-sm font-medium text-foreground">{seg.segment}</span>
                                                <span className="text-sm font-semibold text-foreground tabular-nums">{formatCurrency(seg.cost)}</span>
                                            </div>
                                            <div
                                                className="relative h-7 bg-muted/40 rounded-lg overflow-hidden cursor-default"
                                                onMouseEnter={() => setHoveredBar(seg.segment)}
                                                onMouseLeave={() => setHoveredBar(null)}
                                            >
                                                <div
                                                    className="absolute inset-y-0 left-0 rounded-lg transition-all duration-700 ease-out"
                                                    style={{ width: `${Math.max(pct, 1)}%`, backgroundColor: seg.color }}
                                                />
                                                <span
                                                    className="absolute inset-0 flex items-center px-3 text-xs font-semibold tabular-nums"
                                                    style={{ color: barTextColor }}
                                                >
                                                    {pct.toFixed(1)}% · {seg.hours.toFixed(1)}h
                                                </span>
                                                {/* Tooltip on bar hover */}
                                                {isHovered && (
                                                    <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 bg-foreground text-background rounded-lg px-4 py-2.5 text-xs whitespace-nowrap z-20 shadow-lg pointer-events-none">
                                                        <div className="font-semibold mb-1">{seg.segment}</div>
                                                        <div>Hours: {seg.hours.toFixed(1)}h ({totalHours4way > 0 ? ((seg.hours / totalHours4way) * 100).toFixed(1) : 0}%)</div>
                                                        <div>Cost: {formatCurrency(seg.cost)} ({pct.toFixed(1)}%)</div>
                                                        <div>Rev/hr: {formatCurrency(revPerHr)}</div>
                                                        <div className="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0 border-l-[6px] border-r-[6px] border-t-[6px] border-transparent border-t-foreground" />
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Stacked bar summary */}
                            <div className="mt-5 pt-4 border-t border-border">
                                <div className="text-xs text-muted-foreground mb-2 font-medium">Distribution</div>
                                <div className="flex h-5 rounded-full overflow-hidden">
                                    {fourWayData.map((seg) => {
                                        const pct = totalCost4way > 0 ? (seg.cost / totalCost4way) * 100 : 0;
                                        return (
                                            <div
                                                key={seg.segment}
                                                className="transition-all duration-700"
                                                style={{ width: `${pct}%`, backgroundColor: seg.color }}
                                                title={`${seg.segment}: ${pct.toFixed(1)}%`}
                                            />
                                        );
                                    })}
                                </div>
                                <div className="flex justify-between mt-2 text-[10px] text-muted-foreground">
                                    <span>Total: {formatCurrency(totalCost4way)}</span>
                                    <span>{totalHours4way.toFixed(1)}h</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Staff Rates Table with earnings + breaks */}
                    {(() => {
                        type SortKey = "name" | "role" | "earnings" | "weekday" | "saturday" | "sunday" | "publicHoliday" | "breaks";
                        const activeRates = ratesTable.filter((r) => r.isActive);
                        const inactiveRates = ratesTable.filter((r) => !r.isActive);
                        const base =
                            ratesFilter === "all"
                                ? ratesTable
                                : ratesFilter === "active"
                                    ? activeRates
                                    : inactiveRates;

                        // Sort
                        const sortedRates = [...base].sort((a, b) => {
                            const dir = sortDir === "asc" ? 1 : -1;
                            const valA = (() => {
                                switch (sortCol) {
                                    case "name": return a.name.toLowerCase();
                                    case "role": return a.jobTitle.toLowerCase();
                                    case "earnings": return earningsMap.get(a.name) || 0;
                                    case "weekday": return a.weekday;
                                    case "saturday": return a.saturday;
                                    case "sunday": return a.sunday;
                                    case "publicHoliday": return a.publicHoliday;
                                    case "breaks": return breakMap.get(a.name) || 0;
                                    default: return a.name.toLowerCase();
                                }
                            })();
                            const valB = (() => {
                                switch (sortCol) {
                                    case "name": return b.name.toLowerCase();
                                    case "role": return b.jobTitle.toLowerCase();
                                    case "earnings": return earningsMap.get(b.name) || 0;
                                    case "weekday": return b.weekday;
                                    case "saturday": return b.saturday;
                                    case "sunday": return b.sunday;
                                    case "publicHoliday": return b.publicHoliday;
                                    case "breaks": return breakMap.get(b.name) || 0;
                                    default: return b.name.toLowerCase();
                                }
                            })();
                            if (valA < valB) return -1 * dir;
                            if (valA > valB) return 1 * dir;
                            return 0;
                        });

                        const toggleSort = (col: SortKey) => {
                            if (sortCol === col) {
                                setSortDir((d) => (d === "asc" ? "desc" : "asc"));
                            } else {
                                setSortCol(col);
                                setSortDir(col === "name" || col === "role" ? "asc" : "desc");
                            }
                        };

                        const SortIcon = ({ col }: { col: SortKey }) => (
                            sortCol === col ? (
                                sortDir === "asc" ? (
                                    <ChevronUp className="w-3.5 h-3.5 text-olive" />
                                ) : (
                                    <ChevronDown className="w-3.5 h-3.5 text-olive" />
                                )
                            ) : (
                                <ChevronsUpDown className="w-3.5 h-3.5 opacity-30" />
                            )
                        );

                        // Sum earnings for the total row
                        const totalEarnings = sortedRates.reduce((s, r) => s + (earningsMap.get(r.name) || 0), 0);

                        return (
                            <div className="bg-card rounded-xl border border-border overflow-hidden" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                                <div className="px-6 py-4 border-b border-border flex items-center justify-between">
                                    <div className="flex items-center gap-4">
                                        <h3 className="text-base font-semibold text-foreground">Staff Rates</h3>
                                        <div className="flex items-center gap-2">
                                            {([
                                                { value: "all" as const, label: `All (${ratesTable.length})` },
                                                { value: "active" as const, label: `Active (${activeRates.length})` },
                                                { value: "inactive" as const, label: `Inactive (${inactiveRates.length})` },
                                            ]).map((pill) => (
                                                <button
                                                    key={pill.value}
                                                    onClick={() => setRatesFilter(pill.value)}
                                                    className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors cursor-pointer ${ratesFilter === pill.value
                                                        ? "bg-olive text-white"
                                                        : "bg-olive-surface text-text-body hover:bg-olive/10"
                                                        }`}
                                                >
                                                    {pill.label}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <span className="text-xs text-muted-foreground block">
                                            Rates include 12% super (except under-18)
                                        </span>
                                        <span className="text-[10px] text-muted-foreground">
                                            Earnings period: {new Date(payPeriod.periodStart + "T00:00:00").toLocaleDateString("en-AU", { day: "numeric", month: "short" })} – {new Date(payPeriod.periodEnd + "T00:00:00").toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" })}
                                            {" · "}Next update: {new Date(payPeriod.nextUpdate + "T00:00:00").toLocaleDateString("en-AU", { day: "numeric", month: "short" })}
                                        </span>
                                    </div>
                                </div>

                                {/* Total Earnings bar — OUTSIDE scroll area so it stays visible */}
                                {totalEarnings > 0 && (
                                    <div className="px-6 py-2.5 bg-olive-surface/40 border-b border-border flex items-center justify-between">
                                        <span className="text-xs font-semibold text-olive">Total Earnings</span>
                                        <span className="text-sm font-bold text-olive tabular-nums">{formatCurrency(totalEarnings)}</span>
                                    </div>
                                )}

                                <div className="max-h-[480px] overflow-y-auto">
                                    <table className="w-full text-sm table-fixed">
                                        <colgroup>
                                            <col style={{ width: "18%" }} />
                                            <col style={{ width: "12%" }} />
                                            <col style={{ width: "12%" }} />
                                            <col style={{ width: "10%" }} />
                                            <col style={{ width: "10%" }} />
                                            <col style={{ width: "10%" }} />
                                            <col style={{ width: "14%" }} />
                                            <col style={{ width: "8%" }} />
                                        </colgroup>
                                        <thead className="sticky top-0 z-10">
                                            <tr className="bg-[#FAFAF8]">
                                                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-text-body cursor-pointer select-none hover:text-foreground transition-colors text-left" onClick={() => toggleSort("name")}>
                                                    <span className="inline-flex items-center gap-1">Name<SortIcon col="name" /></span>
                                                </th>
                                                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-text-body cursor-pointer select-none hover:text-foreground transition-colors text-left" onClick={() => toggleSort("role")}>
                                                    <span className="inline-flex items-center gap-1">Role<SortIcon col="role" /></span>
                                                </th>
                                                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-text-body cursor-pointer select-none hover:text-foreground transition-colors text-right" onClick={() => toggleSort("earnings")} title="Biweekly earnings excl. 12% super (for Xero payroll)">
                                                    <span className="inline-flex items-center gap-1 float-right">Earnings<SortIcon col="earnings" /></span>
                                                </th>
                                                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-text-body cursor-pointer select-none hover:text-foreground transition-colors text-right" onClick={() => toggleSort("weekday")}>
                                                    <span className="inline-flex items-center gap-1 float-right">Weekday<SortIcon col="weekday" /></span>
                                                </th>
                                                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-text-body cursor-pointer select-none hover:text-foreground transition-colors text-right" onClick={() => toggleSort("saturday")}>
                                                    <span className="inline-flex items-center gap-1 float-right">Saturday<SortIcon col="saturday" /></span>
                                                </th>
                                                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-text-body cursor-pointer select-none hover:text-foreground transition-colors text-right" onClick={() => toggleSort("sunday")}>
                                                    <span className="inline-flex items-center gap-1 float-right">Sunday<SortIcon col="sunday" /></span>
                                                </th>
                                                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-text-body cursor-pointer select-none hover:text-foreground transition-colors text-right" onClick={() => toggleSort("publicHoliday")}>
                                                    <span className="inline-flex items-center gap-1 float-right">Pub. Holiday<SortIcon col="publicHoliday" /></span>
                                                </th>
                                                <th className="px-2 py-3 text-xs font-semibold uppercase tracking-wider text-text-body cursor-pointer select-none hover:text-foreground transition-colors text-center" onClick={() => toggleSort("breaks")} title="Shifts with 30-min auto-break (>6h15)">
                                                    <span className="inline-flex items-center justify-center gap-1">Breaks<SortIcon col="breaks" /></span>
                                                </th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {sortedRates.map((r, i) => {
                                                const earning = earningsMap.get(r.name) || 0;
                                                const breaks = breakMap.get(r.name) || 0;
                                                return (
                                                    <tr
                                                        key={r.name}
                                                        className={`border-t border-border transition-colors ${!r.isActive
                                                            ? "opacity-50 bg-[#FAFAF8]/50"
                                                            : i % 2 === 0
                                                                ? "bg-white"
                                                                : "bg-[#FAFAF8]/50"
                                                            } hover:bg-olive-surface/30`}
                                                    >
                                                        <td className="px-4 py-3 font-medium text-foreground whitespace-nowrap">
                                                            {r.name}
                                                            {!r.isActive && (
                                                                <span className="ml-2 text-[10px] font-semibold uppercase tracking-wider text-coral bg-coral/10 px-1.5 py-0.5 rounded-full">
                                                                    Inactive
                                                                </span>
                                                            )}
                                                        </td>
                                                        <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">{r.jobTitle}</td>
                                                        <td className="px-4 py-3 text-right tabular-nums font-semibold text-foreground">
                                                            {earning > 0 ? formatCurrency(earning) : (
                                                                <span className="text-muted-foreground font-normal">—</span>
                                                            )}
                                                        </td>
                                                        <td className="px-4 py-3 text-right tabular-nums text-foreground">{formatCurrency(r.weekday)}</td>
                                                        <td className="px-4 py-3 text-right tabular-nums text-foreground">{formatCurrency(r.saturday)}</td>
                                                        <td className="px-4 py-3 text-right tabular-nums text-foreground">{formatCurrency(r.sunday)}</td>
                                                        <td className="px-4 py-3 text-right tabular-nums text-foreground">{formatCurrency(r.publicHoliday)}</td>
                                                        <td className="px-2 py-3 text-center">
                                                            {breaks > 0 ? (
                                                                <span className="inline-flex items-center justify-center min-w-[28px] px-2 py-0.5 text-xs font-medium rounded-full bg-amber-100 text-amber-800">
                                                                    {breaks}
                                                                </span>
                                                            ) : (
                                                                <span className="text-muted-foreground">—</span>
                                                            )}
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                            {sortedRates.length === 0 && (
                                                <tr>
                                                    <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground text-sm">
                                                        No staff match this filter.
                                                    </td>
                                                </tr>
                                            )}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        );
                    })()}
                </>
            )}
        </motion.div>
    );
}
