"use client";

import { useState, useMemo } from "react";
import { Tooltip as ChartTooltip } from "recharts";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import {
    Area,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    ResponsiveContainer,
    Legend,
    ComposedChart,
} from "recharts";
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format";

// ── Metric definitions ──────────────────────────────────────────

export type MemberMetricKey =
    | "net_sales"
    | "transactions"
    | "avg_spend"
    | "sales_ratio"
    | "tx_ratio";

type MemberSideType = "all" | "member" | "non_member";

interface MetricDef {
    label: string;
    shortLabel: string;
    formatter: (v: number) => string;
    yFormatter: (v: number) => string;
    color: string;
    compColor: string;
}

const METRICS: Record<MemberMetricKey, MetricDef> = {
    net_sales: {
        label: "Net Sales",
        shortLabel: "Net Sales",
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
    avg_spend: {
        label: "Avg Spend / Tx",
        shortLabel: "Avg Spend",
        formatter: (v) => formatCurrency(v),
        yFormatter: (v) => `$${v.toFixed(0)}`,
        color: "#6B7355",
        compColor: "#E07A5F",
    },
    sales_ratio: {
        label: "Member Sales %",
        shortLabel: "Sales %",
        formatter: (v) => formatPercent(v),
        yFormatter: (v) => `${v.toFixed(0)}%`,
        color: "#6B7355",
        compColor: "#E07A5F",
    },
    tx_ratio: {
        label: "Member Transaction %",
        shortLabel: "Tx %",
        formatter: (v) => formatPercent(v),
        yFormatter: (v) => `${v.toFixed(0)}%`,
        color: "#6B7355",
        compColor: "#E07A5F",
    },
};

const METRIC_ORDER: MemberMetricKey[] = [
    "net_sales",
    "transactions",
    "avg_spend",
    "sales_ratio",
    "tx_ratio",
];

const SIDE_OPTIONS: { value: MemberSideType; label: string }[] = [
    { value: "all", label: "All" },
    { value: "member", label: "Member" },
    { value: "non_member", label: "Non-Member" },
];

// ── Trend line types ────────────────────────────────────────────

type TrendType = "linear" | "ma_3mo";

const TREND_OPTIONS: { value: TrendType; label: string; icon: string; tip?: string }[] = [
    { value: "linear", label: "Trend", icon: "↗", tip: "Best fit trend for period" },
    { value: "ma_3mo", label: "3mo Avg", icon: "〰" },
];

// ── Trend math ──────────────────────────────────────────────────

function linearRegression(values: number[]): number[] {
    const n = values.length;
    if (n < 2) return values;
    let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
    for (let i = 0; i < n; i++) {
        sumX += i; sumY += values[i]; sumXY += i * values[i]; sumXX += i * i;
    }
    const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
    const intercept = (sumY - slope * sumX) / n;
    return values.map((_, i) => Math.round((slope * i + intercept) * 100) / 100);
}

// ── Data type ───────────────────────────────────────────────────

export interface MemberDailyRow {
    date: string;
    member_net_sales: number;
    non_member_net_sales: number;
    member_transactions: number;
    non_member_transactions: number;
    member_sales_ratio: number;
    member_tx_ratio: number;
    member_unique_customers: number;
}

// ── Component props ─────────────────────────────────────────────

interface MemberMetricChartProps {
    data: MemberDailyRow[];
    compData: MemberDailyRow[];
    /** 6-month historical data for moving averages */
    historicalData: MemberDailyRow[];
}

// ── Helpers ─────────────────────────────────────────────────────

function dateLabel(dateStr: string): string {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-AU", { day: "numeric", month: "short" });
}

function sideLabel(side: MemberSideType): string {
    return side === "all" ? "" : side === "member" ? "Member " : "Non-Member ";
}

function extractValue(r: MemberDailyRow, metric: MemberMetricKey, side: MemberSideType): number {
    switch (metric) {
        case "net_sales":
            return side === "member" ? r.member_net_sales
                : side === "non_member" ? r.non_member_net_sales
                    : r.member_net_sales + r.non_member_net_sales;
        case "transactions":
            return side === "member" ? r.member_transactions
                : side === "non_member" ? r.non_member_transactions
                    : r.member_transactions + r.non_member_transactions;
        case "avg_spend": {
            const sales = side === "member" ? r.member_net_sales
                : side === "non_member" ? r.non_member_net_sales
                    : r.member_net_sales + r.non_member_net_sales;
            const txn = side === "member" ? r.member_transactions
                : side === "non_member" ? r.non_member_transactions
                    : r.member_transactions + r.non_member_transactions;
            return txn > 0 ? Math.round((sales / txn) * 100) / 100 : 0;
        }
        case "sales_ratio":
            return (r.member_sales_ratio || 0) * 100;
        case "tx_ratio":
            return (r.member_tx_ratio || 0) * 100;
    }
}

// ── Main component ──────────────────────────────────────────────

export function MemberMetricChart({ data, compData, historicalData }: MemberMetricChartProps) {
    const [metric, setMetric] = useState<MemberMetricKey>("net_sales");
    const [activeTrends, setActiveTrends] = useState<Set<TrendType>>(new Set(["ma_3mo"]));
    const [side, setSide] = useState<MemberSideType>("all");
    const def = METRICS[metric];

    // ── Build chart data ──
    const chartData = useMemo(() => {
        return data.map((r) => ({
            date: r.date,
            label: dateLabel(r.date),
            value: extractValue(r, metric, side),
        }));
    }, [data, metric, side]);

    const compChartData = useMemo(() => {
        return compData.map((r) => ({
            date: r.date,
            label: dateLabel(r.date),
            value: extractValue(r, metric, side),
        }));
    }, [compData, metric, side]);

    // ── Historical value map for moving averages ──
    const historicalValueMap = useMemo(() => {
        const map = new Map<string, number>();
        for (const r of historicalData) {
            map.set(r.date, extractValue(r, metric, side));
        }
        return map;
    }, [historicalData, metric, side]);

    // ── Trailing average ──
    const computeAvg = useMemo(() => {
        const sortedDates = Array.from(historicalValueMap.keys()).sort();
        const dateIndex = new Map<string, number>();
        sortedDates.forEach((d, i) => dateIndex.set(d, i));

        return (date: string, windowDays: number): number | null => {
            const idx = dateIndex.get(date);
            if (idx === undefined) return null;
            const startIdx = Math.max(0, idx - windowDays + 1);
            if (idx - startIdx < Math.min(windowDays * 0.3, 7)) return null;
            let sum = 0, count = 0;
            for (let i = startIdx; i <= idx; i++) {
                const val = historicalValueMap.get(sortedDates[i]);
                if (val !== undefined) { sum += val; count++; }
            }
            return count > 0 ? Math.round((sum / count) * 100) / 100 : null;
        };
    }, [historicalValueMap]);

    // ── Merge data + trends ──
    const mergedData = useMemo(() => {
        const values = chartData.map(d => d.value);

        const linearValues = activeTrends.has("linear") ? linearRegression(values) : null;
        const ma3Values = activeTrends.has("ma_3mo")
            ? chartData.map(d => computeAvg(d.date, 90))
            : null;

        return chartData.map((row, i) => ({
            ...row,
            comparison: compChartData[i]?.value,
            trend_linear: linearValues ? linearValues[i] : undefined,
            trend_ma3: ma3Values ? ma3Values[i] : undefined,
        }));
    }, [chartData, compChartData, activeTrends, computeAvg]);

    // ── Trend badge (only for 3mo avg, not linear) ──
    const trendBadge = useMemo(() => {
        if (!activeTrends.has("ma_3mo")) return null;
        const trendVals = mergedData
            .map(d => (d as Record<string, unknown>).trend_ma3 as number | null | undefined)
            .filter((v): v is number => v !== null && v !== undefined);
        if (trendVals.length < 2) return null;
        const first = trendVals[0];
        const last = trendVals[trendVals.length - 1];
        const totalChange = last - first;
        const pctChange = first !== 0 ? (totalChange / first) * 100 : 0;
        const direction = totalChange > 0 ? "↑" : totalChange < 0 ? "↓" : "→";
        return { direction, pctChange: Math.abs(pctChange), isPositive: totalChange > 0, label: `${sideLabel(side)}3mo avg` };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeTrends, mergedData, side]);

    if (mergedData.length === 0) {
        return (
            <div className="bg-card rounded-xl border border-border p-6" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                <p className="text-muted-foreground text-sm text-center py-12">No data available</p>
            </div>
        );
    }

    // Dynamic title
    const title = side === "all" ? def.label : `${side === "member" ? "Member" : "Non-Member"} — ${def.label}`;
    // For ratio metrics, side toggle doesn't matter (always shows member ratio)
    const showSideToggle = metric !== "sales_ratio" && metric !== "tx_ratio";

    return (
        <div className="bg-card rounded-xl border border-border p-6" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
            {/* Row 1: Title */}
            <h2 className="text-lg font-semibold text-foreground mb-4">{title}</h2>

            {/* Row 2: Controls */}
            <div className="flex flex-wrap items-center gap-3 mb-5">
                {/* Side toggle */}
                {showSideToggle && (
                    <>
                        <div className="flex items-center gap-1 rounded-lg border border-border bg-background p-0.5">
                            {SIDE_OPTIONS.map((opt) => (
                                <button
                                    key={opt.value}
                                    onClick={() => setSide(opt.value)}
                                    className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200 cursor-pointer whitespace-nowrap ${side === opt.value
                                        ? "bg-[#3B4A2A] text-white shadow-sm"
                                        : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                                        }`}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>
                        <div className="w-px h-5 bg-border" />
                    </>
                )}

                {/* Trend pills (multi-select) */}
                <div className="flex items-center gap-1 rounded-lg border border-border bg-background p-0.5">
                    {TREND_OPTIONS.map((opt) => {
                        const isActive = activeTrends.has(opt.value);
                        const toggle = () => setActiveTrends(prev => {
                            const next = new Set(prev);
                            if (next.has(opt.value)) next.delete(opt.value); else next.add(opt.value);
                            return next;
                        });
                        const btn = (
                            <button
                                key={opt.value}
                                onClick={toggle}
                                className={`px-2.5 py-1.5 text-xs font-medium rounded-md transition-all duration-200 cursor-pointer whitespace-nowrap ${isActive
                                    ? "bg-[#3B4A2A] text-white shadow-sm"
                                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                                    }`}
                            >
                                {opt.icon && <span className="mr-1">{opt.icon}</span>}{opt.label}
                            </button>
                        );
                        return opt.tip ? (
                            <Tooltip key={opt.value}>
                                <TooltipTrigger asChild>{btn}</TooltipTrigger>
                                <TooltipContent side="bottom" sideOffset={6}>{opt.tip}</TooltipContent>
                            </Tooltip>
                        ) : <span key={opt.value}>{btn}</span>;
                    })}
                </div>

                <div className="w-px h-5 bg-border" />

                {/* Metric pills */}
                <div className="flex items-center gap-1 rounded-lg border border-border bg-background p-0.5">
                    {METRIC_ORDER.map((key) => (
                        <button
                            key={key}
                            onClick={() => {
                                setMetric(key);
                                // Reset side for ratio metrics
                                if (key === "sales_ratio" || key === "tx_ratio") setSide("all");
                            }}
                            className={`px-2 py-1 text-xs font-medium rounded-md transition-all duration-200 cursor-pointer whitespace-nowrap ${metric === key
                                ? "bg-olive text-white shadow-sm"
                                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                                }`}
                        >
                            {METRICS[key].shortLabel}
                        </button>
                    ))}
                </div>
            </div>

            {/* Chart with floating badge overlay */}
            <div className="relative">
                {trendBadge && (
                    <div className="absolute top-2 left-1/2 -translate-x-1/2 z-10 pointer-events-none">
                        <div
                            className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold shadow-lg backdrop-blur-md border ${trendBadge.isPositive
                                ? "bg-positive/12 text-positive border-positive/20"
                                : "bg-coral/12 text-coral border-coral/20"
                                }`}
                            style={{ backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)" }}
                        >
                            <span className="text-base">{trendBadge.direction}</span>
                            <span>{trendBadge.pctChange.toFixed(1)}%</span>
                            <span className="opacity-70 text-xs font-medium">{trendBadge.label}</span>
                        </div>
                    </div>
                )}

                <ResponsiveContainer width="100%" height={300}>
                    <ComposedChart data={mergedData}>
                        <defs>
                            <linearGradient id="memGradMain" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={def.color} stopOpacity={0.18} />
                                <stop offset="100%" stopColor={def.color} stopOpacity={0.02} />
                            </linearGradient>
                            <linearGradient id="memGradComp" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={def.compColor} stopOpacity={0.12} />
                                <stop offset="100%" stopColor={def.compColor} stopOpacity={0.02} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#F0F0EE" vertical={false} />
                        <XAxis dataKey="label" tick={{ fill: "#8A8A8A", fontSize: 11 }} axisLine={{ stroke: "#EAEAE8" }} tickLine={false} />
                        <YAxis tick={{ fill: "#8A8A8A", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={def.yFormatter} />
                        <ChartTooltip
                            contentStyle={tooltipStyle}
                            formatter={(value: number, name: string) => {
                                const nameMap: Record<string, string> = { value: "Current", comparison: "Prior", trend_linear: "Trend", trend_ma3: "3mo Avg" };
                                return [def.formatter(value), nameMap[name] || name];
                            }}
                        />
                        <Legend
                            formatter={(v: string) => {
                                const nameMap: Record<string, string> = { value: "Current period", comparison: "Prior period", trend_linear: "Trend", trend_ma3: "3mo Avg" };
                                return nameMap[v] || v;
                            }}
                            wrapperStyle={{ fontSize: 12 }}
                        />
                        <Area type="monotone" dataKey="comparison" stroke={def.compColor} strokeWidth={1.5} strokeDasharray="5 5" strokeOpacity={0.6} fill="url(#memGradComp)" animationDuration={800} />
                        <Area type="monotone" dataKey="value" stroke={def.color} strokeWidth={2.5} fill="url(#memGradMain)" animationDuration={800} />
                        {activeTrends.has("linear") && (
                            <Line type="linear" dataKey="trend_linear" stroke="#3B4A2A" strokeWidth={2} strokeDasharray="8 4" dot={false} connectNulls animationDuration={400} />
                        )}
                        {activeTrends.has("ma_3mo") && (
                            <Line type="monotone" dataKey="trend_ma3" stroke="#7C6F5B" strokeWidth={2} strokeDasharray="4 3" dot={false} connectNulls animationDuration={400} />
                        )}
                    </ComposedChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}

const tooltipStyle = {
    background: "white",
    borderRadius: 8,
    border: "1px solid #EAEAE8",
    boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
    fontSize: 13,
};
