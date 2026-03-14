import { openai } from "@ai-sdk/openai";
import { streamText, convertToModelMessages } from "ai";
import type { UIMessage } from "ai";
import { createClient } from "@supabase/supabase-js";

export const runtime = "edge";
export const maxDuration = 30;

function getSupabase() {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
    const key = process.env.SUPABASE_SERVICE_ROLE_KEY!;
    return createClient(url, key);
}

// ── Build business context from weekly tables ────────────────────────

async function buildBusinessContext(): Promise<string> {
    const supabase = getSupabase();
    const now = new Date();
    const fourWeeksAgo = new Date(now.getTime() - 28 * 86400000)
        .toISOString()
        .split("T")[0];

    // ── Phase 1 + 2: All parallel queries ────────────────────────────
    const [
        storeStats,
        categoryStats,
        memberStats,
        staffStats,
        hourlyPatterns,
        dowStats,
        inventoryStats,
        deadStockItems,
        alertCounts,
        topMembers,
        signUpsByDow,
    ] = await Promise.all([
        // Original 6 queries
        supabase
            .from("weekly_store_stats")
            .select("*")
            .gte("week_start", fourWeeksAgo)
            .eq("side", "All")
            .eq("day_type", "all")
            .order("week_start", { ascending: false })
            .limit(4),
        supabase
            .from("weekly_category_stats")
            .select("*")
            .gte("week_start", fourWeeksAgo)
            .eq("day_type", "all")
            .order("week_start", { ascending: false })
            .order("total_net_sales", { ascending: false })
            .limit(80),
        supabase
            .from("weekly_member_stats")
            .select("*")
            .gte("week_start", fourWeeksAgo)
            .eq("customer_type", "all")
            .eq("day_type", "all")
            .order("week_start", { ascending: false })
            .limit(4),
        supabase
            .from("weekly_staff_stats")
            .select("*")
            .gte("week_start", fourWeeksAgo)
            .eq("side", "All")
            .eq("day_type", "all")
            .order("week_start", { ascending: false })
            .limit(4),
        supabase
            .from("weekly_hourly_patterns")
            .select("*")
            .gte("week_start", fourWeeksAgo)
            .eq("day_type", "all")
            .eq("is_peak", true)
            .order("week_start", { ascending: false })
            .limit(20),
        supabase
            .from("weekly_dow_stats")
            .select("*")
            .gte("week_start", fourWeeksAgo)
            .eq("side", "All")
            .order("week_start", { ascending: false })
            .limit(28),

        // NEW: Inventory stats (stock value, alert counts by category)
        supabase
            .from("weekly_inventory_stats")
            .select("*")
            .order("week_start", { ascending: false })
            .limit(20),

        // NEW: Dead stock / overstock items from inventory_intelligence
        supabase
            .from("inventory_intelligence")
            .select("product_name,sku,reorder_alert,current_quantity,days_of_stock,last_sold_date,revenue_30d,sales_velocity")
            .in("reorder_alert", ["DEAD", "OVERSTOCK", "CRITICAL"])
            .order("revenue_30d", { ascending: true })
            .limit(20),

        // NEW: Alert summary counts
        supabase
            .from("inventory_intelligence")
            .select("reorder_alert"),

        // NEW: Top 10 spending members (last 30 days)
        supabase.rpc("get_top_members", { days_back: 30 }).limit(10),

        // NEW: Member sign-ups by DOW (will fall back gracefully)
        supabase.rpc("get_signups_by_dow", { days_back: 90 }),
    ]);

    // ── Format store overview ────────────────────────────────────────
    const storeRows = storeStats.data || [];
    const storeContext = storeRows
        .map(
            (w) =>
                `${w.week_label}: Sales $${w.total_net_sales?.toLocaleString()}, ` +
                `${w.total_transactions} txns, Avg $${w.avg_transaction_value}, ` +
                `Gross $${w.total_gross_sales?.toLocaleString()}, Discounts $${((w.total_gross_sales || 0) - (w.total_net_sales || 0)).toFixed(0)}, ` +
                `Labour ${w.labour_pct ?? "N/A"}%, Margin ${w.weighted_margin_pct ?? "N/A"}%, ` +
                `Real Profit ${w.real_profit_pct ?? "N/A"}% ($${w.real_profit_dollars ?? "N/A"}), ` +
                `Members ${w.member_tx_ratio ? (w.member_tx_ratio * 100).toFixed(1) : "N/A"}% of txns`
        )
        .join("\n");

    // ── Top categories (latest week + all weeks for margin) ──────────
    const catRows = categoryStats.data || [];
    const latestWeek = catRows[0]?.week_start;
    const topCats = catRows
        .filter((c) => c.week_start === latestWeek)
        .slice(0, 15)
        .map(
            (c) =>
                `${c.category} (${c.side}): $${c.total_net_sales?.toLocaleString()}, ${c.pct_of_total_sales?.toFixed(1)}% of sales, ` +
                `Margin ${c.category_margin_pct?.toFixed(1) ?? "N/A"}%, Est Gross Profit $${c.estimated_gross_profit?.toFixed(0) ?? "N/A"}` +
                (c.wow_sales_change_pct != null
                    ? `, ${c.wow_sales_change_pct > 0 ? "+" : ""}${c.wow_sales_change_pct.toFixed(1)}% WoW`
                    : "")
        )
        .join("\n");

    // ── Member trends (enriched) ─────────────────────────────────────
    const memberRows = memberStats.data || [];
    const memberContext = memberRows
        .map(
            (m) =>
                `${m.week_label}: ${m.unique_customers} members, ` +
                `Avg spend/visit $${m.avg_spend_per_visit?.toFixed(2)}, ` +
                `New sign-ups ${m.new_enrollments ?? 0}, ` +
                `Active ${m.active_count ?? "N/A"}, Cooling ${m.cooling_count ?? "N/A"}, ` +
                `At-Risk ${m.at_risk_count ?? "N/A"}, Churned ${m.churned_count ?? "N/A"}, ` +
                `Points earned ${m.total_points_earned ?? 0}, redeemed ${m.total_points_redeemed ?? 0}, ` +
                `Redemption rate ${m.redemption_rate_pct?.toFixed(1) ?? "N/A"}%`
        )
        .join("\n");

    // Non-member avg spend (calculated)
    const latestStore = storeRows[0];
    const latestMember = memberRows[0];
    let nonMemberAvgSpend = "N/A";
    if (latestStore && latestMember) {
        const nonMemberSales = (latestStore.non_member_net_sales || 0);
        const nonMemberTx = (latestStore.non_member_transactions || 0);
        if (nonMemberTx > 0) {
            nonMemberAvgSpend = `$${(nonMemberSales / nonMemberTx).toFixed(2)}`;
        }
    }

    // ── Labour (enriched with day-type split) ────────────────────────
    const staffRows = staffStats.data || [];
    const staffContext = staffRows
        .map(
            (s) =>
                `${s.week_label}: $${s.total_labour_cost?.toLocaleString()} labour, ` +
                `${s.total_hours?.toFixed(1)}h total, ${s.unique_staff} staff, ` +
                `Teen $${s.teen_cost}/${s.teen_hours?.toFixed(1)}h / Adult $${s.adult_cost}/${s.adult_hours?.toFixed(1)}h, ` +
                `Weekday $${s.weekday_cost ?? 0}, Sat $${s.saturday_cost ?? 0}, Sun $${s.sunday_cost ?? 0}`
        )
        .join("\n");

    // ── Per-day labour breakdown (latest week) ───────────────────────
    const dowRows = (dowStats.data || []).filter(
        (d) => d.week_start === latestWeek
    );
    const dowContext = [...dowRows]
        .sort((a, b) => a.dow - b.dow)
        .map(
            (d) =>
                `${d.dow_name}: Sales $${d.total_net_sales?.toLocaleString()}, ${d.total_transactions} txns, ` +
                `Labour $${d.total_labour_cost?.toFixed(0) ?? "N/A"} (${d.labour_pct?.toFixed(1) ?? "N/A"}%), ` +
                `${d.total_hours?.toFixed(1) ?? "N/A"}h, Rev/h $${((d.total_net_sales || 0) / (d.total_hours || 1)).toFixed(0)}`
        )
        .join("\n");

    const bestDay = [...dowRows].sort(
        (a, b) => (b.total_net_sales || 0) - (a.total_net_sales || 0)
    )[0];

    // Peak hours
    const peakHours = (hourlyPatterns.data || [])
        .filter((h) => h.week_start === latestWeek)
        .map((h) => `${h.hour}:00 (${h.pct_of_daily_total?.toFixed(1)}% of daily)`)
        .join(", ");

    // ── Inventory Intelligence ───────────────────────────────────────
    const invRows = inventoryStats.data || [];
    const latestInvWeek = invRows[0]?.week_start;
    const invContext = invRows
        .filter((r) => r.week_start === latestInvWeek)
        .map(
            (r) =>
                `${r.category} (${r.side}): ${r.total_skus} SKUs, ${r.in_stock_skus} in stock, ${r.zero_stock_skus} out of stock, ` +
                `Stock value $${r.stock_value_ex_gst?.toFixed(0)}, Margin ${r.category_margin_pct?.toFixed(1)}%, ` +
                `Velocity ${r.sales_velocity?.toFixed(1)}/day, ${r.days_of_stock?.toFixed(0)} days of stock, ` +
                `Alerts: ${r.critical_count} critical, ${r.low_count} low, ${r.dead_count} dead, ${r.overstock_count} overstock`
        )
        .join("\n");

    // Dead/overstock/critical items
    const deadItems = (deadStockItems.data || [])
        .map(
            (d) =>
                `${d.product_name}: ${d.reorder_alert}, Qty ${d.current_quantity}, ` +
                `${d.days_of_stock?.toFixed(0) ?? "N/A"} days stock, Last sold ${d.last_sold_date ?? "never"}, ` +
                `Rev 30d $${d.revenue_30d?.toFixed(0) ?? "0"}`
        )
        .join("\n");

    // Alert summary counts
    const alertData = alertCounts.data || [];
    const alertSummary: Record<string, number> = {};
    for (const r of alertData) {
        alertSummary[r.reorder_alert] = (alertSummary[r.reorder_alert] || 0) + 1;
    }
    const alertLine = Object.entries(alertSummary)
        .map(([k, v]) => `${k}: ${v}`)
        .join(", ");

    // ── Top Members Leaderboard ──────────────────────────────────────
    const topMemberRows = topMembers.data || [];
    const topMemberContext = topMemberRows
        .map(
            (m: Record<string, unknown>, i: number) =>
                `#${i + 1}: ${m.first_name ?? ""} ${m.last_name ?? ""} — $${(m.total_spent as number)?.toFixed(2)}, ` +
                `${m.visit_count} visits, Avg $${(m.avg_spend as number)?.toFixed(2)}, ` +
                `Last visit ${m.last_visit_date ?? "N/A"}, Points balance ${m.points_balance ?? 0}`
        )
        .join("\n");

    // ── Sign-ups by DOW ──────────────────────────────────────────────
    const signUpRows = signUpsByDow.data || [];
    const signUpContext = signUpRows
        .map((r: Record<string, unknown>) => `${r.dow_name}: ${r.signup_count} sign-ups`)
        .join(", ");

    return `
## VIE Market — Business Intelligence (Last 4 Weeks)

### Weekly Sales Overview (incl. Discounts)
${storeContext || "No data available yet."}

### Top 15 Categories (Latest Week) — incl. Margin & Gross Profit
${topCats || "No category data yet."}

### Member Engagement & Lifecycle
${memberContext || "No member data yet."}
- Non-member avg spend/txn: ${nonMemberAvgSpend}
- Member avg spend/visit: $${latestMember?.avg_spend_per_visit?.toFixed(2) ?? "N/A"}

### Top 10 Members by Spend (Last 30 Days)
${topMemberContext || "No member leaderboard data yet."}

### Member Sign-ups by Day of Week (Last 90 Days)
${signUpContext || "No sign-up pattern data yet."}

### Labour Costs (Weekly + Day-Type Split)
${staffContext || "No labour data yet."}

### Daily Labour Breakdown (Latest Week)
${dowContext || "No daily labour data yet."}

### Peak Hours (Latest Week)
${peakHours || "No hourly data yet."}

### Best Day (Latest Week)
${bestDay ? `${bestDay.dow_name}: $${bestDay.total_net_sales?.toLocaleString()}, ${bestDay.total_transactions} txns, Labour ${bestDay.labour_pct?.toFixed(1)}%` : "No data yet."}

### Inventory Overview (by Category)
${invContext || "No inventory stats yet."}
- Alert totals: ${alertLine || "No alerts"}

### Stock Requiring Action (Dead / Overstock / Critical)
${deadItems || "No problematic stock items."}

### Business Profile
- Organic grocery + café in Manly, NSW
- Two sides: Café (~70% margin, ~30% of sales) and Retail (~41% margin, ~70% of sales)
- Open since August 20, 2025
- Loyalty program: Points-based via Square
- Financial Year: July 1 – June 30 (Australian)
- KPI Targets: Labour ≤24%, Avg Sale ≥$15, Real Profit ≥25%, Member tx share ≥35%
`.trim();
}

// ── System prompt ────────────────────────────────────────────────────

const SYSTEM_PROMPT = `You are the AI Business Coach for VIE Market, an organic grocery and café in Manly, Sydney.

Your role:
- Provide actionable, data-driven business advice
- Analyse sales trends, labour efficiency, member engagement, and product performance
- Be specific with numbers — always reference the data provided
- Suggest concrete improvements with expected impact
- Be concise but insightful; use bullet points and bold key takeaways
- Speak as a friendly, experienced business consultant
- When data is missing or insufficient, say so honestly

Formatting:
- Use markdown for structure (headings, bold, bullet points)
- Bold key metrics and recommendations
- Use bullet points for lists
- Keep responses focused and under 300 words unless asked for deep analysis
- NEVER use LaTeX, MathJax, or math notation (no \\frac, \\text, \\times, \\left, \\right, \\[ \\] etc.)
- For calculations, write them in plain text like: "Labour % = $4,746 / $30,624 × 100 = 15.5%"
- Use dollar signs for currency ($1,234) and % for percentages (15.5%)
- Use simple tables with pipes (|) when comparing data
`;

// ── Route handler ────────────────────────────────────────────────────

export async function POST(req: Request) {
    const supabase = getSupabase();
    const { messages, sessionId } = await req.json();

    // Build context from weekly tables
    const context = await buildBusinessContext();

    // Extract user text from the last UIMessage (v6 uses parts array)
    const lastMessage = messages[messages.length - 1];
    if (lastMessage?.role === "user" && sessionId) {
        const userText = lastMessage.parts
            ?.filter((p: { type: string }) => p.type === "text")
            .map((p: { text: string }) => p.text)
            .join("") || lastMessage.content || "";
        if (userText) {
            await supabase.from("coach_conversations").insert({
                session_id: sessionId,
                role: "user",
                content: userText,
            });
        }
    }

    // Convert UIMessages → ModelMessages for streamText
    const modelMessages = await convertToModelMessages(messages as UIMessage[]);

    const result = streamText({
        model: openai("gpt-4o-mini"),
        system: `${SYSTEM_PROMPT}\n\n## Current Business Data\n\n${context}`,
        messages: modelMessages,
        onFinish: async ({ text }) => {
            // Save assistant response
            if (sessionId) {
                await supabase.from("coach_conversations").insert({
                    session_id: sessionId,
                    role: "assistant",
                    content: text,
                });
            }
        },
    });

    return result.toTextStreamResponse();
}
