"""
Staff management view — display staff members with rates and provide editing.

When a rate is edited:
1. Saves the new weekday rate to Supabase staff_rates
2. Auto-calculates Sat/Sun/PH rates using the tier multiplier table
3. Recalculates labor cost for ALL existing shifts for that person
"""
import streamlit as st
import pandas as pd
from datetime import date

# Rate multiplier tiers (based on weekday rate)
# If weekday rate matches a tier, use that tier's multipliers
# Otherwise, use the standard $32 tier multipliers
RATE_TIERS = [
    {"weekday": 33.19, "saturday": 39.83, "sunday": 46.46, "public_holiday": 66.38},
    {"weekday": 32.00, "saturday": 38.00, "sunday": 44.00, "public_holiday": 63.00},
    {"weekday": 25.80, "saturday": 30.96, "sunday": 36.12, "public_holiday": 51.60},
    {"weekday": 18.71, "saturday": 22.46, "sunday": 30.00, "public_holiday": 37.42},
    {"weekday": 15.18, "saturday": 18.21, "sunday": 21.25, "public_holiday": 30.36},
    {"weekday": 14.94, "saturday": 17.93, "sunday": 20.91, "public_holiday": 29.88},
]

# Standard multipliers relative to weekday (used when no tier matches)
STD_MULTIPLIERS = {
    "saturday": 38.00 / 32.00,    # 1.1875
    "sunday": 44.00 / 32.00,      # 1.375
    "public_holiday": 63.00 / 32.00,  # 1.96875
}


def _find_tier_rates(weekday_rate):
    """Given a weekday rate, return the full tier rates (sat/sun/ph).
    If rate matches a known tier, use that tier. Otherwise compute using standard multipliers."""
    for tier in RATE_TIERS:
        if abs(tier["weekday"] - weekday_rate) < 0.01:
            return tier
    # No matching tier — compute using standard multipliers
    return {
        "weekday": weekday_rate,
        "saturday": round(weekday_rate * STD_MULTIPLIERS["saturday"], 2),
        "sunday": round(weekday_rate * STD_MULTIPLIERS["sunday"], 2),
        "public_holiday": round(weekday_rate * STD_MULTIPLIERS["public_holiday"], 2),
    }


def _save_rates(client, team_member_id, staff_name, job_title, weekday_rate, flat_rate=False):
    """Save rates to staff_rates table. If flat_rate=True, use same rate for all periods."""
    if flat_rate:
        tier = {
            "weekday": weekday_rate,
            "saturday": weekday_rate,
            "sunday": weekday_rate,
            "public_holiday": weekday_rate,
        }
    else:
        tier = _find_tier_rates(weekday_rate)

    rows = []
    for day_type in ["weekday", "saturday", "sunday", "public_holiday"]:
        rows.append({
            "team_member_id": team_member_id,
            "staff_name": staff_name,
            "job_title": job_title,
            "day_type": day_type,
            "hourly_rate": tier[day_type],
        })

    client.table("staff_rates").upsert(
        rows, on_conflict="team_member_id,job_title,day_type"
    ).execute()

    return tier


def _recalculate_shifts(client, team_member_id, job_title, rates_by_day_type):
    """Recalculate hourly_rate in staff_shifts for all shifts of this person+job.
    
    This updates BOTH the rate and effectively the cost (since cost = hours × rate).
    """
    from scripts.sync_shifts import get_day_type, NSW_HOLIDAYS
    
    # Fetch all shifts for this person + job (including split variants like _Bar, _Retail)
    result = client.table("staff_shifts").select(
        "id, shift_date, job_title, hourly_rate"
    ).eq("team_member_id", team_member_id).execute()
    
    if not result.data:
        return 0
    
    updates = []
    for shift in result.data:
        shift_job = shift["job_title"]
        # Match both exact job title and split variants (e.g., "Retail Assistant_Bar")
        base_job = shift_job.replace("_Bar", "").replace("_Retail", "")
        if base_job != job_title:
            continue
            
        shift_date = date.fromisoformat(shift["shift_date"])
        day_type = get_day_type(shift_date)
        new_rate = rates_by_day_type.get(day_type, rates_by_day_type.get("weekday", 0))
        
        if abs((shift["hourly_rate"] or 0) - new_rate) > 0.001:
            updates.append({
                "id": shift["id"],
                "hourly_rate": new_rate,
            })
    
    if updates:
        # Batch update in chunks of 50
        for i in range(0, len(updates), 50):
            batch = updates[i:i+50]
            for u in batch:
                client.table("staff_shifts").update(
                    {"hourly_rate": u["hourly_rate"]}
                ).eq("id", u["id"]).execute()
    
    return len(updates)


def show_staff(client):
    """Show the Staff management section."""
    st.markdown("## 👥 Staff Management")
    st.caption("Manage staff rates. Rates are stored in Supabase and used for labor cost calculations.")
    st.caption("⚠️ Square's hourly rates are NOT used — only rates set here are applied.")
    
    # Load current rates
    result = client.table("staff_rates").select(
        "team_member_id, staff_name, job_title, day_type, hourly_rate"
    ).order("staff_name").execute()
    
    if not result.data:
        st.warning("No staff rates found. Run the shift sync to auto-detect staff.")
        return
    
    df = pd.DataFrame(result.data)
    
    # Pivot: one row per person+job, columns = day types
    pivot = df.pivot_table(
        index=["team_member_id", "staff_name", "job_title"],
        columns="day_type",
        values="hourly_rate",
        aggfunc="first"
    ).reset_index()
    
    # Reorder columns
    day_cols = ["weekday", "saturday", "sunday", "public_holiday"]
    for col in day_cols:
        if col not in pivot.columns:
            pivot[col] = 0.0
    
    # Flag rows with $0 rates
    pivot["_has_zero"] = pivot[day_cols].apply(lambda row: any(v == 0 or pd.isna(v) for v in row), axis=1)
    
    # Count missing
    zero_count = pivot["_has_zero"].sum()
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    unique_staff = pivot["staff_name"].nunique()
    total_combos = len(pivot)
    with col1:
        st.metric("Staff Members", unique_staff)
    with col2:
        st.metric("Role Assignments", total_combos)
    with col3:
        if zero_count > 0:
            st.metric("⚠️ Missing Rates", int(zero_count))
        else:
            st.metric("✅ Rate Coverage", "100%")
    
    # Alert for missing rates
    if zero_count > 0:
        st.error(f"🚨 **{int(zero_count)} staff×job entries have $0 rates.** Click Edit to set them.")
        zero_rows = pivot[pivot["_has_zero"]]
        for _, row in zero_rows.iterrows():
            st.warning(f"⚠️ **{row['staff_name']}** ({row['job_title']}) — needs rate setup")
    
    st.markdown("---")
    
    # Display staff table
    display_df = pivot[["staff_name", "job_title", "weekday", "saturday", "sunday", "public_holiday", "_has_zero"]].copy()
    display_df.columns = ["Name", "Job Title", "Weekday", "Saturday", "Sunday", "Public Holiday", "_flag"]
    
    # Format rates for display
    for col in ["Weekday", "Saturday", "Sunday", "Public Holiday"]:
        display_df[col] = display_df[col].apply(lambda x: f"${x:.2f}" if x and x > 0 else "⚠️ $0.00")
    
    # Show table without the flag/id columns
    st.dataframe(
        display_df[["Name", "Job Title", "Weekday", "Saturday", "Sunday", "Public Holiday"]],
        use_container_width=True,
        hide_index=True,
    )
    
    st.markdown("---")
    st.markdown("### ✏️ Edit Staff Rate")
    
    # Build selection options
    staff_options = []
    for _, row in pivot.iterrows():
        label = f"{row['staff_name']} — {row['job_title']}"
        if row["_has_zero"]:
            label = f"⚠️ {label} (needs setup)"
        staff_options.append(label)
    
    selected_idx = st.selectbox(
        "Select staff member to edit",
        range(len(staff_options)),
        format_func=lambda i: staff_options[i],
    )
    
    if selected_idx is not None:
        selected = pivot.iloc[selected_idx]
        mid = selected["team_member_id"]
        name = selected["staff_name"]
        job = selected["job_title"]
        current_wd = float(selected["weekday"] or 0)
        
        st.markdown(f"**Editing: {name}** ({job})")
        
        col_rate, col_flat = st.columns([3, 1])
        with col_rate:
            new_rate = st.number_input(
                "Weekday rate ($/hr)",
                min_value=0.0,
                max_value=200.0,
                value=current_wd,
                step=0.50,
                key=f"rate_{mid}_{job}",
            )
        with col_flat:
            flat_rate = st.checkbox(
                "Same rate all days",
                value=False,
                key=f"flat_{mid}_{job}",
                help="If checked, the same rate applies to weekdays, weekends and public holidays (e.g., for salaried managers)."
            )
        
        # Preview the calculated rates
        if flat_rate:
            preview = {"weekday": new_rate, "saturday": new_rate, "sunday": new_rate, "public_holiday": new_rate}
        else:
            preview = _find_tier_rates(new_rate)
        
        st.markdown("**Rate preview:**")
        preview_df = pd.DataFrame([{
            "Weekday": f"${preview['weekday']:.2f}",
            "Saturday": f"${preview['saturday']:.2f}",
            "Sunday": f"${preview['sunday']:.2f}",
            "Public Holiday": f"${preview['public_holiday']:.2f}",
        }])
        st.dataframe(preview_df, hide_index=True, use_container_width=True)
        
        if st.button("💾 Save & Recalculate", type="primary", key=f"save_{mid}_{job}"):
            with st.spinner("Saving rates and recalculating shifts..."):
                # 1. Save rates
                saved_tier = _save_rates(client, mid, name, job, new_rate, flat_rate)
                st.success(f"✅ Saved rates for {name} ({job})")
                
                # 2. Recalculate all existing shifts
                updated_count = _recalculate_shifts(client, mid, job, saved_tier)
                if updated_count > 0:
                    st.success(f"🔄 Recalculated {updated_count} shifts with new rates")
                else:
                    st.info("No existing shifts needed recalculation")
                
                st.rerun()
