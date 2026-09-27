"""Compact OCR rows with distinct hover, selection and keyboard focus."""
from PySide6.QtCore import Qt,QSize,QRect
from PySide6.QtGui import QColor,QPen
from PySide6.QtWidgets import QStyledItemDelegate,QStyle
from .interaction import keyboard_focus, truncated_tooltip

class OCRRowDelegate(QStyledItemDelegate):
    def __init__(self,workspace):super().__init__(workspace);self.workspace=workspace
    def sizeHint(self,option,index):return QSize(190,40)
    def paint(self,painter,option,index):
        t=self.workspace.canvas.tokens;rect=option.rect.adjusted(2,2,-2,-2);selected=bool(option.state & QStyle.StateFlag.State_Selected);hover=bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.save();painter.setClipRect(option.rect);painter.fillRect(rect,QColor(t["selected_bg"] if selected else t["hover_bg"] if hover else t["panel_bg"]))
        if selected:
            painter.setPen(QPen(QColor(t["selected_border"]),1));painter.drawRect(rect.adjusted(0,0,-1,-1));painter.fillRect(QRect(rect.left(),rect.top()+1,2,rect.height()-2),QColor(t["accent"]))
        if option.state & QStyle.StateFlag.State_HasFocus and keyboard_focus(self.workspace.ocr_list):
            painter.setPen(QPen(QColor(t["focus_ring"]),1));painter.drawRect(rect.adjusted(3,3,-4,-4))
        data=index.data(Qt.ItemDataRole.UserRole+1) or {};confidence=data.get("confidence",0);status=data.get("status","")
        painter.setPen(QColor(t["warning"] if confidence<75 else t["text_secondary"]));painter.drawText(rect.adjusted(9,0,-rect.width()+50,0),Qt.AlignmentFlag.AlignVCenter,f"{confidence}%")
        painter.setPen(QColor(t["text_primary"]));text_rect=rect.adjusted(53,0,-35 if status else -7,0);preview=option.fontMetrics.elidedText(data.get("preview",index.data() or ""),Qt.TextElideMode.ElideRight,max(1,text_rect.width()));painter.drawText(text_rect,Qt.AlignmentFlag.AlignVCenter,preview)
        if status:painter.setPen(QColor(t["text_secondary"]));painter.drawText(rect.adjusted(rect.width()-31,0,-6,0),Qt.AlignmentFlag.AlignVCenter,status)
        painter.restore()

    def helpEvent(self,event,view,option,index):
        data=index.data(Qt.ItemDataRole.UserRole+1) or {}
        text=data.get('preview',index.data() or '').replace('\n',' ')
        return truncated_tooltip(event,view,option,text,option.rect.width()-88)
