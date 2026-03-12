"use client";

import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown, ChevronRight, ChevronLeft, Search, X } from "lucide-react";

// ── Types ───────────────────────────────────────────────────────

export interface ColumnDef<T> {
    key: string;
    label: string;
    /** Extract value for sorting (defaults to row[key]) */
    sortValue?: (row: T) => number | string;
    /** Render cell content */
    render: (row: T) => React.ReactNode;
    align?: "left" | "right" | "center";
    /** If set, this column belongs to a collapsible group.
     *  The "parent" column has group = "groupName" and is always visible.
     *  Child columns have group = "groupName" and are hidden when collapsed. */
    group?: string;
    /** If true, this is the parent column that triggers expand/collapse */
    groupParent?: boolean;
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
    /** Optional: extra action buttons rendered in the header row */
    headerActions?: React.ReactNode;
}

// ── Debounce hook ───────────────────────────────────────────────

function useDebouncedValue<T>(value: T, delay: number): T {
    const [debounced, setDebounced] = useState(value);
    useEffect(() => {
        const timer = setTimeout(() => setDebounced(value), delay);
        return () => clearTimeout(timer);
    }, [value, delay]);
    return debounced;
}

// ── Virtualised row rendering ───────────────────────────────────

const ROW_HEIGHT = 36; // px per row
const OVERSCAN = 10; // extra rows above/below viewport

function useVirtualScroll(containerRef: React.RefObject<HTMLDivElement | null>, totalRows: number) {
    const [scrollTop, setScrollTop] = useState(0);
    const [containerHeight, setContainerHeight] = useState(480);

    useEffect(() => {
        const el = containerRef.current;
        if (!el) return;

        const obs = new ResizeObserver((entries) => {
            for (const entry of entries) {
                setContainerHeight(entry.contentRect.height);
            }
        });
        obs.observe(el);

        const handleScroll = () => setScrollTop(el.scrollTop);
        el.addEventListener("scroll", handleScroll, { passive: true });

        return () => {
            obs.disconnect();
            el.removeEventListener("scroll", handleScroll);
        };
    }, [containerRef]);

    const startIndex = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
    const visibleCount = Math.ceil(containerHeight / ROW_HEIGHT) + OVERSCAN * 2;
    const endIndex = Math.min(totalRows, startIndex + visibleCount);

    return { startIndex, endIndex, totalHeight: totalRows * ROW_HEIGHT };
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
    headerActions,
}: SortableTableProps<T>) {
    const [sortKey, setSortKey] = useState(defaultSortKey || columns[0]?.key || "");
    const [sortDir, setSortDir] = useState<"asc" | "desc">(defaultSortDir);
    const [searchQuery, setSearchQuery] = useState("");
    const [searchOpen, setSearchOpen] = useState(false);
    const searchInputRef = useRef<HTMLInputElement>(null);
    const scrollContainerRef = useRef<HTMLDivElement>(null);

    // Debounce search to 150ms — instant feel, stops re-renders mid-typing
    const debouncedQuery = useDebouncedValue(searchQuery, 150);

    // Track which groups are expanded
    const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

    const toggleGroup = (groupName: string) => {
        setExpandedGroups((prev) => {
            const next = new Set(prev);
            if (next.has(groupName)) next.delete(groupName);
            else next.add(groupName);
            return next;
        });
    };

    // Determine visible columns (filter out collapsed group children)
    const visibleColumns = useMemo(() => {
        return columns.filter((col) => {
            if (!col.group) return true;
            if (col.groupParent) return true;
            return expandedGroups.has(col.group);
        });
    }, [columns, expandedGroups]);

    const handleSort = useCallback((key: string) => {
        setSortKey(prev => {
            if (prev === key) {
                setSortDir(d => d === "asc" ? "desc" : "asc");
                return prev;
            }
            setSortDir("desc");
            return key;
        });
    }, []);

    // Focus search input when opened
    useEffect(() => {
        if (searchOpen && searchInputRef.current) {
            searchInputRef.current.focus();
        }
    }, [searchOpen]);

    // Pre-build search value extractors once (avoid columns.find per row per key)
    const searchExtractors = useMemo(() => {
        if (!searchKeys) return [];
        return searchKeys.map((key) => {
            const col = columns.find((c) => c.key === key);
            return (row: T): string => {
                const rawVal = col?.sortValue
                    ? col.sortValue(row)
                    : (row[key as keyof T] as unknown);
                return String(rawVal ?? "").toLowerCase();
            };
        });
    }, [searchKeys, columns]);

    // Filter by search query (uses debounced value)
    const filteredData = useMemo(() => {
        if (!searchExtractors.length || !debouncedQuery.trim()) return data;
        const q = debouncedQuery.trim().toLowerCase();
        return data.filter((row) =>
            searchExtractors.some((extract) => extract(row).includes(q))
        );
    }, [data, debouncedQuery, searchExtractors]);

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

    // Virtual scroll
    const { startIndex, endIndex, totalHeight } = useVirtualScroll(scrollContainerRef, sortedData.length);
    const virtualRows = sortedData.slice(startIndex, endIndex);

    const alignClass = (align?: string) => {
        if (align === "right") return "text-right";
        if (align === "center") return "text-center";
        return "text-left";
    };

    const hasSearch = searchKeys && searchKeys.length > 0;

    // Collect unique group names that have children
    const groups = useMemo(() => {
        const groupNames = new Set<string>();
        for (const col of columns) {
            if (col.group && !col.groupParent) groupNames.add(col.group);
        }
        return groupNames;
    }, [columns]);

    return (
        <div
            className="bg-card rounded-xl border border-border overflow-hidden"
            style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}
        >
            {/* Header */}
            <div className="px-4 py-3 border-b border-border flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                    <h3 className="text-base font-semibold text-foreground">{title}</h3>
                    {showCount && (
                        <span className="text-xs text-muted-foreground bg-muted px-2.5 py-1 rounded-full font-medium">
                            {filteredData.length === data.length
                                ? `${data.length} total`
                                : `${filteredData.length} of ${data.length}`}
                        </span>
                    )}
                    {headerActions}
                </div>
                <div className="flex items-center gap-2">
                    {/* Group expand/collapse toggles */}
                    {groups.size > 0 && (
                        <div className="flex items-center gap-1 mr-2">
                            {Array.from(groups).map((groupName) => {
                                const isExpanded = expandedGroups.has(groupName);
                                return (
                                    <button
                                        key={groupName}
                                        onClick={() => toggleGroup(groupName)}
                                        className={`flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-all duration-200 cursor-pointer ${isExpanded
                                            ? "bg-olive/10 text-olive"
                                            : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                                            }`}
                                        title={isExpanded ? `Collapse ${groupName}` : `Expand ${groupName}`}
                                    >
                                        {isExpanded ? (
                                            <ChevronLeft className="w-3 h-3" />
                                        ) : (
                                            <ChevronRight className="w-3 h-3" />
                                        )}
                                        {groupName}
                                    </button>
                                );
                            })}
                        </div>
                    )}
                    {hasSearch && (
                        <>
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
                        </>
                    )}
                </div>
            </div>

            {/* Table */}
            <div ref={scrollContainerRef} className="overflow-x-auto max-h-[480px] overflow-y-auto">
                <table className="w-full">
                    <thead className="sticky top-0 z-10">
                        <tr className="bg-[#FAFAF8]">
                            {visibleColumns.map((col) => {
                                const isGroupParent = col.groupParent && col.group;
                                const isExpanded = col.group ? expandedGroups.has(col.group) : false;
                                return (
                                    <th
                                        key={col.key}
                                        className={`px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-text-body select-none transition-colors whitespace-nowrap ${alignClass(col.align)} ${col.sortValue || col.key ? "cursor-pointer hover:text-foreground" : ""}`}
                                    >
                                        <span className="inline-flex items-center gap-1">
                                            {isGroupParent && (
                                                <button
                                                    onClick={(e) => { e.stopPropagation(); toggleGroup(col.group!); }}
                                                    className="cursor-pointer hover:text-olive transition-colors"
                                                >
                                                    {isExpanded ? (
                                                        <ChevronLeft className="w-3 h-3" />
                                                    ) : (
                                                        <ChevronRight className="w-3 h-3" />
                                                    )}
                                                </button>
                                            )}
                                            <span onClick={() => handleSort(col.key)}>
                                                {col.label}
                                            </span>
                                            <span onClick={() => handleSort(col.key)} className="cursor-pointer">
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
                                        </span>
                                    </th>
                                );
                            })}
                        </tr>
                    </thead>
                    <tbody>
                        {/* Virtual scroll spacer (top) */}
                        {startIndex > 0 && (
                            <tr style={{ height: startIndex * ROW_HEIGHT }} aria-hidden>
                                <td colSpan={visibleColumns.length} />
                            </tr>
                        )}
                        {virtualRows.map((row, i) => (
                            <tr key={startIndex + i} className="border-b border-[#F0F0EE] row-hover" style={{ height: ROW_HEIGHT }}>
                                {visibleColumns.map((col) => (
                                    <td
                                        key={col.key}
                                        className={`px-3 py-2 text-[13px] ${alignClass(col.align)} ${col.group && !col.groupParent ? "bg-[#FAFAF8]/50" : ""}`}
                                    >
                                        {col.render(row)}
                                    </td>
                                ))}
                            </tr>
                        ))}
                        {/* Virtual scroll spacer (bottom) */}
                        {endIndex < sortedData.length && (
                            <tr style={{ height: (sortedData.length - endIndex) * ROW_HEIGHT }} aria-hidden>
                                <td colSpan={visibleColumns.length} />
                            </tr>
                        )}
                        {sortedData.length === 0 && (
                            <tr>
                                <td
                                    colSpan={visibleColumns.length}
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
