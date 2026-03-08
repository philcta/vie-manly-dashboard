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
    Legend,
} from "recharts";

interface InventoryItem {
    product: string;
    category: string;
    qty: number;
    cost: number;
    price: number;
    actualProfit: number;
    potentialProfit: number;
    popRank: number;
    profitRank: number;
    daysLeft: number;
    status: "OK" | "Warning" | "Low";
}

export default function InventoryPage() {
    const [loading, setLoading] = useState(true);
    const [items, setItems] = useState<InventoryItem[]>([]);
    const [stockValue, setStockValue] = useState(0);
    const [retailValue, setRetailValue] = useState(0);
    const [avgMargin, setAvgMargin] = useState(0);
    const [cafeMargin, setCafeMargin] = useState(0);
    const [retailMargin, setRetailMargin] = useState(0);
    const [lowCount, setLowCount] = useState(0);

    const loadData = useCallback(async () => {
        setLoading(true);
        try {
            // Get the latest source_date for inventory snapshot
            const { data: latestDate } = await supabase
                .from("inventory")
                .select("source_date")
                .order("source_date", { ascending: false })
                .limit(1)
                .single();

            const sourceDate = latestDate?.source_date;

            // Fetch inventory items for latest snapshot
            // Fetch category_mappings to classify Cafe vs Retail
            const { data: catMaps } = await supabase
                .from("category_mappings")
                .select("category, side");

            const cafeCategories = new Set(
                (catMaps || []).filter((c) => c.side === "Cafe").map((c) => c.category)
            );

            const { data: inv, error: invErr } = await supabase
                .from("inventory")
                .select("product_name, categories, current_quantity, default_unit_cost, price")
                .eq("source_date", sourceDate || "")
                .order("product_name", { ascending: true });

            if (invErr) throw invErr;

            // Fetch recent sales data for velocity calculations
            const thirtyDaysAgo = new Date();
            thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
            const dateStr = thirtyDaysAgo.toISOString().split("T")[0];

            const { data: sales, error: salesErr } = await supabase
                .from("daily_item_summary")
                .select("item, category, total_qty, total_net_sales")
                .gte("date", dateStr);

            if (salesErr) throw salesErr;

            // Build sales velocity map
            const salesMap = new Map<string, { qtySold: number; netSales: number }>();
            for (const s of sales || []) {
                const key = s.item;
                if (!salesMap.has(key)) salesMap.set(key, { qtySold: 0, netSales: 0 });
                const entry = salesMap.get(key)!;
                entry.qtySold += s.total_qty;
                entry.netSales += s.total_net_sales;
            }

            // Map inventory to display items
            const displayItems: InventoryItem[] = (inv || []).map((item) => {
                const productName = item.product_name || "Unknown";
                const s = salesMap.get(productName);
                const qtySold = s?.qtySold ?? 0;
                const netSales = s?.netSales ?? 0;
                const unitCost = Number(item.default_unit_cost || 0);
                const retailPrice = Number(item.price || 0);
                const currentQty = Number(item.current_quantity || 0);
                const avgSellingPrice = qtySold > 0 ? netSales / qtySold : retailPrice;
                const dailySales = qtySold / 30;
                const daysLeft = dailySales > 0 ? Math.round(currentQty / dailySales) : 999;

                const actualProfit = avgSellingPrice > 0
                    ? ((avgSellingPrice - unitCost) / avgSellingPrice) * 100
                    : 0;
                const potentialProfit = retailPrice > 0
                    ? ((retailPrice - unitCost) / retailPrice) * 100
                    : 0;

                // Determine category — categories may be comma-separated
                const catStr = (item.categories || "").toString();

                // Default thresholds
                const lowThreshold = 3;
                const warnThreshold = 10;

                let status: "OK" | "Warning" | "Low" = "OK";
                if (currentQty <= lowThreshold) status = "Low";
                else if (currentQty <= warnThreshold) status = "Warning";

                return {
                    product: productName,
                    category: catStr,
                    qty: currentQty,
                    cost: unitCost,
                    price: retailPrice,
                    actualProfit,
                    potentialProfit,
                    popRank: 0,
                    profitRank: 0,
                    daysLeft,
                    status,
                };
            });

            // Calculate ranks
            const sortedByPop = [...displayItems].sort((a, b) => {
                const aSales = salesMap.get(a.product)?.qtySold ?? 0;
                const bSales = salesMap.get(b.product)?.qtySold ?? 0;
                return bSales - aSales;
            });
            sortedByPop.forEach((item, i) => {
                const found = displayItems.find((d) => d.product === item.product);
                if (found) found.popRank = i + 1;
            });

            const sortedByProfit = [...displayItems].sort((a, b) => b.actualProfit - a.actualProfit);
            sortedByProfit.forEach((item, i) => {
                const found = displayItems.find((d) => d.product === item.product);
                if (found) found.profitRank = i + 1;
            });

            setItems(displayItems);

            // Aggregate KPIs
            const sv = displayItems.reduce((s, i) => s + i.qty * i.cost, 0);
            const rv = displayItems.reduce((s, i) => s + i.qty * i.price, 0);
            const lc = displayItems.filter((i) => i.status === "Low").length;

            // Margin calculations use only items with positive stock
            // (negative qty items like cafe drinks distort the margin)
            const inStock = displayItems.filter((i) => i.qty > 0);
            const isSV = inStock.reduce((s, i) => s + i.qty * i.cost, 0);
            const isRV = inStock.reduce((s, i) => s + i.qty * i.price, 0);
            const am = isRV > 0 ? ((isRV - isSV) / isRV) * 100 : 0;

            // Split margin by Cafe vs Retail (positive stock only)
            const cafeInStock = inStock.filter((i) => cafeCategories.has(i.category));
            const retailInStock = inStock.filter((i) => !cafeCategories.has(i.category));

            const cafeSV = cafeInStock.reduce((s, i) => s + i.qty * i.cost, 0);
            const cafeRV = cafeInStock.reduce((s, i) => s + i.qty * i.price, 0);
            const cm = cafeRV > 0 ? ((cafeRV - cafeSV) / cafeRV) * 100 : 0;

            const retSV = retailInStock.reduce((s, i) => s + i.qty * i.cost, 0);
            const retRV = retailInStock.reduce((s, i) => s + i.qty * i.price, 0);
            const rm = retRV > 0 ? ((retRV - retSV) / retRV) * 100 : 0;

            setStockValue(sv);
            setRetailValue(rv);
            setAvgMargin(am);
            setCafeMargin(cm);
            setRetailMargin(rm);
            setLowCount(lc);
        } catch (err) {
            console.error("Failed to load inventory:", err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadData();
    }, [loadData]);

    const statusBadge = (status: string) => {
        switch (status) {
            case "Low":
                return "bg-coral text-white";
            case "Warning":
                return "bg-warning text-white";
            default:
                return "bg-olive text-white";
        }
    };

    const profitColor = (pct: number) => {
        if (pct >= 40) return "text-olive";
        if (pct >= 20) return "text-warning";
        return "text-coral";
    };

    // Category bar chart
    const categories = ["Food", "Drinks", "Cafe", "Retail"];
    const catChartData = categories.map((cat) => {
        const catItems = items.filter(
            (i) => i.category.toLowerCase() === cat.toLowerCase()
        );
        return {
            category: cat,
            stock: catItems.reduce((s, i) => s + i.qty, 0),
        };
    });

    return (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="space-y-8">
            <h1 className="text-[28px] font-bold text-foreground">Inventory</h1>

            <div className="grid grid-cols-4 gap-5">
                <KpiCard label="Stock Value" value={stockValue} formatter={(n) => formatCurrency(n, 0)} delay={0} />
                <KpiCard label="Retail Value" value={retailValue} formatter={(n) => formatCurrency(n, 0)} delay={1} />
                <KpiCard label="Avg Profit Margin" value={avgMargin} formatter={(n) => formatPercent(n)} subtitle={`Cafe: ${formatPercent(cafeMargin)} · Retail: ${formatPercent(retailMargin)}`} delay={2} />
                <KpiCard label="Low Stock Items" value={lowCount} formatter={(n) => formatNumber(n)} delay={3} />
            </div>

            {/* Stock Levels Table */}
            <div className="bg-card rounded-xl border border-border overflow-hidden" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                <div className="px-6 py-4 border-b border-border">
                    <h3 className="text-base font-semibold text-foreground">Stock Levels</h3>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="bg-[#FAFAF8]">
                                {["Product", "Category", "Qty", "Cost", "Price", "Actual %", "Potential %", "Pop #", "Profit #", "Days Left", "Status"].map((h) => (
                                    <th key={h} className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-body whitespace-nowrap">{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {items.map((item, i) => (
                                <tr key={i} className="border-b border-[#F0F0EE] row-hover">
                                    <td className="px-3 py-3 text-sm font-medium text-foreground">{item.product}</td>
                                    <td className="px-3 py-3 text-sm text-text-body">{item.category}</td>
                                    <td className="px-3 py-3 text-sm tabular-nums text-foreground">{item.qty}</td>
                                    <td className="px-3 py-3 text-sm tabular-nums text-foreground">{formatCurrency(item.cost)}</td>
                                    <td className="px-3 py-3 text-sm tabular-nums text-foreground">{formatCurrency(item.price)}</td>
                                    <td className={`px-3 py-3 text-sm tabular-nums font-medium ${profitColor(item.actualProfit)}`}>{formatPercent(item.actualProfit)}</td>
                                    <td className="px-3 py-3 text-sm tabular-nums text-foreground">{formatPercent(item.potentialProfit)}</td>
                                    <td className="px-3 py-3 text-sm tabular-nums font-bold text-foreground">#{item.popRank}</td>
                                    <td className="px-3 py-3 text-sm tabular-nums font-bold text-foreground">#{item.profitRank}</td>
                                    <td className="px-3 py-3 text-sm tabular-nums text-foreground">{item.daysLeft > 900 ? "∞" : item.daysLeft}</td>
                                    <td className="px-3 py-3"><span className={`inline-block text-xs font-semibold px-2 py-0.5 rounded-full ${statusBadge(item.status)}`}>{item.status}</span></td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Category Chart */}
            <div className="bg-card rounded-xl border border-border p-6" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                <h3 className="text-base font-semibold text-foreground mb-4">Stock by Category</h3>
                <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={catChartData} layout="vertical" barSize={24}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#F0F0EE" horizontal={false} />
                        <XAxis type="number" tick={{ fill: "#8A8A8A", fontSize: 11 }} axisLine={false} tickLine={false} />
                        <YAxis dataKey="category" type="category" tick={{ fill: "#8A8A8A", fontSize: 12 }} axisLine={false} tickLine={false} width={60} />
                        <Tooltip contentStyle={{ background: "white", borderRadius: 8, border: "1px solid #EAEAE8", fontSize: 13 }} />
                        <Bar dataKey="stock" fill="#6B7355" radius={[0, 4, 4, 0]} animationDuration={600} />
                    </BarChart>
                </ResponsiveContainer>
            </div>

            {loading && (
                <div className="fixed inset-0 ml-[220px] bg-background/80 flex items-center justify-center z-40">
                    <div className="flex items-center gap-3 text-muted-foreground">
                        <div className="w-5 h-5 border-2 border-olive/30 border-t-olive rounded-full animate-spin" />
                        <span className="text-sm">Loading inventory...</span>
                    </div>
                </div>
            )}
        </motion.div>
    );
}
