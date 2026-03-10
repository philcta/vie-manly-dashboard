"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";
import KpiCard from "@/components/kpi-card";
import PeriodSelector from "@/components/period-selector";
import {
    fetchStaffShifts,
    fetchStaffRates,
    aggregateStaffKPIs,
    pivotRates,
    getPayPeriod,
    fetchBiweeklyEarnings,
    fetchBreakStats,
    type StaffShift,
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
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
    PieChart,
    Pie,
    Cell,
} from "recharts";

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

    // Build daily labour cost data for chart
    const dailyLabourMap = new Map<string, { date: string; cafe: number; retail: number }>();
    for (const s of shifts) {
        if (!dailyLabourMap.has(s.shift_date)) {
            dailyLabourMap.set(s.shift_date, { date: s.shift_date, cafe: 0, retail: 0 });
        }
        const entry = dailyLabourMap.get(s.shift_date)!;
        if (s.business_side === "Bar") {
            entry.cafe += s.labour_cost;
        } else {
            entry.retail += s.labour_cost;
        }
    }
    const dailyLabourData = Array.from(dailyLabourMap.values())
        .sort((a, b) => a.date.localeCompare(b.date))
        .map((d) => ({
            ...d,
            label: new Date(d.date).toLocaleDateString("en-AU", { weekday: "short" }),
        }));

    // Donut data for Cafe vs Retail hours
    const donutData = [
        { name: "Cafe", value: kpis.cafeHours, color: "#6B7355" },
        { name: "Retail", value: kpis.retailHours, color: "#E07A5F" },
    ];

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
                            subtitle="Target: 25–35%"
                            delay={2}
                        />
                        <KpiCard
                            label="Revenue per Hour"
                            value={kpis.revenuePerHour}
                            formatter={(n) => formatCurrency(n)}
                            change={compKpis.revenuePerHour > 0 ? calcChange(kpis.revenuePerHour, compKpis.revenuePerHour) : null}
                            delay={3}
                        />
                    </div>

                    {/* Charts Row */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                        {/* Labour Cost by Day */}
                        <div className="bg-card rounded-xl border border-border p-6" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                            <h3 className="text-base font-semibold text-foreground mb-4">
                                Labour Cost by Day
                            </h3>
                            <ResponsiveContainer width="100%" height={280}>
                                <BarChart data={dailyLabourData} barGap={2}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#F0F0EE" vertical={false} />
                                    <XAxis dataKey="label" tick={{ fill: "#8A8A8A", fontSize: 11 }} axisLine={{ stroke: "#EAEAE8" }} tickLine={false} />
                                    <YAxis tick={{ fill: "#8A8A8A", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v: number) => `$${v}`} />
                                    <Tooltip contentStyle={{ background: "white", borderRadius: 8, border: "1px solid #EAEAE8", boxShadow: "0 4px 12px rgba(0,0,0,0.08)", fontSize: 13 }} formatter={(v: number, name: string) => [formatCurrency(v), name === "cafe" ? "Cafe" : "Retail"]} />
                                    <Legend formatter={(v: string) => (v === "cafe" ? "Cafe" : "Retail")} wrapperStyle={{ fontSize: 12 }} />
                                    <Bar dataKey="cafe" stackId="a" fill="#6B7355" radius={[0, 0, 0, 0]} animationDuration={600} />
                                    <Bar dataKey="retail" stackId="a" fill="#E07A5F" radius={[4, 4, 0, 0]} animationDuration={600} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>

                        {/* Cafe vs Retail Hours Donut */}
                        <div className="bg-card rounded-xl border border-border p-6" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                            <h3 className="text-base font-semibold text-foreground mb-4">
                                Hours Split — Cafe vs Retail
                            </h3>
                            <div className="flex items-center justify-center">
                                <ResponsiveContainer width="100%" height={280}>
                                    <PieChart>
                                        <Pie
                                            data={donutData}
                                            cx="50%"
                                            cy="50%"
                                            innerRadius={70}
                                            outerRadius={110}
                                            paddingAngle={3}
                                            dataKey="value"
                                            animationDuration={800}
                                        >
                                            {donutData.map((entry, i) => (
                                                <Cell key={i} fill={entry.color} />
                                            ))}
                                        </Pie>
                                        <Tooltip contentStyle={{ background: "white", borderRadius: 8, border: "1px solid #EAEAE8", fontSize: 13 }} formatter={(v: number) => [`${v.toFixed(1)}h`]} />
                                        <Legend formatter={(v: string) => v} wrapperStyle={{ fontSize: 12 }} />
                                    </PieChart>
                                </ResponsiveContainer>
                            </div>
                            <p className="text-center text-2xl font-bold text-foreground mt-2 tabular-nums">
                                {kpis.totalHours.toFixed(1)}h
                            </p>
                            <p className="text-center text-xs text-muted-foreground">total</p>
                        </div>
                    </div>

                    {/* Staff Rates Table */}
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
