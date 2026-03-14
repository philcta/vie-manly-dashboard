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

    const [
        storeStats,
        categoryStats,
        memberStats,
        staffStats,
        hourlyPatterns,
        dowStats,
    ] = await Promise.all([
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
            .limit(40),
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
    ]);

    // Format store overview
    const storeRows = storeStats.data || [];
    const storeContext = storeRows
        .map(
            (w) =>
                `${w.week_label}: Sales $${w.total_net_sales?.toLocaleString()}, ` +
                `${w.total_transactions} txns, Avg $${w.avg_transaction_value}, ` +
                `Labour ${w.labour_pct ?? "N/A"}%, Margin ${w.weighted_margin_pct ?? "N/A"}%, ` +
                `Real Profit ${w.real_profit_pct ?? "N/A"}% ($${w.real_profit_dollars ?? "N/A"}), ` +
                `Members ${w.member_tx_ratio ? (w.member_tx_ratio * 100).toFixed(1) : "N/A"}% of txns`
        )
        .join("\n");

    // Top categories this week
    const catRows = categoryStats.data || [];
    const latestWeek = catRows[0]?.week_start;
    const topCats = catRows
        .filter((c) => c.week_start === latestWeek)
        .slice(0, 10)
        .map(
            (c) =>
                `${c.category} (${c.side}): $${c.total_net_sales?.toLocaleString()}, ${c.pct_of_total_sales?.toFixed(1)}% of sales` +
                (c.wow_sales_change_pct != null
                    ? `, ${c.wow_sales_change_pct > 0 ? "+" : ""}${c.wow_sales_change_pct.toFixed(1)}% WoW`
                    : "")
        )
        .join("\n");

    // Member trends
    const memberRows = memberStats.data || [];
    const memberContext = memberRows
        .map(
            (m) =>
                `${m.week_label}: ${m.unique_customers} members, ` +
                `Avg spend/visit $${m.avg_spend_per_visit?.toFixed(2)}, ` +
                `Points earned ${m.total_points_earned ?? 0}, redeemed ${m.total_points_redeemed ?? 0}`
        )
        .join("\n");

    // Labour
    const staffRows = staffStats.data || [];
    const staffContext = staffRows
        .map(
            (s) =>
                `${s.week_label}: $${s.total_labour_cost?.toLocaleString()} labour, ` +
                `${s.total_hours?.toFixed(1)}h total, ${s.unique_staff} staff, ` +
                `Teen $${s.teen_cost} / Adult $${s.adult_cost}`
        )
        .join("\n");

    // Peak hours
    const peakHours = (hourlyPatterns.data || [])
        .filter((h) => h.week_start === latestWeek)
        .map((h) => `${h.hour}:00 (${h.pct_of_daily_total?.toFixed(1)}% of daily)`)
        .join(", ");

    // Best days
    const dowRows = (dowStats.data || []).filter(
        (d) => d.week_start === latestWeek
    );
    const bestDay = dowRows.sort(
        (a, b) => (b.total_net_sales || 0) - (a.total_net_sales || 0)
    )[0];

    return `
## VIE Market — Business Intelligence (Last 4 Weeks)

### Weekly Sales Overview
${storeContext || "No data available yet."}

### Top Categories (Latest Week)
${topCats || "No category data yet."}

### Member Engagement
${memberContext || "No member data yet."}

### Labour Costs
${staffContext || "No labour data yet."}

### Peak Hours (Latest Week)
${peakHours || "No hourly data yet."}

### Best Day (Latest Week)
${bestDay ? `${bestDay.dow_name}: $${bestDay.total_net_sales?.toLocaleString()}, ${bestDay.total_transactions} txns` : "No data yet."}

### Business Profile
- Organic grocery + café in Manly, NSW
- Two sides: Café (~70% margin, ~30% of sales) and Retail (~41% margin, ~70% of sales)
- Open since August 20, 2025
- Loyalty program: Points-based via Square
- Financial Year: July 1 – June 30 (Australian)
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
