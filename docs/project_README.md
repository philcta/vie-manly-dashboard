�# Design Assets — Stitch → Code Workflow

This folder holds all design exports from **Stitch**. The agent reads these to build
UI components in `packages/ui/`.

## Folder Structure

```
design/
├── tokens/         ← Design tokens (colors, spacing, typography, shadows)
│   ├── colors.json
│   ├── typography.json
│   └── spacing.json
├── screens/        ← Full screen mockups (PNG or PDF)
│   ├── auth/
│   ├── deals/
│   ├── admin/
│   └── ...
├── components/     ← Individual component specs / screenshots
│   ├── button.png
│   ├── deal-card.png
│   ├── filter-chips.png
│   └── ...
└── assets/         ← Production assets
    ├── icons/      ← SVG icons (export from Stitch as SVG)
    ├── images/     ← Placeholder images, logos
    └── fonts/      ← Custom fonts (if any)
```

## How to Export from Stitch

### Step 1: Design Tokens
1. In Stitch, go to your project's **Style Guide** / **Design System**
2. Export tokens as **JSON** or **CSS variables**
3. Save to `design/tokens/`

Key tokens to export:
- **Colors**: primary, secondary, accent, neutral palette, error/success/warning
- **Typography**: font families, sizes, weights, line-heights
- **Spacing**: scale (4, 8, 12, 16, 24, 32, 48, 64...)
- **Radius**: border radius values
- **Shadows**: elevation levels

### Step 2: Component Specs
1. Select each component in Stitch
2. Export as **PNG** (for visual reference) at 2x resolution
3. Note the component's: padding, font size, border, colors
4. Save to `design/components/`

Key components to export:
- Buttons (primary, secondary, ghost, disabled states)
- Cards (deal card, stat card)
- Chips / Tags (strategy tags, status badges)
- Input fields (text, search, dropdown)
- Image gallery / carousel
- Badges ("New", "Published", "Draft")
- Navigation (tab bar, header)

### Step 3: Screen Mockups
1. Export each screen as **PNG** or **PDF**
2. Organize by feature area
3. Save to `design/screens/`

Screens to cover:
- **Auth**: Login, Register, Forgot Password
- **Deals**: List/Feed, Filters, Deal Detail
- **Favourites**: Saved deals list
- **Enquiry**: Enquiry form, confirmation
- **Admin**: Login, Deal CRUD, Media manager, Enquiries list

### Step 4: Icons & Assets
1. Export icons as **SVG** files (not PNG)
2. Use consistent sizing (24x24 default)
3. Save to `design/assets/icons/`

## How the Agent Uses These

When building components, the agent will:
1. Read token files from `design/tokens/` to set up the design system
2. Reference component PNGs from `design/components/` for visual accuracy
3. Match screen layouts from `design/screens/`
4. Import SVG icons from `design/assets/icons/`

The output goes to `packages/ui/` as React / React Native components.

## Naming Conventions

- Token files: `kebab-case.json`
- Screen exports: `feature-name--screen-name.png` (e.g., `deals--list.png`)
- Component exports: `component-name.png` (e.g., `deal-card.png`)
- Icons: `icon-name.svg` (e.g., `heart.svg`, `filter.svg`, `arrow-right.svg`)
�*cascade082,file:///f:/phil/antigravity/design/README.md