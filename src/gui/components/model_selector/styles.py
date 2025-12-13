"""
Shared styles for model selector components.
Defines common colors and base styles to ensure consistency and correct rendering.
"""

# Base style to ensure labels are transparent and inherit parent background correctly.
# This fixes the issue where text labels would have their own background color,
# looking like "stickers" on top of the row.
COMMON_BASE_STYLE = """
    QLabel {
        background-color: transparent;
    }
"""

class ModelSelectorColors:
    """Color palette for Model Selector (Light Theme)."""
    
    # Selected State
    SELECTED_BG = "#e3f2fd"      # Material Blue 50
    SELECTED_BORDER = "#1976d2"  # Material Blue 700
    SELECTED_TEXT = "#0066cc"    # Deep Blue
    SELECTED_SUBTEXT = "#1976d2" # Material Blue 700
    
    # Hover State
    HOVER_BG = "#f0f0f0"         # Light Gray
    HOVER_BORDER = "#d0d0d0"     # Gray
    
    # Normal State
    NORMAL_BG = "transparent"
    NORMAL_BORDER = "#e0e0e0"    # Light Gray line
    
    # Text
    TEXT_PRIMARY = "#333333"     # Dark Gray
    TEXT_SECONDARY = "#666666"   # Medium Gray
    TEXT_STARRED = "#f5a623"     # Orange (for Starred items)

