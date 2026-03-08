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

// ── Metric definitions ──────────────────────────────────────────

export type MemberMetricKey =
    | "member_vs_nonmember"
    | "member_sales"
    | "member_transactions"
    | "member_ratio_sales"
    | "member_ratio_tx"
    | "unique_members";

interface MetricDef {
    label: string;
    shortLabel: string;
    formatter: (v: number) => string;
    yFormatter: (v: number) => string;
    color: string;
    compColor: string;
}

const METRICS: Record<MemberMetricKey, MetricDef> = {
    member_vs_nonmember: {
        label: "Member vs Non-Member Revenue",
        shortLabel: "Member vs Non",
        formatter: (v) => formatCurrency(v),
        yFormatter: (v) => `$${(v / 1000).toFixed(1)}K`,
        color: "#6B7355",
        compColor: "#E07A5F",
    },
    member_sales: {
        label: "Member Net Sales",
        shortLabel: "Member Sales",
        formatter: (v) => formatCurrency(v),
        yFormatter: (v) => `$${(v / 1000).toFixed(1)}K`,
        color: "#6B7355",
        compColor: "#E07A5F",
    },
    member_transactions: {
        label: "Member Transactions",
        shortLabel: "Member Tx",
        formatter: (v) => formatNumber(v),
        yFormatter: (v) => formatNumber(v),
        color: "#6B7355",
        compColor: "#E07A5F",
    },
    member_ratio_sales: {
        label: "Member Sales Ratio",
        shortLabel: "Sales %",
        formatter: (v) => formatPercent(v),
        yFormatter: (v) => `${v.toFixed(0)}%`,
        color: "#6B7355",
        compColor: "#E07A5F",
    },
    member_ratio_tx: {
        label: "Member Transaction Ratio",
        shortLabel: "Tx %",
        formatter: (v) => formatPercent(v),
        yFormatter: (v) => `${v.toFixed(0)}%`,
        color: "#6B7355",
        compColor: "#E07A5F",
    },
    unique_members: {
        label: "Unique Members per Day",
        shortLabel: "Unique Members",
        formatter: (v) => formatNumber(v),
        yFormatter: (v) => formatNumber(v),
        color: "#6B7355",
        compColor: "#E07A5F",
    },
};

const METRIC_ORDER: MemberMetricKey[] = [
    "member_vs_nonmember",
    "member_sales",
    "member_transactions",
    "member_ratio_sales",
    "member_ratio_tx",
    "unique_members",
];

// ── Data types ──────────────────────────────────────────────────

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

interface MemberMetricChartProps {
    data: MemberDailyRow[];
    compData: MemberDailyRow[];
}

function dateLabel(dateStr: string): string {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-AU", { day: "numeric", month: "short" });
}

// ── Main component ──────────────────────────────────────────────

export function MemberMetricChart({ data, compData }: MemberMetricChartProps) {
    const [metric, setMetric] = useState<MemberMetricKey>("member_vs_nonmember");
    const def = METRICS[metric];

    const chartData = useMemo(() => {
        if (metric === "member_vs_nonmember") {
            return data.map((r) => ({
                label: dateLabel(r.date),
                member: r.member_net_sales,
                nonMember: r.non_member_net_sales,
            }));
        }

        const getValue = (r: MemberDailyRow) => {
            switch (metric) {
                case "member_sales": return r.member_net_sales;
                case "member_transactions": return r.member_transactions;
                case "member_ratio_sales": return r.member_sales_ratio * 100;
                case "member_ratio_tx": return r.member_tx_ratio * 100;
                case "unique_members": return r.member_unique_customers;
                default: return 0;
            }
        };

        return data.map((r, i) => ({
            label: dateLabel(r.date),
            value: getValue(r),
            comparison: compData[i] ? getValue(compData[i]) : undefined,
        }));
    }, [metric, data, compData]);

    if (chartData.length === 0) {
        return (
            <div className="bg-card rounded-xl border border-border p-6" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                <p className="text-muted-foreground text-sm text-center py-12">No data available</p>
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

    return (
        <div className="bg-card rounded-xl border border-border p-6" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
            <div className="flex items-center justify-between mb-5">
                <h2 className="text-lg font-semibold text-foreground">{def.label}</h2>
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

            <ResponsiveContainer width="100%" height={300}>
                {metric === "member_vs_nonmember" ? (
                    <AreaChart data={chartData}>
                        <defs>
                            <linearGradient id="memGradM" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#6B7355" stopOpacity={0.15} />
                                <stop offset="100%" stopColor="#6B7355" stopOpacity={0.02} />
                            </linearGradient>
                            <linearGradient id="memGradN" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#E07A5F" stopOpacity={0.15} />
                                <stop offset="100%" stopColor="#E07A5F" stopOpacity={0.02} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#F0F0EE" vertical={false} />
                        <XAxis dataKey="label" tick={{ fill: "#8A8A8A", fontSize: 11 }} axisLine={{ stroke: "#EAEAE8" }} tickLine={false} />
                        <YAxis tick={{ fill: "#8A8A8A", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={def.yFormatter} />
                        <Tooltip contentStyle={tooltipStyle} formatter={(v: number, name: string) => [def.formatter(v), name === "member" ? "Member" : "Non-Member"]} />
                        <Legend formatter={(v: string) => (v === "member" ? "Member" : "Non-Member")} wrapperStyle={{ fontSize: 12 }} />
                        <Area type="monotone" dataKey="member" stroke="#6B7355" strokeWidth={2} fill="url(#memGradM)" animationDuration={800} />
                        <Area type="monotone" dataKey="nonMember" stroke="#E07A5F" strokeWidth={2} strokeDasharray="5 5" fill="url(#memGradN)" animationDuration={800} />
                    </AreaChart>
                ) : (
                    <AreaChart data={chartData}>
                        <defs>
                            <linearGradient id="memGradSingle" x1="0" y1="0" x2="0" y2="1">
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
                        <Tooltip contentStyle={tooltipStyle} formatter={(v: number, name: string) => [def.formatter(v), name === "value" ? "Current" : "Prior"]} />
                        <Legend formatter={(v: string) => (v === "value" ? "Current period" : "Prior period")} wrapperStyle={{ fontSize: 12 }} />
                        <Area type="monotone" dataKey="comparison" stroke={def.compColor} strokeWidth={1.5} strokeDasharray="5 5" strokeOpacity={0.6} fill="url(#memGradComp)" animationDuration={800} />
                        <Area type="monotone" dataKey="value" stroke={def.color} strokeWidth={2.5} fill="url(#memGradSingle)" animationDuration={800} />
                    </AreaChart>
                )}
            </ResponsiveContainer>
        </div>
    );
}
