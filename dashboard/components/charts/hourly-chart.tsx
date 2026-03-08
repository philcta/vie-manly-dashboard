"use client";

import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
} from "recharts";
import { formatHour, formatCurrency } from "@/lib/format";
import type { HourlyData } from "@/lib/queries/overview";

interface HourlyChartProps {
    data: HourlyData[];
    comparisonData: HourlyData[];
    title: string;
}

/**
 * Hourly bar chart — grouped bars for current vs comparison period.
 * Per design system: olive #6B7355 for current, sage #A8B094 for comparison.
 * Per ui-ux-pro-max chart guidance: add value labels on bars for clarity.
 */
export function HourlyChart({ data, comparisonData, title }: HourlyChartProps) {
    // Merge current and comparison data into unified hourly buckets (7am-6pm)
    const hours = Array.from({ length: 12 }, (_, i) => i + 7);

    const chartData = hours.map((hour) => {
        const current = data.find((d) => d.hour === hour);
        const comp = comparisonData.find((d) => d.hour === hour);
        return {
            hour,
            label: formatHour(hour),
            current: current?.transactions ?? 0,
            currentSales: current?.net_sales ?? 0,
            comparison: comp?.transactions ?? 0,
            compSales: comp?.net_sales ?? 0,
        };
    });

    return (
        <div
            className="bg-card rounded-xl border border-border p-6"
            style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}
        >
            <h3 className="text-base font-semibold text-foreground mb-4">{title}</h3>
            <ResponsiveContainer width="100%" height={280}>
                <BarChart data={chartData} barGap={2} barCategoryGap="20%">
                    <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="#F0F0EE"
                        vertical={false}
                    />
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
                            value,
                            name === "current" ? "Today" : "Comparison",
                        ]}
                    />
                    <Legend
                        formatter={(value: string) =>
                            value === "current" ? "Today" : "Comparison"
                        }
                        wrapperStyle={{ fontSize: 12 }}
                    />
                    <Bar
                        dataKey="current"
                        fill="#6B7355"
                        radius={[4, 4, 0, 0]}
                        animationDuration={600}
                        animationEasing="ease-out"
                    />
                    <Bar
                        dataKey="comparison"
                        fill="#A8B094"
                        radius={[4, 4, 0, 0]}
                        animationDuration={600}
                        animationEasing="ease-out"
                    />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}
