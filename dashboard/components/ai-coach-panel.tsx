"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useChat } from "@ai-sdk/react";
import { TextStreamChatTransport } from "ai";
import { motion, AnimatePresence } from "framer-motion";
import {
    MessageSquareText,
    X,
    Send,
    Sparkles,
    Loader2,
    Trash2,
    ChevronDown,
    Home,
    FileText,
} from "lucide-react";

function generateSessionId() {
    return `session_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

// ── Markdown-lite renderer ───────────────────────────────────────────

function renderMarkdown(text: string) {
    // Split into lines and process
    const lines = text.split("\n");
    const elements: React.ReactNode[] = [];
    let inList = false;
    let listItems: React.ReactNode[] = [];

    const flushList = () => {
        if (listItems.length > 0) {
            elements.push(
                <ul key={`list-${elements.length}`} className="space-y-1 my-2">
                    {listItems}
                </ul>
            );
            listItems = [];
            inList = false;
        }
    };

    const formatInline = (line: string): React.ReactNode => {
        // Bold + italic
        const parts = line.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g);
        return parts.map((part, i) => {
            if (part.startsWith("**") && part.endsWith("**")) {
                return (
                    <strong key={i} className="font-semibold text-[#1A1A1A]">
                        {part.slice(2, -2)}
                    </strong>
                );
            }
            if (part.startsWith("*") && part.endsWith("*")) {
                return <em key={i}>{part.slice(1, -1)}</em>;
            }
            if (part.startsWith("`") && part.endsWith("`")) {
                return (
                    <code
                        key={i}
                        className="bg-[#F0F1EC] px-1.5 py-0.5 rounded text-xs font-mono text-[#4A5139]"
                    >
                        {part.slice(1, -1)}
                    </code>
                );
            }
            return part;
        });
    };

    lines.forEach((line, idx) => {
        const trimmed = line.trim();

        // Headers
        if (trimmed.startsWith("### ")) {
            flushList();
            elements.push(
                <h4
                    key={idx}
                    className="font-semibold text-[13px] text-[#4A5139] mt-3 mb-1"
                >
                    {formatInline(trimmed.slice(4))}
                </h4>
            );
            return;
        }
        if (trimmed.startsWith("## ")) {
            flushList();
            elements.push(
                <h3
                    key={idx}
                    className="font-semibold text-sm text-[#1A1A1A] mt-3 mb-1"
                >
                    {formatInline(trimmed.slice(3))}
                </h3>
            );
            return;
        }

        // Bullet list
        if (trimmed.startsWith("- ") || trimmed.startsWith("• ")) {
            inList = true;
            listItems.push(
                <li
                    key={idx}
                    className="flex items-start gap-2 text-[13px] leading-relaxed"
                >
                    <span className="text-[#6B7355] mt-1.5 flex-shrink-0 text-[8px]">
                        ●
                    </span>
                    <span>{formatInline(trimmed.slice(2))}</span>
                </li>
            );
            return;
        }

        // Numbered list
        if (/^\d+\.\s/.test(trimmed)) {
            inList = true;
            const num = trimmed.match(/^(\d+)\./)?.[1];
            const content = trimmed.replace(/^\d+\.\s*/, "");
            listItems.push(
                <li
                    key={idx}
                    className="flex items-start gap-2 text-[13px] leading-relaxed"
                >
                    <span className="text-[#6B7355] font-semibold text-xs mt-0.5 flex-shrink-0 min-w-[16px]">
                        {num}.
                    </span>
                    <span>{formatInline(content)}</span>
                </li>
            );
            return;
        }

        // Empty line
        if (trimmed === "") {
            flushList();
            return;
        }

        // Normal paragraph
        flushList();
        elements.push(
            <p key={idx} className="text-[13px] leading-relaxed my-1">
                {formatInline(trimmed)}
            </p>
        );
    });

    flushList();
    return elements;
}

// ── Question categories ──────────────────────────────────────────────

type QuestionCategory = {
    id: string;
    emoji: string;
    label: string;
    color: string;
    activeBg: string;
    questions: string[];
};

const QUESTION_CATEGORIES: QuestionCategory[] = [
    {
        id: "labour",
        emoji: "🎯",
        label: "Labour",
        color: "text-red-700",
        activeBg: "bg-red-50 border-red-200",
        questions: [
            "What's my labour cost % this week vs the 24% target?",
            "Which days this week had labour % above 30%? What went wrong?",
            "Compare weekend vs weekday labour efficiency — where am I overstaffed?",
            "What's the optimal teen vs adult staff split to minimise costs this weekend?",
            "Show me labour cost per transaction for each day this week — any outliers?",
            "If I cut 4 hours on my slowest weekday, how much would I save monthly?",
            "Build me a recommended staffing plan for next week based on recent patterns",
            "Am I spending more on Sunday penalty rates than the extra revenue justifies?",
            "What's my month-over-month labour trend? Am I improving or getting worse?",
        ],
    },
    {
        id: "margins",
        emoji: "💰",
        label: "Margins",
        color: "text-amber-700",
        activeBg: "bg-amber-50 border-amber-200",
        questions: [
            "What's driving my average sale value down? Break it down by factor",
            "Which categories delivered the highest margin this week and why?",
            "My real profit margin target is 25% — where do I stand and what's the gap?",
            "Cafe mix is growing — is the extra margin covering the extra labour cost?",
            "Show me gross vs net spread — are discounts eating into my profits?",
            "What would happen to monthly profit if I lifted avg sale by $1?",
            "Rank my bottom 5 margin categories — should I drop any of them?",
            "Which categories above 42% margin should I give more shelf space to?",
            "Compare this week's real profit per transaction vs last month's average",
            "Set me 3 specific margin goals for next week with action steps",
        ],
    },
    {
        id: "members",
        emoji: "👥",
        label: "Members",
        color: "text-blue-700",
        activeBg: "bg-blue-50 border-blue-200",
        questions: [
            "How many members are at risk of churning this week? What should I do?",
            "What % of my revenue comes from members vs walk-ins? Is it improving?",
            "What's the avg spend difference between members and non-members?",
            "Give me a loyalty campaign idea for this week based on current member data",
            "How many new members signed up this week vs last week?",
            "Which day of the week has the most new member sign-ups?",
            "What points redemption patterns am I seeing? Are members engaged?",
            "Identify my top 10 highest-spending members — are any cooling down?",
            "What should my member re-engagement SMS say this week based on the data?",
        ],
    },
    {
        id: "stock",
        emoji: "📦",
        label: "Stock",
        color: "text-green-700",
        activeBg: "bg-green-50 border-green-200",
        questions: [
            "Which products should I run a clearance promotion on this week?",
            "Show me high-margin products that are underselling — I'll push these today",
            "What categories have dead stock sitting over 90 days? Time to act",
            "Give me a daily sales goal: which 3 products should I actively promote today?",
            "Which categories are declining in sales and what could be causing it?",
            "How many 'Needs Action' inventory alerts do I have? Are they improving?",
            "What high-margin product could I bundle with a café item for an upsell?",
            "Compare Tea, Gifts, and Fermented Goods performance — my best margin categories",
            "How much capital is tied up in slow-moving stock? What should I clear first?",
            "Suggest a weekly promotion plan based on my highest-margin, lowest-selling items",
        ],
    },
    {
        id: "gameplan",
        emoji: "📊",
        label: "Game Plan",
        color: "text-purple-700",
        activeBg: "bg-purple-50 border-purple-200",
        questions: [
            "Give me my Monday morning briefing — how did last week go and what to focus on?",
            "Score my week: rate labour, margins, members, and stock out of 10",
            "What are the 3 most important things I should fix this week?",
            "Set me SMART goals for this week across all key metrics",
            "What does a good week look like for VIE? Define it in numbers",
            "Am I on track for my monthly targets? What needs to change?",
            "What's one quick win I can implement today to improve profitability?",
            "Build me a daily checklist for optimising VIE this week",
        ],
    },
];

// Pick 4 rotating quick suggestions (1 from each of the first 4 categories)
function getQuickSuggestions(): string[] {
    return QUESTION_CATEGORIES.slice(0, 4).map((cat) => {
        const idx = Math.floor(Math.random() * cat.questions.length);
        return cat.questions[idx];
    });
}

// ── Component ────────────────────────────────────────────────────────

// Helper to extract text content from a UIMessage
function getMessageText(msg: { content?: string; parts?: Array<{ type: string; text?: string }> }): string {
    // AI SDK v6 UIMessage has parts array
    if (msg.parts) {
        return msg.parts
            .filter((p) => p.type === "text" && p.text)
            .map((p) => p.text!)
            .join("");
    }
    // Fallback to content string
    return msg.content || "";
}

export default function AiCoachPanel() {
    const [isOpen, setIsOpen] = useState(false);
    const [sessionId] = useState(generateSessionId);
    const [input, setInput] = useState("");
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const scrollRef = useRef<HTMLDivElement>(null);
    const [showScrollBtn, setShowScrollBtn] = useState(false);
    const [activeCategory, setActiveCategory] = useState<string | null>(null);
    const [quickSuggestions] = useState(() => getQuickSuggestions());
    const [showDocs, setShowDocs] = useState(false);

    const { messages, sendMessage, status, setMessages } =
        useChat({
            transport: new TextStreamChatTransport({
                api: "/api/chat",
                body: { sessionId },
            }),
        });

    const isLoading = status === "streaming" || status === "submitted";

    // Auto-scroll on new messages
    useEffect(() => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [messages]);

    // Focus input when panel opens
    useEffect(() => {
        if (isOpen && inputRef.current) {
            setTimeout(() => inputRef.current?.focus(), 300);
        }
    }, [isOpen]);

    // Detect scroll position for scroll-down button
    const handleScroll = useCallback(() => {
        const el = scrollRef.current;
        if (el) {
            const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
            setShowScrollBtn(!atBottom);
        }
    }, []);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    const clearChat = () => {
        setMessages([]);
    };

    const doSend = (text: string) => {
        const trimmed = text.trim();
        if (!trimmed || isLoading) return;
        setInput("");
        sendMessage({ text: trimmed });
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            doSend(input);
        }
    };

    const handleFormSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        doSend(input);
    };

    const handleSuggestion = (prompt: string) => {
        sendMessage({ text: prompt });
    };

    return (
        <>
            {/* FAB Button */}
            <AnimatePresence>
                {!isOpen && (
                    <motion.button
                        initial={{ scale: 0, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0, opacity: 0 }}
                        transition={{ type: "spring", stiffness: 260, damping: 20 }}
                        onClick={() => setIsOpen(true)}
                        className="fixed bottom-6 right-6 z-[100] w-14 h-14 rounded-full
              bg-gradient-to-br from-[#6B7355] to-[#4A5139]
              text-white shadow-lg shadow-[#6B7355]/25
              hover:shadow-xl hover:shadow-[#6B7355]/30
              hover:scale-105 active:scale-95
              transition-all duration-200 cursor-pointer
              flex items-center justify-center group"
                        title="AI Business Coach"
                    >
                        <Sparkles className="w-6 h-6 group-hover:rotate-12 transition-transform" />
                        {/* Pulse ring */}
                        <span className="absolute inset-0 rounded-full bg-[#6B7355]/20 animate-ping" />
                    </motion.button>
                )}
            </AnimatePresence>

            {/* Chat Panel */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: 20, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 20, scale: 0.95 }}
                        transition={{ type: "spring", stiffness: 300, damping: 30 }}
                        className="fixed bottom-6 right-6 z-[100]
              w-[420px] max-w-[calc(100vw-48px)]
              h-[600px] max-h-[calc(100vh-48px)]
              bg-white rounded-2xl shadow-2xl
              border border-[#EAEAE8]
              flex flex-col overflow-hidden"
                    >
                        {/* Header */}
                        <div
                            className="flex items-center justify-between px-5 py-4
              bg-gradient-to-r from-[#1E1E2E] to-[#2A2A3E]
              border-b border-white/10"
                        >
                            <div className="flex items-center gap-3">
                                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#6B7355] to-[#A8B094] flex items-center justify-center">
                                    <Sparkles className="w-5 h-5 text-white" />
                                </div>
                                <div>
                                    <h3 className="text-white font-semibold text-sm tracking-wide">
                                        AI Business Coach
                                    </h3>
                                    <p className="text-[#7A7A8A] text-[11px]">
                                        Powered by your live data
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-1 relative">
                                <button
                                    onClick={() => setShowDocs(!showDocs)}
                                    className={`p-2 rounded-lg transition-all cursor-pointer ${showDocs ? "text-white bg-white/15" : "text-[#7A7A8A] hover:text-white hover:bg-white/10"
                                        }`}
                                    title="Documents"
                                >
                                    <FileText className="w-4 h-4" />
                                </button>
                                {messages.length > 0 && (
                                    <button
                                        onClick={() => { clearChat(); setShowDocs(false); }}
                                        className="p-2 text-[#7A7A8A] hover:text-white hover:bg-white/10 rounded-lg transition-all cursor-pointer"
                                        title="Back to menu"
                                    >
                                        <Home className="w-4 h-4" />
                                    </button>
                                )}
                                {messages.length > 0 && (
                                    <button
                                        onClick={() => { clearChat(); setShowDocs(false); }}
                                        className="p-2 text-[#7A7A8A] hover:text-white hover:bg-white/10 rounded-lg transition-all cursor-pointer"
                                        title="Clear chat"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                )}
                                <button
                                    onClick={() => { setIsOpen(false); setShowDocs(false); }}
                                    className="p-2 text-[#7A7A8A] hover:text-white hover:bg-white/10 rounded-lg transition-all cursor-pointer"
                                    title="Close"
                                >
                                    <X className="w-4 h-4" />
                                </button>

                                {/* Docs dropdown */}
                                <AnimatePresence>
                                    {showDocs && (
                                        <motion.div
                                            initial={{ opacity: 0, y: -8, scale: 0.95 }}
                                            animate={{ opacity: 1, y: 0, scale: 1 }}
                                            exit={{ opacity: 0, y: -8, scale: 0.95 }}
                                            transition={{ duration: 0.15 }}
                                            className="absolute top-full right-0 mt-2 w-64 bg-white rounded-xl shadow-2xl border border-[#EAEAE8] z-50 overflow-hidden"
                                        >
                                            <div className="p-3 space-y-3">
                                                {/* AI Guide */}
                                                <div>
                                                    <p className="text-[10px] font-semibold uppercase tracking-wider text-[#6B7355] mb-1.5 px-1">📘 AI Guide</p>
                                                    <a
                                                        href="/docs/ai_coach_tutorial.pdf"
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg hover:bg-[#F5F5F0] transition-colors group"
                                                    >
                                                        <FileText className="w-4 h-4 text-[#6B7355] shrink-0" />
                                                        <span className="text-xs text-[#1A1A1A] group-hover:text-[#6B7355] transition-colors">AI Coach Tutorial</span>
                                                    </a>
                                                </div>
                                                <div className="border-t border-[#EAEAE8]" />
                                                {/* Big Pic Reports */}
                                                <div>
                                                    <p className="text-[10px] font-semibold uppercase tracking-wider text-[#B8860B] mb-1.5 px-1">📊 Big Pic Reports</p>
                                                    <a
                                                        href="/docs/business_improvement_plan.pdf"
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg hover:bg-[#F5F5F0] transition-colors group"
                                                    >
                                                        <FileText className="w-4 h-4 text-[#B8860B] shrink-0" />
                                                        <span className="text-xs text-[#1A1A1A] group-hover:text-[#B8860B] transition-colors">Business Improvement Plan</span>
                                                    </a>
                                                </div>
                                                <div className="border-t border-[#EAEAE8]" />
                                                {/* Monthly Reports */}
                                                <div>
                                                    <p className="text-[10px] font-semibold uppercase tracking-wider text-[#4A6FA5] mb-1.5 px-1">📅 Monthly Reports</p>
                                                    <p className="text-[11px] text-[#999] italic px-2.5 py-1.5">Coming soon</p>
                                                </div>
                                                <div className="border-t border-[#EAEAE8]" />
                                                {/* Weekly Reports */}
                                                <div>
                                                    <p className="text-[10px] font-semibold uppercase tracking-wider text-[#7B68AE] mb-1.5 px-1">📋 Weekly Reports</p>
                                                    <p className="text-[11px] text-[#999] italic px-2.5 py-1.5">Coming soon</p>
                                                </div>
                                            </div>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </div>
                        </div>

                        {/* Messages Area */}
                        <div
                            ref={scrollRef}
                            onScroll={handleScroll}
                            className="flex-1 overflow-y-auto px-4 py-4 space-y-4 scroll-smooth"
                            style={{ scrollbarWidth: "thin", scrollbarColor: "#EAEAE8 transparent" }}
                        >
                            {messages.length === 0 ? (
                                <div className="flex flex-col h-full overflow-y-auto px-1 py-2"
                                    style={{ scrollbarWidth: "thin", scrollbarColor: "#EAEAE8 transparent" }}>
                                    {/* Welcome */}
                                    <div className="text-center px-3 pt-2 pb-3">
                                        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-[#6B7355]/10 to-[#A8B094]/10 flex items-center justify-center mb-3 mx-auto">
                                            <MessageSquareText className="w-7 h-7 text-[#6B7355]" />
                                        </div>
                                        <h4 className="font-semibold text-[#1A1A1A] text-base mb-0.5">
                                            Hi Boss! 👋
                                        </h4>
                                        <p className="text-[#8A8A8A] text-[12px] leading-relaxed">
                                            Your AI coach for VIE Market — pick a topic or ask anything
                                        </p>
                                    </div>

                                    {/* Quick Suggestions */}
                                    {!activeCategory && (
                                        <div className="px-2 mb-3">
                                            <p className="text-[10px] font-semibold text-[#B0B0B0] uppercase tracking-wider mb-1.5 px-1">
                                                Quick questions
                                            </p>
                                            <div className="grid gap-1.5">
                                                {quickSuggestions.map((prompt: string) => (
                                                    <button
                                                        key={prompt}
                                                        onClick={() => handleSuggestion(prompt)}
                                                        className="text-left px-3 py-2 rounded-xl text-[12px]
                                              bg-[#F8F8F6] hover:bg-[#F0F1EC]
                                              text-[#5A5A5A] hover:text-[#1A1A1A]
                                              border border-[#EAEAE8] hover:border-[#6B7355]/20
                                              transition-all duration-200 cursor-pointer
                                              leading-snug"
                                                    >
                                                        {prompt}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Category Pills */}
                                    <div className="px-2 mb-2">
                                        <p className="text-[10px] font-semibold text-[#B0B0B0] uppercase tracking-wider mb-1.5 px-1">
                                            Browse by topic
                                        </p>
                                        <div className="flex flex-wrap gap-1.5">
                                            {QUESTION_CATEGORIES.map((cat) => (
                                                <button
                                                    key={cat.id}
                                                    onClick={() =>
                                                        setActiveCategory(
                                                            activeCategory === cat.id ? null : cat.id
                                                        )
                                                    }
                                                    className={`px-2.5 py-1.5 rounded-lg text-[12px] font-medium
                                          border transition-all duration-200 cursor-pointer
                                          ${activeCategory === cat.id
                                                            ? `${cat.activeBg} ${cat.color}`
                                                            : "bg-[#F8F8F6] border-[#EAEAE8] text-[#5A5A5A] hover:bg-[#F0F1EC]"
                                                        }`}
                                                >
                                                    {cat.emoji} {cat.label}
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Expanded Category Questions */}
                                    {activeCategory && (
                                        <div className="px-2 pb-2">
                                            {QUESTION_CATEGORIES.filter(
                                                (c) => c.id === activeCategory
                                            ).map((cat) => (
                                                <div key={cat.id} className="grid gap-1.5">
                                                    {cat.questions.map((q) => (
                                                        <button
                                                            key={q}
                                                            onClick={() => handleSuggestion(q)}
                                                            className={`text-left px-3 py-2 rounded-xl text-[12px]
                                                ${cat.activeBg} ${cat.color}
                                                hover:brightness-95
                                                transition-all duration-200 cursor-pointer
                                                leading-snug`}
                                                        >
                                                            {q}
                                                        </button>
                                                    ))}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <>
                                    {messages.map((msg) => (
                                        <div
                                            key={msg.id}
                                            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                                        >
                                            <div
                                                className={`max-w-[85%] rounded-2xl px-4 py-3 ${msg.role === "user"
                                                    ? "bg-gradient-to-br from-[#6B7355] to-[#4A5139] text-white rounded-br-md"
                                                    : "bg-[#F8F8F6] text-[#2C2C2C] border border-[#EAEAE8] rounded-bl-md"
                                                    }`}
                                            >
                                                {msg.role === "user" ? (
                                                    <p className="text-[13px] leading-relaxed whitespace-pre-wrap">
                                                        {getMessageText(msg)}
                                                    </p>
                                                ) : (
                                                    <div className="prose-coach">
                                                        {renderMarkdown(getMessageText(msg))}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                    {isLoading && (
                                        <div className="flex justify-start">
                                            <div className="bg-[#F8F8F6] border border-[#EAEAE8] rounded-2xl rounded-bl-md px-4 py-3">
                                                <div className="flex items-center gap-2">
                                                    <Loader2 className="w-4 h-4 text-[#6B7355] animate-spin" />
                                                    <span className="text-[13px] text-[#8A8A8A]">
                                                        Analysing your data...
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                    <div ref={messagesEndRef} />
                                </>
                            )}
                        </div>

                        {/* Scroll to bottom button */}
                        <AnimatePresence>
                            {showScrollBtn && messages.length > 0 && (
                                <motion.button
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: 10 }}
                                    onClick={scrollToBottom}
                                    className="absolute bottom-[76px] left-1/2 -translate-x-1/2
                    bg-white border border-[#EAEAE8] shadow-md
                    rounded-full p-1.5 cursor-pointer hover:bg-[#F8F8F6]
                    transition-colors z-10"
                                >
                                    <ChevronDown className="w-4 h-4 text-[#5A5A5A]" />
                                </motion.button>
                            )}
                        </AnimatePresence>

                        {/* Input Area */}
                        <div className="border-t border-[#EAEAE8] px-4 py-3 bg-white">
                            <form
                                onSubmit={handleFormSubmit}
                                className="flex items-end gap-2"
                            >
                                <textarea
                                    ref={inputRef}
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    onKeyDown={handleKeyDown}
                                    placeholder="Ask about your business..."
                                    rows={1}
                                    className="flex-1 resize-none rounded-xl border border-[#EAEAE8]
                    bg-[#F8F8F6] px-3.5 py-2.5 text-[13px]
                    placeholder:text-[#B0B0B0]
                    focus:outline-none focus:ring-2 focus:ring-[#6B7355]/20 focus:border-[#6B7355]/40
                    transition-all duration-200
                    max-h-[120px] overflow-y-auto"
                                    style={{ scrollbarWidth: "thin" }}
                                    onInput={(e) => {
                                        const el = e.currentTarget;
                                        el.style.height = "auto";
                                        el.style.height = Math.min(el.scrollHeight, 120) + "px";
                                    }}
                                />
                                <button
                                    type="submit"
                                    disabled={isLoading || !input.trim()}
                                    className="p-2.5 rounded-xl
                    bg-gradient-to-br from-[#6B7355] to-[#4A5139]
                    text-white
                    disabled:opacity-40 disabled:cursor-not-allowed
                    hover:shadow-md hover:shadow-[#6B7355]/20
                    active:scale-95
                    transition-all duration-200 cursor-pointer
                    flex-shrink-0"
                                    title="Send"
                                >
                                    <Send className="w-4 h-4" />
                                </button>
                            </form>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
}
