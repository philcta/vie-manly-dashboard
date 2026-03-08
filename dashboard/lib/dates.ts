/**
 * Date period utilities for the dashboard.
 * Handles comparison period logic per formulas_reference.md Section 7.
 *
 * Australian Tax Year: 1 July – 30 June
 */

/** Get today's date in YYYY-MM-DD format (Sydney timezone) */
export function getToday(): string {
    return new Date().toLocaleDateString("en-CA", {
        timeZone: "Australia/Sydney",
    });
}

/** Get date N days ago */
export function daysAgo(n: number, from?: string): string {
    const d = from ? new Date(from) : new Date();
    d.setDate(d.getDate() - n);
    return d.toISOString().split("T")[0];
}

/** Get start of current week (Monday) */
export function startOfWeek(dateStr?: string): string {
    const d = dateStr ? new Date(dateStr) : new Date();
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    d.setDate(diff);
    return d.toISOString().split("T")[0];
}

/** Get start of current month */
export function startOfMonth(dateStr?: string): string {
    const d = dateStr ? new Date(dateStr) : new Date();
    d.setDate(1);
    return d.toISOString().split("T")[0];
}

/** Get start of last month */
export function startOfLastMonth(dateStr?: string): string {
    const d = dateStr ? new Date(dateStr) : new Date();
    d.setMonth(d.getMonth() - 1);
    d.setDate(1);
    return d.toISOString().split("T")[0];
}

/** Get end of last month */
export function endOfLastMonth(dateStr?: string): string {
    const d = dateStr ? new Date(dateStr) : new Date();
    d.setDate(0); // last day of previous month
    return d.toISOString().split("T")[0];
}

// ============================================
// Australian Tax Year Helpers (1 Jul – 30 Jun)
// ============================================

/** Get the tax year that a date falls in (returns the ending year, e.g. FY2026 = Jul 2025 – Jun 2026) */
export function getTaxYear(dateStr?: string): number {
    const d = dateStr ? new Date(dateStr) : new Date();
    const month = d.getMonth(); // 0-indexed
    const year = d.getFullYear();
    return month >= 6 ? year + 1 : year;
}

/** Get start of a tax year (1 July of the prior calendar year) */
export function startOfTaxYear(fy: number): string {
    return `${fy - 1}-07-01`;
}

/** Get end of a tax year (30 June) */
export function endOfTaxYear(fy: number): string {
    return `${fy}-06-30`;
}

/** Get current tax year start */
export function currentTaxYearStart(dateStr?: string): string {
    return startOfTaxYear(getTaxYear(dateStr));
}

/** Get current tax year end (or today if FY not finished) */
export function currentTaxYearEnd(dateStr?: string): string {
    const today = dateStr || getToday();
    const fy = getTaxYear(today);
    const fyEnd = endOfTaxYear(fy);
    return today < fyEnd ? today : fyEnd;
}

/** Get past tax year start */
export function pastTaxYearStart(dateStr?: string): string {
    const fy = getTaxYear(dateStr) - 1;
    return startOfTaxYear(fy);
}

/** Get past tax year end */
export function pastTaxYearEnd(dateStr?: string): string {
    const fy = getTaxYear(dateStr) - 1;
    return endOfTaxYear(fy);
}

// ============================================
// Quarter helpers (calendar quarters)
// ============================================

/** Get start of the calendar quarter for a given date */
export function startOfQuarter(dateStr?: string): string {
    const d = dateStr ? new Date(dateStr) : new Date();
    const q = Math.floor(d.getMonth() / 3);
    return `${d.getFullYear()}-${String(q * 3 + 1).padStart(2, "0")}-01`;
}

/** Get end of the calendar quarter for a given date */
export function endOfQuarter(dateStr?: string): string {
    const d = dateStr ? new Date(dateStr) : new Date();
    const q = Math.floor(d.getMonth() / 3);
    const endMonth = q * 3 + 3; // 1-indexed: 3, 6, 9, 12
    const endDate = new Date(d.getFullYear(), endMonth, 0); // last day of that month
    return endDate.toISOString().split("T")[0];
}

/** Get start of the previous calendar quarter */
export function startOfLastQuarter(dateStr?: string): string {
    const d = dateStr ? new Date(dateStr) : new Date();
    d.setMonth(d.getMonth() - 3);
    return startOfQuarter(d.toISOString().split("T")[0]);
}

/** Get end of the previous calendar quarter */
export function endOfLastQuarter(dateStr?: string): string {
    const d = dateStr ? new Date(dateStr) : new Date();
    d.setMonth(d.getMonth() - 3);
    return endOfQuarter(d.toISOString().split("T")[0]);
}

// ============================================
// Period Range Resolver
// ============================================

export type PeriodType =
    | "today"
    | "this_week"
    | "this_month"
    | "last_week"
    | "last_month"
    | "this_quarter"
    | "last_quarter"
    | "current_fy"
    | "past_fy"
    | "custom";

export type ComparisonType =
    | "prior_period"
    | "prior_same_weekday"
    | "same_period_last_year"
    | "prior_fy";

export interface DateRange {
    startDate: string;
    endDate: string;
}

/** Resolve a period type to a date range */
export function resolvePeriodRange(
    period: PeriodType,
    customStart?: string,
    customEnd?: string
): DateRange {
    const today = getToday();

    switch (period) {
        case "today":
            return { startDate: today, endDate: today };

        case "this_week": {
            const d = new Date(today);
            const day = d.getDay();
            const monday = new Date(d);
            monday.setDate(d.getDate() - (day === 0 ? 6 : day - 1));
            return { startDate: monday.toISOString().split("T")[0], endDate: today };
        }

        case "this_month":
            return { startDate: startOfMonth(today), endDate: today };

        case "last_week": {
            const d = new Date(today);
            const day = d.getDay();
            // Go to Monday of THIS week, then back 7 days = Monday of last week
            const thisMonday = new Date(d);
            thisMonday.setDate(d.getDate() - (day === 0 ? 6 : day - 1));
            const lastMonday = new Date(thisMonday);
            lastMonday.setDate(thisMonday.getDate() - 7);
            const lastSunday = new Date(lastMonday);
            lastSunday.setDate(lastMonday.getDate() + 6);
            return {
                startDate: lastMonday.toISOString().split("T")[0],
                endDate: lastSunday.toISOString().split("T")[0],
            };
        }

        case "last_month":
            return { startDate: startOfLastMonth(today), endDate: endOfLastMonth(today) };

        case "this_quarter": {
            return { startDate: startOfQuarter(today), endDate: today };
        }

        case "last_quarter":
            return { startDate: startOfLastQuarter(today), endDate: endOfLastQuarter(today) };

        case "current_fy":
            return { startDate: currentTaxYearStart(today), endDate: today };

        case "past_fy":
            return { startDate: pastTaxYearStart(today), endDate: pastTaxYearEnd(today) };

        case "custom":
            return {
                startDate: customStart || today,
                endDate: customEnd || today,
            };

        default:
            return { startDate: today, endDate: today };
    }
}

// ============================================
// Comparison Range Resolver
// ============================================

/**
 * Resolve the comparison ("versus") range given the current period and
 * the type of comparison selected.
 *
 * ## "vs. Prior period" rules
 *
 * The prior period is always the **same-shaped calendar window**
 * immediately before the selected period:
 *
 * | Selected period   | Current range (example)  | Prior period                       |
 * |-------------------|-------------------------|------------------------------------|
 * | Today (Thu Mar 6) | Mar 6 → Mar 6           | Mar 5 → Mar 5 (yesterday)          |
 * | This week         | Mon Mar 3 → Thu Mar 6   | Mon Feb 24 → Thu Feb 27            |
 * | This month        | Mar 1 → Mar 6           | Feb 1 → Feb 6                      |
 * | Last week         | Mon Feb 24 → Sun Mar 2  | Mon Feb 17 → Sun Feb 23            |
 * | Last month        | Feb 1 → Feb 28          | Jan 1 → Jan 31                     |
 * | This quarter      | Jan 1 → Mar 6           | Oct 1 → Dec 6 (same day offset)    |
 * | Last quarter      | Oct 1 → Dec 31          | Jul 1 → Sep 30                     |
 * | Current FY        | Jul 1 → Mar 6           | Prior FY same offset                |
 * | Custom            | N days → N days before   |                                    |
 *
 * ## "vs. Same weekday" — only works for "Today"
 *   Shifts by exactly 7 days so you compare the same weekday.
 *
 * ## "vs. Same period last year" — shifts by 1 calendar year
 *
 * ## "vs. Prior FY" — previous full financial year
 */
export function resolveComparisonRange(
    current: DateRange,
    comparison: ComparisonType,
    period?: PeriodType
): DateRange {
    switch (comparison) {
        case "prior_period":
            return resolvePriorPeriod(current, period);

        case "prior_same_weekday": {
            // Shift by 7 days — only really meaningful for "Today"
            return {
                startDate: daysAgo(7, current.startDate),
                endDate: daysAgo(7, current.endDate),
            };
        }

        case "same_period_last_year": {
            // Same dates, 1 year back
            const start = new Date(current.startDate);
            start.setFullYear(start.getFullYear() - 1);
            const end = new Date(current.endDate);
            end.setFullYear(end.getFullYear() - 1);
            return {
                startDate: start.toISOString().split("T")[0],
                endDate: end.toISOString().split("T")[0],
            };
        }

        case "prior_fy": {
            const fy = getTaxYear(current.startDate);
            const priorFy = fy - 1;
            return {
                startDate: startOfTaxYear(priorFy),
                endDate: endOfTaxYear(priorFy),
            };
        }

        default:
            return resolvePriorPeriod(current, period);
    }
}

/**
 * Calendar-aware "prior period" calculation.
 *
 * Instead of naively shifting by N days, this respects the calendar unit
 * so that "This month (Mar 1–6)" compares to "Feb 1–6", not "Feb 23 – Feb 28".
 */
function resolvePriorPeriod(current: DateRange, period?: PeriodType): DateRange {
    const startD = new Date(current.startDate);
    const endD = new Date(current.endDate);

    switch (period) {
        case "today":
            // Yesterday
            return {
                startDate: daysAgo(1, current.startDate),
                endDate: daysAgo(1, current.endDate),
            };

        case "this_week": {
            // Previous week, same Mon–<weekday> shape
            // e.g. Mon Mar 3 → Thu Mar 6 compares to Mon Feb 24 → Thu Feb 27
            return {
                startDate: daysAgo(7, current.startDate),
                endDate: daysAgo(7, current.endDate),
            };
        }

        case "last_week": {
            // Week before last week (full Mon–Sun)
            return {
                startDate: daysAgo(7, current.startDate),
                endDate: daysAgo(7, current.endDate),
            };
        }

        case "this_month": {
            // Previous month, same day-of-month range
            // e.g. Mar 1–6 → Feb 1–6
            const prevStart = new Date(startD);
            prevStart.setMonth(prevStart.getMonth() - 1);
            const prevEnd = new Date(endD);
            prevEnd.setMonth(prevEnd.getMonth() - 1);
            // Clamp to end of previous month if day overflows
            // (e.g. Mar 31 → Feb 28)
            const lastDayOfPrevMonth = new Date(startD.getFullYear(), startD.getMonth(), 0).getDate();
            if (prevEnd.getDate() > lastDayOfPrevMonth) {
                prevEnd.setDate(lastDayOfPrevMonth);
            }
            return {
                startDate: prevStart.toISOString().split("T")[0],
                endDate: prevEnd.toISOString().split("T")[0],
            };
        }

        case "last_month": {
            // Month before last month (full calendar month)
            const prevStart = new Date(startD);
            prevStart.setMonth(prevStart.getMonth() - 1);
            prevStart.setDate(1);
            const prevEnd = new Date(prevStart);
            prevEnd.setMonth(prevEnd.getMonth() + 1);
            prevEnd.setDate(0); // last day of that month
            return {
                startDate: prevStart.toISOString().split("T")[0],
                endDate: prevEnd.toISOString().split("T")[0],
            };
        }

        case "this_quarter": {
            // Previous quarter, same day offset
            // e.g. Jan 1 – Mar 6 → Oct 1 – Dec 6
            const prevStart = new Date(startD);
            prevStart.setMonth(prevStart.getMonth() - 3);
            const prevEnd = new Date(endD);
            prevEnd.setMonth(prevEnd.getMonth() - 3);
            return {
                startDate: prevStart.toISOString().split("T")[0],
                endDate: prevEnd.toISOString().split("T")[0],
            };
        }

        case "last_quarter": {
            // Quarter before last quarter (full calendar quarter)
            const prevStart = new Date(startD);
            prevStart.setMonth(prevStart.getMonth() - 3);
            const prevEnd = new Date(endD);
            prevEnd.setMonth(prevEnd.getMonth() - 3);
            return {
                startDate: prevStart.toISOString().split("T")[0],
                endDate: prevEnd.toISOString().split("T")[0],
            };
        }

        case "current_fy": {
            // Same offset period in the prior FY
            // e.g. Jul 1 2025 – Mar 6 2026 → Jul 1 2024 – Mar 6 2025
            const prevStart = new Date(startD);
            prevStart.setFullYear(prevStart.getFullYear() - 1);
            const prevEnd = new Date(endD);
            prevEnd.setFullYear(prevEnd.getFullYear() - 1);
            return {
                startDate: prevStart.toISOString().split("T")[0],
                endDate: prevEnd.toISOString().split("T")[0],
            };
        }

        case "past_fy": {
            // The FY before past FY
            const fy = getTaxYear(current.startDate) - 1;
            return {
                startDate: startOfTaxYear(fy),
                endDate: endOfTaxYear(fy),
            };
        }

        default: {
            // Generic fallback for custom: same-length period immediately before
            const rangeDays = Math.round(
                (endD.getTime() - startD.getTime()) / 86400000
            );
            return {
                startDate: daysAgo(rangeDays + 1, current.startDate),
                endDate: daysAgo(1, current.startDate),
            };
        }
    }
}

// ============================================
// Comparison helpers (legacy — kept for compat)
// ============================================

/** Get comparison date based on comparison type */
export function getComparisonDate(
    date: string,
    type: "prior_day" | "prior_same_weekday" | "4_weeks_prior" | string
): string {
    switch (type) {
        case "prior_day":
            return daysAgo(1, date);
        case "prior_same_weekday":
            return daysAgo(7, date);
        case "4_weeks_prior":
            return daysAgo(28, date);
        default:
            return daysAgo(1, date);
    }
}

/** Get comparison range for a period (legacy) */
export function getComparisonRange(
    startDate: string,
    endDate: string,
    type: string
): { startDate: string; endDate: string } {
    const start = new Date(startDate);
    const end = new Date(endDate);
    const rangeDays = Math.round(
        (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)
    );

    switch (type) {
        case "prior_day":
            return { startDate: daysAgo(1, startDate), endDate: daysAgo(1, endDate) };
        case "prior_week":
            return { startDate: daysAgo(7, startDate), endDate: daysAgo(7, endDate) };
        case "prior_month":
            return { startDate: daysAgo(rangeDays + 1, startDate), endDate: daysAgo(1, startDate) };
        case "prior_same_weekday":
            return { startDate: daysAgo(7, startDate), endDate: daysAgo(7, endDate) };
        case "4_weeks_prior":
            return { startDate: daysAgo(28, startDate), endDate: daysAgo(28, endDate) };
        default:
            return { startDate: daysAgo(rangeDays + 1, startDate), endDate: daysAgo(1, startDate) };
    }
}

// ============================================
// Display Helpers
// ============================================

/** Format a date as "Sat, 1 Mar" */
export function formatDisplayDate(dateStr: string): string {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-AU", {
        weekday: "short",
        day: "numeric",
        month: "short",
    });
}

/** Format a date range as "Mon 2 Mar — Thu 6 Mar" or "1 Jul 2025 — 30 Jun 2026" */
export function formatDateRange(start: string, end: string): string {
    if (start === end) return formatDisplayDate(start);
    return `${formatDisplayDate(start)} — ${formatDisplayDate(end)}`;
}

/** Period display labels */
export const periodLabels: Record<PeriodType, string> = {
    today: "Today",
    this_week: "This week",
    this_month: "This month",
    last_week: "Last week",
    last_month: "Last month",
    this_quarter: "This quarter",
    last_quarter: "Last quarter",
    current_fy: "Current FY",
    past_fy: "Past FY",
    custom: "Custom",
};

/** Comparison display labels */
export const comparisonLabels: Record<ComparisonType, string> = {
    prior_period: "vs. Prior period",
    prior_same_weekday: "vs. Same weekday",
    same_period_last_year: "vs. Same period last year",
    prior_fy: "vs. Prior FY",
};
