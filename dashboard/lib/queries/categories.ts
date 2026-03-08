/**
 * Category classification queries.
 * Manages the category_mappings table that determines Cafe vs Retail.
 */
import { supabase } from "@/lib/supabase";

export interface CategoryMapping {
    category: string;
    side: "Cafe" | "Retail";
    first_seen: string | null;
    assigned_at: string | null;
}

/** Fetch all category mappings, ordered by side then name */
export async function fetchCategoryMappings(): Promise<CategoryMapping[]> {
    const { data, error } = await supabase
        .from("category_mappings")
        .select("*")
        .order("side", { ascending: true })
        .order("category", { ascending: true });

    if (error) throw error;
    return data || [];
}

/** Fetch only unassigned categories (assigned_at is null) */
export async function fetchUnassignedCategories(): Promise<CategoryMapping[]> {
    const { data, error } = await supabase
        .from("category_mappings")
        .select("*")
        .is("assigned_at", null)
        .order("category", { ascending: true });

    if (error) throw error;
    return data || [];
}

/** Update the side (Cafe/Retail) for a single category */
export async function updateCategorySide(
    category: string,
    side: "Cafe" | "Retail"
): Promise<void> {
    const { error } = await supabase
        .from("category_mappings")
        .update({ side, assigned_at: new Date().toISOString() })
        .eq("category", category);

    if (error) throw error;
}

/** Get count of unassigned categories (for notification badge) */
export async function getUnassignedCount(): Promise<number> {
    const { count, error } = await supabase
        .from("category_mappings")
        .select("*", { count: "exact", head: true })
        .is("assigned_at", null);

    if (error) throw error;
    return count || 0;
}
