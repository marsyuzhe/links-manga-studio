"""On-demand provenance without exposing request bodies or provider credentials."""
import json
from PySide6.QtWidgets import QDialog,QFormLayout,QLabel,QDialogButtonBox
from app.ocr.review import TextBlockService
from .components import localize_buttons

class TranslationDetailsDialog(QDialog):
    def __init__(self,db,block_id,language,parent=None):
        super().__init__(parent)
        self.setWindowTitle(language.tr("ui.translation_details"))
        self.resize(440,300)
        form=QFormLayout(self)
        form.setContentsMargins(16,16,16,16)
        form.setSpacing(10)
        value=TextBlockService(db).translation(block_id) or {}
        for key in ("provider","model","prompt_version","created_at","updated_at"):
            label=QLabel(str(value.get(key) or "—"));label.setWordWrap(True)
            form.addRow(language.tr("ui.detail_"+key),label)
        row=db.execute("""SELECT i.usage_json FROM task_items i JOIN tasks t ON t.id=i.task_id
            JOIN text_blocks b ON b.page_id=i.page_id WHERE b.id=? AND t.kind='AI_TRANSLATION'
            AND i.status='completed' ORDER BY i.finished_at DESC LIMIT 1""",(block_id,)).fetchone()
        usage=json.loads(row[0]) if row else {}
        form.addRow(language.tr("ui.detail_usage"),QLabel(str(usage.get("total_tokens","—"))))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        localize_buttons(buttons,language.tr)
        buttons.rejected.connect(self.reject);form.addRow(buttons)
