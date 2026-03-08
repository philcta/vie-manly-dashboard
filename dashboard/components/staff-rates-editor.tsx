"use client";

import { useEffect, useState, useCallback } from "react";
import { supabase } from "@/lib/supabase";
import { formatCurrency } from "@/lib/format";

interface RateRow {
    staffName: string;
    jobTitle: string;
    teamMemberId: string;
    weekday: number;
    saturday: number;
    sunday: number;
    publicHoliday: number;
}

interface RawRate {
    id: string;
    team_member_id: string;
    staff_name: string;
    job_title: string;
    day_type: string;
    hourly_rate: number;
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
        }));

        setRows(pivoted.sort((a, b) => a.staffName.localeCompare(b.staffName)));
        setLoading(false);
        setDirty(false);
    }, []);

    useEffect(() => {
        loadRates();
    }, [loadRates]);

    const updateRate = (idx: number, field: keyof RateRow, value: number) => {
        setRows((prev) => {
            const updated = [...prev];
            updated[idx] = { ...updated[idx], [field]: value };
            return updated;
        });
        setDirty(true);
        setSaveMsg("");
    };

    const saveRates = async () => {
        setSaving(true);
        setSaveMsg("");

        // Build upsert records — one per (staff_name, job_title) combo + day_type
        // Since we merged titles, we update ALL titles for each staff member
        // with the same rate values
        const upsertRows: {
            team_member_id: string;
            staff_name: string;
            job_title: string;
            day_type: string;
            hourly_rate: number;
        }[] = [];

        // First, load current raw data to know which job_titles exist per person
        const { data: rawData } = await supabase
            .from("staff_rates")
            .select("team_member_id, staff_name, job_title, day_type")
            .order("staff_name");

        // Build a map of staff_name -> set of {team_member_id, job_title}
        const staffJobs = new Map<string, { teamMemberId: string; jobTitles: Set<string> }>();
        for (const r of rawData || []) {
            if (!r.staff_name) continue;
            if (!staffJobs.has(r.staff_name)) {
                staffJobs.set(r.staff_name, { teamMemberId: r.team_member_id, jobTitles: new Set() });
            }
            staffJobs.get(r.staff_name)!.jobTitles.add(r.job_title);
        }

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
                    });
                }
            }
        }

        // Upsert in batches
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
        return <p className="text-sm text-muted-foreground py-4">Loading staff rates...</p>;
    }

    const cellInput = "w-20 px-2 py-1.5 text-sm text-right border border-border rounded-lg tabular-nums bg-white focus:outline-none focus:ring-2 focus:ring-olive/20 focus:border-olive transition-colors";

    return (
        <div>
            <div className="flex items-center justify-between mb-3">
                <p className="text-xs text-muted-foreground">
                    {rows.length} staff · Rates include 12% superannuation (except under-18)
                </p>
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

            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="text-left text-xs font-medium uppercase tracking-wider text-muted-foreground border-b border-border">
                            <th className="pb-2.5 pr-4">Name</th>
                            <th className="pb-2.5 pr-4">Role</th>
                            <th className="pb-2.5 pr-2 text-right">Weekday</th>
                            <th className="pb-2.5 pr-2 text-right">Saturday</th>
                            <th className="pb-2.5 pr-2 text-right">Sunday</th>
                            <th className="pb-2.5 text-right">Public Holiday</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row, i) => (
                            <tr
                                key={row.staffName}
                                className="border-b border-border/50 hover:bg-olive-surface/30 transition-colors"
                            >
                                <td className="py-2 pr-4 font-medium text-foreground whitespace-nowrap">
                                    {row.staffName}
                                </td>
                                <td className="py-2 pr-4 text-muted-foreground whitespace-nowrap">
                                    {row.jobTitle}
                                </td>
                                <td className="py-1.5 pr-2 text-right">
                                    <input
                                        type="number"
                                        step="0.01"
                                        value={row.weekday || ""}
                                        onChange={(e) => updateRate(i, "weekday", Number(e.target.value))}
                                        className={cellInput}
                                        placeholder="0.00"
                                    />
                                </td>
                                <td className="py-1.5 pr-2 text-right">
                                    <input
                                        type="number"
                                        step="0.01"
                                        value={row.saturday || ""}
                                        onChange={(e) => updateRate(i, "saturday", Number(e.target.value))}
                                        className={cellInput}
                                        placeholder="0.00"
                                    />
                                </td>
                                <td className="py-1.5 pr-2 text-right">
                                    <input
                                        type="number"
                                        step="0.01"
                                        value={row.sunday || ""}
                                        onChange={(e) => updateRate(i, "sunday", Number(e.target.value))}
                                        className={cellInput}
                                        placeholder="0.00"
                                    />
                                </td>
                                <td className="py-1.5 text-right">
                                    <input
                                        type="number"
                                        step="0.01"
                                        value={row.publicHoliday || ""}
                                        onChange={(e) => updateRate(i, "publicHoliday", Number(e.target.value))}
                                        className={cellInput}
                                        placeholder="0.00"
                                    />
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
