"use client";

import { useState, useMemo } from "react";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell,
} from "recharts";
import { formatPercent, formatCurrency } from "@/lib/format";

interface CategoryMargin {
    scope: string;
    side: string;
    margin_pct: number;
    stock_value: number;
    product_count: number;
}

interface CategoryMarginChartProps {
    data: CategoryMargin[];
}

// Color palette for bars
const BAR_COLORS = {
    Cafe: "#6B7355",
    Retail: "#8A9166",
    Unknown: "#B8B8C8",
};

export function CategoryMarginChart({ data }: CategoryMarginChartProps) {
    const [selectedSide, setSelectedSide] = useState<"All" | "Cafe" | "Retail">("All");
    const [sortBy, setSortBy] = useState<"margin" | "value" | "alpha">("margin");

    const filtered = useMemo(() => {
        let items = data.filter(d => d.scope !== "overall" && d.scope !== "");
        if (selectedSide !== "All") {
            items = items.filter(d => d.side === selectedSide);
        }

        switch (sortBy) {
            case "margin":
                items.sort((a, b) => b.margin_pct - a.margin_pct);
                break;
            case "value":
                items.sort((a, b) => b.stock_value - a.stock_value);
                break;
            case "alpha":
                items.sort((a, b) => a.scope.localeCompare(b.scope));
                break;
        }

        return items;
    }, [data, selectedSide, sortBy]);

    const avgMargin = filtered.length > 0
        ? filtered.reduce((s, d) => s + d.margin_pct, 0) / filtered.length
        : 0;

    return (
        <div
            className="bg-card rounded-xl border border-border overflow-hidden"
            style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}
        >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
                <div>
                    <h3 className="text-base font-semibold text-foreground">
                        Profit Margins by Category
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                        Avg: {formatPercent(avgMargin)} across {filtered.length} categories
                    </p>
                </div>

                {/* Controls */}
                <div className="flex items-center gap-3">
                    {/* Side filter */}
                    <div className="flex items-center gap-1 rounded-lg border border-border bg-background p-0.5">
                        {(["All", "Cafe", "Retail"] as const).map((side) => (
                            <button
                                key={side}
                                onClick={() => setSelectedSide(side)}
                                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200 cursor-pointer ${selectedSide === side
                                    ? "bg-olive text-white shadow-sm"
                                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                                    }`}
                            >
                                {side}
                            </button>
                        ))}
                    </div>

                    {/* Sort */}
                    <select
                        value={sortBy}
                        onChange={(e) => setSortBy(e.target.value as "margin" | "value" | "alpha")}
                        className="text-xs border border-border rounded-md px-2 py-1.5 bg-background text-foreground cursor-pointer"
                    >
                        <option value="margin">Sort: Margin %</option>
                        <option value="value">Sort: Stock Value</option>
                        <option value="alpha">Sort: A–Z</option>
                    </select>
                </div>
            </div>

            {/* Scrollable table-style chart */}
            <div className="overflow-y-auto" style={{ maxHeight: 480 }}>
                <table className="w-full">
                    <thead className="sticky top-0 bg-[#FAFAF8] z-10">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-body w-[220px]">
                                Category
                            </th>
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-body w-[60px]">
                                Side
                            </th>
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-body">
                                Margin
                            </th>
                            <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-text-body w-[80px]">
                                %
                            </th>
                            <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-text-body w-[90px]">
                                Stock Value
                            </th>
                            <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-text-body w-[60px]">
                                Items
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {filtered.map((item, i) => {
                            const barWidth = Math.max(item.margin_pct, 1);
                            const barColor = BAR_COLORS[item.side as keyof typeof BAR_COLORS] || BAR_COLORS.Unknown;
                            return (
                                <tr
                                    key={item.scope}
                                    className="border-b border-[#F0F0EE] row-hover transition-colors"
                                >
                                    <td className="px-6 py-2.5 text-sm font-medium text-foreground truncate max-w-[220px]" title={item.scope}>
                                        {item.scope}
                                    </td>
                                    <td className="px-4 py-2.5">
                                        <span className={`inline-block text-[10px] font-semibold px-2 py-0.5 rounded-full ${item.side === "Cafe"
                                            ? "bg-olive/10 text-olive"
                                            : item.side === "Retail"
                                                ? "bg-[#E07A5F]/10 text-[#E07A5F]"
                                                : "bg-muted text-muted-foreground"
                                            }`}>
                                            {item.side}
                                        </span>
                                    </td>
                                    <td className="px-4 py-2.5">
                                        <div className="w-full bg-[#F0F0EE] rounded-full h-[10px] overflow-hidden">
                                            <div
                                                className="h-full rounded-full transition-all duration-500"
                                                style={{
                                                    width: `${barWidth}%`,
                                                    backgroundColor: barColor,
                                                    opacity: 0.8,
                                                }}
                                            />
                                        </div>
                                    </td>
                                    <td className="px-4 py-2.5 text-sm tabular-nums text-right font-medium text-foreground">
                                        {item.margin_pct.toFixed(1)}%
                                    </td>
                                    <td className="px-4 py-2.5 text-sm tabular-nums text-right text-text-body">
                                        {formatCurrency(item.stock_value, 0)}
                                    </td>
                                    <td className="px-4 py-2.5 text-sm tabular-nums text-right text-text-body">
                                        {item.product_count}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {/* Footer */}
            <div className="px-6 py-3 border-t border-border bg-[#FAFAF8] text-xs text-muted-foreground">
                {filtered.length} categories · Avg margin: {formatPercent(avgMargin)}
            </div>
        </div>
    );
}
