"use client";

import { useState, useRef, useEffect } from "react";
import { CalendarDays, ChevronDown } from "lucide-react";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import {
    type PeriodType,
    type ComparisonType,
    periodLabels,
    comparisonLabels,
    formatDateRange,
    resolvePeriodRange,
    resolveComparisonRange,
    type DateRange,
} from "@/lib/dates";

interface PeriodSelectorProps {
    period: PeriodType;
    comparison: ComparisonType;
    customStart?: string;
    customEnd?: string;
    onPeriodChange: (period: PeriodType) => void;
    onComparisonChange: (comparison: ComparisonType) => void;
    onCustomRangeChange?: (start: string, end: string) => void;
    /** Which period options to show (defaults to all) */
    periods?: PeriodType[];
    /** Which comparison options to show (defaults to all) */
    comparisons?: ComparisonType[];
    /** Show comparison selector? */
    showComparison?: boolean;
}

const DEFAULT_PERIODS: PeriodType[] = [
    "today", "this_week", "this_month", "last_week", "last_month",
    "this_quarter", "last_quarter", "current_fy", "past_fy", "custom",
];

const DEFAULT_COMPARISONS: ComparisonType[] = [
    "prior_period", "prior_same_weekday",
    "same_period_last_year", "prior_fy",
];

/** Pills shown directly in the toolbar */
const PILL_PERIODS: PeriodType[] = ["today", "this_week", "this_month", "last_week", "last_month"];

export default function PeriodSelector({
    period,
    comparison,
    customStart = "",
    customEnd = "",
    onPeriodChange,
    onComparisonChange,
    onCustomRangeChange,
    periods = DEFAULT_PERIODS,
    comparisons = DEFAULT_COMPARISONS,
    showComparison = true,
}: PeriodSelectorProps) {
    const [customOpen, setCustomOpen] = useState(false);
    const [tempStart, setTempStart] = useState<Date | null>(
        customStart ? new Date(customStart) : null
    );
    const [tempEnd, setTempEnd] = useState<Date | null>(
        customEnd ? new Date(customEnd) : null
    );
    const customRef = useRef<HTMLDivElement>(null);

    // Close custom picker on outside click
    useEffect(() => {
        function handleClick(e: MouseEvent) {
            if (customRef.current && !customRef.current.contains(e.target as Node)) {
                setCustomOpen(false);
            }
        }
        if (customOpen) document.addEventListener("mousedown", handleClick);
        return () => document.removeEventListener("mousedown", handleClick);
    }, [customOpen]);

    // Calculate current range for display
    const currentRange = resolvePeriodRange(period, customStart, customEnd);
    const compRange = resolveComparisonRange(currentRange, comparison, period);

    // Split periods into "pill" presets and "dropdown" options
    const activePills = PILL_PERIODS.filter((p) => periods.includes(p));
    const dropdownPeriods = periods.filter(
        (p) => !PILL_PERIODS.includes(p) && p !== "custom"
    );
    const hasCustom = periods.includes("custom");

    // Handle period selection from dropdown
    const handleDropdownPeriod = (p: PeriodType) => {
        if (p === "custom") {
            setCustomOpen(true);
        } else {
            onPeriodChange(p);
        }
    };

    // Format Date to YYYY-MM-DD string
    const toDateStr = (d: Date | null): string => {
        if (!d) return "";
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, "0");
        const day = String(d.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    };

    // Apply custom date range
    const applyCustomRange = () => {
        if (tempStart && tempEnd) {
            onCustomRangeChange?.(toDateStr(tempStart), toDateStr(tempEnd));
            onPeriodChange("custom");
            setCustomOpen(false);
        }
    };

    // Filter comparisons: "Same weekday" only sensible for "today"
    const availableComparisons = comparisons.filter((c) => {
        if (c === "prior_same_weekday" && period !== "today") return false;
        return true;
    });

    return (
        <div className="space-y-2">
            <div className="flex items-center gap-3">
                {/* Period pills (Today / This week / This month / Last week / Last month) */}
                <div className="flex items-center rounded-full border border-border bg-card overflow-hidden">
                    {activePills.map((p) => (
                        <button
                            key={p}
                            onClick={() => onPeriodChange(p)}
                            className={`px-4 py-1.5 text-sm font-medium transition-colors duration-200 cursor-pointer whitespace-nowrap ${period === p
                                ? "bg-olive text-white"
                                : "text-text-body hover:bg-olive-surface"
                                }`}
                        >
                            {periodLabels[p]}
                        </button>
                    ))}
                </div>

                {/* Extended period dropdown (This quarter / Last quarter / Current FY / Past FY / Custom) */}
                {(dropdownPeriods.length > 0 || hasCustom) && (
                    <div className="relative" ref={customRef}>
                        <button
                            onClick={() => setCustomOpen(!customOpen)}
                            className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-full border transition-colors duration-200 cursor-pointer ${dropdownPeriods.includes(period) || period === "custom"
                                ? "bg-olive text-white border-olive"
                                : "border-border bg-card text-text-body hover:bg-olive-surface"
                                }`}
                        >
                            <CalendarDays className="w-3.5 h-3.5" />
                            {dropdownPeriods.includes(period) || period === "custom"
                                ? periodLabels[period]
                                : "More"}
                            <ChevronDown className="w-3 h-3" />
                        </button>

                        {customOpen && (
                            <div className="absolute right-0 top-full mt-2 z-50 bg-card rounded-xl border border-border shadow-lg overflow-visible min-w-[260px]"
                                style={{ boxShadow: "0 8px 24px rgba(0,0,0,0.12)" }}>
                                {/* Preset options */}
                                <div className="py-1">
                                    {dropdownPeriods.map((p) => (
                                        <button
                                            key={p}
                                            onClick={() => {
                                                handleDropdownPeriod(p);
                                                setCustomOpen(false);
                                            }}
                                            className={`w-full text-left px-4 py-2.5 text-sm cursor-pointer transition-colors ${period === p
                                                ? "bg-olive-surface text-olive font-medium"
                                                : "text-foreground hover:bg-[#F8F8F6]"
                                                }`}
                                        >
                                            {periodLabels[p]}
                                        </button>
                                    ))}
                                </div>

                                {/* Custom date picker */}
                                {hasCustom && (
                                    <>
                                        <div className="border-t border-border" />
                                        <div className="p-4 space-y-3">
                                            <p className="text-xs font-semibold uppercase tracking-wider text-text-body">
                                                Custom range
                                            </p>
                                            <div className="grid grid-cols-2 gap-2">
                                                <div>
                                                    <label className="text-xs text-muted-foreground block mb-1">From</label>
                                                    <DatePicker
                                                        selected={tempStart}
                                                        onChange={(date: Date | null) => setTempStart(date)}
                                                        selectsStart
                                                        startDate={tempStart}
                                                        endDate={tempEnd}
                                                        dateFormat="dd/MM/yyyy"
                                                        placeholderText="dd/mm/yyyy"
                                                        className="w-full px-2.5 py-1.5 text-sm rounded-lg border border-border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-olive/30 focus:border-olive"
                                                        calendarClassName="vie-datepicker"
                                                        showPopperArrow={false}
                                                        popperPlacement="bottom-start"
                                                    />
                                                </div>
                                                <div>
                                                    <label className="text-xs text-muted-foreground block mb-1">To</label>
                                                    <DatePicker
                                                        selected={tempEnd}
                                                        onChange={(date: Date | null) => setTempEnd(date)}
                                                        selectsEnd
                                                        startDate={tempStart}
                                                        endDate={tempEnd}
                                                        minDate={tempStart ?? undefined}
                                                        dateFormat="dd/MM/yyyy"
                                                        placeholderText="dd/mm/yyyy"
                                                        className="w-full px-2.5 py-1.5 text-sm rounded-lg border border-border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-olive/30 focus:border-olive"
                                                        calendarClassName="vie-datepicker"
                                                        showPopperArrow={false}
                                                        popperPlacement="bottom-start"
                                                    />
                                                </div>
                                            </div>
                                            <button
                                                onClick={applyCustomRange}
                                                disabled={!tempStart || !tempEnd}
                                                className="w-full py-2 text-sm font-semibold rounded-lg bg-olive text-white hover:bg-olive/90 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
                                            >
                                                Apply
                                            </button>
                                        </div>
                                    </>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {/* Comparison selector */}
                {showComparison && (
                    <select
                        value={availableComparisons.includes(comparison) ? comparison : "prior_period"}
                        onChange={(e) => onComparisonChange(e.target.value as ComparisonType)}
                        className="px-3 py-1.5 text-sm rounded-full border border-border bg-card text-text-body cursor-pointer focus:outline-none focus:ring-2 focus:ring-olive/20"
                    >
                        {availableComparisons.map((c) => (
                            <option key={c} value={c}>{comparisonLabels[c]}</option>
                        ))}
                    </select>
                )}
            </div>

            {/* Date display bar */}
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <CalendarDays className="w-4 h-4" />
                <span>{formatDateRange(currentRange.startDate, currentRange.endDate)}</span>
                {showComparison && (
                    <>
                        <span className="text-olive">•</span>
                        <span>{comparisonLabels[comparison]}: {formatDateRange(compRange.startDate, compRange.endDate)}</span>
                    </>
                )}
            </div>
        </div>
    );
}
