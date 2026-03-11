/**
 * Staff page data queries.
 * Per formulas_reference.md Section 5:
 * - Staff Today: COUNT(DISTINCT staff_id) WHERE shift includes today
 * - Total Hours: SUM(effective_hours) for period
 * - Labour Cost Ratio: SUM(labour_cost) / Net Sales × 100
 * - Revenue per Hour: Net Sales / Total Hours
 */
import { supabase } from "@/lib/supabase";

export interface StaffShift {
    id: string;
    shift_date: string;
    team_member_id: string;
    staff_name: string;
    job_title: string;
    business_side: string;
    scheduled_start: string | null;
    scheduled_end: string | null;
    actual_start: string | null;
    actual_end: string | null;
    effective_hours: number;
    hourly_rate: number;
    labour_cost: number;
    is_teen: boolean;
}

export interface StaffRate {
    id: string;
    team_member_id: string;
    staff_name: string;
    job_title: string;
    day_type: string;
    hourly_rate: number;
    is_active: boolean;
}

/** Fetch all shifts for a date range */
export async function fetchStaffShifts(
    startDate: string,
    endDate: string
): Promise<StaffShift[]> {
    const { data, error } = await supabase
        .from("staff_shifts")
        .select("*")
        .gte("shift_date", startDate)
        .lte("shift_date", endDate)
        .order("shift_date", { ascending: true });

    if (error) throw error;
    return (data || []).map((s) => ({
        ...s,
        effective_hours: Number(s.effective_hours),
        hourly_rate: Number(s.hourly_rate),
        labour_cost: Number(s.labour_cost),
    }));
}

/** Fetch all staff rates */
export async function fetchStaffRates(): Promise<StaffRate[]> {
    const { data, error } = await supabase
        .from("staff_rates")
        .select("*")
        .order("staff_name", { ascending: true });

    if (error) throw error;
    return (data || []).map((r) => ({
        ...r,
        hourly_rate: Number(r.hourly_rate),
    }));
}

/** Aggregate staff KPIs */
export function aggregateStaffKPIs(shifts: StaffShift[], netSales: number) {
    const uniqueStaff = new Set(shifts.map((s) => s.team_member_id));
    const totalHours = shifts.reduce((s, sh) => s + sh.effective_hours, 0);
    const totalLabourCost = shifts.reduce((s, sh) => s + sh.labour_cost, 0);
    const labourCostRatio = netSales > 0 ? (totalLabourCost / netSales) * 100 : 0;
    const revenuePerHour = totalHours > 0 ? netSales / totalHours : 0;

    // Split by business side
    const cafeShifts = shifts.filter((s) => s.business_side === "Bar");
    const retailShifts = shifts.filter((s) => s.business_side === "Retail");
    const cafeHours = cafeShifts.reduce((s, sh) => s + sh.effective_hours, 0);
    const retailHours = retailShifts.reduce((s, sh) => s + sh.effective_hours, 0);
    const cafeCost = cafeShifts.reduce((s, sh) => s + sh.labour_cost, 0);
    const retailCost = retailShifts.reduce((s, sh) => s + sh.labour_cost, 0);

    // Teen / Adult split
    const teenShifts = shifts.filter((s) => s.is_teen);
    const adultShifts = shifts.filter((s) => !s.is_teen);
    const teenCost = teenShifts.reduce((s, sh) => s + sh.labour_cost, 0);
    const adultCost = adultShifts.reduce((s, sh) => s + sh.labour_cost, 0);
    const teenHours = teenShifts.reduce((s, sh) => s + sh.effective_hours, 0);
    const adultHours = adultShifts.reduce((s, sh) => s + sh.effective_hours, 0);

    // 4-way split: teen cafe, teen retail, adult cafe, adult retail
    const teenCafeCost = shifts.filter((s) => s.is_teen && s.business_side === "Bar").reduce((s, sh) => s + sh.labour_cost, 0);
    const teenRetailCost = shifts.filter((s) => s.is_teen && s.business_side === "Retail").reduce((s, sh) => s + sh.labour_cost, 0);
    const adultCafeCost = shifts.filter((s) => !s.is_teen && s.business_side === "Bar").reduce((s, sh) => s + sh.labour_cost, 0);
    const adultRetailCost = shifts.filter((s) => !s.is_teen && s.business_side === "Retail").reduce((s, sh) => s + sh.labour_cost, 0);
    const teenCafeHours = shifts.filter((s) => s.is_teen && s.business_side === "Bar").reduce((s, sh) => s + sh.effective_hours, 0);
    const teenRetailHours = shifts.filter((s) => s.is_teen && s.business_side === "Retail").reduce((s, sh) => s + sh.effective_hours, 0);
    const adultCafeHours = shifts.filter((s) => !s.is_teen && s.business_side === "Bar").reduce((s, sh) => s + sh.effective_hours, 0);
    const adultRetailHours = shifts.filter((s) => !s.is_teen && s.business_side === "Retail").reduce((s, sh) => s + sh.effective_hours, 0);

    return {
        staffCount: uniqueStaff.size,
        totalHours,
        totalLabourCost,
        labourCostRatio,
        revenuePerHour,
        cafeStaffCount: new Set(cafeShifts.map((s) => s.team_member_id)).size,
        retailStaffCount: new Set(retailShifts.map((s) => s.team_member_id)).size,
        cafeHours,
        retailHours,
        cafeCost,
        retailCost,
        // Teen / Adult
        teenCost,
        adultCost,
        teenHours,
        adultHours,
        // 4-way split
        teenCafeCost,
        teenRetailCost,
        adultCafeCost,
        adultRetailCost,
        teenCafeHours,
        teenRetailHours,
        adultCafeHours,
        adultRetailHours,
    };
}

/** Build Gantt data — group shifts by staff member */
export function buildGanttData(shifts: StaffShift[]) {
    const staffMap = new Map<
        string,
        { name: string; side: string; shifts: { start: string; end: string; date: string }[] }
    >();

    for (const s of shifts) {
        if (!s.actual_start || !s.actual_end) continue;
        if (!staffMap.has(s.team_member_id)) {
            staffMap.set(s.team_member_id, {
                name: s.staff_name,
                side: s.business_side,
                shifts: [],
            });
        }
        staffMap.get(s.team_member_id)!.shifts.push({
            start: s.actual_start,
            end: s.actual_end,
            date: s.shift_date,
        });
    }

    return Array.from(staffMap.values());
}

/** Pivot staff rates into per-person rows for the rates table.
 *  Staff with multiple job titles are merged into a single row
 *  with a combined title (e.g. "Kitchen / Manager") and the
 *  highest applicable rate for each day type.
 */
export function pivotRates(rates: StaffRate[]) {
    // Short labels for common job titles
    const shortTitle = (t: string) => {
        const map: Record<string, string> = {
            "Retail Assistant": "Retail",
            "Expansion/Meeting": "Expansion",
        };
        return map[t] || t;
    };

    const rateMap = new Map<
        string,
        {
            name: string;
            jobTitles: Set<string>;
            teamMemberId: string;
            weekday: number;
            saturday: number;
            sunday: number;
            publicHoliday: number;
            isActive: boolean;
        }
    >();

    for (const r of rates) {
        // Group by staff_name (not team_member_id+job_title)
        const key = r.staff_name;
        if (!rateMap.has(key)) {
            rateMap.set(key, {
                name: r.staff_name,
                jobTitles: new Set(),
                teamMemberId: r.team_member_id,
                weekday: 0,
                saturday: 0,
                sunday: 0,
                publicHoliday: 0,
                isActive: r.is_active !== false,
            });
        }
        const entry = rateMap.get(key)!;
        entry.jobTitles.add(r.job_title);

        // Take the max rate for each day type across all roles
        switch (r.day_type) {
            case "weekday":
                entry.weekday = Math.max(entry.weekday, r.hourly_rate);
                break;
            case "saturday":
                entry.saturday = Math.max(entry.saturday, r.hourly_rate);
                break;
            case "sunday":
                entry.sunday = Math.max(entry.sunday, r.hourly_rate);
                break;
            case "public_holiday":
                entry.publicHoliday = Math.max(entry.publicHoliday, r.hourly_rate);
                break;
        }
    }

    return Array.from(rateMap.values())
        .map((entry) => ({
            name: entry.name,
            jobTitle: Array.from(entry.jobTitles).sort().map(shortTitle).join(" / "),
            teamMemberId: entry.teamMemberId,
            weekday: entry.weekday,
            saturday: entry.saturday,
            sunday: entry.sunday,
            publicHoliday: entry.publicHoliday,
            isActive: entry.isActive,
        }))
        .sort((a, b) => a.name.localeCompare(b.name));
}

/**
 * Calculate the biweekly Xero pay period.
 * Anchored to March 9, 2026 as the first update Monday.
 * Every 2 weeks from that date, we show the PREVIOUS completed 2-week period.
 *
 * @returns { periodStart, periodEnd, nextUpdate } - all as YYYY-MM-DD strings
 */
export function getPayPeriod(today: Date = new Date()) {
    // Reference Monday: March 9, 2026 (UTC)
    const REF_MONDAY = new Date("2026-03-09T00:00:00");
    const MS_PER_DAY = 86400000;
    const PERIOD_DAYS = 14;

    const daysSinceRef = Math.floor(
        (today.getTime() - REF_MONDAY.getTime()) / MS_PER_DAY
    );

    // Which 2-week cycle are we in?
    const periodIndex = Math.max(0, Math.floor(daysSinceRef / PERIOD_DAYS));

    // The update Monday for this cycle
    const updateMonday = new Date(
        REF_MONDAY.getTime() + periodIndex * PERIOD_DAYS * MS_PER_DAY
    );

    // The pay period is the 2 weeks BEFORE the update Monday
    const periodStart = new Date(updateMonday.getTime() - PERIOD_DAYS * MS_PER_DAY);
    const periodEnd = new Date(updateMonday.getTime() - MS_PER_DAY);

    // Next update Monday
    const nextUpdate = new Date(
        updateMonday.getTime() + PERIOD_DAYS * MS_PER_DAY
    );

    const fmt = (d: Date) => d.toISOString().split("T")[0];
    return {
        periodStart: fmt(periodStart),
        periodEnd: fmt(periodEnd),
        nextUpdate: fmt(nextUpdate),
    };
}

/**
 * Fetch biweekly earnings (no_super_earning) grouped by staff_name
 * for the last completed pay period.
 */
export async function fetchBiweeklyEarnings(
    periodStart: string,
    periodEnd: string
): Promise<Map<string, number>> {
    const { data, error } = await supabase
        .from("staff_shifts")
        .select("staff_name, no_super_earning")
        .gte("shift_date", periodStart)
        .lte("shift_date", periodEnd);

    if (error) throw error;

    const earningsMap = new Map<string, number>();
    for (const row of data || []) {
        const name = row.staff_name;
        const earning = Number(row.no_super_earning) || 0;
        earningsMap.set(name, (earningsMap.get(name) || 0) + earning);
    }
    return earningsMap;
}

/**
 * Break-deducted shift count per staff member within a date range.
 */
export async function fetchBreakStats(
    periodStart: string,
    periodEnd: string
): Promise<Map<string, number>> {
    const { data, error } = await supabase
        .from("staff_shifts")
        .select("staff_name")
        .eq("break_deducted", true)
        .gte("shift_date", periodStart)
        .lte("shift_date", periodEnd);

    if (error) throw error;

    const breakMap = new Map<string, number>();
    for (const row of data || []) {
        const name = row.staff_name;
        breakMap.set(name, (breakMap.get(name) || 0) + 1);
    }
    return breakMap;
}

// ── NSW Public Holidays (same as sync_shifts.py) ──
const NSW_HOLIDAYS = new Set([
    "2025-01-01", "2025-01-27", "2025-04-18", "2025-04-19",
    "2025-04-21", "2025-04-25", "2025-06-09", "2025-08-04",
    "2025-10-06", "2025-12-25", "2025-12-26",
    "2026-01-01", "2026-01-26", "2026-04-03", "2026-04-04",
    "2026-04-06", "2026-04-25", "2026-06-08", "2026-08-03",
    "2026-10-05", "2026-12-25", "2026-12-26", "2026-12-28",
]);

function getDayType(dateStr: string): "weekday" | "saturday" | "sunday" | "publicHoliday" {
    if (NSW_HOLIDAYS.has(dateStr)) return "publicHoliday";
    const d = new Date(dateStr + "T00:00:00");
    const dow = d.getDay();
    if (dow === 6) return "saturday";
    if (dow === 0) return "sunday";
    return "weekday";
}

export interface StaffEarningsRow {
    name: string;
    jobTitle: string;
    total: number;
    weekday: number;
    saturday: number;
    sunday: number;
    publicHoliday: number;
    weekdayHours: number;
    saturdayHours: number;
    sundayHours: number;
    publicHolidayHours: number;
    totalHours: number;
    breaks: number;
}

/**
 * Fetch per-staff earnings breakdown by day type for a date range.
 * Returns earnings excl. super (no_super_earning) grouped by staff and day type.
 */
export async function fetchEarningsBreakdown(
    periodStart: string,
    periodEnd: string
): Promise<StaffEarningsRow[]> {
    const { data, error } = await supabase
        .from("staff_shifts")
        .select("staff_name, job_title, shift_date, effective_hours, no_super_earning, break_deducted")
        .gte("shift_date", periodStart)
        .lte("shift_date", periodEnd);

    if (error) throw error;

    const map = new Map<string, {
        jobTitles: Set<string>;
        weekday: number; saturday: number; sunday: number; publicHoliday: number;
        weekdayHours: number; saturdayHours: number; sundayHours: number; publicHolidayHours: number;
        breaks: number;
    }>();

    for (const row of data || []) {
        const name = row.staff_name as string;
        if (!name) continue;
        if (!map.has(name)) {
            map.set(name, {
                jobTitles: new Set(),
                weekday: 0, saturday: 0, sunday: 0, publicHoliday: 0,
                weekdayHours: 0, saturdayHours: 0, sundayHours: 0, publicHolidayHours: 0,
                breaks: 0,
            });
        }
        const entry = map.get(name)!;
        // Clean job title (strip _Bar, _Retail suffixes for display)
        const rawTitle = (row.job_title as string) || "";
        const cleanTitle = rawTitle.replace(/_Bar$/, "").replace(/_Retail$/, "");
        if (cleanTitle) entry.jobTitles.add(cleanTitle);
        const earning = Number(row.no_super_earning) || 0;
        const hours = Number(row.effective_hours) || 0;
        const dt = getDayType(row.shift_date as string);
        entry[dt] += earning;
        if (dt === "weekday") entry.weekdayHours += hours;
        else if (dt === "saturday") entry.saturdayHours += hours;
        else if (dt === "sunday") entry.sundayHours += hours;
        else entry.publicHolidayHours += hours;
        if (row.break_deducted) entry.breaks++;
    }

    return Array.from(map.entries()).map(([name, e]) => ({
        name,
        jobTitle: Array.from(e.jobTitles).sort().join(" / "),
        total: e.weekday + e.saturday + e.sunday + e.publicHoliday,
        weekday: e.weekday,
        saturday: e.saturday,
        sunday: e.sunday,
        publicHoliday: e.publicHoliday,
        weekdayHours: e.weekdayHours,
        saturdayHours: e.saturdayHours,
        sundayHours: e.sundayHours,
        publicHolidayHours: e.publicHolidayHours,
        totalHours: e.weekdayHours + e.saturdayHours + e.sundayHours + e.publicHolidayHours,
        breaks: e.breaks,
    }));
}
