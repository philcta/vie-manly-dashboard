# AI Coach — Full Implementation Guide

> **Reusable blueprint for adding an AI Business Coach to any Next.js + Supabase dashboard.**  
> Last updated: 2026-03-16

---

## Overview

The AI Business Coach is a floating chat panel that gives store owners real-time, data-backed business insights. It combines:

1. **Pre-computed context** — weekly summary tables loaded into the system prompt (zero latency)
2. **On-demand tools** — Supabase RPC functions the AI calls when it needs specific data (product lookup, daily sales, etc.)
3. **Anti-hallucination guardrails** — strict rules preventing the AI from fabricating numbers
4. **Conversation persistence** — auto-saved to Supabase, with history, favorites, and PDF export

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Frontend (Next.js)                  │
│                                                     │
│  ai-coach-panel.tsx                                 │
│  ├── useChat() hook (AI SDK v6)                     │
│  ├── Topic categories (5 sections, 53 questions)    │
│  ├── Conversation history (Supabase)                │
│  ├── Favorites (localStorage)                       │
│  ├── PDF export (lib/export-pdf.ts)                 │
│  └── Navigation: Home / Topics / Strip              │
│                                                     │
│  ──── Streams ──────────────────────────────────▶    │
│                                                     │
│  app/api/chat/route.ts (Edge Runtime)               │
│  ├── buildBusinessContext() — queries weekly tables  │
│  ├── SYSTEM_PROMPT — rules + formatting + tools     │
│  ├── streamText() with 4 tools                      │
│  │   ├── lookup_product (fuzzy search)              │
│  │   ├── lookup_category (category deep dive)       │
│  │   ├── get_daily_sales (day-by-day breakdown)     │
│  │   └── get_mtd_summary (month-to-date totals)    │
│  └── onFinish → saves to coach_conversations        │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│                  Supabase (Postgres)                 │
│                                                     │
│  Pre-computed weekly tables (context):               │
│  ├── weekly_store_stats                             │
│  ├── weekly_category_stats                          │
│  ├── weekly_member_stats                            │
│  ├── weekly_staff_stats                             │
│  ├── weekly_inventory_stats                         │
│  ├── weekly_hourly_patterns                         │
│  └── weekly_dow_stats                               │
│                                                     │
│  Tool RPC functions (on-demand):                     │
│  ├── lookup_product(search_term text)               │
│  ├── lookup_category_products(cat_name text)        │
│  ├── get_daily_sales(num_days int)                  │
│  └── get_mtd_summary()                              │
│                                                     │
│  Storage:                                           │
│  ├── coach_conversations (per-message log)          │
│  ├── ai_coach_conversations (full session save)     │
│  └── kpi_targets (business goals)                   │
└─────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | Next.js (App Router) | 16.x |
| AI SDK | `ai` (Vercel AI SDK) | v6 |
| AI Provider | `@ai-sdk/openai` | v3 |
| Chat Hook | `@ai-sdk/react` | v2 |
| Model | GPT-4o | — |
| Schema Validation | Zod | v3/v4 |
| Database | Supabase (PostgreSQL) | — |
| Styling | Tailwind CSS | v4 |
| Animation | Framer Motion | — |
| Icons | Lucide React | — |

---

## Implementation Phases

### Phase 1: Pre-computed Context + Basic Chat

**Goal**: AI can answer general business questions using pre-loaded weekly data.

**Steps**:
1. Create 7 weekly summary tables in Supabase (see `ai_coach_supabase_rpcs.md`)
2. Write `buildBusinessContext()` function that queries top-level stats and formats them as text
3. Set up `app/api/chat/route.ts` with `streamText()` and system prompt
4. Build floating chat panel component (`ai-coach-panel.tsx`)
5. Add conversation persistence (auto-save to Supabase)

**Key code — API route**:
```typescript
import { openai } from "@ai-sdk/openai";
import { streamText, convertToModelMessages } from "ai";

export const runtime = "edge";
export const maxDuration = 30;

const context = await buildBusinessContext(); // queries weekly tables

const result = streamText({
    model: openai("gpt-4o"),
    system: `${SYSTEM_PROMPT}\n\n## Current Business Data\n\n${context}`,
    messages: modelMessages,
});

return result.toTextStreamResponse();
```

**Key code — Frontend**:
```typescript
import { useChat } from "@ai-sdk/react";
import { TextStreamChatTransport } from "ai";

const { messages, sendMessage, status } = useChat({
    transport: new TextStreamChatTransport({
        api: "/api/chat",
        body: { sessionId },
    }),
});
```

---

### Phase 2: Conversation Persistence + History + Favorites

**Goal**: Users can revisit past conversations, bookmark questions, and export to PDF.

**Features**:
- Auto-save conversations to `ai_coach_conversations` table
- History panel with date/time, question count, restore, delete
- Favorites stored in `localStorage` with star toggle on questions
- PDF export using custom `exportConversationToPdf()` function
- Markdown table formatting preserved in PDF export

**Tables needed**:
```sql
-- Per-message log (used by API route)
CREATE TABLE coach_conversations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Full conversation save (used by frontend)
CREATE TABLE ai_coach_conversations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE,
    title TEXT,
    messages JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

---

### Phase 3: Anti-Hallucination Guardrails

**Goal**: Prevent the AI from fabricating numbers or making up data.

**Changes**:
1. Upgrade model from `gpt-4o-mini` to `gpt-4o` (better instruction following)
2. Add side-by-side week comparison data (current + prior week)
3. Add data freshness timestamp to context
4. Strict system prompt rules:

```
## CRITICAL DATA INTEGRITY RULES
1. NEVER invent, estimate, or approximate data
2. ONLY use numbers from the Business Data section above
3. If data is missing, say "I don't have that data" or show "N/A"
4. Category margin percentages are FIXED — don't fabricate different values for different weeks
5. For WoW comparisons, use ONLY the provided WoW% column — do NOT calculate your own
6. When comparing weeks, use exact figures from both W[current] and W[prior] rows
```

---

### Phase 4: Tool Use (Function Calling)

**Goal**: AI can query Supabase on demand for specific data not in the pre-loaded context.

**4 Supabase RPC Functions** (see `ai_coach_supabase_rpcs.md` for full SQL):

| Tool | Purpose | Avg Response Time |
|------|---------|-------------------|
| `lookup_product(search_term)` | Fuzzy product search across 4,290 items | 7ms |
| `lookup_category_products(cat_name)` | All products in a category | 9ms |
| `get_daily_sales(num_days)` | Day-by-day sales for last N days | 33ms |
| `get_mtd_summary()` | Month-to-date totals | 21ms |

**Required indexes** (for sub-10ms performance):
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_ii_product_name_trgm ON inventory_intelligence USING gin (product_name gin_trgm_ops);
CREATE INDEX idx_ii_category_trgm ON inventory_intelligence USING gin (category gin_trgm_ops);
CREATE INDEX idx_transactions_date ON transactions (date DESC);
```

**Tool integration in route.ts** (AI SDK v6 syntax):
```typescript
import { streamText, stepCountIs } from "ai";
import { z } from "zod";

const result = streamText({
    model: openai("gpt-4o"),
    system: systemPrompt,
    messages: modelMessages,
    stopWhen: stepCountIs(3), // v6 replaces maxSteps
    tools: {
        lookup_product: {
            description: "Search for a specific product by name...",
            inputSchema: z.object({  // v6 uses inputSchema, not parameters
                search_term: z.string(),
            }),
            execute: async ({ search_term }: { search_term: string }) => {
                const { data } = await supabase.rpc("lookup_product", { search_term });
                return data || [];
            },
        },
        // ... more tools
    },
});
```

**AI SDK v6 gotchas**:
- Use `inputSchema` not `parameters` (renamed in v6)
- Use `stopWhen: stepCountIs(N)` not `maxSteps: N`
- Use inline tool objects, not `tool()` wrapper (avoids Zod v3/v4 incompatibility)
- `import { stepCountIs } from "ai"` — it's in the main `ai` package

**System prompt tool documentation**:
```
## Available Tools
You have access to live database query tools. Use them when:
- **lookup_product**: User asks about a SPECIFIC product not in your top 15 list
- **lookup_category**: User asks about ALL products in a category
- **get_daily_sales**: User asks about daily trends or specific days
- **get_mtd_summary**: User asks about month-to-date performance
Do NOT call tools for questions you can already answer from the Business Data context above.
```

---

## UI Navigation System

The AI Coach panel has 3 navigation levels:

### 1. Header Bar (always visible)
- **Home** — clears chat, returns to welcome screen with topic browser
- **Docs** — dropdown with PDF guides and reports
- **History** — past conversations (from Supabase)
- **Favs** — bookmarked questions (from localStorage)
- **Export** — PDF export of current conversation (only when messages exist)

### 2. Welcome Screen (when no messages)
- Welcome message ("Hi Boss! 👋")
- Quick questions (4 random, one from each category)
- Topic browser with 5 category tabs
- Expandable question lists with star-to-favorite toggle

### 3. In-Conversation Navigation
- **"New topic" banner** — at top of messages, with question counter ("3 Qs")
- **"Browse topics" strip** — collapsible panel above input area with full topic browser
- Both navigate back to welcome screen or allow asking from categories mid-conversation

---

## Question Categories

5 categories, 53 total questions — all data-backed:

| Category | Emoji | # Questions | Data Sources |
|----------|-------|-------------|--------------|
| Labour | 🎯 | 10 | `weekly_store_stats`, `weekly_staff_stats` |
| Margins | 💰 | 10 | `weekly_category_stats`, `kpi_targets`, `get_mtd_summary` tool |
| Members | 👥 | 10 | `weekly_member_stats`, `mv_top_members_30d`, loyalty data |
| Stock | 📦 | 12 | `inventory_intelligence`, `lookup_product` tool, `lookup_category` tool |
| Game Plan | 📊 | 11 | All tables + `get_daily_sales` tool + `get_mtd_summary` tool |

---

## KPI Targets

5 active targets that the AI Coach tracks:

| Metric | Target | Category |
|--------|--------|----------|
| Labour vs Sales % | ≤ 24% | Profitability |
| Average Sale | ≥ $24.00 | Revenue |
| Real Profit Margin | ≥ 25% | Profitability |
| Member Revenue % | +5% vs current | Members |
| Dead/Overstock Items | −30% vs current | Inventory |

---

## Cost

- **OpenAI GPT-4o**: ~$0.01–0.05 per conversation (input ~4K tokens context + output)
- **Supabase**: Free tier covers this easily
- **No extra latency** for normal questions (tools only fire on specific requests)

---

## How to Reuse for Another Project

1. **Copy the API route**: `app/api/chat/route.ts` — modify `buildBusinessContext()` for your data
2. **Copy the panel component**: `components/ai-coach-panel.tsx` — modify categories/questions
3. **Create your weekly tables**: Adapt the schema for your domain
4. **Create your tool RPCs**: Replace product/sales RPCs with your domain-specific queries
5. **Set env vars**: `OPENAI_API_KEY`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
6. **Install deps**: `npm install ai @ai-sdk/openai @ai-sdk/react zod`

---

## Files Reference

| File | Purpose |
|------|---------|
| `app/api/chat/route.ts` | API route — context builder, system prompt, tool definitions, streaming |
| `components/ai-coach-panel.tsx` | Full chat panel UI — categories, history, favorites, navigation |
| `lib/export-pdf.ts` | PDF export with markdown table/formatting support |
| `docs/ai_coach_supabase_rpcs.md` | All SQL for RPC functions, indexes, tables |
| `supabase/migrations/01-08_*.sql` | Weekly knowledge base table schemas |
| `scripts/backfill_weekly_stats.py` | Backfill script for weekly tables |
