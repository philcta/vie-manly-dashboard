# VIE. MANLY Dashboard — v15 Design System

> **Version**: 15.0 — Modern Premium Dashboard  
> **Date**: 5 March 2026  
> **Stack**: Next.js 15 + Tailwind CSS v4 + shadcn/ui + Recharts + Framer Motion  
> **Mockup files**: `.artifacts/mockups_backup/v15_*.png`

---

## 1. Design Philosophy

Moving away from the rigid Square-style design system toward a **warm, sophisticated, brand-aligned** aesthetic that feels premium without being flashy. The design should breathe — generous whitespace, subtle shadows, and olive/sage tones reflecting the VIE. MANLY brand identity.

**Core principles:**
- **Warm neutrals** — no cold grays or stark whites
- **Brand olive** as the primary accent, not generic blues
- **Subtle depth** — soft shadows, not borders
- **Breathing room** — generous padding, no cramping
- **Quiet animations** — numbers count up, cards lift on hover, charts animate in

---

## 2. Color Palette

### Primary

| Token | Hex | Usage |
|-------|-----|-------|
| `--olive` | `#6B7355` | Primary brand accent, active states, chart primary |
| `--olive-light` | `#A8B094` | Comparison charts, secondary data, hover states |
| `--olive-dark` | `#4A5139` | Text emphasis, dark accents |
| `--olive-surface` | `#F0F1EC` | Subtle olive tint backgrounds, hover |

### Secondary

| Token | Hex | Usage |
|-------|-----|-------|
| `--coral` | `#E07A5F` | Negative changes, warnings, Retail side accent |
| `--coral-light` | `#F4B8A8` | Coral surface, light badges |
| `--coral-dark` | `#C45D42` | Error states, urgent actions |

### Semantic

| Token | Hex | Usage |
|-------|-----|-------|
| `--positive` | `#2D936C` | Positive change badges (white text) |
| `--negative` | `#E07A5F` | Negative change badges (white text) |
| `--warning` | `#D4A843` | Warning status (amber) |
| `--ok` | `#6B7355` | OK/healthy status |

### Neutrals

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg` | `#F8F8F6` | Page background (warm gray) |
| `--card` | `#FFFFFF` | Card backgrounds |
| `--text-primary` | `#1A1A1A` | Headings, KPI values |
| `--text-secondary` | `#5A5A5A` | Body text, descriptions |
| `--text-muted` | `#8A8A8A` | Labels, captions |
| `--border` | `#EAEAE8` | Subtle borders when needed |
| `--sidebar` | `#1E1E2E` | Sidebar background (deep charcoal) |
| `--sidebar-text` | `#B8B8C8` | Sidebar inactive text |

---

## 3. Typography

**Font family:** `Inter` (Google Fonts) — clean, modern, excellent at small sizes

| Element | Size | Weight | Color | Extra |
|---------|------|--------|-------|-------|
| Page title | 28px / 1.75rem | 700 | `--text-primary` | — |
| Section title | 18px / 1.125rem | 600 | `--text-primary` | — |
| KPI value | 32px / 2rem | 700 | `--text-primary` | Tabular nums |
| KPI label | 12px / 0.75rem | 500 | `--text-muted` | Uppercase tracking |
| Table header | 13px / 0.8125rem | 600 | `--text-secondary` | Uppercase tracking |
| Table body | 14px / 0.875rem | 400 | `--text-primary` | — |
| Body text | 14px / 0.875rem | 400 | `--text-secondary` | — |
| Caption | 12px / 0.75rem | 400 | `--text-muted` | — |
| Badge | 12px / 0.75rem | 600 | white | Inside colored pill |
| Nav item | 14px / 0.875rem | 500 | `--sidebar-text` | Active: `--olive` |

---

## 4. Spacing & Layout

### Grid

- **Page width**: 1440px max, centered
- **Sidebar**: 220px fixed width
- **Main content**: `calc(100% - 220px)`, padding: 32px
- **Card gap**: 20px (between cards)
- **Section gap**: 32px (between sections)
- **Card padding**: 24px

### Card Grid Patterns

| Pattern | Usage |
|---------|-------|
| 4 equal columns | KPI cards row (Overview top, Members, Staff) |
| 3 equal columns | Overview KPI rows (2 rows × 3 cols) |
| 2 equal columns | Side-by-side charts |
| Full width | Tables, Gantt timeline |

### Breakpoints (responsive)

| Breakpoint | Width | Sidebar | Grid |
|------------|-------|---------|------|
| Desktop | ≥1280px | Fixed 220px | Full grid |
| Tablet | 768-1279px | Collapsed (icons only, 64px) | 2-col reduce |
| Mobile | <768px | Hidden (hamburger menu) | Single column |

---

## 5. Components

### Sidebar

```
Background: --sidebar (#1E1E2E)
Width: 220px
Logo: VIE. MANLY olive serif, centered, 24px top padding
Nav items: 14px Inter 500, --sidebar-text color
Active item: 
  - Left 3px solid border --olive
  - Text color --olive
  - Background rgba(107, 115, 85, 0.08)
Icons: Lucide React, 18px, inline with text
Hover: text color lightens to white, 200ms transition
```

### KPI Card

```
Background: --card
Border-radius: 12px
Box-shadow: 0 2px 8px rgba(0,0,0,0.04)
Padding: 24px
Hover: transform translateY(-2px), shadow deepens to 0 4px 16px rgba(0,0,0,0.08)
Transition: all 200ms ease

Contents:
  Label: 12px 500 --text-muted, uppercase
  Value: 32px 700 --text-primary, tabular-nums
  Change badge: 12px 600, pill shape (border-radius 100px)
    Positive: bg --positive, text white, "▲ 2.24%"
    Negative: bg --negative, text white, "▼ 18.25%"
  Sub-info: 12px 400 --text-muted
```

### Chart Card

```
Background: --card
Border-radius: 12px
Box-shadow: 0 2px 8px rgba(0,0,0,0.04)
Padding: 24px (top 20px for title area)

Title: 16px 600 --text-primary
Subtitle/legend: 12px --text-muted

Chart colors:
  Primary series: --olive with 20% opacity gradient fill below line
  Comparison series: --olive-light, dashed for line charts
  Retail/secondary: --coral
  Grid lines: #F0F0EE, 1px
  Axis text: 11px --text-muted
  Tooltip: white bg, 8px radius, subtle shadow, 13px text
```

### Data Table

```
Background: --card
Border-radius: 12px
Box-shadow: 0 2px 8px rgba(0,0,0,0.04)
Padding: 0 (full bleed within card)

Header row: 
  Background: #FAFAF8
  Text: 13px 600 uppercase --text-secondary
  Sort arrows: ↕ inline, --text-muted
  Padding: 12px 16px

Body rows:
  Text: 14px 400 --text-primary
  Padding: 12px 16px
  Border-bottom: 1px solid #F0F0EE
  Hover: background #F8F8F4 (very subtle warm tint)

Status badges:
  Active: bg --positive, text white, pill
  Inactive: bg #D4D4D4, text white, pill
  Warning: bg --warning, text white, pill
  Low: bg --coral, text white, pill
  OK: bg --olive, text white, pill
```

### Pill Selector / Toggle

```
Inactive pill:
  Background: transparent
  Border: 1px solid --border
  Text: 14px 500 --text-secondary
  Padding: 6px 14px
  Border-radius: 100px

Active pill:
  Background: --olive
  Border: 1px solid --olive
  Text: 14px 500 white
  
Hover (inactive): background --olive-surface

Group: gap 8px between pills
```

### Form Inputs (Settings page)

```
Input field:
  Background: white
  Border: 1px solid --border
  Border-radius: 8px
  Padding: 8px 12px
  Font: 14px Inter
  Focus: border-color --olive, box-shadow 0 0 0 3px rgba(107,115,85,0.12)

Dropdown: same as input + chevron icon right
Slider: track --border, filled --olive, thumb 20px olive circle with white center
```

### Buttons

```
Primary:
  Background: --olive
  Text: 14px 600 white
  Padding: 10px 20px
  Border-radius: 8px
  Hover: background --olive-dark, translateY(-1px)
  Active: translateY(0)

Ghost/Secondary:
  Background: transparent
  Border: 1px solid --border
  Text: 14px 500 --text-secondary
  Hover: background #F5F5F3

Danger:
  Background: --coral
  Text: white
```

---

## 6. Animations (Framer Motion)

**Philosophy**: Subtle, purposeful. Never distracting. The dashboard should feel alive but calm.

### Number Count-Up

```jsx
// KPI values animate on mount/data change
<AnimatedNumber value={2922.48} duration={0.8} />
// Uses spring animation with damping: 20, stiffness: 100
// Digits appear to increment rapidly then settle
```

### Card Hover

```jsx
// Gentle lift effect
whileHover={{ y: -2 }}
transition={{ duration: 0.2, ease: "easeOut" }}
// Shadow deepens from 0.04 to 0.08 opacity
```

### Chart Entry

```jsx
// Bars grow upward from baseline
initial={{ scaleY: 0, originY: 1 }}
animate={{ scaleY: 1 }}
transition={{ delay: index * 0.05, duration: 0.4, ease: "easeOut" }}

// Lines draw from left
pathLength: 0 → 1, duration: 1.2s easeInOut
// Area fill fades in after line finishes
opacity: 0 → 1, delay: 1.0s, duration: 0.4
```

### Page Transitions

```jsx
// Content fades + slides up slightly
initial={{ opacity: 0, y: 12 }}
animate={{ opacity: 1, y: 0 }}
transition={{ duration: 0.3 }}
```

### Table Row Hover

```jsx
// Very subtle background color shift
// No motion — just color transition 150ms
```

### Tooltip Appear

```jsx
// Scale up from 0.95 + fade
initial={{ opacity: 0, scale: 0.95 }}
animate={{ opacity: 1, scale: 1 }}
transition={{ duration: 0.15 }}
```

### Sidebar Active Indicator

```jsx
// Left border slides to new position via layoutId
<motion.div layoutId="activeNav" />
// Spring transition, 300ms
```

---

## 7. Page Specifications

### 7.1 Overview

| Section | Component | Data Source |
|---------|-----------|-------------|
| Date controls | Pill selector + dropdown | Local state |
| Hourly chart | Grouped bar chart (Recharts) | `daily_store_stats` |
| 6 KPI cards | 2 rows × 3 cols | `daily_store_stats` |
| Cafe vs Retail chart | Dual-line chart with toggle tabs | `daily_item_summary` |
| 6 comparison KPIs | 2 rows × 3 cols | `daily_item_summary` |

### 7.2 Members

| Section | Component | Data Source |
|---------|-----------|-------------|
| 4 KPI cards | Active, Revenue %, ALV, Points | `member_daily_stats` |
| Revenue chart | Dual-line (member vs non-member) | `member_daily_stats` |
| 3 Ratio cards | Transaction/Sales/Items ratios | `member_daily_stats` |
| Top Members table | Sortable, sparklines, badges | `members` + `transactions` |
| Loyalty Insights | 3 stat cards + donut | `members` |

### 7.3 Staff

| Section | Component | Data Source |
|---------|-----------|-------------|
| 4 KPI cards | Staff/Hours/LCR/Rev per Hour | `staff_shifts` + `daily_store_stats` |
| Labour vs Revenue | Dual-axis grouped bar + line | `staff_shifts` + `daily_store_stats` |
| Peak Hour Staffing | Stacked area + line overlay | `staff_shifts` + hourly transactions |
| Cafe vs Retail Hours | Donut chart | `staff_shifts` |
| Weekly Hours | Stacked bar | `staff_shifts` |
| Staff Coverage | Gantt timeline (custom) | `staff_shifts` |
| Staff Rates | Editable table | `staff_rates` |

### 7.4 SMS Campaigns

| Section | Component | Data Source |
|---------|-----------|-------------|
| 4 KPI cards | Campaigns/Reached/Rate/Revenue | `sms_campaigns` |
| Campaign Performance | Data table with status badges | `sms_campaigns` |
| Impact Timeline | Multi-line chart | `sms_campaign_results` |
| Contact Frequency | Horizontal bar chart | `sms_enrollments` |
| Create Campaign | Form with auto-enrollment rules | Write to `sms_campaigns` |
| Recent Enrollments | Data table with status | `sms_enrollments` |

### 7.5 Inventory

| Section | Component | Data Source |
|---------|-----------|-------------|
| 4 KPI cards | Stock/Retail Value/Margin/Low | `inventory_items` |
| Stock Levels table | Sortable, color-coded status | `inventory_items` |
| Stock vs Sold chart | Horizontal grouped bar | `inventory_items` + `daily_item_summary` |
| Sales Velocity | Multi-line chart | `daily_item_summary` |
| 4 insight cards | Fastest/Slowest/Best Margin/Restock | `inventory_items` |

### 7.6 Settings

| Section | Component | Data Source |
|---------|-----------|-------------|
| General | Form inputs, dropdowns, pill toggle | `app_settings` |
| Inventory Thresholds | Inputs, color dots, slider | `app_settings` |
| Member Criteria | Inputs with color indicators | `app_settings` |
| Staff / SMS | Collapsed accordions | `app_settings` |
| Chart Appearance | Color pickers | `app_settings` |
| Notifications | Collapsed accordion | `app_settings` |

---

## 8. Mockup File Index

| Page | File | Status |
|------|------|--------|
| Overview | `v15_overview.png` | ✅ Complete |
| Members | `v15_members.png` | ✅ Complete |
| Staff | `v15_staff.png` | ✅ Complete |
| SMS Campaigns | `v15_sms_campaigns.png` | ✅ Complete |
| Inventory | `v15_inventory.png` | ✅ Complete |
| Settings | `v15_settings.png` | ✅ Complete |

---

## 9. Implementation Notes

### Folder Structure (Next.js App Router)

```
app/
├── layout.tsx          # Root layout with sidebar
├── page.tsx            # Overview (default)
├── members/
│   └── page.tsx
├── inventory/
│   └── page.tsx
├── staff/
│   └── page.tsx
├── campaigns/
│   └── page.tsx
├── settings/
│   └── page.tsx
├── globals.css         # Tailwind + custom tokens
components/
├── sidebar.tsx         # Dark sidebar nav
├── kpi-card.tsx        # Reusable KPI metric card
├── chart-card.tsx      # Wrapper for chart sections
├── data-table.tsx      # Sortable table component
├── pill-selector.tsx   # Toggle pill buttons
├── date-picker.tsx     # Date range selector
├── animated-number.tsx # Count-up animation
├── status-badge.tsx    # Active/Warning/Low/OK badges
├── change-badge.tsx    # ▲/▼ percentage pill
lib/
├── supabase.ts         # Supabase client config
├── queries/            # Server-side data fetching
│   ├── overview.ts
│   ├── members.ts
│   ├── staff.ts
│   ├── inventory.ts
│   └── campaigns.ts
```

### Key Dependencies

```json
{
  "next": "^15.0",
  "react": "^19.0",
  "tailwindcss": "^4.0",
  "@supabase/supabase-js": "^2.x",
  "recharts": "^2.x",
  "framer-motion": "^11.x",
  "lucide-react": "^0.4",
  "@radix-ui/react-*": "latest"
}
```

### shadcn/ui Components to Install

```bash
npx shadcn@latest add card table button input select dropdown-menu
npx shadcn@latest add tabs separator badge avatar
npx shadcn@latest add tooltip popover dialog sheet
npx shadcn@latest add chart   # Recharts wrapper
```
