"""Independent project glossary workspace, immediate saves and beginner empty states."""
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLineEdit,QComboBox,
    QTabWidget,QTableWidget,QTableWidgetItem,QHeaderView,QStackedWidget,QFileDialog,QMessageBox,
    QDialog,QFormLayout,QDialogButtonBox,QPlainTextEdit,QListWidget,QListWidgetItem,QSplitter,QMenu)
from app.translation.glossary import GlossaryService,CATEGORIES
from .components import localize_buttons,exec_dialog

class TermEditor(QDialog):
    def __init__(self, owner, values=None):
        super().__init__(owner);self.owner=owner;self.values=values or {}
        self.setWindowTitle(owner.text("编辑术语","Edit term") if values else owner.text("添加术语","Add term"));self.resize(500,320)
        layout=QVBoxLayout(self);layout.setContentsMargins(16,16,16,16);form=QFormLayout();layout.addLayout(form)
        self.source=QLineEdit(self.values.get("source_term",""));self.target=QLineEdit(self.values.get("target_term",""))
        self.category=QComboBox()
        for k in CATEGORIES:self.category.addItem(owner.categories[k],k)
        self.category.setCurrentIndex(self.category.findData(self.values.get("category","other")))
        self.note=QPlainTextEdit(self.values.get("note",""));self.note.setMaximumHeight(90)
        for title,field in ((owner.text("原文","Source"),self.source),(owner.text("固定译名","Translation"),self.target),(owner.text("分类","Category"),self.category),(owner.text("备注","Notes"),self.note)):form.addRow(title,field)
        self.error=QLabel();self.error.setWordWrap(True);layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        localize_buttons(buttons,owner.host.language.tr);buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
    def save(self):
        try:self.owner.service.save({"source_term":self.source.text(),"target_term":self.target.text(),"category":self.category.currentData(),"note":self.note.toPlainText()},self.values.get("id"))
        except ValueError as e:self.error.setText(str(e));return
        self.accept()

class GlossaryWorkspace(QWidget):
    def __init__(self, host):
        super().__init__();self.host=host;self.service=None;self.loading=False;self.character_id=None
        self.categories=dict(zip(CATEGORIES,[self.text(c,e) for c,e in zip(("人物","地点","组织","物品","技能","其他"),("Character","Place","Organization","Item","Skill","Other"))]))
        outer=QVBoxLayout(self);outer.setContentsMargins(16,12,16,16);outer.setSpacing(10)
        heading=QHBoxLayout();title=QLabel(self.text("项目术语库","Project Glossary"));title.setProperty("role","title");heading.addWidget(title);heading.addStretch()
        back=QPushButton(self.text("返回漫画","Back to manga"));back.clicked.connect(host.show_manga);heading.addWidget(back);outer.addLayout(heading)
        outer.addWidget(QLabel(self.text("用于统一人物、地点和专有名词译法。","Keep names, places and terms consistent.")))
        self.summary=QLabel();self.summary.setProperty("role","muted");outer.addWidget(self.summary)
        self.tabs=QTabWidget();outer.addWidget(self.tabs,1)
        term_page=QWidget();layout=QVBoxLayout(term_page);layout.setContentsMargins(12,12,12,12)
        tools=QHBoxLayout();add=QPushButton(self.text("＋ 添加术语","+ Add term"));add.clicked.connect(self.add);tools.addWidget(add)
        self.search=QLineEdit();self.search.setPlaceholderText(self.text("搜索原文、译名或备注","Search source, translation or notes"));self.search.setClearButtonEnabled(True);tools.addWidget(self.search,1)
        self.category=QComboBox();self.category.addItem(self.text("所有分类","All categories"),"")
        for k in CATEGORIES:self.category.addItem(self.categories[k],k)
        tools.addWidget(self.category);self.sort=QComboBox();self.sort.addItems([self.text("名称","Name"),self.text("最近修改","Recently edited")]);tools.addWidget(self.sort)
        self.more=QPushButton("•••");self.more.setAccessibleName(self.text("术语操作","Glossary actions"));menu=QMenu(self.more)
        for cn,en,action in (("导入 CSV","Import CSV",self.import_csv),("导出 CSV","Export CSV",self.export_csv),("清理空项","Clean empty terms",self.clean),("删除所选术语","Delete selected term",self.delete),("撤销","Undo",lambda:self.history(False)),("重做","Redo",lambda:self.history(True))):
            menu.addAction(self.text(cn,en),action)
        self.more.setMenu(menu);tools.addWidget(self.more);layout.addLayout(tools)
        self.stack=QStackedWidget();layout.addWidget(self.stack,1)
        empty=QWidget();el=QVBoxLayout(empty);el.addStretch();self.empty_title=QLabel();self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter);el.addWidget(self.empty_title)
        helper=QLabel(self.text("术语帮助整本漫画保持固定译法一致。","Terms keep the whole manga consistent."));helper.setAlignment(Qt.AlignmentFlag.AlignCenter);el.addWidget(helper)
        for cn,en,action in (("添加第一个术语","Add first term",self.add),("导入 CSV","Import CSV",self.import_csv)):
            button=QPushButton(self.text(cn,en));button.clicked.connect(action);el.addWidget(button,alignment=Qt.AlignmentFlag.AlignCenter)
        el.addStretch();self.stack.addWidget(empty)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels([self.text(c,e) for c,e in zip(("原文","固定译名","分类","备注","状态"),("Source","Translation","Category","Notes","Status"))]);self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection);self.table.verticalHeader().hide();self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch);self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch);self.table.setColumnWidth(3,240)
        for n,w in ((0,220),(1,220),(2,110),(4,100)):self.table.setColumnWidth(n,w)
        self.table.cellChanged.connect(self.inline_save);self.table.cellDoubleClicked.connect(self.double_click);self.stack.addWidget(self.table)
        self.message=QLabel(self.text("修改即时保存 · 双击编辑","Changes save immediately · Double-click to edit"));layout.addWidget(self.message)
        self.tabs.addTab(term_page,self.text("术语","Terms"))
        chars=QWidget();cl=QVBoxLayout(chars);cl.setContentsMargins(12,12,12,12);row=QHBoxLayout()
        ca=QPushButton(self.text("＋ 添加人物","+ Add character"));ca.clicked.connect(self.add_character);row.addWidget(ca)
        cd=QPushButton(self.text("删除人物","Delete character"));cd.clicked.connect(self.delete_character);row.addWidget(cd);row.addStretch();cl.addLayout(row)
        split=QSplitter();split.setHandleWidth(7);self.characters=QListWidget();self.characters.setMinimumWidth(180);split.addWidget(self.characters)
        detail=QWidget();form=QFormLayout(detail);form.setContentsMargins(16,12,16,16);self.character_fields={}
        for key,cn,en in (("name","姓名","Name"),("translated_name","固定译名","Translation"),("description","身份","Identity"),("speech_style","说话风格","Speech style"),("note","备注","Notes")):
            field=QPlainTextEdit() if key=="note" else QLineEdit();self.character_fields[key]=field;form.addRow(self.text(cn,en),field)
            if key=="note":field.setMaximumHeight(150);field.textChanged.connect(self.schedule_character)
            else:field.editingFinished.connect(self.save_character)
        self.character_hint=QLabel(self.text("添加人物并填写说话风格。修改自动保存。","Add a character and their speech style. Changes save automatically."));self.character_hint.setWordWrap(True);form.addRow(self.character_hint)
        split.addWidget(detail);split.setSizes([240,800]);cl.addWidget(split,1);self.tabs.addTab(chars,self.text("人物","Characters"))
        self.character_timer=QTimer(self);self.character_timer.setSingleShot(True);self.character_timer.timeout.connect(self.save_character)
        self.characters.currentRowChanged.connect(self.select_character)
        for signal in (self.search.textChanged,self.category.currentIndexChanged,self.sort.currentIndexChanged):signal.connect(self.refresh_terms)
    def text(self,cn,en):return cn if self.host.language.language=="zh_CN" else en
    def load(self):
        self.save_character()
        self.service=GlossaryService(self.host.service.connection);self.refresh_terms();self.refresh_characters()
    def refresh_terms(self,*args):
        if not self.service:return
        rows=self.service.terms(self.search.text(),self.category.currentData(),self.sort.currentIndex()==1);conflicts=self.service.conflicts();self.loading=True;self.table.setRowCount(len(rows))
        for n,r in enumerate(rows):
            for col,val in enumerate((r["source_term"],r["target_term"],self.categories.get(r["category"],self.categories["other"]),r["note"],self.text("⚠ 冲突","Conflict") if r["source_term"].casefold() in conflicts else "")):
                item=QTableWidgetItem(val);item.setData(Qt.ItemDataRole.UserRole,r);item.setToolTip(val)
                if col in (2,4):item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(n,col,item)
        self.loading=False;self.stack.setCurrentIndex(1 if rows else 0);self.empty_title.setText(self.text("没有搜索结果","No matches") if self.search.text() or self.category.currentData() else self.text("还没有术语","No terms yet"))
        self.summary.setText(self.text(f"{len(self.service.terms())} 条术语 · {len(self.service.characters())} 个人物 · {len(conflicts)} 条冲突",f"{len(self.service.terms())} terms · {len(self.service.characters())} characters · {len(conflicts)} conflicts"))
    def add(self):
        if self.service and exec_dialog(TermEditor(self)):self.refresh_terms()
    def double_click(self,row,col):
        if col==2 and exec_dialog(TermEditor(self,self.table.item(row,0).data(Qt.ItemDataRole.UserRole))):self.refresh_terms()
    def inline_save(self,row,col):
        if self.loading or col in (2,4):return
        record=dict(self.table.item(row,0).data(Qt.ItemDataRole.UserRole));record[("source_term","target_term","category","note","status")[col]]=self.table.item(row,col).text()
        try:self.service.save(record,record["id"]);self.message.setText(self.text("已保存","Saved"));self.refresh_terms()
        except ValueError as e:self.message.setText(str(e));self.refresh_terms()
    def delete(self):
        row=self.table.currentRow()
        if row>=0:self.service.delete(self.table.item(row,0).data(Qt.ItemDataRole.UserRole)["id"]);self.refresh_terms()
    def clean(self):
        with self.service.db:self.service.db.execute("DELETE FROM glossary WHERE project_id=? AND (trim(source_term)='' OR trim(target_term)='')",(self.service.project_id,))
        self.refresh_terms()
    def import_csv(self):
        path,_=QFileDialog.getOpenFileName(self,self.text("导入术语 CSV","Import glossary CSV"),"","CSV (*.csv)")
        if not path:return
        try:
            from pathlib import Path
            result=self.service.import_csv(Path(path).read_text(encoding="utf-8-sig"));self.message.setText(self.text(f"成功 {result['success']} · 跳过 {result['skipped']} · 冲突 {result['conflicts']}",str(result)));self.refresh_terms()
        except (OSError,ValueError) as e:QMessageBox.warning(self,self.text("CSV 导入失败","CSV import failed"),str(e))
    def export_csv(self):
        path,_=QFileDialog.getSaveFileName(self,self.text("导出术语 CSV","Export glossary CSV"),"glossary.csv","CSV (*.csv)")
        if path:
            try:
                from pathlib import Path
                Path(path).write_text(self.service.export_csv(),encoding="utf-8-sig")
            except OSError as e:QMessageBox.warning(self,self.text("导出失败","Export failed"),str(e))
    def refresh_characters(self):
        self.loading=True;self.characters.clear();self.character_id=None;self.character_timer.stop()
        for r in self.service.characters():item=QListWidgetItem(r["name"]);item.setData(Qt.ItemDataRole.UserRole,r);self.characters.addItem(item)
        self.loading=False
        if self.characters.count():self.characters.setCurrentRow(0)
        else:
            self.character_id=None
            for f in self.character_fields.values():f.setEnabled(False);f.clear()
        self.refresh_terms()
    def select_character(self,row):
        if self.loading:return
        self.save_character()
        self.loading=True;record=self.characters.item(row).data(Qt.ItemDataRole.UserRole) if row>=0 else {};self.character_id=record.get("id")
        for key,field in self.character_fields.items():
            field.setEnabled(row>=0)
            if isinstance(field,QPlainTextEdit):field.setPlainText(record.get(key,""))
            else:field.setText(record.get(key,""))
        self.loading=False
    def schedule_character(self):
        if not self.loading:self.character_timer.start(300)
    def save_character(self):
        if self.loading or not self.character_id:return
        self.character_timer.stop();values={k:f.toPlainText() if isinstance(f,QPlainTextEdit) else f.text() for k,f in self.character_fields.items()}
        try:
            self.service.save_character(values,self.character_id);self.character_hint.setText(self.text("已自动保存","Saved automatically"));item=next((self.characters.item(n) for n in range(self.characters.count()) if self.characters.item(n).data(Qt.ItemDataRole.UserRole).get("id")==self.character_id),None)
            if item:item.setText(values["name"]);item.setData(Qt.ItemDataRole.UserRole,{**values,"id":self.character_id})
        except ValueError as e:self.character_hint.setText(str(e))
    def add_character(self):
        self.save_character();cid=self.service.save_character({"name":self.text("新人物","New character")});self.refresh_characters()
        for n in range(self.characters.count()):
            if self.characters.item(n).data(Qt.ItemDataRole.UserRole)["id"]==cid:self.characters.setCurrentRow(n);self.character_fields["name"].setFocus();self.character_fields["name"].selectAll()
    def delete_character(self):
        if self.character_id:self.character_timer.stop();self.service.delete_character(self.character_id);self.refresh_characters()

    def history(self,redo=False):
        from app.history import HistoryService
        self.save_character()
        service=HistoryService(self.service.db)
        if redo:service.redo()
        else:service.undo()
        self.refresh_terms();self.refresh_characters()
