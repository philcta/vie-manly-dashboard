"use client";

import { useState, useMemo } from "react";
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
} from "recharts";
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format";
import type { DailyStats, CategoryDailyData, DailyLabour } from "@/lib/queries/overview";

// ── Metric definitions ──────────────────────────────────────────

export type MetricKey =
    | "cafe_vs_retail"
    | "net_sales"
    | "gross_sales"
    | "transactions"
    | "avg_sale"
    | "labour_cost"
    | "labour_pct";

interface MetricDef {
    label: string;
    shortLabel: string;
    formatter: (v: number) => string;
    yFormatter: (v: number) => string;
    color: string;
    compColor: string;
}

const METRICS: Record<MetricKey, MetricDef> = {
    cafe_vs_retail: {
        label: "Cafe vs Retail — Net Sales",
        shortLabel: "Cafe vs Retail",
        formatter: (v) => formatCurrency(v),
        yFormatter: (v) => `$${(v / 1000).toFixed(1)}K`,
        color: "#6B7355",
        compColor: "#E07A5F",
    },
    net_sales: {
        label: "Net Sales",
        shortLabel: "Net Sales",
        formatter: (v) => formatCurrency(v),
        yFormatter: (v) => `$${(v / 1000).toFixed(1)}K`,
        color: "#6B7355",
        compColor: "#E07A5F",
    },
    gross_sales: {
        label: "Gross Sales",
        shortLabel: "Gross Sales",
        formatter: (v) => formatCurrency(v),
        yFormatter: (v) => `$${(v / 1000).toFixed(1)}K`,
        color: "#6B7355",
        compColor: "#E07A5F",
    },
    transactions: {
        label: "Transactions",
        shortLabel: "Transactions",
        formatter: (v) => formatNumber(v),
        yFormatter: (v) => formatNumber(v),
        color: "#6B7355",
        compColor: "#E07A5F",
    },
    avg_sale: {
        label: "Average Sale",
        shortLabel: "Avg Sale",
        formatter: (v) => formatCurrency(v),
        yFormatter: (v) => `$${v.toFixed(0)}`,
        color: "#6B7355",
        compColor: "#E07A5F",
    },
    labour_cost: {
        label: "Labour Cost",
        shortLabel: "Labour",
        formatter: (v) => formatCurrency(v),
        yFormatter: (v) => `$${(v / 1000).toFixed(1)}K`,
        color: "#6B7355",
        compColor: "#E07A5F",
    },
    labour_pct: {
        label: "Labour Cost vs Sales %",
        shortLabel: "Labour %",
        formatter: (v) => formatPercent(v),
        yFormatter: (v) => `${v.toFixed(0)}%`,
        color: "#6B7355",
        compColor: "#E07A5F",
    },
};

const METRIC_ORDER: MetricKey[] = [
    "cafe_vs_retail",
    "net_sales",
    "gross_sales",
    "transactions",
    "avg_sale",
    "labour_cost",
    "labour_pct",
];

// ── Component props ─────────────────────────────────────────────

interface MetricTimeSeriesChartProps {
    dailyStats: DailyStats[];
    compDailyStats: DailyStats[];
    categoryData: CategoryDailyData[];
    compCategoryData: CategoryDailyData[];
    dailyLabour: DailyLabour[];
    compDailyLabour: DailyLabour[];
}

// ── Helper: format date label ───────────────────────────────────

function dateLabel(dateStr: string): string {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-AU", { day: "numeric", month: "short" });
}

// ── Main component ──────────────────────────────────────────────

export function MetricTimeSeriesChart({
    dailyStats,
    compDailyStats,
    categoryData,
    compCategoryData,
    dailyLabour,
    compDailyLabour,
}: MetricTimeSeriesChartProps) {
    const [metric, setMetric] = useState<MetricKey>("cafe_vs_retail");
    const def = METRICS[metric];

    // ── Build chart data based on selected metric ──

    const chartData = useMemo(() => {
        if (metric === "cafe_vs_retail") {
            return buildCafeRetailData(categoryData);
        }
        return buildSingleMetricData(dailyStats, dailyLabour, metric);
    }, [metric, dailyStats, categoryData, dailyLabour]);

    const compChartData = useMemo(() => {
        if (metric === "cafe_vs_retail") return null; // dual-line, no comparison overlay
        return buildSingleMetricData(compDailyStats, compDailyLabour, metric);
    }, [metric, compDailyStats, compDailyLabour]);

    // ── For single-metric views, merge current + comparison by index ──

    const mergedData = useMemo(() => {
        if (metric === "cafe_vs_retail") return chartData;

        return chartData.map((row, i) => ({
            ...row,
            comparison: compChartData && compChartData[i] ? compChartData[i].value : undefined,
        }));
    }, [metric, chartData, compChartData]);

    if (mergedData.length === 0) {
        return (
            <div className="bg-card rounded-xl border border-border p-6" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                <p className="text-muted-foreground text-sm text-center py-12">
                    No data available for this period
                </p>
            </div>
        );
    }

    return (
        <div
            className="bg-card rounded-xl border border-border p-6"
            style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}
        >
            {/* Header with metric selector */}
            <div className="flex items-center justify-between mb-5">
                <h2 className="text-lg font-semibold text-foreground">
                    {def.label}
                </h2>

                {/* Metric pills */}
                <div className="flex items-center gap-1 rounded-lg border border-border bg-background p-0.5">
                    {METRIC_ORDER.map((key) => (
                        <button
                            key={key}
                            onClick={() => setMetric(key)}
                            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200 cursor-pointer whitespace-nowrap ${metric === key
                                ? "bg-olive text-white shadow-sm"
                                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                                }`}
                        >
                            {METRICS[key].shortLabel}
                        </button>
                    ))}
                </div>
            </div>

            {/* Chart */}
            <ResponsiveContainer width="100%" height={300}>
                {metric === "cafe_vs_retail" ? (
                    <AreaChart data={mergedData}>
                        <defs>
                            <linearGradient id="tsGradCafe" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#6B7355" stopOpacity={0.15} />
                                <stop offset="100%" stopColor="#6B7355" stopOpacity={0.02} />
                            </linearGradient>
                            <linearGradient id="tsGradRetail" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#E07A5F" stopOpacity={0.15} />
                                <stop offset="100%" stopColor="#E07A5F" stopOpacity={0.02} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#F0F0EE" vertical={false} />
                        <XAxis
                            dataKey="label"
                            tick={{ fill: "#8A8A8A", fontSize: 11 }}
                            axisLine={{ stroke: "#EAEAE8" }}
                            tickLine={false}
                        />
                        <YAxis
                            tick={{ fill: "#8A8A8A", fontSize: 11 }}
                            axisLine={false}
                            tickLine={false}
                            tickFormatter={def.yFormatter}
                        />
                        <Tooltip
                            contentStyle={tooltipStyle}
                            formatter={(value: number, name: string) => [
                                def.formatter(value),
                                name === "cafe" ? "Cafe" : "Retail",
                            ]}
                        />
                        <Legend
                            formatter={(v: string) => (v === "cafe" ? "Cafe" : "Retail")}
                            wrapperStyle={{ fontSize: 12 }}
                        />
                        <Area
                            type="monotone"
                            dataKey="cafe"
                            stroke="#6B7355"
                            strokeWidth={2}
                            fill="url(#tsGradCafe)"
                            animationDuration={800}
                        />
                        <Area
                            type="monotone"
                            dataKey="retail"
                            stroke="#E07A5F"
                            strokeWidth={2}
                            strokeDasharray="5 5"
                            fill="url(#tsGradRetail)"
                            animationDuration={800}
                        />
                    </AreaChart>
                ) : (
                    <AreaChart data={mergedData}>
                        <defs>
                            <linearGradient id="tsGradMain" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={def.color} stopOpacity={0.18} />
                                <stop offset="100%" stopColor={def.color} stopOpacity={0.02} />
                            </linearGradient>
                            <linearGradient id="tsGradComp" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={def.compColor} stopOpacity={0.12} />
                                <stop offset="100%" stopColor={def.compColor} stopOpacity={0.02} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#F0F0EE" vertical={false} />
                        <XAxis
                            dataKey="label"
                            tick={{ fill: "#8A8A8A", fontSize: 11 }}
                            axisLine={{ stroke: "#EAEAE8" }}
                            tickLine={false}
                        />
                        <YAxis
                            tick={{ fill: "#8A8A8A", fontSize: 11 }}
                            axisLine={false}
                            tickLine={false}
                            tickFormatter={def.yFormatter}
                        />
                        <Tooltip
                            contentStyle={tooltipStyle}
                            formatter={(value: number, name: string) => [
                                def.formatter(value),
                                name === "value" ? "Current" : "Prior",
                            ]}
                        />
                        <Legend
                            formatter={(v: string) => (v === "value" ? "Current period" : "Prior period")}
                            wrapperStyle={{ fontSize: 12 }}
                        />
                        {/* Comparison line (dashed, behind) */}
                        <Area
                            type="monotone"
                            dataKey="comparison"
                            stroke={def.compColor}
                            strokeWidth={1.5}
                            strokeDasharray="5 5"
                            strokeOpacity={0.6}
                            fill="url(#tsGradComp)"
                            animationDuration={800}
                        />
                        {/* Current period line (solid, on top) */}
                        <Area
                            type="monotone"
                            dataKey="value"
                            stroke={def.color}
                            strokeWidth={2.5}
                            fill="url(#tsGradMain)"
                            animationDuration={800}
                        />
                    </AreaChart>
                )}
            </ResponsiveContainer>
        </div>
    );
}

// ── Tooltip style ───────────────────────────────────────────────

const tooltipStyle = {
    background: "white",
    borderRadius: 8,
    border: "1px solid #EAEAE8",
    boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
    fontSize: 13,
};

// ── Data builders ───────────────────────────────────────────────

function buildCafeRetailData(data: CategoryDailyData[]) {
    const map = new Map<string, { date: string; cafe: number; retail: number }>();
    for (const row of data) {
        if (!map.has(row.date)) map.set(row.date, { date: row.date, cafe: 0, retail: 0 });
        const entry = map.get(row.date)!;
        if (row.category === "Cafe") entry.cafe += row.total_net_sales;
        else entry.retail += row.total_net_sales;
    }
    return Array.from(map.values())
        .sort((a, b) => a.date.localeCompare(b.date))
        .map((d) => ({ ...d, label: dateLabel(d.date) }));
}

function buildSingleMetricData(
    stats: DailyStats[],
    labour: DailyLabour[],
    metric: MetricKey
) {
    // Build a labour lookup for labour-related metrics
    const labourMap = new Map<string, number>();
    for (const l of labour) labourMap.set(l.date, l.labour_cost);

    return stats.map((row) => {
        let value = 0;
        switch (metric) {
            case "net_sales":
                value = row.total_net_sales;
                break;
            case "gross_sales":
                value = row.total_gross_sales || 0;
                break;
            case "transactions":
                value = row.total_transactions;
                break;
            case "avg_sale":
                value =
                    row.total_transactions > 0
                        ? Math.round((row.total_net_sales / row.total_transactions) * 100) / 100
                        : 0;
                break;
            case "labour_cost":
                value = labourMap.get(row.date) || 0;
                break;
            case "labour_pct": {
                const lc = labourMap.get(row.date) || 0;
                value =
                    row.total_net_sales > 0
                        ? Math.round((lc / row.total_net_sales) * 10000) / 100
                        : 0;
                break;
            }
        }
        return {
            date: row.date,
            label: dateLabel(row.date),
            value,
        };
    });
}
