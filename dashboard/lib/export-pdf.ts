/**
 * AI Coach — Export conversation to PDF
 * Uses browser-native print-to-PDF via a styled hidden iframe
 */

import { supabase } from "@/lib/supabase";

interface ChatMessage {
    role: "user" | "assistant" | string;
    content: string;
    createdAt?: string | Date;
}

interface ConversationExport {
    title: string;
    messages: ChatMessage[];
    createdAt: string; // ISO date
}

interface KpiTarget {
    metric: string;
    current_value: string;
    target_value: string;
    timeline: string;
}

// Fallback KPI targets if DB fetch fails
const FALLBACK_KPI_TARGETS: KpiTarget[] = [
    { metric: "Labour vs Sales %", current_value: "24.4% (trending 28%)", target_value: "≤ 24%", timeline: "4 weeks" },
    { metric: "Average Sale", current_value: "$24.10 (trending $22)", target_value: "≥ $24.00", timeline: "8 weeks" },
    { metric: "Real Profit Margin", current_value: "23.8%", target_value: "≥ 25%", timeline: "3 months" },
    { metric: "Member Revenue %", current_value: "TBD", target_value: "+5% vs current", timeline: "3 months" },
    { metric: "Dead/Overstock Items", current_value: "TBD", target_value: "−30% vs current", timeline: "6 weeks" },
];

async function fetchKpiTargets(): Promise<KpiTarget[]> {
    try {
        const { data } = await supabase
            .from("kpi_targets")
            .select("metric, current_value, target_value, timeline")
            .eq("active", true)
            .order("sort_order", { ascending: true });
        return (data as KpiTarget[]) || FALLBACK_KPI_TARGETS;
    } catch {
        return FALLBACK_KPI_TARGETS;
    }
}

function formatDate(d: string | Date): string {
    const date = new Date(d);
    return date.toLocaleDateString("en-AU", {
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function stripMarkdown(text: string): string {
    return text
        .replace(/#{1,6}\s/g, "")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>")
        .replace(/`(.*?)`/g, '<code style="background:#f0f0f0;padding:1px 4px;border-radius:3px;font-size:12px;">$1</code>')
        .replace(/^\s*[-•]\s/gm, "• ")
        .replace(/\n/g, "<br>");
}

function buildHtml(conv: ConversationExport, kpiTargets: KpiTarget[]): string {
    const dateStr = formatDate(conv.createdAt);

    const qaPairs = [];
    for (let i = 0; i < conv.messages.length; i++) {
        const msg = conv.messages[i];
        if (msg.role === "user") {
            const answer = conv.messages[i + 1];
            const msgTime = msg.createdAt ? formatDate(msg.createdAt) : "";
            qaPairs.push({
                question: msg.content,
                answer: answer?.role === "assistant" ? answer.content : "(No response)",
                time: msgTime,
            });
        }
    }

    const qaHtml = qaPairs
        .map(
            (qa, idx) => `
        <div style="margin-bottom:24px;page-break-inside:avoid;">
            <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:6px;">
                <span style="background:#6B7355;color:white;font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px;">Q${idx + 1}</span>
                ${qa.time ? `<span style="font-size:10px;color:#999;">${qa.time}</span>` : ""}
            </div>
            <div style="background:#f7f5f0;border-left:3px solid #6B7355;padding:10px 14px;border-radius:0 8px 8px 0;margin-bottom:8px;">
                <p style="margin:0;font-weight:600;color:#2a2a2a;font-size:13px;">${stripMarkdown(qa.question)}</p>
            </div>
            <div style="padding:4px 14px 4px 20px;color:#333;font-size:12.5px;line-height:1.65;">
                ${stripMarkdown(qa.answer)}
            </div>
        </div>
    `
        )
        .join("");

    const kpiRows = kpiTargets.map(
        (kpi) => `
        <tr>
            <td style="padding:7px 10px;border-bottom:1px solid #eee;font-weight:500;font-size:12px;">${kpi.metric}</td>
            <td style="padding:7px 10px;border-bottom:1px solid #eee;font-size:12px;color:#888;">${kpi.current_value}</td>
            <td style="padding:7px 10px;border-bottom:1px solid #eee;font-size:12px;color:#6B7355;font-weight:600;">${kpi.target_value}</td>
            <td style="padding:7px 10px;border-bottom:1px solid #eee;font-size:11px;color:#999;">${kpi.timeline}</td>
        </tr>
    `
    ).join("");

    return `<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>VIE. MANLY — AI Coach Report</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', -apple-system, sans-serif; color: #333; padding: 40px; max-width: 800px; margin: 0 auto; }
        @media print {
            body { padding: 20px; }
            .no-print { display: none !important; }
        }
    </style>
</head>
<body>
    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #6B7355;padding-bottom:16px;margin-bottom:24px;">
        <div>
            <h1 style="font-size:22px;color:#1a1a1a;letter-spacing:2px;margin-bottom:2px;">VIE<span style="color:#6B7355;">.</span> MANLY</h1>
            <p style="font-size:11px;color:#999;letter-spacing:3px;text-transform:uppercase;">AI Business Coach Report</p>
        </div>
        <div style="text-align:right;">
            <p style="font-size:11px;color:#666;">${dateStr}</p>
            <p style="font-size:10px;color:#aaa;">${qaPairs.length} question${qaPairs.length !== 1 ? "s" : ""}</p>
        </div>
    </div>

    <!-- Title -->
    <h2 style="font-size:16px;color:#2a2a2a;margin-bottom:20px;">${conv.title}</h2>

    <!-- Q&A Sections -->
    ${qaHtml}

    <!-- KPI Targets Reminder -->
    <div style="margin-top:32px;page-break-inside:avoid;border-top:1px solid #ddd;padding-top:20px;">
        <h3 style="font-size:13px;color:#6B7355;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:12px;">
            📊 KPI Targets Reminder
        </h3>
        <table style="width:100%;border-collapse:collapse;font-size:12px;">
            <thead>
                <tr style="background:#f7f5f0;">
                    <th style="padding:8px 10px;text-align:left;font-size:11px;color:#666;font-weight:600;border-bottom:2px solid #ddd;">Metric</th>
                    <th style="padding:8px 10px;text-align:left;font-size:11px;color:#666;font-weight:600;border-bottom:2px solid #ddd;">Current</th>
                    <th style="padding:8px 10px;text-align:left;font-size:11px;color:#666;font-weight:600;border-bottom:2px solid #ddd;">Target</th>
                    <th style="padding:8px 10px;text-align:left;font-size:11px;color:#666;font-weight:600;border-bottom:2px solid #ddd;">Timeline</th>
                </tr>
            </thead>
            <tbody>
                ${kpiRows}
            </tbody>
        </table>
        <p style="font-size:9px;color:#bbb;margin-top:8px;text-align:right;">Source: VIE. MANLY Business Improvement Plan — March 2026</p>
    </div>

    <!-- Footer -->
    <div style="margin-top:40px;border-top:1px solid #eee;padding-top:12px;text-align:center;">
        <p style="font-size:9px;color:#ccc;">Generated from VIE. MANLY Dashboard · vie-manly-dashboard.vercel.app</p>
    </div>
</body>
</html>`;
}

export async function exportConversationToPdf(conv: ConversationExport) {
    // Fetch latest KPI targets from Supabase
    const kpiTargets = await fetchKpiTargets();
    const html = buildHtml(conv, kpiTargets);

    // Open a new window with the styled report (user can Ctrl+P / Save as PDF)
    const win = window.open("", "_blank");
    if (!win) {
        alert("Please allow popups to export PDF.");
        return;
    }
    win.document.write(html);
    win.document.close();
}

export type { ChatMessage, ConversationExport };
