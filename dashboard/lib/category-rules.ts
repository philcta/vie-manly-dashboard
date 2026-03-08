/**
 * Category classification rules.
 * Ported from services/category_rules.py — is_bar_category()
 *
 * If a category is a "bar category" → Cafe (displayed as "Cafe" on dashboard)
 * Everything else → Retail
 */

const BAR_CATEGORIES = new Set([
    "Cafe Drinks",
    "Cafe Drinks ", // trailing space variant in DB
    "Smoothie Bar",
    "Soups",
    "Sweet Treats",
    "Wraps & Salads",
    "Breakfast Bowls",
    "Chia Bowls",
    // Historical CSV categories (pre-Aug 2025)
    "Breakfast - Savoury",
    "Breakfast - Sweet",
    "Breakfast Menu",
    "Kids Menu",
    "Lunch",
    "Lunch Menu",
    "Sweet Treat Menu",
    "Catering",
]);

export function isBarCategory(cat: string): boolean {
    if (!cat) return false;
    // Check explicit set
    if (BAR_CATEGORIES.has(cat)) return true;
    // Check MTO pattern (Made To Order menus)
    if (cat.toUpperCase().includes("MTO")) return true;
    return false;
}

/**
 * Classify a category string as "Cafe" or "Retail"
 * This is the single source of truth for all charts and KPIs.
 */
export function classifySide(cat: string): "Cafe" | "Retail" {
    return isBarCategory(cat) ? "Cafe" : "Retail";
}
