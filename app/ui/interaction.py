"""Shared keyboard focus and quiet item selection; no business state."""
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import (QApplication, QAbstractButton, QAbstractItemView,
    QMenu, QProxyStyle, QStyle, QStyledItemDelegate, QCheckBox, QRadioButton, QTabBar,
    QMessageBox, QInputDialog)


def tokens():
    return QApplication.instance()._lmw_tokens


def set_state(widget, name, value):
    if widget.property(name) == value:
        return
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
    if isinstance(widget, QAbstractItemView):
        widget.viewport().update()


def keyboard_focus(widget):
    return bool(widget and widget.property('keyboardFocus'))


def truncated_tooltip(event, view, option, text: str, available_width: int) -> bool:
    from PySide6.QtWidgets import QToolTip
    preview = str(text).replace('\n', ' ')[:120]
    private_path = ':\\' in preview or ':/' in preview or preview.startswith(('/', '\\'))
    if private_path or option.fontMetrics.horizontalAdvance(preview) <= max(1, available_width):
        QToolTip.hideText()
        return True
    preview = option.fontMetrics.elidedText(preview, Qt.TextElideMode.ElideRight, 360)
    QToolTip.showText(event.globalPos(), preview, view, option.rect, 3500)
    return True


class WorkspaceStyle(QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_FrameFocusRect:
            if widget and keyboard_focus(widget) and isinstance(widget,(QCheckBox,QRadioButton,QTabBar)):
                painter.save()
                painter.setPen(QPen(QColor(tokens()["focus_ring"]),1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(option.rect.adjusted(1,1,-2,-2))
                painter.restore()
            return  # Own solid keyboard rings replace native dotted focus.
        super().drawPrimitive(element, option, painter, widget)

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ToolTip_WakeUpDelay:
            return 650
        return super().styleHint(hint, option, widget, returnData)


class SelectionDelegate(QStyledItemDelegate):
    """Reuse native text/editor layout while owning item states and focus."""
    def paint(self, painter, option, index):
        from PySide6.QtWidgets import QStyleOptionViewItem
        opt = QStyleOptionViewItem(option)
        focused = bool(opt.state & QStyle.StateFlag.State_HasFocus)
        opt.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter, opt, index)
        if focused and keyboard_focus(self.parent()):
            painter.save()
            painter.setPen(QPen(QColor(tokens()['focus_ring']), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(opt.rect.adjusted(3, 3, -4, -4))
            painter.restore()

    def helpEvent(self, event, view, option, index):
        # Item previews only when actually truncated, never absolute paths.
        text = index.data(Qt.ItemDataRole.ToolTipRole) or index.data() or ''
        first = str(text).splitlines()[0][:120] if text else ''
        return truncated_tooltip(event, view, option, first, option.rect.width()-20)


class InteractionFilter(QObject):
    NAVIGATION = {Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Up,
        Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Home,
        Qt.Key.Key_End, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown}

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind == QEvent.Type.Show and isinstance(obj, (QMessageBox, QInputDialog)):
            from .components import polish_standard_prompt
            polish_standard_prompt(obj)
        target = obj
        if hasattr(obj, 'parentWidget') and isinstance(obj.parentWidget(), QAbstractItemView):
            target = obj.parentWidget()
        supported = isinstance(target, (QAbstractItemView, QAbstractButton, QTabBar))
        if supported:
            if kind == QEvent.Type.MouseButtonPress:
                set_state(target, 'keyboardFocus', False)
            elif kind == QEvent.Type.FocusIn:
                set_state(target, 'keyboardFocus', event.reason() in (
                    Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason,
                    Qt.FocusReason.ShortcutFocusReason))
            elif kind == QEvent.Type.KeyPress and event.key() in self.NAVIGATION:
                set_state(target, 'keyboardFocus', True)
            elif kind == QEvent.Type.Polish and isinstance(target, QAbstractItemView):
                if type(target.itemDelegate()) is QStyledItemDelegate:
                    target.setItemDelegate(SelectionDelegate(target))
        if isinstance(obj, QMenu):
            if kind in (QEvent.Type.Show, QEvent.Type.Hide) and isinstance(obj.parentWidget(), QAbstractButton):
                set_state(obj.parentWidget(), 'menuOpen', kind == QEvent.Type.Show)
            if kind == QEvent.Type.KeyPress:
                set_state(obj, 'keyboardNavigation', True)
            elif kind == QEvent.Type.MouseMove:
                set_state(obj, 'keyboardNavigation', False)
        return False


def install_interactions(app, theme_tokens):
    app._lmw_tokens = theme_tokens
    if not hasattr(app, '_lmw_interaction_filter'):
        app.setStyle(WorkspaceStyle(app.style().name()))
        app._lmw_interaction_filter = InteractionFilter(app)
        app.installEventFilter(app._lmw_interaction_filter)
