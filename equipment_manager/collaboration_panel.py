from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QAbstractItemView,QHBoxLayout,QHeaderView,QLabel,QMessageBox,QPushButton,
    QTableWidget,QTableWidgetItem,QTextEdit,QVBoxLayout,QWidget
)

from table_productivity import install_table_productivity


def _item(value):
    if isinstance(value,datetime):value=value.strftime("%Y-%m-%d %H:%M")
    return QTableWidgetItem("" if value is None else str(value))


class CollaborationPanel(QWidget):
    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.entity_type="";self.entity_key="";self.equipment_id="";self.rows=[]
        root=QVBoxLayout(self);head=QHBoxLayout()
        self.context=QLabel("Discussion");self.context.setStyleSheet("font-weight:700")
        self.watch=QPushButton("Watch");self.watch.clicked.connect(self.toggle_watch)
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh)
        self.watchers=QLabel();self.watchers.setStyleSheet("color:#647581")
        head.addWidget(self.context);head.addWidget(self.watchers);head.addStretch(1);head.addWidget(self.watch);head.addWidget(refresh);root.addLayout(head)
        self.table=QTableWidget(0,3);self.table.setHorizontalHeaderLabels(["Time","User","Comment"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True);install_table_productivity(self.table,"Discussion")
        root.addWidget(self.table,2)
        self.editor=QTextEdit();self.editor.setPlaceholderText("Add context, decision, update, or @mention a username…");self.editor.setMaximumHeight(110);root.addWidget(self.editor)
        foot=QHBoxLayout();hint=QLabel("Tip: use @username to place this record in that person's My Work queue.");hint.setStyleSheet("color:#647581")
        post=QPushButton("Post comment");post.clicked.connect(self.post)
        foot.addWidget(hint);foot.addStretch(1);foot.addWidget(post);root.addLayout(foot)
        self.post_button=post;self.set_entity("","")

    def set_entity(self,entity_type: str,entity_key: str,equipment_id: str=""):
        self.entity_type=(entity_type or "").upper();self.entity_key=str(entity_key or "");self.equipment_id=equipment_id or ""
        self.refresh()

    def refresh(self):
        enabled=bool(self.entity_type and self.entity_key);self.post_button.setEnabled(enabled);self.watch.setEnabled(enabled);self.editor.setEnabled(enabled)
        if not enabled:
            self.context.setText("Discussion");self.rows=[];self.table.setRowCount(0);self.watchers.setText("");self.watch.setText("Watch");return
        self.context.setText(f"Discussion · {self.entity_type}:{self.entity_key}")
        self.rows=self.db.list_record_comments(self.entity_type,self.entity_key)
        self.table.setRowCount(len(self.rows))
        for r,row in enumerate(self.rows):
            for c,value in enumerate([row.created_at,row.created_by,row.body]):self.table.setItem(r,c,_item(value))
        watchers=self.db.list_record_watchers(self.entity_type,self.entity_key)
        names=[x.username for x in watchers];self.watchers.setText(f"{len(names)} watcher(s)" + (f": {', '.join(names[:6])}" if names else ""))
        watching=self.db.is_watching_record(self.entity_type,self.entity_key,self.user["username"])
        self.watch.setText("Unwatch" if watching else "Watch")

    def toggle_watch(self):
        if not self.entity_key:return
        watching=self.db.is_watching_record(self.entity_type,self.entity_key,self.user["username"])
        try:self.db.set_record_watch(self.entity_type,self.entity_key,self.user["username"],not watching);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Discussion",str(exc))

    def post(self):
        body=self.editor.toPlainText().strip()
        if not body:return
        try:
            self.db.add_record_comment(self.entity_type,self.entity_key,body,self.user["username"],self.equipment_id,"COLLABORATION")
            self.editor.clear();self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Discussion",str(exc))
