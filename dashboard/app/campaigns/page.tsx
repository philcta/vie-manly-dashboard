"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import KpiCard from "@/components/kpi-card";
import { supabase } from "@/lib/supabase";
import { formatCurrency, formatPercent, formatNumber } from "@/lib/format";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from "recharts";

interface Campaign {
    id: number;
    name: string;
    status: string;
    enrolled_count: number;
    sent_count: number;
    return_rate: number;
    net_sales_impact: number;
    roi: number;
}

interface Enrollment {
    member_name: string;
    campaign_name: string;
    enrolled_count: number;
    sms_status: string;
    sales_after: number;
}

export default function CampaignsPage() {
    const [loading, setLoading] = useState(true);
    const [campaigns, setCampaigns] = useState<Campaign[]>([]);
    const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
    const [activeCampaigns, setActiveCampaigns] = useState(0);
    const [totalReached, setTotalReached] = useState(0);
    const [avgReturnRate, setAvgReturnRate] = useState(0);
    const [revenueImpact, setRevenueImpact] = useState(0);

    const loadData = useCallback(async () => {
        setLoading(true);
        try {
            // Fetch campaign summaries
            const { data: campData, error: campErr } = await supabase
                .from("sms_campaign_summary")
                .select("*")
                .order("campaign_id", { ascending: true });

            if (campErr) {
                // Fallback if table doesn't exist — use sms_campaigns
                const { data: fallback } = await supabase
                    .from("sms_campaigns")
                    .select("*")
                    .order("id", { ascending: true });

                if (fallback) {
                    const mapped: Campaign[] = fallback.map((c) => ({
                        id: c.id,
                        name: c.name || c.campaign_name || "Unnamed",
                        status: c.status || "Draft",
                        enrolled_count: c.enrolled_count || 0,
                        sent_count: c.sent_count || 0,
                        return_rate: c.return_rate || 0,
                        net_sales_impact: c.net_sales_impact || 0,
                        roi: c.roi || 0,
                    }));
                    setCampaigns(mapped);
                    computeKPIs(mapped);
                }
            } else if (campData) {
                const mapped: Campaign[] = campData.map((c) => ({
                    id: c.campaign_id || c.id,
                    name: c.campaign_name || c.name || "Unnamed",
                    status: c.status || "Active",
                    enrolled_count: c.enrolled_count || 0,
                    sent_count: c.sent_count || 0,
                    return_rate: c.return_rate || 0,
                    net_sales_impact: c.net_sales_impact || 0,
                    roi: c.roi || 0,
                }));
                setCampaigns(mapped);
                computeKPIs(mapped);
            }

            // Fetch recent enrollments
            const { data: enrData } = await supabase
                .from("sms_campaign_enrollments")
                .select("*")
                .order("id", { ascending: false })
                .limit(10);

            if (enrData) {
                setEnrollments(
                    enrData.map((e) => ({
                        member_name: e.member_name || "Unknown",
                        campaign_name: e.campaign_name || "—",
                        enrolled_count: e.enrolled_count || 0,
                        sms_status: e.sms_status || "Pending",
                        sales_after: e.sales_after || 0,
                    }))
                );
            }
        } catch (err) {
            console.error("Failed to load campaigns:", err);
        } finally {
            setLoading(false);
        }
    }, []);

    function computeKPIs(camps: Campaign[]) {
        const active = camps.filter((c) => c.status === "Active").length;
        const reached = camps.reduce((s, c) => s + c.sent_count, 0);
        const avgRate = camps.length > 0
            ? camps.reduce((s, c) => s + c.return_rate, 0) / camps.length
            : 0;
        const revenue = camps.reduce((s, c) => s + c.net_sales_impact, 0);

        setActiveCampaigns(active);
        setTotalReached(reached);
        setAvgReturnRate(avgRate);
        setRevenueImpact(revenue);
    }

    useEffect(() => {
        loadData();
    }, [loadData]);

    const statusBadge = (status: string) => {
        switch (status) {
            case "Active":
                return "bg-positive text-white";
            case "Completed":
                return "bg-muted text-muted-foreground";
            case "Delivered":
                return "bg-positive text-white";
            case "Pending":
                return "bg-warning text-white";
            case "Failed":
                return "bg-coral text-white";
            default:
                return "bg-muted text-muted-foreground";
        }
    };

    // Contact frequency chart
    const contactData = [
        { label: "Never", count: 1240 },
        { label: "1 campaign", count: 380 },
        { label: "2 campaigns", count: 215 },
        { label: "3+ campaigns", count: 52 },
    ];

    return (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="space-y-8">
            <div className="flex items-center justify-between">
                <h1 className="text-[28px] font-bold text-foreground">SMS Campaigns</h1>
                <button className="px-4 py-2 bg-olive text-white text-sm font-semibold rounded-lg hover:bg-olive-dark transition-colors duration-200 cursor-pointer">
                    + New Campaign
                </button>
            </div>

            <div className="grid grid-cols-4 gap-5">
                <KpiCard label="Active Campaigns" value={activeCampaigns} formatter={(n) => formatNumber(n)} delay={0} />
                <KpiCard label="Total Reached" value={totalReached} formatter={(n) => formatNumber(n)} delay={1} />
                <KpiCard label="Avg Return Rate" value={avgReturnRate} formatter={(n) => formatPercent(n)} delay={2} />
                <KpiCard label="Revenue Impact" value={revenueImpact} formatter={(n) => formatCurrency(n, 0)} delay={3} />
            </div>

            {/* Campaign Performance Table */}
            <div className="bg-card rounded-xl border border-border overflow-hidden" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                <div className="px-6 py-4 border-b border-border">
                    <h3 className="text-base font-semibold text-foreground">Campaign Performance</h3>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="bg-[#FAFAF8]">
                                {["Campaign", "Status", "Enrolled", "Sent", "Return Rate", "Net Sales", "ROI"].map((h) => (
                                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-body">{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {campaigns.map((c, i) => (
                                <tr key={i} className="border-b border-[#F0F0EE] row-hover">
                                    <td className="px-4 py-3 text-sm font-medium text-foreground">{c.name}</td>
                                    <td className="px-4 py-3"><span className={`inline-block text-xs font-semibold px-2.5 py-0.5 rounded-full ${statusBadge(c.status)}`}>{c.status}</span></td>
                                    <td className="px-4 py-3 text-sm tabular-nums">{c.enrolled_count}</td>
                                    <td className="px-4 py-3 text-sm tabular-nums">{c.sent_count}</td>
                                    <td className="px-4 py-3 text-sm tabular-nums">{formatPercent(c.return_rate)}</td>
                                    <td className="px-4 py-3 text-sm tabular-nums font-medium">{formatCurrency(c.net_sales_impact)}</td>
                                    <td className="px-4 py-3 text-sm tabular-nums font-medium">{c.roi.toFixed(1)}x</td>
                                </tr>
                            ))}
                            {campaigns.length === 0 && (
                                <tr>
                                    <td colSpan={7} className="px-4 py-8 text-center text-sm text-muted-foreground">
                                        No campaigns yet. Click &quot;+ New Campaign&quot; to create one.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Contact Frequency Chart */}
            <div className="bg-card rounded-xl border border-border p-6" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                <h3 className="text-base font-semibold text-foreground mb-4">Member Contact Frequency</h3>
                <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={contactData} layout="vertical" barSize={20}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#F0F0EE" horizontal={false} />
                        <XAxis type="number" tick={{ fill: "#8A8A8A", fontSize: 11 }} axisLine={false} tickLine={false} />
                        <YAxis dataKey="label" type="category" tick={{ fill: "#8A8A8A", fontSize: 12 }} axisLine={false} tickLine={false} width={100} />
                        <Tooltip contentStyle={{ background: "white", borderRadius: 8, border: "1px solid #EAEAE8", fontSize: 13 }} />
                        <Bar dataKey="count" fill="#6B7355" radius={[0, 4, 4, 0]} animationDuration={600} />
                    </BarChart>
                </ResponsiveContainer>
            </div>

            {/* Recent Enrollments */}
            {enrollments.length > 0 && (
                <div className="bg-card rounded-xl border border-border overflow-hidden" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                    <div className="px-6 py-4 border-b border-border">
                        <h3 className="text-base font-semibold text-foreground">Recent Enrollments</h3>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="bg-[#FAFAF8]">
                                    {["Member", "Campaign", "SMS Status", "Sales After"].map((h) => (
                                        <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-body">{h}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {enrollments.map((e, i) => (
                                    <tr key={i} className="border-b border-[#F0F0EE] row-hover">
                                        <td className="px-4 py-3 text-sm font-medium text-foreground">{e.member_name}</td>
                                        <td className="px-4 py-3 text-sm text-text-body">{e.campaign_name}</td>
                                        <td className="px-4 py-3"><span className={`inline-block text-xs font-semibold px-2.5 py-0.5 rounded-full ${statusBadge(e.sms_status)}`}>{e.sms_status}</span></td>
                                        <td className="px-4 py-3 text-sm tabular-nums">{formatCurrency(e.sales_after)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {loading && (
                <div className="fixed inset-0 ml-[220px] bg-background/80 flex items-center justify-center z-40">
                    <div className="flex items-center gap-3 text-muted-foreground">
                        <div className="w-5 h-5 border-2 border-olive/30 border-t-olive rounded-full animate-spin" />
                        <span className="text-sm">Loading campaigns...</span>
                    </div>
                </div>
            )}
        </motion.div>
    );
}
