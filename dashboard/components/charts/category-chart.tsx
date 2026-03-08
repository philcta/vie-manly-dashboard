"use client";

import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
    Area,
    AreaChart,
} from "recharts";
import { formatCurrency } from "@/lib/format";

import type { CategoryDailyData } from "@/lib/queries/overview";

interface CategoryChartProps {
    data: CategoryDailyData[];
    comparisonData: CategoryDailyData[];
}

/**
 * Cafe vs Retail dual-line chart.
 * Per design system: olive solid for Cafe, coral dashed for Retail.
 * Subtle gradient fill under lines.
 */
export function CategoryChart({ data, comparisonData }: CategoryChartProps) {
    // Aggregate by date — combine category rows into daily Cafe vs Retail totals
    const dateMap = new Map<string, { date: string; cafe: number; retail: number }>();

    for (const row of data) {
        const key = row.date;
        if (!dateMap.has(key)) {
            dateMap.set(key, { date: key, cafe: 0, retail: 0 });
        }
        const entry = dateMap.get(key)!;
        if (row.category === "Cafe") {
            entry.cafe += row.total_net_sales;
        } else {
            entry.retail += row.total_net_sales;
        }
    }

    const chartData = Array.from(dateMap.values())
        .sort((a, b) => a.date.localeCompare(b.date))
        .map((d) => ({
            ...d,
            label: new Date(d.date).toLocaleDateString("en-AU", {
                day: "numeric",
                month: "short",
            }),
        }));

    if (chartData.length === 0) {
        return (
            <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
                No category data available for this period
            </div>
        );
    }

    return (
        <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData}>
                <defs>
                    <linearGradient id="cafeGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#6B7355" stopOpacity={0.2} />
                        <stop offset="100%" stopColor="#6B7355" stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="retailGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#E07A5F" stopOpacity={0.2} />
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
                    tickFormatter={(v: number) => `$${(v / 1000).toFixed(1)}K`}
                />
                <Tooltip
                    contentStyle={{
                        background: "white",
                        borderRadius: 8,
                        border: "1px solid #EAEAE8",
                        boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
                        fontSize: 13,
                    }}
                    formatter={(value: number, name: string) => [
                        formatCurrency(value),
                        name === "cafe" ? "Cafe" : "Retail",
                    ]}
                />
                <Legend
                    formatter={(value: string) => (value === "cafe" ? "Cafe" : "Retail")}
                    wrapperStyle={{ fontSize: 12 }}
                />
                <Area
                    type="monotone"
                    dataKey="cafe"
                    stroke="#6B7355"
                    strokeWidth={2}
                    fill="url(#cafeGradient)"
                    animationDuration={1200}
                    animationEasing="ease-out"
                />
                <Area
                    type="monotone"
                    dataKey="retail"
                    stroke="#E07A5F"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    fill="url(#retailGradient)"
                    animationDuration={1200}
                    animationEasing="ease-out"
                />
            </AreaChart>
        </ResponsiveContainer>
    );
}
