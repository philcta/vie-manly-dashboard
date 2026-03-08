"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
    fetchCategoryMappings,
    updateCategorySide,
    type CategoryMapping,
} from "@/lib/queries/categories";

export default function CategoryClassification() {
    const [mappings, setMappings] = useState<CategoryMapping[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState<string | null>(null);
    const [filter, setFilter] = useState<"all" | "Cafe" | "Retail" | "unassigned">("all");

    const load = useCallback(async () => {
        try {
            const data = await fetchCategoryMappings();
            setMappings(data);
        } catch (e) {
            console.error("Failed to load categories:", e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const handleToggle = async (category: string, newSide: "Cafe" | "Retail") => {
        setSaving(category);
        try {
            await updateCategorySide(category, newSide);
            setMappings((prev) =>
                prev.map((m) =>
                    m.category === category
                        ? { ...m, side: newSide, assigned_at: new Date().toISOString() }
                        : m
                )
            );
        } catch (e) {
            console.error("Failed to update:", e);
        } finally {
            setSaving(null);
        }
    };

    const unassignedCount = mappings.filter((m) => !m.assigned_at).length;

    const filtered = mappings.filter((m) => {
        if (filter === "all") return true;
        if (filter === "unassigned") return !m.assigned_at;
        return m.side === filter;
    });

    const cafeCount = mappings.filter((m) => m.side === "Cafe").length;
    const retailCount = mappings.filter((m) => m.side === "Retail").length;

    if (loading) {
        return (
            <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-olive border-t-transparent" />
                Loading categories...
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Alert for unassigned */}
            {unassignedCount > 0 && (
                <motion.div
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex items-center gap-3 px-4 py-3 bg-warning/10 border border-warning/30 rounded-lg"
                >
                    <span className="text-lg">⚠️</span>
                    <p className="text-sm text-foreground">
                        <strong>{unassignedCount} new {unassignedCount === 1 ? "category needs" : "categories need"}</strong>{" "}
                        classification. Toggle each to <strong>Cafe</strong> or <strong>Retail</strong>.
                    </p>
                    <button
                        onClick={() => setFilter("unassigned")}
                        className="ml-auto text-xs font-semibold text-olive hover:text-olive-dark cursor-pointer"
                    >
                        Show unassigned
                    </button>
                </motion.div>
            )}

            {/* Filter pills */}
            <div className="flex items-center gap-2">
                {[
                    { value: "all" as const, label: `All (${mappings.length})` },
                    { value: "Cafe" as const, label: `Cafe (${cafeCount})` },
                    { value: "Retail" as const, label: `Retail (${retailCount})` },
                    ...(unassignedCount > 0
                        ? [{ value: "unassigned" as const, label: `Unassigned (${unassignedCount})` }]
                        : []),
                ].map((pill) => (
                    <button
                        key={pill.value}
                        onClick={() => setFilter(pill.value)}
                        className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors cursor-pointer ${filter === pill.value
                                ? "bg-olive text-white"
                                : "bg-olive-surface text-text-body hover:bg-olive/10"
                            }`}
                    >
                        {pill.label}
                    </button>
                ))}
            </div>

            {/* Category list */}
            <div className="rounded-lg border border-border overflow-hidden">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="bg-[#FAFAF8] text-xs text-text-muted uppercase tracking-wider">
                            <th className="text-left px-4 py-2.5 font-medium">Category</th>
                            <th className="text-center px-4 py-2.5 font-medium w-40">Classification</th>
                            <th className="text-right px-4 py-2.5 font-medium w-28">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filtered.map((m, i) => (
                            <tr
                                key={m.category}
                                className={`border-t border-border transition-colors ${!m.assigned_at ? "bg-warning/5" : i % 2 === 0 ? "bg-white" : "bg-[#FAFAF8]/50"
                                    }`}
                            >
                                <td className="px-4 py-2.5 text-text-body font-medium">
                                    {m.category}
                                </td>
                                <td className="px-4 py-2.5">
                                    <div className="flex justify-center">
                                        <div className="inline-flex rounded-full border border-border overflow-hidden">
                                            <button
                                                onClick={() => handleToggle(m.category, "Cafe")}
                                                disabled={saving === m.category}
                                                className={`px-3 py-1 text-xs font-medium transition-colors cursor-pointer ${m.side === "Cafe"
                                                        ? "bg-olive text-white"
                                                        : "text-text-body hover:bg-olive-surface"
                                                    }`}
                                            >
                                                Cafe
                                            </button>
                                            <button
                                                onClick={() => handleToggle(m.category, "Retail")}
                                                disabled={saving === m.category}
                                                className={`px-3 py-1 text-xs font-medium transition-colors cursor-pointer ${m.side === "Retail"
                                                        ? "bg-olive text-white"
                                                        : "text-text-body hover:bg-olive-surface"
                                                    }`}
                                            >
                                                Retail
                                            </button>
                                        </div>
                                    </div>
                                </td>
                                <td className="px-4 py-2.5 text-right">
                                    {saving === m.category ? (
                                        <span className="text-xs text-muted-foreground">Saving...</span>
                                    ) : !m.assigned_at ? (
                                        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-warning/10 text-warning">
                                            New
                                        </span>
                                    ) : (
                                        <span className="text-xs text-muted-foreground">✓</span>
                                    )}
                                </td>
                            </tr>
                        ))}
                        {filtered.length === 0 && (
                            <tr>
                                <td colSpan={3} className="px-4 py-8 text-center text-muted-foreground text-sm">
                                    No categories match this filter.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
