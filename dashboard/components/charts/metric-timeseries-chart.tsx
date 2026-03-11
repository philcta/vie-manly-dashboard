"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { ChevronDown } from "lucide-react";
import {
    Area,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip as ChartTooltip,
    ResponsiveContainer,
    Legend,
    ComposedChart,
    Customized,
} from "recharts";
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format";
import type { DailyStats, CategoryDailyData, DailyLabour } from "@/lib/queries/overview";

// ── Metric definitions ──────────────────────────────────────────

export type MetricKey =
    | "net_sales"
    | "customers"
    | "transactions"
    | "avg_sale"
    | "real_profit_pct"
    | "labour_pct";

type SideType = "all" | "cafe" | "retail" | "category";

// Metrics that don't support category filtering (need whole-store data)
const CATEGORY_INCOMPATIBLE: Set<MetricKey> = new Set(["labour_pct", "real_profit_pct", "customers"]);

interface MetricDef {
    label: string;
    shortLabel: string;
    formatter: (v: number) => string;
    yFormatter: (v: number) => string;
    color: string;
    compColor: string;
}

const METRICS: Record<MetricKey, MetricDef> = {
    net_sales: {
        label: "Net Sales",
        shortLabel: "Net Sales",
        formatter: (v) => formatCurrency(v),
        yFormatter: (v) => `$${(v / 1000).toFixed(1)}K`,
        color: "#6B7355",
        compColor: "#E07A5F",
    },
    customers: {
        label: "Customers",
        shortLabel: "Customers",
        formatter: (v) => formatNumber(v),
        yFormatter: (v) => formatNumber(v),
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
    real_profit_pct: {
        label: "Real Profit %",
        shortLabel: "Real Profit %",
        formatter: (v) => formatPercent(v),
        yFormatter: (v) => `${v.toFixed(0)}%`,
        color: "#3B7A57",
        compColor: "#E07A5F",
    },
    labour_pct: {
        label: "Labour vs Sales %",
        shortLabel: "Labour %",
        formatter: (v) => formatPercent(v),
        yFormatter: (v) => `${v.toFixed(0)}%`,
        color: "#6B7355",
        compColor: "#E07A5F",
    },
};

const METRIC_ORDER: MetricKey[] = [
    "net_sales",
    "customers",
    "transactions",
    "avg_sale",
    "real_profit_pct",
    "labour_pct",
];

const SIDE_OPTIONS: { value: SideType; label: string }[] = [
    { value: "all", label: "All" },
    { value: "cafe", label: "Cafe" },
    { value: "retail", label: "Retail" },
    { value: "category", label: "Category" },
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
        sumX += i;
        sumY += values[i];
        sumXY += i * values[i];
        sumXX += i * i;
    }
    const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
    const intercept = (sumY - slope * sumX) / n;

    return values.map((_, i) => Math.round((slope * i + intercept) * 100) / 100);
}

// ── Component props ─────────────────────────────────────────────

interface MetricTimeSeriesChartProps {
    dailyStats: DailyStats[];
    compDailyStats: DailyStats[];
    categoryData: CategoryDailyData[];
    compCategoryData: CategoryDailyData[];
    dailyLabour: DailyLabour[];
    compDailyLabour: DailyLabour[];
    historicalStats: DailyStats[];
    historicalCategoryData: CategoryDailyData[];
    historicalLabour: DailyLabour[];
    /** Effective inventory margin % for computing daily Real Profit % */
    effectiveMargin: number;
    /** Per-category (granular) daily stats for category filter */
    categoryDetailData?: CategoryDailyData[];
}

// ── Helper: format date label ───────────────────────────────────

function dateLabel(dateStr: string): string {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-AU", { day: "numeric", month: "short" });
}

// ── Side label helper ───────────────────────────────────────────

function sideLabel(side: SideType): string {
    return side === "all" ? "" : side === "cafe" ? "Cafe " : side === "retail" ? "Retail " : "";
}

// ── Category multi-select filter dropdown ────────────────────────

function CategoryFilterDropdown({
    options,
    selected,
    onChange,
}: {
    options: string[];
    selected: Set<string>;
    onChange: (next: Set<string>) => void;
}) {
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        };
        document.addEventListener("mousedown", handler);
        return () => document.removeEventListener("mousedown", handler);
    }, []);

    const allSelected = options.length > 0 && selected.size === options.length;

    return (
        <div className="relative" ref={ref}>
            <button
                onClick={() => setOpen(!open)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full transition-colors cursor-pointer border ${selected.size > 0
                    ? "bg-olive text-white border-olive"
                    : "bg-muted text-muted-foreground border-border hover:text-foreground"
                    }`}
            >
                Category{selected.size > 0 && ` (${selected.size})`}
                <ChevronDown size={12} />
            </button>
            {open && (
                <div className="absolute z-50 mt-1 w-64 max-h-80 overflow-y-auto bg-card border border-border rounded-lg shadow-lg p-2 space-y-0.5">
                    {/* Select All / Clear All */}
                    <button
                        onClick={() => {
                            if (allSelected) {
                                onChange(new Set());
                            } else {
                                onChange(new Set(options));
                            }
                        }}
                        className="w-full flex items-center justify-between px-2 py-1.5 text-xs font-semibold rounded hover:bg-muted transition-colors cursor-pointer"
                    >
                        <span className="text-olive">{allSelected ? "Clear all" : "Select all"}</span>
                        <span className="text-muted-foreground text-[10px]">{selected.size}/{options.length}</span>
                    </button>
                    <div className="border-b border-border my-1" />
                    {options.map((opt) => (
                        <label key={opt} className="flex items-center gap-2 px-2 py-1 text-xs cursor-pointer hover:bg-muted rounded">
                            <input
                                type="checkbox"
                                checked={selected.has(opt)}
                                onChange={() => {
                                    const next = new Set(selected);
                                    next.has(opt) ? next.delete(opt) : next.add(opt);
                                    onChange(next);
                                }}
                                className="rounded border-border accent-olive"
                            />
                            {opt}
                        </label>
                    ))}
                </div>
            )}
        </div>
    );
}

// ── Main component ──────────────────────────────────────────────

export function MetricTimeSeriesChart({
    dailyStats,
    compDailyStats,
    categoryData,
    compCategoryData,
    dailyLabour,
    compDailyLabour,
    historicalStats,
    historicalCategoryData,
    historicalLabour,
    effectiveMargin,
    categoryDetailData = [],
}: MetricTimeSeriesChartProps) {
    const [metric, setMetric] = useState<MetricKey>("net_sales");
    const [activeTrends, setActiveTrends] = useState<Set<TrendType>>(new Set(["ma_3mo"]));
    const [side, setSide] = useState<SideType>("all");
    const [selectedCategories, setSelectedCategories] = useState<Set<string>>(new Set());
    const def = METRICS[metric];

    // Build unique category list from detail data
    const allCategories = useMemo(() => {
        const cats = new Set<string>();
        for (const r of categoryDetailData) {
            if (r.category) cats.add(r.category);
        }
        return Array.from(cats).sort();
    }, [categoryDetailData]);

    // When switching to Category mode, ensure we're on a compatible metric
    const handleSideChange = (newSide: SideType) => {
        setSide(newSide);
        if (newSide === "category" && CATEGORY_INCOMPATIBLE.has(metric)) {
            setMetric("net_sales");
        }
    };

    // ── Build chart data based on selected metric + side ──

    const chartData = useMemo(() => {
        return buildMetricData(dailyStats, categoryData, dailyLabour, metric, side, effectiveMargin, categoryDetailData, selectedCategories);
    }, [metric, side, dailyStats, categoryData, dailyLabour, effectiveMargin, categoryDetailData, selectedCategories]);

    const compChartData = useMemo(() => {
        return buildMetricData(compDailyStats, compCategoryData, compDailyLabour, metric, side, effectiveMargin);
    }, [metric, side, compDailyStats, compCategoryData, compDailyLabour, effectiveMargin]);

    // ── Build historical value map for moving averages ──
    const historicalValueMap = useMemo(() => {
        const map = new Map<string, number>();
        const labourMap = new Map<string, number>();
        for (const l of historicalLabour) labourMap.set(l.date, l.labour_cost);

        if (side !== "all" && metric !== "labour_pct" && metric !== "real_profit_pct" && metric !== "customers") {
            // Side-filtered: use category data
            const targetSide = side === "cafe" ? "Cafe" : "Retail";
            const dayAgg = new Map<string, { net: number; gross: number; txn: number }>();
            for (const r of historicalCategoryData) {
                if (r.category !== targetSide) continue;
                const entry = dayAgg.get(r.date) || { net: 0, gross: 0, txn: 0 };
                entry.net += r.total_net_sales;
                entry.gross += r.total_gross_sales;
                entry.txn += r.transaction_count;
                dayAgg.set(r.date, entry);
            }
            for (const [date, agg] of dayAgg) {
                let value = 0;
                switch (metric) {
                    case "net_sales": value = agg.net; break;
                    case "transactions": value = agg.txn; break;
                    case "avg_sale": value = agg.txn > 0 ? agg.net / agg.txn : 0; break;
                }
                map.set(date, value);
            }
        } else {
            // "All" or labour/profit metrics: use total daily stats
            for (const row of historicalStats) {
                let value = 0;
                const lc = labourMap.get(row.date) || 0;
                switch (metric) {
                    case "net_sales": value = row.total_net_sales; break;
                    case "customers": value = row.total_unique_customers || 0; break;
                    case "transactions": value = row.total_transactions; break;
                    case "avg_sale": value = row.total_transactions > 0 ? row.total_net_sales / row.total_transactions : 0; break;
                    case "real_profit_pct":
                        value = row.total_net_sales > 0
                            ? effectiveMargin - (lc / row.total_net_sales * 100)
                            : 0;
                        break;
                    case "labour_pct":
                        value = row.total_net_sales > 0 ? (lc / row.total_net_sales) * 100 : 0;
                        break;
                }
                map.set(row.date, value);
            }
        }
        return map;
    }, [metric, side, historicalStats, historicalCategoryData, historicalLabour, effectiveMargin]);

    // ── Trailing average computation ──
    const computeAvg = useMemo(() => {
        const sortedDates = Array.from(historicalValueMap.keys()).sort();
        const dateIndex = new Map<string, number>();
        sortedDates.forEach((d, i) => dateIndex.set(d, i));

        return (date: string, windowDays: number): number | null => {
            const idx = dateIndex.get(date);
            if (idx === undefined) return null;
            const startIdx = Math.max(0, idx - windowDays + 1);
            if (idx - startIdx < Math.min(windowDays * 0.3, 7)) return null;
            let sum = 0;
            let count = 0;
            for (let i = startIdx; i <= idx; i++) {
                const val = historicalValueMap.get(sortedDates[i]);
                if (val !== undefined) { sum += val; count++; }
            }
            return count > 0 ? Math.round((sum / count) * 100) / 100 : null;
        };
    }, [historicalValueMap]);

    // ── Merge current + comparison + trends ──
    const mergedData = useMemo(() => {
        const values = chartData.map((d: { value?: number }) => d.value ?? 0);

        const linearValues = activeTrends.has("linear") ? linearRegression(values) : null;
        const ma3Values = activeTrends.has("ma_3mo")
            ? chartData.map((d: { date?: string }) => computeAvg(d.date as string, 90))
            : null;

        return chartData.map((row: Record<string, unknown>, i: number) => ({
            ...row,
            comparison: compChartData && compChartData[i] ? (compChartData[i] as { value: number }).value : undefined,
            trend_linear: linearValues ? linearValues[i] : undefined,
            trend_ma3: ma3Values ? ma3Values[i] : undefined,
        }));
    }, [chartData, compChartData, activeTrends, computeAvg]);

    // ── Trend badge computation (only for 3mo avg, not linear) ──
    const trendBadge = useMemo(() => {
        if (!activeTrends.has("ma_3mo")) return null;
        const trendVals = mergedData
            .map((d: Record<string, unknown>) => d.trend_ma3 as number | null | undefined)
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
                <p className="text-muted-foreground text-sm text-center py-12">
                    No data available for this period
                </p>
            </div>
        );
    }

    // Dynamic title based on side + metric
    const title = side === "all" ? def.label
        : side === "category" ? (selectedCategories.size > 0 ? `${selectedCategories.size} Categories — ${def.label}` : def.label)
            : `${side === "cafe" ? "Cafe" : "Retail"} — ${def.label}`;

    return (
        <div
            className="bg-card rounded-xl border border-border p-6"
            style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}
        >
            {/* Row 1: Title */}
            <h2 className="text-lg font-semibold text-foreground mb-4">
                {title}
            </h2>

            {/* Row 2: Controls — Side toggle | Trend pills | Metric pills */}
            <div className="flex flex-wrap items-center gap-3 mb-5">
                {/* Side toggle */}
                <div className="flex items-center gap-1 rounded-lg border border-border bg-background p-0.5">
                    {SIDE_OPTIONS.map((opt) => (
                        <button
                            key={opt.value}
                            onClick={() => handleSideChange(opt.value)}
                            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200 cursor-pointer whitespace-nowrap ${side === opt.value
                                ? "bg-[#3B4A2A] text-white shadow-sm"
                                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                                }`}
                        >
                            {opt.label}
                        </button>
                    ))}
                </div>

                {/* Category multi-select filter (visible when side === "category") */}
                {side === "category" && (
                    <CategoryFilterDropdown
                        options={allCategories}
                        selected={selectedCategories}
                        onChange={setSelectedCategories}
                    />
                )}

                <div className="w-px h-5 bg-border" />

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
                    {METRIC_ORDER.map((key) => {
                        const disabled = side === "category" && CATEGORY_INCOMPATIBLE.has(key);
                        return (
                            <button
                                key={key}
                                onClick={() => !disabled && setMetric(key)}
                                disabled={disabled}
                                className={`px-2 py-1 text-xs font-medium rounded-md transition-all duration-200 whitespace-nowrap ${disabled
                                    ? "text-muted-foreground/40 cursor-not-allowed"
                                    : metric === key
                                        ? "bg-olive text-white shadow-sm cursor-pointer"
                                        : "text-muted-foreground hover:text-foreground hover:bg-muted/50 cursor-pointer"
                                    }`}
                            >
                                {METRICS[key].shortLabel}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Chart with floating badge overlay */}
            <div className="relative">
                {/* Floating trend badge — centered above chart */}
                {trendBadge && (
                    <div className="absolute top-2 left-1/2 -translate-x-1/2 z-10 pointer-events-none">
                        <div
                            className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold shadow-lg backdrop-blur-md border ${trendBadge.isPositive
                                ? "bg-positive/12 text-positive border-positive/20"
                                : "bg-coral/12 text-coral border-coral/20"
                                }`}
                            style={{
                                backdropFilter: "blur(12px)",
                                WebkitBackdropFilter: "blur(12px)",
                            }}
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
                            <linearGradient id="tsGradMain" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={def.color} stopOpacity={0.18} />
                                <stop offset="100%" stopColor={def.color} stopOpacity={0.02} />
                            </linearGradient>
                            <linearGradient id="tsGradComp" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={def.compColor} stopOpacity={0.12} />
                                <stop offset="100%" stopColor={def.compColor} stopOpacity={0.02} />
                            </linearGradient>
                        </defs>
                        {/* Weekend shading via Customized SVG */}
                        <Customized
                            component={(props: Record<string, unknown>) => {
                                const xAxisMap = props.xAxisMap as Record<string, { x: number; width: number; categoricalDomain?: string[]; scale?: (v: string) => number; bandSize?: number }> | undefined;
                                const yAxisMap = props.yAxisMap as Record<string, { y: number; height: number }> | undefined;
                                if (!xAxisMap || !yAxisMap) return null;
                                const xAxis = Object.values(xAxisMap)[0];
                                const yAxis = Object.values(yAxisMap)[0];
                                if (!xAxis?.scale || !yAxis) return null;
                                const bandSize = xAxis.bandSize || (xAxis.width / (mergedData.length || 1));
                                return (
                                    <g>
                                        {mergedData.map((d: Record<string, unknown>, i: number) => {
                                            const dateStr = d.date as string;
                                            const day = new Date(dateStr).getDay();
                                            if (day !== 0 && day !== 6) return null;
                                            const label = d.label as string;
                                            const cx = xAxis.scale ? xAxis.scale(label) : undefined;
                                            if (cx === undefined) return null;
                                            return (
                                                <rect
                                                    key={`wknd-${i}`}
                                                    x={cx - bandSize / 2}
                                                    y={yAxis.y}
                                                    width={bandSize}
                                                    height={yAxis.height}
                                                    fill="#D4A574"
                                                    fillOpacity={0.12}
                                                />
                                            );
                                        })}
                                    </g>
                                );
                            }}
                        />
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
                        <ChartTooltip
                            contentStyle={tooltipStyle}
                            formatter={(value: number, name: string) => {
                                const nameMap: Record<string, string> = {
                                    value: "Current",
                                    comparison: "Prior",
                                    trend_linear: "Trend",
                                    trend_ma3: "3mo Avg",
                                };
                                return [def.formatter(value), nameMap[name] || name];
                            }}
                        />
                        <Legend
                            formatter={(v: string) => {
                                const nameMap: Record<string, string> = {
                                    value: "Current period",
                                    comparison: "Prior period",
                                    trend_linear: "Trend",
                                    trend_ma3: "3mo Avg",
                                };
                                return nameMap[v] || v;
                            }}
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
                        {/* Linear trend line */}
                        {activeTrends.has("linear") && (
                            <Line
                                type="linear"
                                dataKey="trend_linear"
                                stroke="#3B4A2A"
                                strokeWidth={2}
                                strokeDasharray="8 4"
                                dot={false}
                                connectNulls
                                animationDuration={400}
                            />
                        )}
                        {/* 3mo moving average line */}
                        {activeTrends.has("ma_3mo") && (
                            <Line
                                type="monotone"
                                dataKey="trend_ma3"
                                stroke="#7C6F5B"
                                strokeWidth={2}
                                strokeDasharray="4 3"
                                dot={false}
                                connectNulls
                                animationDuration={400}
                            />
                        )}
                    </ComposedChart>
                </ResponsiveContainer>
            </div>
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

// ── Data builder ────────────────────────────────────────────────

function buildMetricData(
    stats: DailyStats[],
    categoryData: CategoryDailyData[],
    labour: DailyLabour[],
    metric: MetricKey,
    side: SideType,
    effectiveMargin: number,
    categoryDetailData?: CategoryDailyData[],
    selectedCategories?: Set<string>,
) {
    const labourMap = new Map<string, number>();
    for (const l of labour) labourMap.set(l.date, l.labour_cost);

    // For category-filtered metrics, build from categoryDetailData
    if (side === "category" && categoryDetailData && selectedCategories && selectedCategories.size > 0) {
        const dayAgg = new Map<string, { date: string; net: number; gross: number; txn: number }>();
        for (const r of categoryDetailData) {
            if (!selectedCategories.has(r.category)) continue;
            const entry = dayAgg.get(r.date) || { date: r.date, net: 0, gross: 0, txn: 0 };
            entry.net += r.total_net_sales;
            entry.gross += r.total_gross_sales;
            entry.txn += r.transaction_count;
            dayAgg.set(r.date, entry);
        }
        return Array.from(dayAgg.values())
            .sort((a, b) => a.date.localeCompare(b.date))
            .map((agg) => {
                let value = 0;
                switch (metric) {
                    case "net_sales": value = agg.net; break;
                    case "transactions": value = agg.txn; break;
                    case "avg_sale": value = agg.txn > 0 ? Math.round((agg.net / agg.txn) * 100) / 100 : 0; break;
                }
                return { date: agg.date, label: dateLabel(agg.date), value };
            });
    }

    // For side-filtered sales metrics (Cafe / Retail), build from categoryData
    if ((side === "cafe" || side === "retail") && metric !== "labour_pct" && metric !== "real_profit_pct" && metric !== "customers") {
        const targetSide = side === "cafe" ? "Cafe" : "Retail";
        const dayAgg = new Map<string, { date: string; net: number; gross: number; txn: number }>();
        for (const r of categoryData) {
            if (r.category !== targetSide) continue;
            const entry = dayAgg.get(r.date) || { date: r.date, net: 0, gross: 0, txn: 0 };
            entry.net += r.total_net_sales;
            entry.gross += r.total_gross_sales;
            entry.txn += r.transaction_count;
            dayAgg.set(r.date, entry);
        }
        return Array.from(dayAgg.values())
            .sort((a, b) => a.date.localeCompare(b.date))
            .map((agg) => {
                let value = 0;
                switch (metric) {
                    case "net_sales": value = agg.net; break;
                    case "transactions": value = agg.txn; break;
                    case "avg_sale": value = agg.txn > 0 ? Math.round((agg.net / agg.txn) * 100) / 100 : 0; break;
                }
                return { date: agg.date, label: dateLabel(agg.date), value };
            });
    }

    // "all" side or labour/profit metrics: use total stats
    return stats.map((row) => {
        let value = 0;
        const lc = labourMap.get(row.date) || 0;
        switch (metric) {
            case "net_sales":
                value = row.total_net_sales;
                break;
            case "customers":
                value = row.total_unique_customers || 0;
                break;
            case "transactions":
                value = row.total_transactions;
                break;
            case "avg_sale":
                value = row.total_transactions > 0
                    ? Math.round((row.total_net_sales / row.total_transactions) * 100) / 100
                    : 0;
                break;
            case "real_profit_pct":
                value = row.total_net_sales > 0
                    ? Math.round((effectiveMargin - (lc / row.total_net_sales * 100)) * 100) / 100
                    : 0;
                break;
            case "labour_pct":
                value = row.total_net_sales > 0
                    ? Math.round((lc / row.total_net_sales) * 10000) / 100
                    : 0;
                break;
        }
        return { date: row.date, label: dateLabel(row.date), value };
    });
}
