from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QAbstractItemView,QHBoxLayout,QHeaderView,QInputDialog,QLabel,QMessageBox,
    QPushButton,QTableWidget,QTableWidgetItem,QTextEdit,QVBoxLayout,QWidget,
)

from table_productivity import install_table_productivity


def _item(value):
    if isinstance(value,datetime):value=value.strftime("%Y-%m-%d %H:%M")
    return QTableWidgetItem("" if value is None else str(value))


class CollaborationPanel(QWidget):
    def __init__(self,db,user,entity_type="",entity_key="",equipment_id="",parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.entity_type="";self.entity_key="";self.equipment_id="";self.comments=[]
        root=QVBoxLayout(self);head=QHBoxLayout()
        self.context=QLabel("Select a record to collaborate.");self.context.setStyleSheet("color:#647581")
        self.watch=QPushButton("Watch");self.watch.clicked.connect(self.toggle_watch)
        self.watchers=QLabel();self.watchers.setStyleSheet("color:#647581")
        head.addWidget(self.context);head.addStretch(1);head.addWidget(self.watchers);head.addWidget(self.watch);root.addLayout(head)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(["By","Comment","Created","Edited","Ver"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.table.setAlternatingRowColors(True)
        install_table_productivity(self.table,"Comments")
        root.addWidget(self.table,2)
        self.editor=QTextEdit();self.editor.setPlaceholderText("Add a comment. Mention an EMS user with @username.");self.editor.setMaximumHeight(110);root.addWidget(self.editor)
        buttons=QHBoxLayout();add=QPushButton("Post comment");edit=QPushButton("Edit mine");remove=QPushButton("Remove mine")
        add.clicked.connect(self.add_comment);edit.clicked.connect(self.edit_comment);remove.clicked.connect(self.remove_comment)
        buttons.addWidget(add);buttons.addWidget(edit);buttons.addWidget(remove);buttons.addStretch(1);root.addLayout(buttons)
        self.set_entity(entity_type,entity_key,equipment_id)

    def set_entity(self,entity_type,entity_key,equipment_id=""):
        self.entity_type=(entity_type or "").strip().upper();self.entity_key=str(entity_key or "");self.equipment_id=equipment_id or "";self.refresh()

    def refresh(self):
        enabled=bool(self.entity_type and self.entity_key);self.editor.setEnabled(enabled);self.watch.setEnabled(enabled)
        if not enabled:
            self.context.setText("Select a record to collaborate.");self.comments=[];self.table.setRowCount(0);self.watchers.setText("");return
        self.context.setText(f"{self.entity_type}:{self.entity_key}")
        self.comments=self.db.list_record_comments(self.entity_type,self.entity_key)
        self.table.setRowCount(len(self.comments))
        for r,row in enumerate(self.comments):
            vals=[row.created_by,row.body,row.created_at,row.edited_at,row.version]
            for c,val in enumerate(vals):self.table.setItem(r,c,_item(val))
        watching=self.db.is_record_watching(self.entity_type,self.entity_key,self.user["username"])
        self.watch.setText("Unwatch" if watching else "Watch")
        watcher_names=[x.username for x in self.db.list_record_watchers(self.entity_type,self.entity_key)]
        self.watchers.setText(("Watching: "+", ".join(watcher_names[:8])) if watcher_names else "No watchers")

    def selected(self):
        i=self.table.currentRow();return self.comments[i] if 0<=i<len(self.comments) else None

    def add_comment(self):
        text=self.editor.toPlainText().strip()
        if not text:return
        try:self.db.add_record_comment(self.entity_type,self.entity_key,text,self.user["username"],self.equipment_id);self.editor.clear();self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Comment",str(exc))

    def edit_comment(self):
        row=self.selected()
        if not row:return
        text,ok=QInputDialog.getMultiLineText(self,"Edit comment","Comment",row.body)
        if not ok:return
        try:self.db.edit_record_comment(row.id,text,self.user["username"],row.version);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Comment",str(exc))

    def remove_comment(self):
        row=self.selected()
        if not row:return
        if QMessageBox.question(self,"Remove comment","Remove this comment?")!=QMessageBox.StandardButton.Yes:return
        try:self.db.remove_record_comment(row.id,self.user["username"]);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Comment",str(exc))

    def toggle_watch(self):
        if not self.entity_key:return
        current=self.db.is_record_watching(self.entity_type,self.entity_key,self.user["username"])
        try:self.db.set_record_watch(self.entity_type,self.entity_key,self.user["username"],not current);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Watch record",str(exc))
