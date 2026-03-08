"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import KpiCard from "@/components/kpi-card";
import PeriodSelector from "@/components/period-selector";
import {
    fetchStaffShifts,
    fetchStaffRates,
    aggregateStaffKPIs,
    pivotRates,
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
    const [period, setPeriod] = useState<PeriodType>("this_week");
    const [comparison, setComparison] = useState<ComparisonType>("prior_period");
    const [customStart, setCustomStart] = useState("");
    const [customEnd, setCustomEnd] = useState("");
    const [loading, setLoading] = useState(true);
    const [shifts, setShifts] = useState<StaffShift[]>([]);
    const [compShifts, setCompShifts] = useState<StaffShift[]>([]);
    const [netSales, setNetSales] = useState(0);
    const [compNetSales, setCompNetSales] = useState(0);
    const [ratesTable, setRatesTable] = useState<ReturnType<typeof pivotRates>>([]);

    const loadData = useCallback(async () => {
        setLoading(true);
        try {
            const currentRange = resolvePeriodRange(period, customStart, customEnd);
            const compRange = resolveComparisonRange(currentRange, comparison, period);

            const [currentShifts, compShiftData, dailyStats, compDailyStats, rates] =
                await Promise.all([
                    fetchStaffShifts(currentRange.startDate, currentRange.endDate),
                    fetchStaffShifts(compRange.startDate, compRange.endDate),
                    fetchDailyStats(currentRange.startDate, currentRange.endDate),
                    fetchDailyStats(compRange.startDate, compRange.endDate),
                    fetchStaffRates(),
                ]);

            setShifts(currentShifts);
            setCompShifts(compShiftData);

            const stats = aggregateStats(dailyStats);
            const compStats = aggregateStats(compDailyStats);
            setNetSales(stats.netSales);
            setCompNetSales(compStats.netSales);
            setRatesTable(pivotRates(rates));
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
            className="space-y-8"
        >
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
            <div className="grid grid-cols-4 gap-5">
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
            <div className="grid grid-cols-2 gap-5">
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
            <div className="bg-card rounded-xl border border-border overflow-hidden" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                <div className="px-6 py-4 border-b border-border flex items-center justify-between">
                    <h3 className="text-base font-semibold text-foreground">Staff Rates</h3>
                    <span className="text-xs text-muted-foreground">
                        Rates include 12% superannuation (except under-18)
                    </span>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="bg-[#FAFAF8]">
                                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-body">Name</th>
                                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-body">Job Title</th>
                                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-text-body">Weekday</th>
                                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-text-body">Saturday</th>
                                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-text-body">Sunday</th>
                                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-text-body">Public Holiday</th>
                            </tr>
                        </thead>
                        <tbody>
                            {ratesTable.map((r, i) => (
                                <tr key={i} className="border-b border-[#F0F0EE] row-hover">
                                    <td className="px-4 py-3 text-sm font-medium text-foreground">{r.name}</td>
                                    <td className="px-4 py-3 text-sm text-text-body">{r.jobTitle}</td>
                                    <td className="px-4 py-3 text-sm text-right tabular-nums text-foreground">{formatCurrency(r.weekday)}</td>
                                    <td className="px-4 py-3 text-sm text-right tabular-nums text-foreground">{formatCurrency(r.saturday)}</td>
                                    <td className="px-4 py-3 text-sm text-right tabular-nums text-foreground">{formatCurrency(r.sunday)}</td>
                                    <td className="px-4 py-3 text-sm text-right tabular-nums text-foreground">{formatCurrency(r.publicHoliday)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {loading && (
                <div className="fixed inset-0 ml-[220px] bg-background/80 flex items-center justify-center z-40">
                    <div className="flex items-center gap-3 text-muted-foreground">
                        <div className="w-5 h-5 border-2 border-olive/30 border-t-olive rounded-full animate-spin" />
                        <span className="text-sm">Loading staff data...</span>
                    </div>
                </div>
            )}
        </motion.div>
    );
}
