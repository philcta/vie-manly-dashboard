"use client";

import { useState, useMemo } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";

// ── Types ───────────────────────────────────────────────────────

export interface ColumnDef<T> {
    key: string;
    label: string;
    /** Extract value for sorting (defaults to row[key]) */
    sortValue?: (row: T) => number | string;
    /** Render cell content */
    render: (row: T) => React.ReactNode;
    align?: "left" | "right" | "center";
}

interface SortableTableProps<T> {
    title: string;
    columns: ColumnDef<T>[];
    data: T[];
    defaultSortKey?: string;
    defaultSortDir?: "asc" | "desc";
    /** Optional: show a count badge in the header */
    showCount?: boolean;
}

// ── Component ───────────────────────────────────────────────────

export function SortableTable<T extends Record<string, unknown>>({
    title,
    columns,
    data,
    defaultSortKey,
    defaultSortDir = "desc",
    showCount = true,
}: SortableTableProps<T>) {
    const [sortKey, setSortKey] = useState(defaultSortKey || columns[0]?.key || "");
    const [sortDir, setSortDir] = useState<"asc" | "desc">(defaultSortDir);

    const handleSort = (key: string) => {
        if (sortKey === key) {
            setSortDir(sortDir === "asc" ? "desc" : "asc");
        } else {
            setSortKey(key);
            setSortDir("desc");
        }
    };

    const sortedData = useMemo(() => {
        const col = columns.find((c) => c.key === sortKey);
        if (!col) return data;

        return [...data].sort((a, b) => {
            const aVal = col.sortValue ? col.sortValue(a) : (a[col.key as keyof T] as unknown);
            const bVal = col.sortValue ? col.sortValue(b) : (b[col.key as keyof T] as unknown);

            let cmp = 0;
            if (typeof aVal === "string" && typeof bVal === "string") {
                cmp = aVal.localeCompare(bVal);
            } else {
                cmp = (Number(aVal) || 0) - (Number(bVal) || 0);
            }

            return sortDir === "asc" ? cmp : -cmp;
        });
    }, [data, sortKey, sortDir, columns]);

    const alignClass = (align?: string) => {
        if (align === "right") return "text-right";
        if (align === "center") return "text-center";
        return "text-left";
    };

    return (
        <div
            className="bg-card rounded-xl border border-border overflow-hidden"
            style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}
        >
            {/* Header */}
            <div className="px-6 py-4 border-b border-border flex items-center justify-between">
                <h3 className="text-base font-semibold text-foreground">{title}</h3>
                {showCount && (
                    <span className="text-xs text-muted-foreground bg-muted px-2.5 py-1 rounded-full font-medium">
                        {data.length} total
                    </span>
                )}
            </div>

            {/* Table */}
            <div className="overflow-x-auto max-h-[520px] overflow-y-auto">
                <table className="w-full">
                    <thead className="sticky top-0 z-10">
                        <tr className="bg-[#FAFAF8]">
                            {columns.map((col) => (
                                <th
                                    key={col.key}
                                    onClick={() => handleSort(col.key)}
                                    className={`px-4 py-3 text-xs font-semibold uppercase tracking-wider text-text-body cursor-pointer select-none hover:text-foreground transition-colors ${alignClass(col.align)}`}
                                >
                                    <span className="inline-flex items-center gap-1">
                                        {col.label}
                                        {sortKey === col.key ? (
                                            sortDir === "asc" ? (
                                                <ChevronUp className="w-3.5 h-3.5 text-olive" />
                                            ) : (
                                                <ChevronDown className="w-3.5 h-3.5 text-olive" />
                                            )
                                        ) : (
                                            <ChevronsUpDown className="w-3.5 h-3.5 opacity-30" />
                                        )}
                                    </span>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {sortedData.map((row, i) => (
                            <tr key={i} className="border-b border-[#F0F0EE] row-hover">
                                {columns.map((col) => (
                                    <td
                                        key={col.key}
                                        className={`px-4 py-3 text-sm ${alignClass(col.align)}`}
                                    >
                                        {col.render(row)}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
