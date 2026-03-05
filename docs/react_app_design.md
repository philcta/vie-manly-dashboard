# Vie Market & Bar — React Dashboard (Square Style)

> Complete design document — Square Dashboard-inspired, clean & professional

---

## UI Mockups (Square Style)

````carousel
![1. Overview - Cafe vs Retail section, metric selector, 6 unique cards](C:/Users/panto/.gemini/antigravity/brain/dc95d672-52cc-4b33-bcab-99f1af1275ba/v12_overview_v2_1772504634681.png)
<!-- slide -->
![2. Members - Sortable table with Redeemed, % to Redeem, Loyalty Insights](C:/Users/panto/.gemini/antigravity/brain/dc95d672-52cc-4b33-bcab-99f1af1275ba/v12_members_1772505352527.png)
<!-- slide -->
![3. Staff - Cafe/Retail roles, gaps, colored Gantt](C:/Users/panto/.gemini/antigravity/brain/dc95d672-52cc-4b33-bcab-99f1af1275ba/v10_staff_v2_1772498665273.png)
<!-- slide -->
![4. SMS Campaigns - Builder, rules, history](C:/Users/panto/.gemini/antigravity/brain/dc95d672-52cc-4b33-bcab-99f1af1275ba/v10_sms_v2_1772498700253.png)
<!-- slide -->
![5. Inventory - Cafe categories, full bottom cards visible](C:/Users/panto/.gemini/antigravity/brain/dc95d672-52cc-4b33-bcab-99f1af1275ba/v10_inventory_v2_1772498685313.png)
<!-- slide -->
![6. Settings - Cafe categories in thresholds](C:/Users/panto/.gemini/antigravity/brain/dc95d672-52cc-4b33-bcab-99f1af1275ba/v10_settings_v2_1772498719197.png)
````

---

## 🎨 Prompt for Google AI Studio

```
Design a premium analytics dashboard web application for "Vie Market & Bar", 
a boutique café and retail store in Manly, Sydney. 

The design MUST follow Square Dashboard's visual language exactly:

DESIGN SYSTEM (Square-inspired):
- Font: "Square Sans" (fallback: Inter, -apple-system, system-ui)
- Background: Pure white #FFFFFF
- Surface/cards: White with 1px #E5E7EB border, no shadows
- Section backgrounds: #F7F7F8 very light gray
- Headings: #1A1A1A bold, 24px-32px
- KPI labels: Muted teal #6B8E8E, 13px
- KPI values: #1A1A1A black, 28px-36px bold
- Change badges: Green pill (#ECFDF5 bg, #059669 text, ▲ arrow) for positive, 
  Red pill (#FEF2F2 bg, #DC2626 text, ▼ arrow) for negative, 
  Gray pill (#F3F4F6 bg, #6B7280 text) for N/A
- Primary blue: #006AFF (charts, buttons, active states)
- Comparison blue: #B3D6FF (lighter bars for comparison period)
- Border radius: 8px for cards, 20px for pill buttons
- Icons: Lucide (thin, 20px, #6B7280)
- No glassmorphism, no gradients, no dark mode
- Ultra clean, minimal, professional

LAYOUT:
- LEFT SIDEBAR (collapsible, 220px expanded / 56px collapsed):
  - White background, right border #E5E7EB
  - Logo: VIE. MANLY brand mark at top center of sidebar
    "VIE." in elegant serif font, olive/sage green #7B7F5A, with distinctive
    V hairline stroke, bold I, bold E, period dot. 
    "MANLY" below in smaller, wide letter-spaced text, same olive green.
    Logo image file: /assets/vie-logo.png (160px wide, centered, 24px top pad)
    When sidebar collapsed: show just "V." mark (40px wide)
  - Nav items: icon + label, 14px, #6B7280
  - Active: left 3px #006AFF border, #006AFF text, #F0F7FF background
  - Sections: Overview, Sales, Members, Inventory, Staff, SMS Campaigns, Settings
  - Bottom: collapse toggle chevron

- TOP CONTROLS (Square-style pill selectors):
  - "Date" pill: shows selected date/period, opens dropdown with:
    Today, Yesterday, This week, Last week, This month, Last month,
    This year, Last year, Custom (with calendar picker)
  - "vs." pill: shows comparison, opens dropdown with:
    Prior day (shows actual date), Prior [same weekday] (shows date),
    4 weeks prior (shows date), 52 weeks prior (shows date), Prior year (shows date)
  - Both pills: white bg, 1px #E5E7EB border, rounded-full, 13px text,
    bold value portion, click to show clean dropdown with list items

CHART RULES:
- Hourly data: Vertical bars — blue #006AFF current, #B3D6FF comparison
- Daily data: Smooth line charts — blue #006AFF primary, #D1D5DB secondary
- Bars: 6px border-radius on top corners
- Grid lines: #F3F4F6 horizontal only
- Axis text: #9CA3AF, 12px
- Tooltips: White card with subtle shadow, 13px
- 7-day smoothing toggle available
- Skip days with zero sales (non-working days)
- Compare selected day vs average of last 4 same weekdays

RESPONSIVE / MOBILE:
- All pages are vertically scrollable
- Tables: horizontally scrollable on mobile (swipe gesture), sticky first column
- Sidebar: collapsed to bottom tab bar on mobile (<768px)
- KPI cards: stack 2×2 on tablet, 1 column on phone
- Charts: full-width, maintain aspect ratio, touch-friendly tooltips
- Font sizes scale down proportionally on small screens

=== PAGE 1: OVERVIEW (Performance) ===
The Overview page has TWO independent sections, each with its own time controls:

--- SECTION 1: Performance (top) ---
Own pills: "Date 1 Mar" | "vs. Prior day" | "Bills Closed"
- Hourly bar chart (blue current + light blue comparison)
- KPI grid below (2 columns, 3 rows):
  Net Sales / Transactions / Gross Sales / Average Sale /
  Actual Sales Profit / Labour Cost vs Sales Profit %
- "Actual Sales Profit" = Net Sales minus cost of goods sold
- "Labour Cost vs Sales Profit %" = labour cost / actual profit × 100
- Each KPI: muted teal label, large black value, change pill badge

--- SECTION 2: Category Breakdown (bottom, separated by thin divider) ---
Own pills: "Period This month ▼" | "vs. Prior month"
Series selector tabs: "Bar" | "Retail" | "Bar vs Retail" (tab with underline)
- Full-width smooth line chart spanning entire content width
  When "Bar" selected: single blue line for Bar category revenue
  When "Retail" selected: single blue line for Retail category revenue
  When "Bar vs Retail" selected: two lines (blue solid Bar, lighter dashed Retail)
- 4 KPI cards in a row below the chart:
  "Bar Net Sales" / "Retail Net Sales" / "Bar Sales Profit %" / "Retail Sales Profit %"
- Alert strip at bottom: low stock warnings, member birthdays, anomalies

=== PAGE 2: SALES ===
- Revenue by category (stacked area, blue shades per category)
- Top selling items table with sparklines
- Average transaction value trend line
- Sales heatmap (day of week × hour, blue gradient intensity)
- Profit tracking: Net Sales - (items sold × unit cost from catalog)
- Discount analysis: total comps & discounts vs revenue
- Period comparison: same layout as Square's overlay (bold bars vs faded bars)

=== PAGE 3: MEMBERS ===
KPIs: Active Members (775), Revenue Share (58%), Avg LTV ($210), Churn Risk (12)

Charts using member_daily_stats data:
- Member vs Non-Member Revenue (dual line, blue vs gray)
- Three ratio sparklines: Transaction 45%, Sales 58%, Items 54%
  (from daily_store_stats: member_tx_ratio, member_sales_ratio, member_items_ratio)
- Visit Frequency Trend (visit_frequency_30d over time per member)
- Spend Trend (spend_trend_30d — are members spending more or less?)
- Days Since Last Visit distribution (histogram, color-coded: 
  green <7d, yellow 7-14d, orange 14-30d, red >30d)
- Member Growth: new members per week
- Top Members leaderboard table: Name, Total Spent, Visits, Last Visit, 
  Avg Spend/Visit, 30d Trend sparkline, Status badge (Active/At Risk/Churned)
- Birthday calendar strip (upcoming 7 days)
- "Send SMS" action button next to at-risk members (links to Campaigns)

=== PAGE 4: INVENTORY ===
KPIs: Stock Value, Retail Value, Avg Profit Margin %, Low Stock Count

Main table — ALL columns sortable (click header toggles ▲▼):
Columns: Product Name | Category | Qty | Unit Cost | Price | 
  Actual Profit % | Potential Profit % | Popularity Rank | 
  Actual Profit Rank | Days Left | Status

Hover tooltips (ⓘ icon next to column header, shows on hover):
- "Actual Profit %" ⓘ → "(price - cost - avg discount applied) / price × 100
  Actual margin after all discounts are applied"
  Color thresholds defined in Settings (defaults: green >40%, orange 20-40%, red <20%)
- "Potential Profit %" ⓘ → "(price - cost) / price × 100
  Maximum possible margin if sold at full price with no discounts"
  Color thresholds defined in Settings
- "Popularity Rank" ⓘ → "Ranked by total units sold over selected period.
  #1 = most popular item"
  Top N highlight count defined in Settings (default: top 3 in blue bold)
- "Actual Profit Rank" ⓘ → "Ranked by actual profit dollars per unit sold.
  #1 = highest real profit per unit"
  Top N highlight count defined in Settings
- "Days Left" ⓘ → "Current quantity / average daily sales.
  Estimates how many days until stock runs out"
- "Status" ⓘ → "Stock health: Low / Warning / OK.
  Thresholds configurable in Settings per category"
  SORTABLE — sorts by severity: Low → Warning → OK

All color bands, thresholds, and ranking highlights are user-configurable
in Settings → Inventory Thresholds.

Side panel:
- Low stock alerts: items below threshold (user-configurable per category)
- Reorder suggestions: auto-calculated from 4-week sales velocity
  Suggested qty = (avg daily sales × lead time days × 1.5 safety factor)
- "Create Purchase Order" button to export reorder list

--- Bottom Section: Category Insights (full-width, below table) ---
Chart 1 (left half): "Stock Available vs Sold (30 days)"
  Grouped horizontal bar chart, one row per category:
  Dark blue bar = available stock units, Lighter blue = sold in last 30 days
  Categories: Bar, Food, Drinks, Retail
  Instantly shows which categories are turning fast vs sitting

Chart 2 (right half): "Sales Velocity by Category"
  Line chart, 30-day trend, units/day on Y-axis
  One line per category with velocity label: "Food ▲ 23/day", 
  "Drinks → 11/day", "Bar ▲ 14/day", "Retail → 3/day"
  Arrows indicate acceleration (▲), steady (→), or slowing (▼)

4 mini KPI cards below charts:
  "Fastest Moving" → product name + units/day (blue)
  "Slowest Moving" → product name + units/day (red)
  "Best Margin" → product name + actual profit % (green)
  "Restock Urgent" → product name + days left (red)

=== PAGE 5: STAFF ===
KPIs: Staff Today, Total Hours, Labor Cost Ratio (target 25-35%), 
      Revenue per Labor Hour

Charts:
1. Labor Cost vs Revenue (dual axis: blue bars revenue, red line labor cost %)
   Target band shaded at 25-35% in light green
2. Peak Hour Staffing (overlay: gray bars = staff count, blue line = transactions)
   ANNOTATED GAPS: Where staff bars >> transaction line, highlight with 
   light red/pink tint + label "Overstaffed gap" with arrow.
   Where transaction line >> staff bars, highlight with light orange tint + 
   label "Understaffed gap" with arrow. These annotations help identify 
   scheduling inefficiencies at a glance.
3. Staff Coverage Timeline (Gantt: who worked when, horizontal bars per day)
   DISTINCT COLOR PER STAFF MEMBER:
   - Holly: blue #006AFF
   - Camilla: red #DC2626
   - Noah: green #059669
   - Sarah: amber #D97706
   Each person gets their own color for all shift blocks across the week.
   Color legend at bottom of chart.
4. Transactions per Staff (line, 7-day smoothed, trending up = good)
5. Weekend vs Weekday Efficiency (grouped bars comparing ratios)
6. Individual Staff Hours Table: Name, Hours This Week, Shifts, 
   Avg Hours/Shift, Tips

=== PAGE 6: SMS CAMPAIGNS ===
Campaign Builder (left panel):
- Campaign name input
- SMS text editor with merge tags: {first_name}, {last_name}, {points},
  {total_spent}, {days_since_visit}, {favorite_item}
- Character counter: "148/160" (160 = 1 SMS segment)
- Phone preview mockup showing formatted message
- Schedule: "Send now" / "Schedule" with date-time picker
- Blue "Send Campaign" button

Auto-Enrollment Rules Engine (right panel):
- Match logic: "ALL conditions" / "ANY condition" dropdown
- Rule sliders (clean, Square-style with blue track):
  - Total Items Purchased: dual-thumb slider [min—max]
  - Total Net Sales ($): dual-thumb slider [$min—$max]
  - Days Since Last Visit: single slider [threshold]
  - Visit Frequency (30d): dual-thumb slider [min—max]
  - Loyalty Points: dual-thumb slider [min—max]
- Live counter: "47 members match" in blue bold
- Expandable member preview list

Campaign Analytics (bottom):
- Sent / Delivered / Failed KPI cards
- Before/After comparison: avg member spend 7/14/30 days after SMS
- Revenue Impact: total incremental revenue attributed to campaign
- Per-member tracking rows: name, pre-spend, post-spend, visits delta

Campaign History table: Name, Date, Recipients, Delivered %, 
  Revenue Impact, Status badge (Completed/Scheduled/Draft)
  Click to view detailed analytics

SMS API: mobilemessage.com.au
  POST https://api.mobilemessage.com.au/v1/messages
  Auth: Basic (base64 username:password)
  Body: { "to": "+61...", "from": "VieMarket", "message": "..." }

=== PAGE 7: SETTINGS ===
Organized into collapsible sections:

--- General ---
- Store name, timezone (Australia/Sydney)
- Data sync schedule (cron frequency for Square API sync)
- Default date range (Today/This week/This month)

--- Inventory Thresholds ---
- Profit % color bands (per category or global):
  Green threshold: default >40% (editable number input)
  Orange threshold: default 20-40%
  Red threshold: default <20%
- Stock status thresholds (per category):
  "Low" when qty below: [input] (default: 5)
  "Warning" when qty below: [input] (default: 15)
- Top rank highlight count: [input] (default: 3, shown in blue bold)
- Reorder safety factor: [slider 1.0—2.0] (default: 1.5)
- Lead time days per category: [input per category]

--- Member Criteria ---
- Churn risk thresholds (days since last visit):
  Green: < [7] days | Yellow: < [14] days | Orange: < [30] days | Red: > [30] days
  All values editable
- "At Risk" status after: [input] days without visit (default: 14)
- "Churned" status after: [input] days without visit (default: 45)

--- Staff ---
- Hourly rates per team member (table of name + rate input)
- Labor cost ratio target band: min [25%] — max [35%] (editable)
- Overstaffed highlight: when staff/transaction ratio > [input]

--- SMS Campaigns ---
- mobilemessage.com.au API credentials (username/password, masked)
- Default sender ID: [input] (e.g. "VieMarket")
- SMS segment limit: [160] characters

--- Chart Appearance ---
- Primary color: [color picker] (default: #006AFF)
- Comparison color: [color picker] (default: #B3D6FF)
- Positive change badge: [color picker] (default: #059669 green)
- Negative change badge: [color picker] (default: #DC2626 red)

--- Notifications ---
- Low stock alerts: on/off toggle
- Churn risk alerts: on/off toggle
- Sales anomaly alerts: on/off toggle + threshold %
- Birthday reminders: on/off toggle + days ahead [input]

--- Export ---
- Export data: CSV / PDF report buttons
- Purchase order export format: CSV / PDF
```

---

## Implementation Plan

### Tech Stack
| Tool | Purpose |
|------|---------|
| **Next.js 15** (App Router) | React framework |
| **Tailwind CSS v4** | Styling (configured to match Square's design tokens) |
| **Recharts** | Charts (bar, line, area) |
| **Lucide React** | Icons |
| **Framer Motion** | Subtle animations (number counters, transitions) |
| **Supabase JS** | Direct database queries |
| **Vercel** | Hosting (free tier) |

### Phase 1: Foundation (Days 1-2)
- [ ] Next.js project + Tailwind configured with Square design tokens
- [ ] Sidebar layout + routing
- [ ] Date picker + "vs." comparison picker components
- [ ] Supabase client connection

### Phase 2: Overview + Sales (Days 3-5)
- [ ] KPI cards component
- [ ] Hourly bar chart with comparison overlay
- [ ] Sales by category, top items
- [ ] 7-day smoothing + same-day comparison logic

### Phase 3: Members (Days 6-7)
- [ ] Member/non-member ratio charts
- [ ] Top members table with sparklines
- [ ] Churn early warning
- [ ] Birthday calendar

### Phase 4: Inventory + Staff (Days 8-9)
- [ ] Stock table with status badges + days remaining
- [ ] Reorder suggestions engine
- [ ] Staff KPIs + labor charts
- [ ] Shift timeline (Gantt)

### Phase 5: SMS Campaigns (Days 10-12)
- [ ] Campaign builder UI + message editor
- [ ] Rules engine with range sliders
- [ ] mobilemessage.com.au API integration
- [ ] Campaign analytics + ROI tracking

### Phase 6: Polish (Days 13-14)
- [ ] Mobile responsive
- [ ] Animations
- [ ] Settings page
- [ ] Deploy to Vercel
