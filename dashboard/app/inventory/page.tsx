"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { motion } from "framer-motion";
import KpiCard from "@/components/kpi-card";
import { SortableTable, type ColumnDef } from "@/components/sortable-table";
import { supabase } from "@/lib/supabase";
import { formatCurrency, formatPercent, formatNumber } from "@/lib/format";
import { ChevronDown, X, Filter } from "lucide-react";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from "recharts";

interface InventoryItem {
    product: string;
    category: string;
    qty: number;
    cost: number;
    price: number;
    actualProfit: number;
    daysLeft: number;
    stockStatus: "OK" | "Warning" | "Low";
    gst: boolean;
    itemStatus: string;
    defaultVendor: string | null;
    lastSaleDate: string | null;
    sku: string;
    [key: string]: unknown;
}

/* ── Multi-select dropdown filter ─────────────────────────────── */
function FilterDropdown({
    label, options, selected, onChange,
}: {
    label: string;
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

    const active = selected.size > 0 && selected.size < options.length;

    return (
        <div ref={ref} className="relative">
            <button
                onClick={() => setOpen(!open)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors cursor-pointer ${active
                    ? "border-olive bg-olive/10 text-olive"
                    : "border-border bg-card text-muted-foreground hover:text-foreground"
                    }`}
            >
                {label}
                {active && <span className="bg-olive text-white text-[10px] rounded-full px-1.5 leading-4">{selected.size}</span>}
                <ChevronDown size={12} />
            </button>
            {open && (
                <div className="absolute z-50 mt-1 w-56 max-h-64 overflow-y-auto bg-card border border-border rounded-lg shadow-lg py-1">
                    <button
                        className="w-full text-left px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted transition-colors cursor-pointer"
                        onClick={() => {
                            onChange(new Set());
                        }}
                    >
                        {selected.size === 0 ? "✓ All" : "Select all"}
                    </button>
                    <div className="border-t border-border my-1" />
                    {options.map((opt) => (
                        <label
                            key={opt}
                            className="flex items-center gap-2 px-3 py-1.5 text-xs text-foreground hover:bg-muted cursor-pointer transition-colors"
                        >
                            <input
                                type="checkbox"
                                checked={selected.has(opt)}
                                onChange={() => {
                                    const next = new Set(selected);
                                    if (next.has(opt)) next.delete(opt);
                                    else next.add(opt);
                                    onChange(next);
                                }}
                                className="rounded border-border accent-olive"
                            />
                            {opt || "(none)"}
                        </label>
                    ))}
                </div>
            )}
        </div>
    );
}

export default function InventoryPage() {
    const [loading, setLoading] = useState(true);
    const [items, setItems] = useState<InventoryItem[]>([]);
    const [saleFilter, setSaleFilter] = useState<"all" | "6mo" | "3mo" | "1mo">("1mo");
    const [categoryFilter, setCategoryFilter] = useState<Set<string>>(new Set());
    const [vendorFilter, setVendorFilter] = useState<Set<string>>(new Set());
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

            // Fetch category_mappings to classify Cafe vs Retail
            const { data: catMaps } = await supabase
                .from("category_mappings")
                .select("category, side");

            const cafeCategories = new Set(
                (catMaps || []).filter((c) => c.side === "Cafe").map((c) => c.category)
            );

            const { data: inv, error: invErr } = await supabase
                .from("inventory")
                .select("product_name, categories, current_quantity, default_unit_cost, price, gst_applicable, status, default_vendor, last_sale_date, sku")
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

                const catStr = (item.categories || "").toString();

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
                    daysLeft,
                    stockStatus: status,
                    gst: item.gst_applicable === true,
                    itemStatus: (item.status as string) || "ACTIVE",
                    defaultVendor: (item.default_vendor as string) || null,
                    lastSaleDate: (item.last_sale_date as string) || null,
                    sku: (item.sku as string) || "",
                };
            });

            setItems(displayItems);

            // Aggregate KPIs — only positive stock (matches Square dashboard)
            const positiveStock = displayItems.filter((i) => i.qty > 0);
            const sv = positiveStock.reduce((s, i) => s + i.qty * i.cost, 0);
            const rv = positiveStock.reduce((s, i) => s + i.qty * i.price, 0);
            const lc = displayItems.filter((i) => i.stockStatus === "Low").length;

            // Margin calculations: only items with positive stock
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

    // ── Column definitions for SortableTable ─────────────────────
    const stockColumns: ColumnDef<InventoryItem>[] = [
        {
            key: "product",
            label: "Product",
            sortValue: (r) => r.product.toLowerCase(),
            render: (r) => <span className="font-medium text-foreground">{r.product}</span>,
        },
        {
            key: "category",
            label: "Category",
            sortValue: (r) => r.category.toLowerCase(),
            render: (r) => <span className="text-text-body">{r.category}</span>,
        },
        {
            key: "qty",
            label: "Qty",
            align: "right",
            sortValue: (r) => r.qty,
            render: (r) => <span className="tabular-nums">{r.qty}</span>,
        },
        {
            key: "cost",
            label: "Cost",
            align: "right",
            sortValue: (r) => r.cost,
            render: (r) => <span className="tabular-nums">{formatCurrency(r.cost)}</span>,
        },
        {
            key: "price",
            label: "Price",
            align: "right",
            sortValue: (r) => r.price,
            render: (r) => <span className="tabular-nums">{formatCurrency(r.price)}</span>,
        },
        {
            key: "actualProfit",
            label: "Actual %",
            align: "right",
            sortValue: (r) => r.actualProfit,
            render: (r) => (
                <span className={`tabular-nums font-medium ${profitColor(r.actualProfit)}`}>
                    {formatPercent(r.actualProfit)}
                </span>
            ),
        },
        {
            key: "sku",
            label: "SKU",
            sortValue: (r) => r.sku.toLowerCase(),
            render: (r) => <span className="text-muted-foreground text-xs tabular-nums">{r.sku || "—"}</span>,
        },
        {
            key: "defaultVendor",
            label: "Vendor",
            sortValue: (r) => (r.defaultVendor || "").toLowerCase(),
            render: (r) => <span className="text-text-body text-xs">{r.defaultVendor || <span className="text-muted-foreground">—</span>}</span>,
        },
        {
            key: "daysLeft",
            label: "Days Left",
            align: "right",
            sortValue: (r) => r.daysLeft,
            render: (r) => <span className="tabular-nums">{r.daysLeft > 900 ? "∞" : r.daysLeft}</span>,
        },
        {
            key: "gst",
            label: "Tax",
            align: "center",
            sortValue: (r) => r.gst ? 1 : 0,
            render: (r) => (
                r.gst
                    ? <span className="inline-flex items-center justify-center w-5 h-5 rounded bg-amber-100 text-amber-700 text-[9px] font-bold leading-none" title="GST 10%">G</span>
                    : <span className="text-muted-foreground text-[10px]">—</span>
            ),
        },
        {
            key: "stockStatus",
            label: "Stock",
            align: "center",
            sortValue: (r) => r.stockStatus === "Low" ? 0 : r.stockStatus === "Warning" ? 1 : 2,
            render: (r) => (
                <span className={`inline-block text-xs font-semibold px-2 py-0.5 rounded-full ${statusBadge(r.stockStatus as string)}`}>
                    {r.stockStatus as string}
                </span>
            ),
        },
    ];

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

            {/* Filters + Stock Levels table */}
            <div className="space-y-3">
                {/* Filter row */}
                <div className="flex flex-wrap items-center gap-2">
                    <Filter size={14} className="text-muted-foreground" />

                    {/* Category filter dropdown */}
                    <FilterDropdown
                        label="Category"
                        options={[...new Set(items.map(i => i.category))].filter(Boolean).sort()}
                        selected={categoryFilter}
                        onChange={setCategoryFilter}
                    />

                    {/* Vendor filter dropdown */}
                    <FilterDropdown
                        label="Vendor"
                        options={[...new Set(items.map(i => i.defaultVendor || "(none)"))].sort()}
                        selected={vendorFilter}
                        onChange={setVendorFilter}
                    />

                    {/* Divider */}
                    <div className="w-px h-5 bg-border mx-1" />

                    {/* Sale recency pills */}
                    {(["all", "6mo", "3mo", "1mo"] as const).map((f) => {
                        const label = f === "all" ? "All"
                            : f === "6mo" ? "6 months"
                                : f === "3mo" ? "3 months"
                                    : "Last month";
                        return (
                            <button
                                key={f}
                                onClick={() => setSaleFilter(f)}
                                className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors cursor-pointer ${saleFilter === f
                                        ? "bg-olive text-white"
                                        : "bg-muted text-muted-foreground hover:text-foreground"
                                    }`}
                            >
                                {label}
                            </button>
                        );
                    })}

                    {/* Clear filters */}
                    {(categoryFilter.size > 0 || vendorFilter.size > 0 || saleFilter !== "1mo") && (
                        <button
                            onClick={() => { setCategoryFilter(new Set()); setVendorFilter(new Set()); setSaleFilter("1mo"); }}
                            className="ml-auto inline-flex items-center gap-1 px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                        >
                            <X size={12} />
                            Reset filters
                        </button>
                    )}
                </div>

                <SortableTable
                    title="Stock Levels"
                    columns={stockColumns}
                    data={(() => {
                        let filtered = items;

                        // Sale recency filter
                        if (saleFilter !== "all") {
                            const days = saleFilter === "6mo" ? 180 : saleFilter === "3mo" ? 90 : 30;
                            const cutoff = new Date(Date.now() - days * 86400000).toISOString().split("T")[0];
                            filtered = filtered.filter(i => i.lastSaleDate && i.lastSaleDate >= cutoff);
                        }

                        // Category filter
                        if (categoryFilter.size > 0) {
                            filtered = filtered.filter(i => categoryFilter.has(i.category));
                        }

                        // Vendor filter
                        if (vendorFilter.size > 0) {
                            filtered = filtered.filter(i => vendorFilter.has(i.defaultVendor || "(none)"));
                        }

                        return filtered;
                    })()}
                    defaultSortKey="product"
                    defaultSortDir="asc"
                    searchKeys={["product", "category", "sku", "defaultVendor"]}
                    searchPlaceholder="Search product, category, SKU or vendor…"
                />
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
