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
}

export interface StaffRate {
    id: string;
    team_member_id: string;
    staff_name: string;
    job_title: string;
    day_type: string;
    hourly_rate: number;
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
        }))
        .sort((a, b) => a.name.localeCompare(b.name));
}
