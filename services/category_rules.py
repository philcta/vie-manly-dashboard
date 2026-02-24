# services/category_rules.py

def is_bar_category(cat: str) -> bool:
    if not isinstance(cat, str):
        return False
    return (
        "MTO" in cat.upper()
        or cat in {
            "Cafe Drinks",
            "Smoothie Bar",
            "Soups",
            "Sweet Treats",
            "Wraps & Salads",
            "Breakfast Bowls",
            "Chia Bowls",
        }
    )
