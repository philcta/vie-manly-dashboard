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

// ── Suggested prompts ────────────────────────────────────────────────

const SUGGESTED_PROMPTS = [
    "How are sales trending this week vs last week?",
    "Which categories are growing fastest?",
    "How can I reduce labour costs?",
    "What's my member engagement like?",
    "Give me a quick health check of the business",
    "What should I focus on this week?",
];

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
                            <div className="flex items-center gap-1">
                                {messages.length > 0 && (
                                    <button
                                        onClick={clearChat}
                                        className="p-2 text-[#7A7A8A] hover:text-white hover:bg-white/10 rounded-lg transition-all cursor-pointer"
                                        title="Clear chat"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                )}
                                <button
                                    onClick={() => setIsOpen(false)}
                                    className="p-2 text-[#7A7A8A] hover:text-white hover:bg-white/10 rounded-lg transition-all cursor-pointer"
                                    title="Close"
                                >
                                    <X className="w-4 h-4" />
                                </button>
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
                                <div className="flex flex-col items-center justify-center h-full text-center px-4">
                                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#6B7355]/10 to-[#A8B094]/10 flex items-center justify-center mb-4">
                                        <MessageSquareText className="w-8 h-8 text-[#6B7355]" />
                                    </div>
                                    <h4 className="font-semibold text-[#1A1A1A] text-base mb-1">
                                        Hi Phil! 👋
                                    </h4>
                                    <p className="text-[#8A8A8A] text-sm mb-6 leading-relaxed">
                                        I&apos;m your AI business coach for VIE Market. Ask me
                                        about sales, labour, members, or anything else.
                                    </p>
                                    <div className="grid gap-2 w-full">
                                        {SUGGESTED_PROMPTS.slice(0, 4).map((prompt) => (
                                            <button
                                                key={prompt}
                                                onClick={() => handleSuggestion(prompt)}
                                                className="text-left px-3.5 py-2.5 rounded-xl text-[13px]
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
