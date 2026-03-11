"use client";

import { useState, useMemo } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";
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

type SortKey = "scope" | "side" | "margin_pct" | "stock_value" | "product_count";

export function CategoryMarginChart({ data }: CategoryMarginChartProps) {
    const [selectedSide, setSelectedSide] = useState<"All" | "Cafe" | "Retail">("All");
    const [sortKey, setSortKey] = useState<SortKey>("margin_pct");
    const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

    const handleSort = (key: SortKey) => {
        if (sortKey === key) {
            setSortDir(sortDir === "asc" ? "desc" : "asc");
        } else {
            setSortKey(key);
            setSortDir(key === "scope" || key === "side" ? "asc" : "desc");
        }
    };

    const filtered = useMemo(() => {
        let items = data.filter(d => d.scope !== "overall" && d.scope !== "");
        if (selectedSide !== "All") {
            items = items.filter(d => d.side === selectedSide);
        }

        const sorted = [...items].sort((a, b) => {
            const aVal = a[sortKey];
            const bVal = b[sortKey];
            let cmp = 0;
            if (typeof aVal === "string" && typeof bVal === "string") {
                cmp = aVal.localeCompare(bVal);
            } else {
                cmp = (Number(aVal) || 0) - (Number(bVal) || 0);
            }
            return sortDir === "asc" ? cmp : -cmp;
        });

        return sorted;
    }, [data, selectedSide, sortKey, sortDir]);

    const avgMargin = filtered.length > 0
        ? filtered.reduce((s, d) => s + d.margin_pct, 0) / filtered.length
        : 0;

    const SortIcon = ({ colKey }: { colKey: SortKey }) => {
        if (sortKey === colKey) {
            return sortDir === "asc"
                ? <ChevronUp className="w-3.5 h-3.5 text-olive" />
                : <ChevronDown className="w-3.5 h-3.5 text-olive" />;
        }
        return <ChevronsUpDown className="w-3.5 h-3.5 opacity-30" />;
    };

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
            </div>

            {/* Table */}
            <div className="overflow-y-auto" style={{ maxHeight: 480 }}>
                <table className="w-full">
                    <thead className="sticky top-0 bg-[#FAFAF8] z-10">
                        <tr>
                            <th
                                onClick={() => handleSort("scope")}
                                className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-body w-[220px] cursor-pointer select-none hover:text-foreground transition-colors"
                            >
                                <span className="inline-flex items-center gap-1">
                                    Category <SortIcon colKey="scope" />
                                </span>
                            </th>
                            <th
                                onClick={() => handleSort("side")}
                                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-body w-[60px] cursor-pointer select-none hover:text-foreground transition-colors"
                            >
                                <span className="inline-flex items-center gap-1">
                                    Side <SortIcon colKey="side" />
                                </span>
                            </th>
                            <th
                                onClick={() => handleSort("margin_pct")}
                                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-body cursor-pointer select-none hover:text-foreground transition-colors"
                            >
                                <span className="inline-flex items-center gap-1">
                                    Margin <SortIcon colKey="margin_pct" />
                                </span>
                            </th>
                            <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-text-body w-[80px]">
                                %
                            </th>
                            <th
                                onClick={() => handleSort("stock_value")}
                                className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-text-body w-[90px] cursor-pointer select-none hover:text-foreground transition-colors"
                            >
                                <span className="inline-flex items-center gap-1 justify-end">
                                    Stock Value <SortIcon colKey="stock_value" />
                                </span>
                            </th>
                            <th
                                onClick={() => handleSort("product_count")}
                                className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-text-body w-[60px] cursor-pointer select-none hover:text-foreground transition-colors"
                            >
                                <span className="inline-flex items-center gap-1 justify-end">
                                    Items <SortIcon colKey="product_count" />
                                </span>
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {filtered.map((item) => {
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
