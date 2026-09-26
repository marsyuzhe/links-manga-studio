"""Shared semantic color tokens for both desktop appearances."""
from app.resources import resource_path

DARK = {
    "window_bg": "#171A20", "workspace_bg": "#171A20", "panel_bg": "#1D2129",
    "panel_secondary": "#242933", "canvas_bg": "#2B2E35", "card_bg": "#20252E",
    "input_bg": "#111318", "hover_bg": "#2A303B", "pressed_bg": "#343C49",
    "selected_bg": "#242F42", "border": "#2E3440", "divider": "#2E3440",
    "text_primary": "#E8EAF0", "text_secondary": "#A8AFBD", "text_muted": "#788293",
    "accent": "#4A8DFF", "accent_hover": "#67A0FF", "accent_pressed": "#3379E8",
    "accent_text": "#10141D", "success": "#66B892", "warning": "#D6A45F",
    "danger": "#CE7474", "overlay": "#4A8DFF", "tooltip_bg": "#242933",
    "scrollbar_thumb": "#434B59", "scrollbar_hover": "#5A6475",
    "shadow": "#0B0D11", "drop_border": "#475366",
    "page_ink": "#E8EAF0", "page_secondary": "#A8AFBD", "page_placeholder": "#E1E5EC",
    "overlay_idle": "#4A849B", "overlay_selected": "#4A8DFF",
}

LIGHT = {
    "window_bg": "#F3F5F8", "workspace_bg": "#EDF0F4", "panel_bg": "#FAFBFC",
    "panel_secondary": "#EFF2F6", "canvas_bg": "#D8DEE7", "card_bg": "#FFFFFF",
    "input_bg": "#FFFFFF", "hover_bg": "#E7ECF3", "pressed_bg": "#DCE4EF",
    "selected_bg": "#E4EEFC", "border": "#D4DBE5", "divider": "#D9DFE8",
    "text_primary": "#202735", "text_secondary": "#566274", "text_muted": "#707D8E",
    "accent": "#3175D6", "accent_hover": "#4385E4", "accent_pressed": "#2867BF",
    "accent_text": "#FFFFFF", "success": "#27835F", "warning": "#A96724",
    "danger": "#B74B50", "overlay": "#3175D6", "tooltip_bg": "#FFFFFF",
    "scrollbar_thumb": "#A7B2C1", "scrollbar_hover": "#8896A8",
    "shadow": "#697789", "drop_border": "#B8C5D5",
    "page_ink": "#202735", "page_secondary": "#596578", "page_placeholder": "#E7EBF0",
    "overlay_idle": "#4D809D", "overlay_selected": "#3175D6",
}


def stylesheet(tokens: dict[str, str] = DARK) -> str:
    return resource_path("app/themes/dark.qss").read_text(encoding="utf-8").format_map(tokens)
