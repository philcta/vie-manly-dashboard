# Dashboard Tech Stack — Streamlit vs Modern JS

## The Honest Comparison

| Aspect | Streamlit (Current) | Next.js + Vercel |
|--------|-------------------|------------------|
| **Initial load** | ~5-10s (runs Python, loads all data, re-executes script) | **<1s** (static HTML served from CDN, data loaded async) |
| **Interaction speed** | Every click re-runs the entire Python script | **Instant** — React state updates, no server round-trip |
| **Design freedom** | Very limited (fixed layout, basic widgets) | **Unlimited** — full CSS, animations, glassmorphism |
| **Charts** | Plotly (functional but heavy) | Recharts/Tremor — lightweight, beautiful, animated |
| **Mobile** | Barely responsive | **Fully responsive** with Tailwind |
| **Cost** | Streamlit Cloud free tier (slow, cold starts) | Vercel free tier (fast, global CDN, no cold starts) |
| **Auth/security** | Basic | Supabase Auth built-in |

### Verdict: **Yes, migrate.** Here's why:

1. **Your data is already in Supabase** — the frontend just reads it. No Python needed for the dashboard.
2. **Pre-computed tables** (`daily_item_summary`, `daily_store_stats`, `member_daily_stats`) = the frontend fetches ~20-200 rows, not 300K.
3. **Python stays** for the sync jobs (Square API → Supabase via GitHub Actions). That's the right tool for ETL.

---

## Recommended Stack

### Frontend
| Tool | Purpose |
|------|---------|
| **Next.js 15** (App Router) | React framework with server components |
| **Tailwind CSS v4** | Utility-first styling, dark mode, responsive |
| **Tremor** | Dashboard UI components (KPI cards, charts, tables) built on Recharts |
| **Recharts** | Lightweight animated charts (comes with Tremor) |
| **Lucide Icons** | Modern, clean icon set (600+ icons) |
| **Framer Motion** | Micro-animations (number counters, transitions) |
| **Supabase JS Client** | Direct database queries from frontend |

### Hosting
| Tool | Purpose |
|------|---------|
| **Vercel** | Deploy Next.js (free tier: 100GB bandwidth, instant deploys) |
| **Supabase** | Database + Auth (already set up) |
| **GitHub Actions** | Python sync jobs (already set up) |

### Backend (Keep Python)
- `square_sync.py` runs as a GitHub Actions cron job
- No API server needed — frontend queries Supabase directly

---

## UI Design Vision

### Layout
```
┌─────────────────────────────────────────────────┐
│  Sidebar (dark/glass)     │  Main Content       │
│  ┌─────────────────┐      │                     │
│  │ 🏪 Vie Manly    │      │  KPI Cards (4-col)  │
│  │                 │      │  ┌───┬───┬───┬───┐  │
│  │ 📊 Overview     │      │  │$$ │#tx│qty│avg│  │
│  │ 📈 Sales        │      │  └───┴───┴───┴───┘  │
│  │ 👥 Members      │      │                     │
│  │ 📦 Inventory    │      │  Revenue Chart      │
│  │ 🧪 Product Mix  │      │  ┌───────────────┐  │
│  │ 💡 Insights     │      │  │ ~~~~~~~~~~~~~ │  │
│  │                 │      │  │ ~~~~~~~~~~~~~ │  │
│  └─────────────────┘      │  └───────────────┘  │
│                           │                     │
│  Date Picker              │  Category Breakdown │
│  [From] → [To]            │  + Member Ratios    │
└─────────────────────────────────────────────────┘
```

### Design Elements
- **Dark mode** with glassmorphism sidebar (blur + transparency)
- **KPI cards** with animated counters (↑12% green / ↓5% red)
- **Gradient area charts** (not just lines — filled gradients underneath)
- **Smooth transitions** between date ranges (no page reload)
- **Skeleton loaders** while data fetches (not a spinner)
- **Sparklines** in table cells (mini inline charts)

### Chart Recommendations

| Current (Streamlit) | Upgrade To |
|---------------------|------------|
| Static bar charts | **Animated bar charts** with hover tooltips |
| Line charts | **Gradient area charts** with smooth curves |
| Data tables | **Sortable tables with sparklines** per row |
| Pie charts | **Donut charts** with center KPI |
| No heatmaps | **Calendar heatmap** (GitHub-style) for daily sales |
| No gauges | **Radial progress** for member ratio targets |

---

## Migration Strategy

### Phase 1: New Dashboard (1-2 days)
- Set up Next.js + Tailwind + Tremor
- Build Overview page (KPI cards + revenue chart)
- Connect to Supabase (read `daily_item_summary`, `daily_store_stats`)

### Phase 2: All Reports (2-3 days)
- Sales by category
- Member insights (ratios over time, churn analysis)
- Inventory / Product mix
- Customer search

### Phase 3: Polish (1 day)
- Animations, dark mode toggle
- Mobile responsive
- Auth (optional — restrict access)

### What Stays in Python
- `square_sync.py` — GitHub Actions cron (already works)
- `backfill_*.py` scripts — one-time data jobs
- Nothing else needs Python!

---

## Speed Estimate

| Action | Streamlit | Next.js + Vercel |
|--------|-----------|-----------------|
| First page load | 5-10s | **<1s** |
| Switch tabs | 3-5s (re-run script) | **instant** |
| Change date range | 2-3s | **<500ms** |
| Load member insights | 5-8s (lazy load) | **<1s** |
