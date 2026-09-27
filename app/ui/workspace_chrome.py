"""Compact command/tool presentation over the existing actions."""
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QPushButton, QToolButton, QSplitter, QSplitterHandle
from .interaction import tokens, set_state, keyboard_focus
from .icons import icon


class CommandButton(QToolButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty('role', 'command')
        self.setProperty('menuOpen', False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setIconSize(QSize(16,16))
        self.setFixedHeight(34)
        self.setMouseTracking(True)

    def setMenu(self, menu):
        super().setMenu(menu)
        menu.aboutToShow.connect(lambda: set_state(self, 'menuOpen', True))
        menu.aboutToHide.connect(lambda: set_state(self, 'menuOpen', False))

    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.text())+66,34)

    def paintEvent(self, event):
        t=tokens();p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=self.rect().adjusted(1,1,-1,-1);test=self.property('visualState')
        opened=self.property('menuOpen');pressed=self.isDown() or test=='pressed'
        hovered=self.underMouse() or test=='hover'
        bg=t['pressed_bg'] if pressed else t['selected_bg'] if opened else t['hover_bg'] if hovered else None
        border=t['selected_border'] if opened else t['panel_border'] if hovered else None
        p.setPen(QPen(QColor(border),1) if border else Qt.PenStyle.NoPen)
        p.setBrush(QColor(bg) if bg else Qt.BrushStyle.NoBrush);p.drawRoundedRect(r,4,4)
        if self.hasFocus() and keyboard_focus(self):
            p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(QColor(t['focus_ring']),1));p.drawRoundedRect(r.adjusted(2,2,-2,-2),3,3)
        self.icon().paint(p,QRect(11,9,16,16),Qt.AlignmentFlag.AlignCenter,
            self.icon().Mode.Normal if self.isEnabled() else self.icon().Mode.Disabled)
        p.setPen(QColor(t['text_primary'] if self.isEnabled() else t['text_muted']))
        p.drawText(QRect(33,0,self.width()-55,34),Qt.AlignmentFlag.AlignVCenter,self.text())
        x=self.width()-14;y=17
        p.setPen(QPen(QColor(t['text_secondary'] if self.isEnabled() else t['text_muted']),1.4))
        p.drawLine(x-4,y-2,x,y+2);p.drawLine(x,y+2,x+4,y-2)


class RailButton(QPushButton):
    def __init__(self, glyph, parent=None):
        super().__init__(parent)
        self.glyph=glyph
        self.setProperty('role','tool');self.setProperty('variant','rail')
        self.setFixedSize(36,36);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self,event):
        t=tokens();p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        state=self.property('visualState');selected=self.isChecked()
        bg=t['pressed_bg'] if self.isDown() or state=='pressed' else t['selected_bg'] if selected else t['hover_bg'] if self.underMouse() or state=='hover' else None
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(bg) if bg else Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(self.rect().adjusted(1,1,-1,-1),4,4)
        if selected:p.fillRect(QRect(1,7,2,22),QColor(t['accent']))
        if self.hasFocus() and keyboard_focus(self):
            p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(QColor(t['focus_ring']),1));p.drawRoundedRect(self.rect().adjusted(3,3,-3,-3),3,3)
        color=t['text_muted'] if not self.isEnabled() else t['accent'] if selected else t['text_secondary']
        icon(self.glyph,color,18).paint(p,QRect(9,9,18,18))


class DividerHandle(QSplitterHandle):
    def __init__(self,orientation,parent):
        super().__init__(orientation,parent)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.SplitHCursor)
    def enterEvent(self,event):self.update();super().enterEvent(event)
    def leaveEvent(self,event):self.update();super().leaveEvent(event)
    def paintEvent(self,event):
        p=QPainter(self);t=tokens();p.fillRect(self.rect(),QColor(t['panel_bg']))
        color=t['divider_strong'] if self.underMouse() or self.property('visualState')=='hover' else t['divider']
        p.setPen(QPen(QColor(color),1));x=self.width()//2;p.drawLine(x,0,x,self.height()-1)


class WorkspaceSplitter(QSplitter):
    def createHandle(self):return DividerHandle(self.orientation(),self)
