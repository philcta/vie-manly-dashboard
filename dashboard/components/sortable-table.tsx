"use client";

import { useState, useMemo, useRef, useEffect } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown, Search, X } from "lucide-react";

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
    /** Column keys to enable text search on. If provided, a search bar appears. */
    searchKeys?: string[];
    /** Placeholder text for the search input */
    searchPlaceholder?: string;
}

// ── Component ───────────────────────────────────────────────────

export function SortableTable<T extends Record<string, unknown>>({
    title,
    columns,
    data,
    defaultSortKey,
    defaultSortDir = "desc",
    showCount = true,
    searchKeys,
    searchPlaceholder = "Search…",
}: SortableTableProps<T>) {
    const [sortKey, setSortKey] = useState(defaultSortKey || columns[0]?.key || "");
    const [sortDir, setSortDir] = useState<"asc" | "desc">(defaultSortDir);
    const [searchQuery, setSearchQuery] = useState("");
    const [searchOpen, setSearchOpen] = useState(false);
    const searchInputRef = useRef<HTMLInputElement>(null);

    const handleSort = (key: string) => {
        if (sortKey === key) {
            setSortDir(sortDir === "asc" ? "desc" : "asc");
        } else {
            setSortKey(key);
            setSortDir("desc");
        }
    };

    // Focus search input when opened
    useEffect(() => {
        if (searchOpen && searchInputRef.current) {
            searchInputRef.current.focus();
        }
    }, [searchOpen]);

    // Filter by search query
    const filteredData = useMemo(() => {
        if (!searchKeys || !searchQuery.trim()) return data;

        const q = searchQuery.trim().toLowerCase();
        return data.filter((row) =>
            searchKeys.some((key) => {
                const col = columns.find((c) => c.key === key);
                // Use sortValue if available (it returns a string for text columns)
                const rawVal = col?.sortValue
                    ? col.sortValue(row)
                    : (row[key as keyof T] as unknown);
                const strVal = String(rawVal ?? "").toLowerCase();
                return strVal.includes(q);
            })
        );
    }, [data, searchQuery, searchKeys, columns]);

    const sortedData = useMemo(() => {
        const col = columns.find((c) => c.key === sortKey);
        if (!col) return filteredData;

        return [...filteredData].sort((a, b) => {
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
    }, [filteredData, sortKey, sortDir, columns]);

    const alignClass = (align?: string) => {
        if (align === "right") return "text-right";
        if (align === "center") return "text-center";
        return "text-left";
    };

    const hasSearch = searchKeys && searchKeys.length > 0;

    return (
        <div
            className="bg-card rounded-xl border border-border overflow-hidden"
            style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}
        >
            {/* Header */}
            <div className="px-6 py-4 border-b border-border flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                    <h3 className="text-base font-semibold text-foreground">{title}</h3>
                    {showCount && (
                        <span className="text-xs text-muted-foreground bg-muted px-2.5 py-1 rounded-full font-medium">
                            {filteredData.length === data.length
                                ? `${data.length} total`
                                : `${filteredData.length} of ${data.length}`}
                        </span>
                    )}
                </div>
                {hasSearch && (
                    <div className="flex items-center gap-2">
                        {searchOpen ? (
                            <div className="flex items-center gap-1.5 bg-[#FAFAF8] border border-border rounded-lg px-3 py-1.5 transition-all duration-200">
                                <Search className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                                <input
                                    ref={searchInputRef}
                                    type="text"
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    placeholder={searchPlaceholder}
                                    className="bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none w-48"
                                />
                                {searchQuery && (
                                    <button
                                        onClick={() => setSearchQuery("")}
                                        className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                                    >
                                        <X className="w-3.5 h-3.5" />
                                    </button>
                                )}
                                <button
                                    onClick={() => { setSearchQuery(""); setSearchOpen(false); }}
                                    className="text-xs text-muted-foreground hover:text-foreground ml-1 cursor-pointer"
                                >
                                    Close
                                </button>
                            </div>
                        ) : (
                            <button
                                onClick={() => setSearchOpen(true)}
                                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer px-2.5 py-1.5 rounded-lg hover:bg-[#FAFAF8]"
                            >
                                <Search className="w-3.5 h-3.5" />
                                Search
                            </button>
                        )}
                    </div>
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
                        {sortedData.length === 0 && (
                            <tr>
                                <td
                                    colSpan={columns.length}
                                    className="px-4 py-8 text-center text-muted-foreground text-sm"
                                >
                                    {searchQuery
                                        ? `No results for "${searchQuery}"`
                                        : "No data available"}
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
