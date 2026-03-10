"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronRight } from "lucide-react";

const CategoryClassification = dynamic(
    () => import("@/components/category-classification"),
    { ssr: false, loading: () => <p className="text-sm text-muted-foreground py-4">Loading...</p> }
);

const StaffRatesEditor = dynamic(
    () => import("@/components/staff-rates-editor"),
    { ssr: false, loading: () => <p className="text-sm text-muted-foreground py-4">Loading rates...</p> }
);

interface AccordionSectionProps {
    title: string;
    defaultOpen?: boolean;
    children: React.ReactNode;
}

function AccordionSection({ title, defaultOpen = false, children }: AccordionSectionProps) {
    const [open, setOpen] = useState(defaultOpen);

    return (
        <div className="bg-card rounded-xl border border-border overflow-hidden" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
            <button
                onClick={() => setOpen(!open)}
                className="w-full px-6 py-4 flex items-center justify-between cursor-pointer hover:bg-[#FAFAF8] transition-colors duration-200"
            >
                <h3 className="text-base font-semibold text-foreground">{title}</h3>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{open ? "EXPANDED" : "COLLAPSED"}</span>
                    {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                </div>
            </button>
            <AnimatePresence>
                {open && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                    >
                        <div className="px-6 pb-6 pt-2">{children}</div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

export default function SettingsPage() {
    const [storeName, setStoreName] = useState("Vie Market & Bar");
    const [timezone, setTimezone] = useState("Australia/Sydney");
    const [syncSchedule, setSyncSchedule] = useState("Every 1 hour");
    const [defaultRange, setDefaultRange] = useState("this_month");

    // Inventory thresholds
    const [greenAbove, setGreenAbove] = useState(40);
    const [orangeAbove, setOrangeAbove] = useState(20);
    const [redBelow, setRedBelow] = useState(20);
    const [topRankHighlight, setTopRankHighlight] = useState(3);
    const [safetyFactor, setSafetyFactor] = useState(1.5);

    // Member criteria
    const [activeDays, setActiveDays] = useState(7);
    const [coolingDays, setCoolingDays] = useState(14);
    const [atRiskDays, setAtRiskDays] = useState(30);
    const [churnedDays, setChurnedDays] = useState(45);

    const inputStyle = "w-full px-3 py-2 text-sm border border-border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-olive/20 focus:border-olive transition-colors";
    const labelStyle = "text-sm font-medium text-text-body mb-1 block";

    return (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="space-y-5 max-w-4xl">
            <h1 className="text-[28px] font-bold text-foreground">Settings</h1>

            {/* General */}
            <AccordionSection title="General" defaultOpen>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <div>
                        <label className={labelStyle}>Store Name</label>
                        <input type="text" value={storeName} onChange={(e) => setStoreName(e.target.value)} className={inputStyle} />
                    </div>
                    <div>
                        <label className={labelStyle}>Timezone</label>
                        <select value={timezone} onChange={(e) => setTimezone(e.target.value)} className={inputStyle}>
                            <option>Australia/Sydney</option>
                            <option>Australia/Melbourne</option>
                            <option>Australia/Brisbane</option>
                        </select>
                    </div>
                    <div>
                        <label className={labelStyle}>Sync Schedule</label>
                        <select value={syncSchedule} onChange={(e) => setSyncSchedule(e.target.value)} className={inputStyle}>
                            <option>Every 15 minutes</option>
                            <option>Every 30 minutes</option>
                            <option>Every 1 hour</option>
                            <option>Every 4 hours</option>
                        </select>
                    </div>
                    <div>
                        <label className={labelStyle}>Default Range</label>
                        <div className="flex rounded-full border border-border overflow-hidden">
                            {[
                                { value: "today", label: "Today" },
                                { value: "this_week", label: "This week" },
                                { value: "this_month", label: "This month" },
                            ].map((opt) => (
                                <button
                                    key={opt.value}
                                    onClick={() => setDefaultRange(opt.value)}
                                    className={`flex-1 px-3 py-2 text-xs font-medium transition-colors duration-200 cursor-pointer ${defaultRange === opt.value ? "bg-olive text-white" : "text-text-body hover:bg-olive-surface"
                                        }`}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            </AccordionSection>

            {/* Inventory Thresholds */}
            <AccordionSection title="Inventory Thresholds" defaultOpen>
                <div className="grid grid-cols-2 gap-8">
                    <div>
                        <h4 className="text-sm font-semibold text-foreground mb-3">Profit Color Bands</h4>
                        <div className="space-y-3">
                            <div className="flex items-center gap-3">
                                <div className="w-4 h-4 rounded-full bg-olive" />
                                <span className="text-sm text-text-body flex-1">Green above</span>
                                <input type="number" value={greenAbove} onChange={(e) => setGreenAbove(Number(e.target.value))} className="w-16 px-2 py-1 text-sm text-right border border-border rounded-lg tabular-nums" />
                                <span className="text-sm text-text-muted">%</span>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="w-4 h-4 rounded-full bg-warning" />
                                <span className="text-sm text-text-body flex-1">Orange above</span>
                                <input type="number" value={orangeAbove} onChange={(e) => setOrangeAbove(Number(e.target.value))} className="w-16 px-2 py-1 text-sm text-right border border-border rounded-lg tabular-nums" />
                                <span className="text-sm text-text-muted">%</span>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="w-4 h-4 rounded-full bg-coral" />
                                <span className="text-sm text-text-body flex-1">Red below</span>
                                <input type="number" value={redBelow} onChange={(e) => setRedBelow(Number(e.target.value))} className="w-16 px-2 py-1 text-sm text-right border border-border rounded-lg tabular-nums" />
                                <span className="text-sm text-text-muted">%</span>
                            </div>
                            <div className="flex items-center gap-3">
                                <span className="text-sm text-text-body flex-1 ml-7">Top Rank Highlight</span>
                                <input type="number" value={topRankHighlight} onChange={(e) => setTopRankHighlight(Number(e.target.value))} className="w-16 px-2 py-1 text-sm text-right border border-border rounded-lg tabular-nums" />
                            </div>
                        </div>
                    </div>
                    <div>
                        <h4 className="text-sm font-semibold text-foreground mb-3">Stock Status Thresholds</h4>
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-left text-xs text-text-muted">
                                    <th className="pb-2">Category</th>
                                    <th className="pb-2">Low</th>
                                    <th className="pb-2">Warning</th>
                                </tr>
                            </thead>
                            <tbody className="space-y-2">
                                {[
                                    { cat: "Cafe", low: 5, warn: 15 },
                                    { cat: "Food", low: 3, warn: 10 },
                                    { cat: "Drinks", low: 3, warn: 12 },
                                    { cat: "Retail", low: 10, warn: 25 },
                                ].map((row) => (
                                    <tr key={row.cat}>
                                        <td className="py-1 text-text-body">[{row.cat}]</td>
                                        <td className="py-1"><input type="number" defaultValue={row.low} className="w-12 px-2 py-1 text-sm text-right border border-border rounded tabular-nums" /></td>
                                        <td className="py-1"><input type="number" defaultValue={row.warn} className="w-12 px-2 py-1 text-sm text-right border border-border rounded tabular-nums" /></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        <div className="mt-4">
                            <label className="text-sm text-text-body mb-2 block">Safety Factor: {safetyFactor.toFixed(1)}</label>
                            <input
                                type="range"
                                min="1.0"
                                max="2.0"
                                step="0.1"
                                value={safetyFactor}
                                onChange={(e) => setSafetyFactor(Number(e.target.value))}
                                className="w-full accent-[#6B7355] cursor-pointer"
                            />
                            <div className="flex justify-between text-xs text-text-muted mt-1">
                                <span>1.0</span>
                                <span>2.0</span>
                            </div>
                        </div>
                    </div>
                </div>
            </AccordionSection>

            {/* Member Criteria */}
            <AccordionSection title="Member Criteria" defaultOpen>
                <div>
                    <h4 className="text-sm font-semibold text-foreground mb-3">Churn Thresholds</h4>
                    <div className="grid grid-cols-2 gap-6">
                        <div className="space-y-3">
                            <div className="flex items-center gap-3">
                                <div className="w-4 h-4 rounded-full bg-positive" />
                                <span className="text-sm text-text-body flex-1">Active &lt;</span>
                                <input type="number" value={activeDays} onChange={(e) => setActiveDays(Number(e.target.value))} className="w-16 px-2 py-1 text-sm text-right border border-border rounded-lg tabular-nums" />
                                <span className="text-sm text-text-muted">days</span>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="w-4 h-4 rounded-full bg-warning" />
                                <span className="text-sm text-text-body flex-1">Cooling &lt;</span>
                                <input type="number" value={coolingDays} onChange={(e) => setCoolingDays(Number(e.target.value))} className="w-16 px-2 py-1 text-sm text-right border border-border rounded-lg tabular-nums" />
                                <span className="text-sm text-text-muted">days</span>
                            </div>
                        </div>
                        <div className="space-y-3">
                            <div className="flex items-center gap-3">
                                <div className="w-4 h-4 rounded-full bg-coral" />
                                <span className="text-sm text-text-body flex-1">At Risk &lt;</span>
                                <input type="number" value={atRiskDays} onChange={(e) => setAtRiskDays(Number(e.target.value))} className="w-16 px-2 py-1 text-sm text-right border border-border rounded-lg tabular-nums" />
                                <span className="text-sm text-text-muted">days</span>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="w-4 h-4 rounded-full bg-[#8B0000]" />
                                <span className="text-sm text-text-body flex-1">Churned &gt;</span>
                                <input type="number" value={churnedDays} onChange={(e) => setChurnedDays(Number(e.target.value))} className="w-16 px-2 py-1 text-sm text-right border border-border rounded-lg tabular-nums" />
                                <span className="text-sm text-text-muted">days</span>
                            </div>
                        </div>
                    </div>
                </div>
            </AccordionSection>

            {/* Category Classification */}
            <AccordionSection title="Category Classification — Cafe vs Retail" defaultOpen>
                <CategoryClassification />
            </AccordionSection>

            {/* Collapsed sections */}
            <AccordionSection title="Staff Rates" defaultOpen>
                <StaffRatesEditor />
            </AccordionSection>

            <AccordionSection title="SMS Campaigns">
                <p className="text-sm text-muted-foreground">SMS campaign configuration options coming soon.</p>
            </AccordionSection>

            <AccordionSection title="Chart Appearance">
                <div className="flex gap-8">
                    {[
                        { label: "Primary Color", color: "#6B7355" },
                        { label: "Comparison", color: "#A8B094" },
                        { label: "Positive Badge", color: "#2D936C" },
                        { label: "Negative Badge", color: "#E07A5F" },
                    ].map((item) => (
                        <div key={item.label} className="text-center">
                            <div className="w-10 h-10 rounded-full mx-auto mb-2 border-2 border-border" style={{ backgroundColor: item.color }} />
                            <span className="text-xs text-text-body">{item.label}</span>
                        </div>
                    ))}
                </div>
            </AccordionSection>

            <AccordionSection title="Notifications">
                <p className="text-sm text-muted-foreground">Notification preferences coming soon.</p>
            </AccordionSection>

            {/* Save buttons */}
            <div className="flex gap-3 justify-end pt-2">
                <button className="px-6 py-2.5 bg-olive text-white text-sm font-semibold rounded-lg hover:bg-olive-dark transition-colors duration-200 cursor-pointer">
                    Save Settings
                </button>
                <button className="px-6 py-2.5 border border-border text-text-body text-sm font-medium rounded-lg hover:bg-olive-surface transition-colors duration-200 cursor-pointer">
                    Reset to Defaults
                </button>
            </div>
        </motion.div>
    );
}
