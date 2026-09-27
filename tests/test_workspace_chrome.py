"""Workspace-only behavior: focus accessibility, popup states and safe edges."""
import pytest
from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QStyle, QStyleOptionViewItem, QAbstractItemView
from test_ai_translation import ai_project
from test_product_060 import ready_window
from app.ui.interaction import keyboard_focus, SelectionDelegate
from app.themes import DARK, LIGHT


def row_image(view,index,state):
    img=QImage(280,104,QImage.Format.Format_RGB32);img.fill(QColor('#ff00ff'))
    p=QPainter(img);opt=QStyleOptionViewItem();opt.initFrom(view);opt.rect=QRect(0,0,280,104);opt.state=state
    view.itemDelegate().paint(p,opt,index);p.end();return img


@pytest.mark.parametrize('theme',['dark','light'])
def test_mouse_selection_vs_keyboard_focus(ai_project,qtbot,theme):
    w=ready_window(ai_project,qtbot);w.set_theme(theme);v=w.workspace.panel
    v.setCurrentIndex(v.model().index(0));qtbot.mouseClick(v.viewport(),Qt.MouseButton.LeftButton,pos=v.visualRect(v.currentIndex()).center())
    assert not keyboard_focus(v)
    selected=QStyle.StateFlag.State_Enabled|QStyle.StateFlag.State_Selected
    a=row_image(v,v.currentIndex(),selected);b=row_image(v,v.currentIndex(),selected|QStyle.StateFlag.State_HasFocus)
    assert a==b  # Mouse focus must not add another rectangle.
    qtbot.keyClick(v,Qt.Key.Key_Down);assert keyboard_focus(v) and v.currentIndex().row()==1
    c=row_image(v,v.currentIndex(),selected|QStyle.StateFlag.State_HasFocus)
    assert a!=c
    assert v.focusPolicy()!=Qt.FocusPolicy.NoFocus
    w.close()


@pytest.mark.parametrize('theme',['dark','light'])
def test_quiet_selection_hover_and_ring(ai_project,qtbot,theme):
    w=ready_window(ai_project,qtbot);w.set_theme(theme);v=w.workspace.panel;index=v.model().index(0)
    normal=row_image(v,index,QStyle.StateFlag.State_Enabled)
    hover=row_image(v,index,QStyle.StateFlag.State_Enabled|QStyle.StateFlag.State_MouseOver)
    selected=row_image(v,index,QStyle.StateFlag.State_Enabled|QStyle.StateFlag.State_Selected)
    assert normal!=hover and hover!=selected
    t=w.theme.tokens;assert selected.pixelColor(278,50)==QColor(t['selected_bg'])
    assert t['selected_bg']!=t['accent']
    w.close()


def test_popup_state_and_main_action_are_preserved(ai_project,qtbot):
    w=ready_window(ai_project,qtbot)
    for key in ('ocr','translation','export'):
        b=w.workflow_buttons[key][0];m=b.menu();m.popup(b.mapToGlobal(b.rect().bottomLeft()))
        qtbot.waitUntil(lambda:b.property('menuOpen') is True)
        assert m.isVisible();m.hide();assert b.property('menuOpen') is False
    w.workflow_buttons['translation'][0].click();assert w.stack.currentWidget() is w.translation_center
    w.close()


def test_tab_navigation_and_tool_actions(ai_project,qtbot):
    w=ready_window(ai_project,qtbot);ws=w.workspace
    assert w.focus_action.shortcut().toString()=='Ctrl+Tab'
    b=w.workflow_buttons['import'][0];b.setFocus(Qt.FocusReason.TabFocusReason)
    qtbot.keyClick(b,Qt.Key.Key_Tab)
    assert w.workspace.left_tabs.isVisible() and w.focusWidget() is not b
    for name in ('pointer','hand','text'):
        ws.rail_buttons[name].setFocus(Qt.FocusReason.TabFocusReason)
        qtbot.keyClick(ws.rail_buttons[name],Qt.Key.Key_Space)
        assert ws.rail_buttons[name].isChecked()
    assert all(b.height()==36 and b.width()==36 for b in ws.rail_buttons.values())
    assert ws.canvas.text_tool
    w.close()


def test_no_page_or_font_path_tooltips(ai_project,qtbot):
    from app.ui.font_picker import FontPicker
    w=ready_window(ai_project,qtbot);v=w.workspace.panel
    for row in range(v.model().rowCount()):assert not v.model().index(row).data(Qt.ItemDataRole.ToolTipRole)
    picker=FontPicker([{'family':'Arial','file_path':'C:/private/font.ttf'}],'Arial',w)
    assert picker.list.item(0).toolTip()=='Arial'
    assert w.style().styleHint(QStyle.StyleHint.SH_ToolTip_WakeUpDelay)==650
    w.close()


@pytest.mark.parametrize('size',[(1366,768),(1920,1080)])
@pytest.mark.parametrize('theme',['dark','light'])
def test_chrome_corner_and_splitter_geometry(ai_project,qtbot,size,theme):
    w=ready_window(ai_project,qtbot);w.set_theme(theme);w.resize(*size);qtbot.wait(20);ws=w.workspace
    toolbar_bottom=w.toolbar.mapTo(w,QPoint(0,w.toolbar.height())).y()
    rail_top=ws.tool_rail.mapTo(w,QPoint(0,0)).y()
    assert rail_top==toolbar_bottom
    assert ws.tool_rail.mapTo(w,QPoint(0,0)).x()==0
    assert ws.left_tabs.mapTo(w,QPoint(0,0)).x()==44
    assert ws.left_tabs.mapTo(w,QPoint(0,0)).y()==rail_top
    assert ws.canvas.width()>=650 and ws.inspector_panel.width()>=300
    for i in (1,2):
        h=ws.main_splitter.handle(i);assert h.width()==7 and h.cursor().shape()==Qt.CursorShape.SplitHCursor
    original=ws.main_splitter.sizes();h=ws.main_splitter.handle(1)
    qtbot.mousePress(h,Qt.MouseButton.LeftButton,pos=h.rect().center());qtbot.mouseMove(h,QPoint(32,h.height()//2));qtbot.mouseRelease(h,Qt.MouseButton.LeftButton,pos=QPoint(32,h.height()//2))
    assert ws.main_splitter.sizes()!=original
    ws.main_splitter.setSizes([240,600,400]);w.reset_panel_layout();qtbot.wait(20)
    assert abs(ws.main_splitter.sizes()[0]-280)<30
    w.close()


def test_shared_delegate_used_by_other_item_views(ai_project,qtbot):
    from app.ui.settings_dialog import SettingsDialog
    w=ready_window(ai_project,qtbot);w.show_translation_center();qtbot.wait(20)
    assert isinstance(w.translation_center.history.itemDelegate(),SelectionDelegate)
    w.show_glossary();assert isinstance(w.glossary_workspace.table.itemDelegate(),SelectionDelegate)
    d=SettingsDialog(w);d.show();qtbot.wait(10)
    assert isinstance(d.navigation.itemDelegate(),SelectionDelegate)
    d.close();w.close()


def test_full_path_is_only_in_explicit_page_information(ai_project,qtbot):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication,QDialog,QPlainTextEdit
    w=ready_window(ai_project,qtbot);observed=[]
    def inspect():
        dialog=QApplication.activeModalWidget()
        assert isinstance(dialog,QDialog)
        text=dialog.findChild(QPlainTextEdit)
        observed.append(text.toPlainText())
        assert text.isReadOnly()
        dialog.accept()
    QTimer.singleShot(20,inspect)
    w.workspace.show_page_information()
    page=w.workspace.model.pages[w.workspace.current_row]
    assert page['filename'] in observed[0] and page['path'] in observed[0]
    w.close()


def test_preview_tooltip_is_truncated_only_and_bounded(ai_project,qtbot,monkeypatch):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QHelpEvent
    from PySide6.QtWidgets import QToolTip
    w=ready_window(ai_project,qtbot);ws=w.workspace;view=ws.ocr_list;item=view.item(0)
    option=QStyleOptionViewItem();option.initFrom(view);option.rect=QRect(0,0,260,40)
    event=QHelpEvent(QEvent.Type.ToolTip,QPoint(10,10),QPoint(10,10));shown=[]
    monkeypatch.setattr(QToolTip,'showText',lambda *args:shown.append(args[1]))
    item.setData(Qt.ItemDataRole.UserRole+1,{'preview':'短文'})
    view.itemDelegate().helpEvent(event,view,option,view.model().index(0))
    assert not shown
    item.setData(Qt.ItemDataRole.UserRole+1,{'preview':'很长的文字预览 '*100})
    view.itemDelegate().helpEvent(event,view,option,view.model().index(0))
    assert len(shown)==1 and '\n' not in shown[0]
    assert option.fontMetrics.horizontalAdvance(shown[0])<=360
    w.close()
