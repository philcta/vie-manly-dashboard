"use client";

import { useEffect, useState, useCallback } from "react";
import { supabase } from "@/lib/supabase";

interface RateRow {
    staffName: string;
    jobTitle: string;
    teamMemberId: string;
    weekday: number;
    saturday: number;
    sunday: number;
    publicHoliday: number;
    isActive: boolean;
}

interface RawRate {
    id: string;
    team_member_id: string;
    staff_name: string;
    job_title: string;
    day_type: string;
    hourly_rate: number;
    is_active: boolean;
}

/** Short label for common job titles */
const shortTitle = (t: string) => {
    const map: Record<string, string> = {
        "Retail Assistant": "Retail",
        "Expansion/Meeting": "Expansion",
    };
    return map[t] || t;
};

export default function StaffRatesEditor() {
    const [rows, setRows] = useState<RateRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [dirty, setDirty] = useState(false);
    const [saveMsg, setSaveMsg] = useState("");
    const [filter, setFilter] = useState<"all" | "active" | "inactive">("active");

    const loadRates = useCallback(async () => {
        setLoading(true);
        const { data, error } = await supabase
            .from("staff_rates")
            .select("*")
            .order("staff_name", { ascending: true });

        if (error) {
            console.error("Failed to load staff rates:", error);
            setLoading(false);
            return;
        }

        const raw = (data || []) as RawRate[];

        // Group by staff_name — merge job titles, take max rate per day type
        const map = new Map<string, {
            staffName: string;
            jobTitles: Set<string>;
            teamMemberId: string;
            weekday: number;
            saturday: number;
            sunday: number;
            publicHoliday: number;
            isActive: boolean;
        }>();

        for (const r of raw) {
            if (!r.staff_name) continue;
            const key = r.staff_name;
            if (!map.has(key)) {
                map.set(key, {
                    staffName: r.staff_name,
                    jobTitles: new Set(),
                    teamMemberId: r.team_member_id,
                    weekday: 0,
                    saturday: 0,
                    sunday: 0,
                    publicHoliday: 0,
                    isActive: r.is_active !== false,
                });
            }
            const entry = map.get(key)!;
            entry.jobTitles.add(r.job_title);

            const rate = Number(r.hourly_rate) || 0;
            switch (r.day_type) {
                case "weekday":
                    entry.weekday = Math.max(entry.weekday, rate);
                    break;
                case "saturday":
                    entry.saturday = Math.max(entry.saturday, rate);
                    break;
                case "sunday":
                    entry.sunday = Math.max(entry.sunday, rate);
                    break;
                case "public_holiday":
                    entry.publicHoliday = Math.max(entry.publicHoliday, rate);
                    break;
            }
        }

        const pivoted = Array.from(map.values()).map((e) => ({
            staffName: e.staffName,
            jobTitle: Array.from(e.jobTitles).sort().map(shortTitle).join(" / "),
            teamMemberId: e.teamMemberId,
            weekday: e.weekday,
            saturday: e.saturday,
            sunday: e.sunday,
            publicHoliday: e.publicHoliday,
            isActive: e.isActive,
        }));

        setRows(pivoted.sort((a, b) => a.staffName.localeCompare(b.staffName)));
        setLoading(false);
        setDirty(false);
    }, []);

    useEffect(() => {
        loadRates();
    }, [loadRates]);

    const updateRate = (idx: number, field: keyof RateRow, value: number | boolean) => {
        setRows((prev) => {
            const updated = [...prev];
            updated[idx] = { ...updated[idx], [field]: value };
            return updated;
        });
        setDirty(true);
        setSaveMsg("");
    };

    const toggleActive = async (idx: number) => {
        const row = rows[idx];
        const newActive = !row.isActive;

        // Optimistic update
        updateRate(idx, "isActive", newActive);

        // Immediately persist to DB
        const { error } = await supabase
            .from("staff_rates")
            .update({ is_active: newActive })
            .eq("staff_name", row.staffName);

        if (error) {
            console.error("Toggle error:", error);
            updateRate(idx, "isActive", !newActive); // revert
        }
    };

    const saveRates = async () => {
        setSaving(true);
        setSaveMsg("");

        // Load current raw data to know which job_titles exist per person
        const { data: rawData } = await supabase
            .from("staff_rates")
            .select("team_member_id, staff_name, job_title, day_type")
            .order("staff_name");

        const staffJobs = new Map<string, { teamMemberId: string; jobTitles: Set<string> }>();
        for (const r of rawData || []) {
            if (!r.staff_name) continue;
            if (!staffJobs.has(r.staff_name)) {
                staffJobs.set(r.staff_name, { teamMemberId: r.team_member_id, jobTitles: new Set() });
            }
            staffJobs.get(r.staff_name)!.jobTitles.add(r.job_title);
        }

        const upsertRows: {
            team_member_id: string;
            staff_name: string;
            job_title: string;
            day_type: string;
            hourly_rate: number;
            is_active: boolean;
        }[] = [];

        for (const row of rows) {
            const jobs = staffJobs.get(row.staffName);
            if (!jobs) continue;

            const dayRates = [
                { day_type: "weekday", hourly_rate: row.weekday },
                { day_type: "saturday", hourly_rate: row.saturday },
                { day_type: "sunday", hourly_rate: row.sunday },
                { day_type: "public_holiday", hourly_rate: row.publicHoliday },
            ];

            for (const jt of jobs.jobTitles) {
                for (const dr of dayRates) {
                    upsertRows.push({
                        team_member_id: jobs.teamMemberId,
                        staff_name: row.staffName,
                        job_title: jt,
                        day_type: dr.day_type,
                        hourly_rate: dr.hourly_rate,
                        is_active: row.isActive,
                    });
                }
            }
        }

        let ok = true;
        for (let i = 0; i < upsertRows.length; i += 200) {
            const batch = upsertRows.slice(i, i + 200);
            const { error } = await supabase
                .from("staff_rates")
                .upsert(batch, { onConflict: "team_member_id,job_title,day_type" });

            if (error) {
                console.error("Save error:", error);
                setSaveMsg(`❌ Error: ${error.message}`);
                ok = false;
                break;
            }
        }

        if (ok) {
            setSaveMsg(`✅ Saved ${rows.length} staff rates`);
            setDirty(false);
        }
        setSaving(false);
    };

    if (loading) {
        return (
            <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-olive border-t-transparent" />
                Loading staff rates...
            </div>
        );
    }

    const activeCount = rows.filter((r) => r.isActive).length;
    const inactiveCount = rows.filter((r) => !r.isActive).length;

    const filtered = rows.filter((r) => {
        if (filter === "all") return true;
        if (filter === "active") return r.isActive;
        return !r.isActive;
    });

    const cellInput = "w-20 px-2 py-1.5 text-sm text-right border border-border rounded-lg tabular-nums bg-white focus:outline-none focus:ring-2 focus:ring-olive/20 focus:border-olive transition-colors";

    return (
        <div className="space-y-4">
            {/* Filter pills + save */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    {([
                        { value: "all" as const, label: `All (${rows.length})` },
                        { value: "active" as const, label: `Active (${activeCount})` },
                        { value: "inactive" as const, label: `Inactive (${inactiveCount})` },
                    ]).map((pill) => (
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
                <div className="flex items-center gap-3">
                    {saveMsg && (
                        <span className="text-xs font-medium text-muted-foreground">{saveMsg}</span>
                    )}
                    <button
                        onClick={saveRates}
                        disabled={!dirty || saving}
                        className={`px-4 py-1.5 text-xs font-semibold rounded-lg transition-colors duration-200 cursor-pointer ${dirty
                                ? "bg-olive text-white hover:bg-olive-dark"
                                : "bg-muted text-muted-foreground cursor-not-allowed"
                            }`}
                    >
                        {saving ? "Saving..." : "Save Rates"}
                    </button>
                </div>
            </div>

            {/* Table */}
            <div className="rounded-lg border border-border overflow-hidden">
                <div className="max-h-[480px] overflow-y-auto">
                    <table className="w-full text-sm">
                        <thead className="sticky top-0 z-10">
                            <tr className="bg-[#FAFAF8] text-xs font-medium uppercase tracking-wider text-muted-foreground">
                                <th className="text-left px-4 py-2.5">Name</th>
                                <th className="text-left px-4 py-2.5">Role</th>
                                <th className="text-center px-2 py-2.5 w-32">Status</th>
                                <th className="text-right px-2 py-2.5 w-24">Weekday</th>
                                <th className="text-right px-2 py-2.5 w-24">Saturday</th>
                                <th className="text-right px-2 py-2.5 w-24">Sunday</th>
                                <th className="text-right px-4 py-2.5 w-28">Public Holiday</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map((row, i) => (
                                <tr
                                    key={row.staffName}
                                    className={`border-t border-border transition-colors ${!row.isActive
                                            ? "opacity-50 bg-[#FAFAF8]/50"
                                            : i % 2 === 0
                                                ? "bg-white"
                                                : "bg-[#FAFAF8]/50"
                                        } hover:bg-olive-surface/30`}
                                >
                                    <td className="px-4 py-2 font-medium text-foreground whitespace-nowrap">
                                        {row.staffName}
                                    </td>
                                    <td className="px-4 py-2 text-muted-foreground whitespace-nowrap">
                                        {row.jobTitle}
                                    </td>
                                    <td className="px-2 py-2">
                                        <div className="flex justify-center">
                                            <div className="inline-flex rounded-full border border-border overflow-hidden">
                                                <button
                                                    onClick={() => {
                                                        const idx = rows.findIndex((r) => r.staffName === row.staffName);
                                                        if (idx >= 0 && !row.isActive) toggleActive(idx);
                                                    }}
                                                    className={`px-3 py-1 text-xs font-medium transition-colors cursor-pointer ${row.isActive
                                                            ? "bg-olive text-white"
                                                            : "text-text-body hover:bg-olive-surface"
                                                        }`}
                                                >
                                                    Active
                                                </button>
                                                <button
                                                    onClick={() => {
                                                        const idx = rows.findIndex((r) => r.staffName === row.staffName);
                                                        if (idx >= 0 && row.isActive) toggleActive(idx);
                                                    }}
                                                    className={`px-3 py-1 text-xs font-medium transition-colors cursor-pointer ${!row.isActive
                                                            ? "bg-coral text-white"
                                                            : "text-text-body hover:bg-olive-surface"
                                                        }`}
                                                >
                                                    Inactive
                                                </button>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-2 py-1.5 text-right">
                                        <input
                                            type="number"
                                            step="0.01"
                                            value={row.weekday || ""}
                                            onChange={(e) => {
                                                const idx = rows.findIndex((r) => r.staffName === row.staffName);
                                                if (idx >= 0) updateRate(idx, "weekday", Number(e.target.value));
                                            }}
                                            className={cellInput}
                                            placeholder="0.00"
                                        />
                                    </td>
                                    <td className="px-2 py-1.5 text-right">
                                        <input
                                            type="number"
                                            step="0.01"
                                            value={row.saturday || ""}
                                            onChange={(e) => {
                                                const idx = rows.findIndex((r) => r.staffName === row.staffName);
                                                if (idx >= 0) updateRate(idx, "saturday", Number(e.target.value));
                                            }}
                                            className={cellInput}
                                            placeholder="0.00"
                                        />
                                    </td>
                                    <td className="px-2 py-1.5 text-right">
                                        <input
                                            type="number"
                                            step="0.01"
                                            value={row.sunday || ""}
                                            onChange={(e) => {
                                                const idx = rows.findIndex((r) => r.staffName === row.staffName);
                                                if (idx >= 0) updateRate(idx, "sunday", Number(e.target.value));
                                            }}
                                            className={cellInput}
                                            placeholder="0.00"
                                        />
                                    </td>
                                    <td className="px-4 py-1.5 text-right">
                                        <input
                                            type="number"
                                            step="0.01"
                                            value={row.publicHoliday || ""}
                                            onChange={(e) => {
                                                const idx = rows.findIndex((r) => r.staffName === row.staffName);
                                                if (idx >= 0) updateRate(idx, "publicHoliday", Number(e.target.value));
                                            }}
                                            className={cellInput}
                                            placeholder="0.00"
                                        />
                                    </td>
                                </tr>
                            ))}
                            {filtered.length === 0 && (
                                <tr>
                                    <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground text-sm">
                                        No staff match this filter.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
