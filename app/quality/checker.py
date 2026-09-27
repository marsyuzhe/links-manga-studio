"""Read-only, navigable project checks; no automatic edits."""
from __future__ import annotations

import json
from collections import defaultdict

from app.rendering.layout import fit_layout
from app.styles.project_styles import ProjectStyleService


def _overlap(a: list[float], b: list[float]) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    area = max(0, x1-x0) * max(0, y1-y0)
    denominator = min(max(1, (a[2]-a[0])*(a[3]-a[1])), max(1, (b[2]-b[0])*(b[3]-b[1])))
    return area / denominator


class QualityChecker:
    def __init__(self, db, font_records: list[dict] | None = None) -> None:
        self.db = db
        self.font_records = font_records or []
        self.fonts = {r["family"].casefold(): r for r in self.font_records}
        self.styles = ProjectStyleService(db)

    def scan(self, progress=lambda *args: None, cancel=None) -> dict:
        pages = [dict(row) for row in self.db.execute("SELECT id,page_uid,width,height FROM pages WHERE deleted_at IS NULL ORDER BY display_order")]
        rows = [dict(row) for row in self.db.execute("""SELECT t.*,p.page_uid,p.width AS page_width,p.height AS page_height,
            x.text AS translation,x.status AS translation_status,s.settings_json AS legacy_settings
            FROM text_blocks t JOIN pages p ON p.id=t.page_id
            LEFT JOIN translations x ON x.text_block_id=t.id AND x.language='zh_CN'
            LEFT JOIN styles s ON s.id=t.style_id WHERE t.active=1 AND p.deleted_at IS NULL
            ORDER BY p.display_order,t.reading_order""")]
        issues: list[dict] = []
        by_page: dict[str, list[tuple[dict, list[float]]]] = defaultdict(list)
        style_counts: dict[str, int] = defaultdict(int)

        def add(row: dict, severity: str, code: str) -> None:
            issues.append({"severity": severity, "code": code, "page_id": row.get("page_id"),
                           "page_uid": row.get("page_uid"), "text_uid": row.get("text_uid"),
                           "block_id": row.get("id"), "reading_order": row.get("reading_order")})

        for index, row in enumerate(rows, 1):
            if cancel is not None and cancel.is_set():
                return {"status": "cancelled", "issues": issues}
            if index % 20 == 0:
                progress(index, max(1, len(rows)), "status.quality_check")
            bbox = json.loads(row["bbox_json"])
            by_page[row["page_id"]].append((row, bbox))
            if row["review_status"] != "reviewed":
                add(row, "info", "ocr_unreviewed")
            if row["ocr_confidence"] is not None and row["ocr_confidence"] < .75:
                add(row, "warning", "low_confidence")
            translation = (row["translation"] or "").strip()
            if not translation:
                add(row, "warning", "translation_empty")
            if row["translation_status"] == "ai_draft":
                add(row, "warning", "ai_draft_unreviewed")
            if translation and row["typeset_status"] != "ready":
                add(row, "warning", "not_typeset")
            if row["erase_status"] == "erased" and not translation:
                add(row, "error", "erased_without_translation")
            if bbox[0] < 0 or bbox[1] < 0 or bbox[2] > row["page_width"] or bbox[3] > row["page_height"]:
                add(row, "error", "outside_page")
            legacy = json.loads(row["legacy_settings"] or "{}")
            style = self.styles.resolve(row, legacy)
            base = json.loads(self.styles.preset(row["style_role"] or "speech")["settings_json"])
            role = row["style_role"] or "speech"
            style_counts[role] += 1
            family = style.get("font", "Microsoft YaHei")
            font_record = self.fonts.get(family.casefold())
            if self.font_records and font_record is None:
                add(row, "error", "font_missing")
            elif font_record and any('\u4e00' <= c <= '\u9fff' for c in translation) and "zh" not in font_record["supported_languages"]:
                add(row, "warning", "font_no_chinese")
            if family != base.get("font"):
                add(row, "info", "style_inconsistent")
            if int(style.get("max_size", 72)) > max(48, int(base.get("max_size", 72)) * 1.6):
                add(row, "warning", "font_size_outlier")
            if int(style.get("min_size", 18)) < 12:
                add(row, "warning", "tiny_font")
            if translation:
                fit = fit_layout(translation, style, bbox[2]-bbox[0], bbox[3]-bbox[1])
                if fit.status == "overflow":
                    add(row, "error", "overflow")
                elif fit.status == "warning":
                    add(row, "warning", "near_overflow")
        for page_rows in by_page.values():
            for index, (row, box) in enumerate(page_rows):
                if any(_overlap(box, other_box) > .65 for _, other_box in page_rows[index+1:]):
                    add(row, "warning", "block_overlap")
        exported = {r[0] for r in self.db.execute("""SELECT DISTINCT i.page_id FROM task_items i JOIN tasks t ON t.id=i.task_id
            WHERE t.kind='final_export' AND i.status='completed'""")}
        for page in pages:
            if page["id"] not in exported:
                add({"page_id": page["id"], "page_uid": page["page_uid"]}, "info", "not_exported")
        return {"status": "completed", "issues": issues,
                "counts": {key: sum(1 for issue in issues if issue["severity"] == key)
                           for key in ("error", "warning", "info")},
                "style_counts": dict(style_counts)}
