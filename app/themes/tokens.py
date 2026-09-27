"""Shared semantic color tokens for both desktop appearances."""
from app.resources import resource_path

DARK = {
    "preview_bg": "#F9F8F4", "preview_ink": "#202735",
    "workspace_chrome_bg": "#24262A", "divider_strong": "#7A8594", "panel_border": "#41454D",
    "window_bg": "#1B1C1F", "workspace_bg": "#1B1C1F", "panel_bg": "#202124",
    "panel_secondary": "#242933", "canvas_bg": "#303134", "card_bg": "#20252E",
    "input_bg": "#111318", "hover_bg": "#2A303B", "pressed_bg": "#343C49",
    "selected_bg": "#303944", "border": "#41454D", "divider": "#41454D",
    "border_strong":"#69727E", "selected_border":"#69A2FF", "focus_ring":"#AFD2FF",
    "text_primary": "#E8EAF0", "text_secondary": "#A8AFBD", "text_muted": "#788293",
    "accent": "#4A8DFF", "accent_hover": "#67A0FF", "accent_pressed": "#3379E8",
    "accent_text": "#10141D", "success": "#66B892", "warning": "#D6A45F",
    "danger": "#CE7474", "overlay": "#4A8DFF", "tooltip_bg": "#242933",
    "scrollbar_thumb": "#434B59", "scrollbar_hover": "#5A6475",
    "shadow": "#0B0D11", "drop_border": "#475366",
    "page_ink": "#E8EAF0", "page_secondary": "#A8AFBD", "page_placeholder": "#E1E5EC",
    "overlay_idle": "#73777F", "overlay_selected": "#4A8DFF",
}

LIGHT = {
    "preview_bg": "#F9F8F4", "preview_ink": "#202735",
    "workspace_chrome_bg": "#EFF0F1", "divider_strong": "#8A96A8", "panel_border": "#BAC2CE",
    "window_bg": "#F2F2F2", "workspace_bg": "#EDF0F4", "panel_bg": "#F6F6F5",
    "panel_secondary": "#EFF2F6", "canvas_bg": "#D9DADB", "card_bg": "#FFFFFF",
    "input_bg": "#FFFFFF", "hover_bg": "#E7ECF3", "pressed_bg": "#DCE4EF",
    "selected_bg": "#E7EEF8", "border": "#BAC2CE", "divider": "#BAC2CE",
    "border_strong":"#8A96A8", "selected_border":"#2564B9", "focus_ring":"#123F85",
    "text_primary": "#202735", "text_secondary": "#566274", "text_muted": "#707D8E",
    "accent": "#3175D6", "accent_hover": "#4385E4", "accent_pressed": "#2867BF",
    "accent_text": "#FFFFFF", "success": "#27835F", "warning": "#A96724",
    "danger": "#B74B50", "overlay": "#3175D6", "tooltip_bg": "#FFFFFF",
    "scrollbar_thumb": "#A7B2C1", "scrollbar_hover": "#8896A8",
    "shadow": "#697789", "drop_border": "#B8C5D5",
    "page_ink": "#202735", "page_secondary": "#596578", "page_placeholder": "#E7EBF0",
    "overlay_idle": "#8A8D93", "overlay_selected": "#3175D6",
}


def stylesheet(tokens: dict[str, str] = DARK) -> str:
    values={**tokens,"dropdown_arrow":resource_path("assets/icons/dropdown_dark.svg" if tokens["window_bg"]==DARK["window_bg"] else "assets/icons/dropdown_light.svg").as_posix()}
    return resource_path("app/themes/dark.qss").read_text(encoding="utf-8").format_map(values)
