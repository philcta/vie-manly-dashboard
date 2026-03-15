"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { motion } from "framer-motion";
import KpiCard from "@/components/kpi-card";
import { SortableTable, type ColumnDef } from "@/components/sortable-table";
import { supabase } from "@/lib/supabase";
import { formatCurrency, formatPercent, formatNumber } from "@/lib/format";
import { ChevronDown, X, Filter, AlertTriangle, TrendingDown, Package, Clock, ShoppingCart, Download } from "lucide-react";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";

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
    /* Intelligence fields */
    salesVelocity: number;
    sold7d: number;
    sold30d: number;
    sold90d: number;
    revenue30d: number;
    lastSoldDate: string | null;
    lastReceivedDate: string | null;
    daysOfStock: number;
    sellThrough: number;
    reorderAlert: string;
    [key: string]: unknown;
}

interface AlertSummary {
    critical: number;
    low: number;
    watch: number;
    overstock: number;
    dead: number;
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
                {label}{selected.size > 0 && ` (${selected.size})`}
                <ChevronDown size={12} />
            </button>
            {open && (
                <div className="absolute z-50 mt-1 w-56 max-h-72 overflow-y-auto bg-card border border-border rounded-lg shadow-lg p-2 space-y-0.5">
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
                            {opt || "(none)"}
                        </label>
                    ))}
                </div>
            )}
        </div>
    );
}

/* ── Reorder Alert Badge ──────────────────────────────────────── */
function AlertBadge({ level }: { level: string }) {
    const styles: Record<string, string> = {
        CRITICAL: "bg-red-500/15 text-red-600 ring-red-500/30",
        LOW: "bg-orange-500/15 text-orange-600 ring-orange-500/30",
        WATCH: "bg-yellow-500/15 text-yellow-700 ring-yellow-500/30",
        OK: "bg-olive/10 text-olive ring-olive/20",
        OVERSTOCK: "bg-blue-500/15 text-blue-600 ring-blue-500/30",
        DEAD: "bg-zinc-500/15 text-zinc-500 ring-zinc-500/30",
    };
    return (
        <span className={`inline-block text-[10px] font-bold px-2 py-0.5 rounded-full ring-1 ${styles[level] || styles.OK}`}>
            {level}
        </span>
    );
}

/* ── Alert Summary Card ───────────────────────────────────────── */
function AlertCard({ icon, label, count, color, onClick, active }: {
    icon: React.ReactNode;
    label: string;
    count: number;
    color: string;
    onClick: () => void;
    active: boolean;
}) {
    return (
        <button
            onClick={onClick}
            className={`flex items-center gap-2 px-3 py-2 rounded-xl border transition-all cursor-pointer hover:shadow-md ${active ? `ring-2 ${color} border-transparent shadow-md` : "border-border bg-card"
                }`}
        >
            <div className={`p-1.5 rounded-lg ${color.replace("ring-", "bg-").replace("/40", "/10")}`}>
                {icon}
            </div>
            <div className="text-left">
                <div className="text-base font-bold tabular-nums text-foreground">{count}</div>
                <div className="text-[11px] text-muted-foreground">{label}</div>
            </div>
        </button>
    );
}

export default function InventoryPage() {
    const [loading, setLoading] = useState(true);
    const [items, setItems] = useState<InventoryItem[]>([]);

    const [categoryFilter, setCategoryFilter] = useState<Set<string>>(new Set());
    const [vendorFilter, setVendorFilter] = useState<Set<string>>(new Set());
    const [alertFilter, setAlertFilter] = useState<string | null>(null);
    const [stockValue, setStockValue] = useState(0);
    const [stockValueExGst, setStockValueExGst] = useState(0);
    const [retailValue, setRetailValue] = useState(0);
    const [avgMargin, setAvgMargin] = useState(0);
    const [cafeMargin, setCafeMargin] = useState(0);
    const [retailMargin, setRetailMargin] = useState(0);
    const [lowCount, setLowCount] = useState(0);
    const [snapshotDate, setSnapshotDate] = useState("");
    const [alerts, setAlerts] = useState<AlertSummary>({ critical: 0, low: 0, watch: 0, overstock: 0, dead: 0 });
    const [hasIntelligence, setHasIntelligence] = useState(false);

    const loadData = useCallback(async () => {
        setLoading(true);
        try {
            // Single consolidated RPC replaces 4+ separate queries
            const { data: result, error: rpcErr } = await supabase.rpc("get_inventory_full");
            if (rpcErr) throw rpcErr;

            const sourceDate = result?.snapshot_date;
            if (sourceDate) setSnapshotDate(sourceDate);

            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const invRows = (result?.items || []) as any[];
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const catSides = (result?.category_sides || []) as any[];

            const cafeCategories = new Set(
                catSides.filter((c: { side: string }) => c.side === "Cafe").map((c: { category: string }) => c.category)
            );

            const hasIntel = invRows.some((r: { sales_velocity?: number }) => (r.sales_velocity ?? 0) > 0);
            setHasIntelligence(hasIntel);

            // Map inventory to display items — intelligence + sales already joined
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const displayItems: InventoryItem[] = invRows.map((item: any) => {
                const productName = item.product_name || "Unknown";
                const qtySold = Number(item.dis_qty_sold) || 0;
                const netSales = Number(item.dis_net_sales) || 0;
                const rawCost = Number(item.default_unit_cost || 0);
                const hasGst = (item.tax_gst_10 as string) === 'Y';
                const unitCost = hasGst ? rawCost * 1.10 : rawCost;
                const retailPrice = Number(item.price || 0);
                const currentQty = Number(item.current_quantity || 0);
                const avgSellingPrice = qtySold > 0 ? netSales / qtySold : retailPrice;
                const dailySales = qtySold / 30;
                const daysLeft = dailySales > 0 ? Math.round(currentQty / dailySales) : 999;

                const actualProfit = avgSellingPrice > 0
                    ? ((avgSellingPrice - unitCost) / avgSellingPrice) * 100
                    : 0;

                const catStr = (item.categories || "").toString();
                const sku = (item.sku as string) || "";

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
                    gst: hasGst,
                    itemStatus: (item.status as string) || "ACTIVE",
                    defaultVendor: (item.default_vendor as string) || null,
                    lastSaleDate: (item.last_sale_date as string) || null,
                    sku,
                    salesVelocity: item.sales_velocity ?? 0,
                    sold7d: item.units_sold_7d ?? 0,
                    sold30d: item.units_sold_30d ?? 0,
                    sold90d: item.units_sold_90d ?? 0,
                    revenue30d: item.revenue_30d ?? 0,
                    lastSoldDate: item.last_sold_date ? String(item.last_sold_date).split("T")[0] : null,
                    lastReceivedDate: item.last_received_date ? String(item.last_received_date).split("T")[0] : null,
                    daysOfStock: item.days_of_stock ?? (daysLeft > 900 ? 9999 : daysLeft),
                    sellThrough: item.sell_through_pct ?? 0,
                    reorderAlert: item.reorder_alert ?? "OK",
                };
            });

            setItems(displayItems);

            // Aggregate KPIs — only positive stock (matches Square dashboard)
            const positiveStock = displayItems.filter((i) => i.qty > 0);
            const sv = positiveStock.reduce((s, i) => s + i.qty * i.cost, 0);
            const svExGst = positiveStock.reduce((s, i) =>
                s + i.qty * (i.gst ? i.cost / 1.10 : i.cost), 0);
            const rv = positiveStock.reduce((s, i) => s + i.qty * i.price, 0);
            const lc = displayItems.filter((i) => i.stockStatus === "Low").length;

            const inStock = displayItems.filter((i) => i.qty > 0);
            const isSV = inStock.reduce((s, i) => s + i.qty * i.cost, 0);
            const isRV = inStock.reduce((s, i) => s + i.qty * i.price, 0);
            const am = isRV > 0 ? ((isRV - isSV) / isRV) * 100 : 0;

            const cafeInStock = inStock.filter((i) => cafeCategories.has(i.category));
            const retailInStock = inStock.filter((i) => !cafeCategories.has(i.category));

            const cafeSV = cafeInStock.reduce((s, i) => s + i.qty * i.cost, 0);
            const cafeRV = cafeInStock.reduce((s, i) => s + i.qty * i.price, 0);
            const cm = cafeRV > 0 ? ((cafeRV - cafeSV) / cafeRV) * 100 : 0;

            const retSV = retailInStock.reduce((s, i) => s + i.qty * i.cost, 0);
            const retRV = retailInStock.reduce((s, i) => s + i.qty * i.price, 0);
            const rm = retRV > 0 ? ((retRV - retSV) / retRV) * 100 : 0;

            setStockValue(sv);
            setStockValueExGst(svExGst);
            setRetailValue(rv);
            setAvgMargin(am);
            setCafeMargin(cm);
            setRetailMargin(rm);
            setLowCount(lc);

            // Alert summary
            const alertCounts: AlertSummary = { critical: 0, low: 0, watch: 0, overstock: 0, dead: 0 };
            for (const item of displayItems) {
                if (item.reorderAlert === "CRITICAL") alertCounts.critical++;
                else if (item.reorderAlert === "LOW") alertCounts.low++;
                else if (item.reorderAlert === "WATCH") alertCounts.watch++;
                else if (item.reorderAlert === "OVERSTOCK") alertCounts.overstock++;
                else if (item.reorderAlert === "DEAD") alertCounts.dead++;
            }
            setAlerts(alertCounts);
        } catch (err) {
            console.error("Failed to load inventory:", err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadData();
    }, [loadData]);

    const profitColor = (pct: number) => {
        if (pct >= 40) return "text-olive";
        if (pct >= 20) return "text-warning";
        return "text-coral";
    };

    const formatDaysAgo = (dateStr: string | null) => {
        if (!dateStr) return "—";
        const d = new Date(dateStr);
        const now = new Date();
        const days = Math.floor((now.getTime() - d.getTime()) / 86400000);
        if (days === 0) return "Today";
        if (days === 1) return "Yesterday";
        if (days < 7) return `${days}d ago`;
        if (days < 30) return `${Math.floor(days / 7)}w ago`;
        return `${Math.floor(days / 30)}mo ago`;
    };

    const velocityLabel = (v: number) => {
        if (v === 0) return "—";
        if (v < 1) return `${v.toFixed(1)}/mo`;
        return `${Math.round(v)}/mo`;
    };

    // ── Column definitions ─────────────────────────────────────
    const stockColumns: ColumnDef<InventoryItem>[] = [
        {
            key: "reorderAlert",
            label: "Alert",
            align: "center",
            sortValue: (r) => {
                const order: Record<string, number> = { CRITICAL: 0, LOW: 1, WATCH: 2, OK: 3, OVERSTOCK: 4, DEAD: 5 };
                return order[r.reorderAlert] ?? 3;
            },
            render: (r) => <AlertBadge level={r.reorderAlert} />,
        },
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
            label: "On Hand",
            align: "right",
            sortValue: (r) => r.qty,
            render: (r) => (
                <span className={`tabular-nums font-medium ${r.qty <= 0 ? "text-red-500" : r.qty <= 3 ? "text-orange-500" : ""}`}>
                    {r.qty}
                </span>
            ),
        },
        {
            key: "salesVelocity",
            label: "Velocity",
            align: "right",
            sortValue: (r) => r.salesVelocity,
            render: (r) => <span className="tabular-nums text-text-body">{velocityLabel(r.salesVelocity)}</span>,
        },
        {
            key: "sold30d",
            label: "Sold 30d",
            align: "right",
            sortValue: (r) => r.sold30d,
            render: (r) => <span className="tabular-nums">{r.sold30d > 0 ? r.sold30d : "—"}</span>,
        },
        {
            key: "daysOfStock",
            label: "Days Left",
            align: "right",
            sortValue: (r) => r.daysOfStock,
            render: (r) => {
                const d = r.daysOfStock;
                const color = d < 3 ? "text-red-500 font-bold" : d < 7 ? "text-orange-500 font-semibold" : d < 14 ? "text-yellow-600" : "";
                return <span className={`tabular-nums ${color}`}>{d >= 9999 ? "–" : Math.round(d)}</span>;
            },
        },
        {
            key: "lastSoldDate",
            label: "Last Sold",
            sortValue: (r) => r.lastSoldDate || "0",
            render: (r) => <span className="text-text-body text-xs">{formatDaysAgo(r.lastSoldDate)}</span>,
        },
        {
            key: "lastReceivedDate",
            label: "Last Recv",
            sortValue: (r) => r.lastReceivedDate || "0",
            render: (r) => <span className="text-text-body text-xs">{formatDaysAgo(r.lastReceivedDate)}</span>,
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
            label: "Margin",
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
    ];

    // ── CSV export helper ───────────────────────────────────────
    const exportInventoryCSV = (data: InventoryItem[]) => {
        const headers = [
            "Product", "Category", "SKU", "Vendor", "On Hand", "Unit Cost",
            "Retail Price", "Margin %", "Velocity (units/day)", "Sold 7d",
            "Sold 30d", "Sold 90d", "Revenue 30d", "Days of Stock",
            "Sell Through %", "Alert", "Last Sold", "Last Received",
        ];
        const rows = data.map((r) => [
            r.product,
            r.category,
            r.sku || "",
            r.defaultVendor || "",
            r.qty,
            r.cost.toFixed(2),
            r.price.toFixed(2),
            r.actualProfit.toFixed(1),
            r.salesVelocity.toFixed(2),
            r.sold7d,
            r.sold30d,
            r.sold90d,
            r.revenue30d.toFixed(2),
            r.daysOfStock >= 9999 ? "" : Math.round(r.daysOfStock),
            r.sellThrough.toFixed(1),
            r.reorderAlert,
            r.lastSoldDate || "",
            r.lastReceivedDate || "",
        ]);
        const csvContent = [
            headers.join(","),
            ...rows.map((row) =>
                row.map((val) => {
                    const str = String(val);
                    return str.includes(",") || str.includes('"') || str.includes("\n")
                        ? `"${str.replace(/"/g, '""')}"`
                        : str;
                }).join(",")
            ),
        ].join("\n");
        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `inventory_export_${new Date().toISOString().slice(0, 10)}.csv`;
        link.click();
        URL.revokeObjectURL(url);
    };

    // Compute filtered data
    const filteredItems = (() => {
        let filtered = items;

        // Alert filter
        if (alertFilter) {
            filtered = filtered.filter(i => i.reorderAlert === alertFilter);
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
    })();

    const needsActionCount = alerts.critical + alerts.low;

    return (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="space-y-6 relative min-h-[80vh]">
            {loading ? (
                <div className="absolute inset-0 flex items-center justify-center z-40 bg-background">
                    <div className="flex flex-col items-center gap-3 text-muted-foreground">
                        <div className="w-8 h-8 border-2 border-olive/30 border-t-olive rounded-full animate-spin" />
                        <span className="text-sm font-medium">Loading inventory...</span>
                    </div>
                </div>
            ) : (
                <>
                    <h1 className="text-2xl font-bold text-foreground">Inventory</h1>

                    {/* KPI Cards */}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
                        <KpiCard label="Stock Value (GST inc.)" value={stockValue} formatter={(n) => formatCurrency(n, 0)} subtitle={`Ex-GST: ${formatCurrency(stockValueExGst, 0)} · ${snapshotDate}`} delay={0} />
                        <KpiCard label="Retail Value" value={retailValue} formatter={(n) => formatCurrency(n, 0)} subtitle={snapshotDate ? `as of ${snapshotDate}` : undefined} delay={1} />
                        <KpiCard label="Avg Profit Margin" value={avgMargin} formatter={(n) => formatPercent(n)} subtitle={`Cafe: ${formatPercent(cafeMargin)} · Retail: ${formatPercent(retailMargin)}`} delay={2} />
                        <KpiCard label="Needs Action" value={needsActionCount} formatter={(n) => formatNumber(n)} subtitle={`${alerts.critical} critical · ${alerts.low} low`} goal="Reduce dead/overstock by 30% within 6 weeks" delay={3} />
                    </div>

                    {/* ── Restock Alerts Panel ──────────────────────────── */}
                    {hasIntelligence && (
                        <div className="bg-card rounded-xl border border-border p-4" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
                            <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                                <AlertTriangle size={16} className="text-orange-500" />
                                Stock Intelligence
                            </h3>
                            <div className="grid grid-cols-3 lg:grid-cols-5 gap-2">
                                <AlertCard
                                    icon={<AlertTriangle size={16} className="text-red-500" />}
                                    label="Critical"
                                    count={alerts.critical}
                                    color="ring-red-500/40"
                                    onClick={() => setAlertFilter(alertFilter === "CRITICAL" ? null : "CRITICAL")}
                                    active={alertFilter === "CRITICAL"}
                                />
                                <AlertCard
                                    icon={<TrendingDown size={16} className="text-orange-500" />}
                                    label="Low Stock"
                                    count={alerts.low}
                                    color="ring-orange-500/40"
                                    onClick={() => setAlertFilter(alertFilter === "LOW" ? null : "LOW")}
                                    active={alertFilter === "LOW"}
                                />
                                <AlertCard
                                    icon={<Clock size={16} className="text-yellow-600" />}
                                    label="Watch"
                                    count={alerts.watch}
                                    color="ring-yellow-500/40"
                                    onClick={() => setAlertFilter(alertFilter === "WATCH" ? null : "WATCH")}
                                    active={alertFilter === "WATCH"}
                                />
                                <AlertCard
                                    icon={<Package size={16} className="text-blue-500" />}
                                    label="Overstock"
                                    count={alerts.overstock}
                                    color="ring-blue-500/40"
                                    onClick={() => setAlertFilter(alertFilter === "OVERSTOCK" ? null : "OVERSTOCK")}
                                    active={alertFilter === "OVERSTOCK"}
                                />
                                <AlertCard
                                    icon={<ShoppingCart size={16} className="text-zinc-400" />}
                                    label="Dead Stock"
                                    count={alerts.dead}
                                    color="ring-zinc-500/40"
                                    onClick={() => setAlertFilter(alertFilter === "DEAD" ? null : "DEAD")}
                                    active={alertFilter === "DEAD"}
                                />
                            </div>
                        </div>
                    )}

                    {/* Filters + Stock Levels table */}
                    <div className="space-y-3">
                        {/* Filter row */}
                        <div className="flex flex-wrap items-center gap-2">
                            <Filter size={14} className="text-muted-foreground" />

                            <FilterDropdown
                                label="Category"
                                options={[...new Set(items.map(i => i.category))].filter(Boolean).sort()}
                                selected={categoryFilter}
                                onChange={setCategoryFilter}
                            />

                            <FilterDropdown
                                label="Vendor"
                                options={[...new Set(items.map(i => i.defaultVendor || "(none)"))].sort()}
                                selected={vendorFilter}
                                onChange={setVendorFilter}
                            />



                            {/* Clear filters */}
                            {(categoryFilter.size > 0 || vendorFilter.size > 0 || alertFilter) && (
                                <button
                                    onClick={() => { setCategoryFilter(new Set()); setVendorFilter(new Set()); setAlertFilter(null); }}
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
                            data={filteredItems}
                            defaultSortKey={alertFilter ? "daysOfStock" : "product"}
                            defaultSortDir="asc"
                            searchKeys={["product", "category", "sku", "defaultVendor"]}
                            searchPlaceholder="Search product, category, SKU or vendor..."
                            mobileCardRender={(row: InventoryItem) => (
                                <div className="px-4 py-3 space-y-1.5">
                                    <div className="flex items-start justify-between gap-2">
                                        <div className="min-w-0">
                                            <span className="font-medium text-sm text-foreground block truncate">{row.product}</span>
                                            <span className="text-[11px] text-muted-foreground">{row.category}</span>
                                        </div>
                                        {row.reorderAlert && row.reorderAlert !== "OK" && (
                                            <AlertBadge level={row.reorderAlert} />
                                        )}
                                    </div>
                                    <div className="grid grid-cols-4 gap-2 text-xs">
                                        <div>
                                            <span className="text-muted-foreground block">Qty</span>
                                            <span className="font-medium tabular-nums">{row.qty}</span>
                                        </div>
                                        <div>
                                            <span className="text-muted-foreground block">Cost</span>
                                            <span className="font-medium tabular-nums">${row.cost.toFixed(2)}</span>
                                        </div>
                                        <div>
                                            <span className="text-muted-foreground block">Price</span>
                                            <span className="font-medium tabular-nums">${row.price.toFixed(2)}</span>
                                        </div>
                                        <div>
                                            <span className="text-muted-foreground block">Margin</span>
                                            <span className={`font-medium tabular-nums ${profitColor(row.actualProfit)}`}>{row.actualProfit.toFixed(1)}%</span>
                                        </div>
                                    </div>
                                    <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                                        <span>
                                            Sold: {row.sold30d} (30d) · {row.sold7d} (7d)
                                        </span>
                                        <span>
                                            {row.daysOfStock >= 9999 ? "∞ days" : `${Math.round(row.daysOfStock)}d left`}
                                        </span>
                                    </div>
                                </div>
                            )}
                            headerActions={
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <button
                                            onClick={() => exportInventoryCSV(filteredItems)}
                                            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors cursor-pointer"
                                        >
                                            <Download size={13} />
                                            CSV
                                        </button>
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom" sideOffset={6}>Export filtered list as CSV</TooltipContent>
                                </Tooltip>
                            }
                        />
                    </div>
                </>
            )}
        </motion.div>
    );
}
