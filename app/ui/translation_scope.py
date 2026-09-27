"""Shared UI page scope resolution; no task persistence or provider logic."""
from app.translation.profiles import TranslationError


def page_ids(workspace, scope: str, selection: str = "") -> list[str]:
    if scope in ("block", "page"):
        return [workspace.current_id] if workspace.current_id else []
    if scope == "project":
        return [p["id"] for p in workspace.model.pages]
    if scope == "batch":
        return [r[0] for r in workspace.pages_service.connection.execute("""SELECT bp.page_id FROM batch_pages bp
            JOIN pages p ON bp.page_id=p.id WHERE bp.batch_id IN
            (SELECT batch_id FROM batch_pages WHERE page_id=?) AND p.deleted_at IS NULL ORDER BY p.display_order""", (workspace.current_id,))]
    numbers = set()
    try:
        for part in selection.split(','):
            if '-' in part:
                lo, hi = map(int, part.split('-'))
                if lo < 1 or hi < lo or hi > len(workspace.model.pages):
                    raise ValueError()
                numbers.update(range(lo, hi+1))
            elif part.strip():
                numbers.add(int(part))
        if any(n < 1 or n > len(workspace.model.pages) for n in numbers):
            raise ValueError()
    except ValueError:
        raise TranslationError("invalid_range") from None
    return [workspace.model.pages[n-1]["id"] for n in sorted(numbers)]


def options(workspace, scope: str, drafts: bool, overwrite: bool) -> dict:
    value = {"include_ai_draft": drafts, "overwrite_protected": overwrite}
    if scope == "block":
        value["block_ids"] = [workspace.selected_block] if workspace.selected_block else ["no-selection"]
    return value
