/**
 * Formatting utilities for the VIE. MANLY dashboard.
 * All formatters used by KPI cards, tables, and charts.
 */

/** Format as AUD currency — $1,234.56 */
export function formatCurrency(value: number, decimals = 2): string {
    return new Intl.NumberFormat("en-AU", {
        style: "currency",
        currency: "AUD",
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    }).format(value);
}

/** Format as compact currency — $1.2K */
export function formatCompactCurrency(value: number): string {
    if (Math.abs(value) >= 1000) {
        return `$${(value / 1000).toFixed(1)}K`;
    }
    return formatCurrency(value, 0);
}

/** Format as percentage — 42.3% */
export function formatPercent(value: number, decimals = 1): string {
    return `${value.toFixed(decimals)}%`;
}

/** Format number with comma separators — 1,234 */
export function formatNumber(value: number, decimals = 0): string {
    return new Intl.NumberFormat("en-AU", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    }).format(value);
}

/**
 * Calculate % change between current and comparison values.
 * Formula: (current - comparison) / comparison × 100
 * Returns null when comparison is 0 (no data) to avoid misleading "100%" badges.
 */
export function calcChange(current: number, comparison: number): number | null {
    if (comparison === 0) return null; // No comparison data — show no badge
    return ((current - comparison) / Math.abs(comparison)) * 100;
}

/** Format a date string to display format */
export function formatDate(dateStr: string): string {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-AU", {
        day: "numeric",
        month: "short",
        year: "numeric",
    });
}

/** Format a date to short day — "Mon", "Tue" */
export function formatShortDay(dateStr: string): string {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-AU", { weekday: "short" });
}

/** Format hour number to label — 7 → "7am", 13 → "1pm" */
export function formatHour(hour: number): string {
    if (hour === 0) return "12am";
    if (hour < 12) return `${hour}am`;
    if (hour === 12) return "12pm";
    return `${hour - 12}pm`;
}
