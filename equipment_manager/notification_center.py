from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,QCheckBox,QComboBox,QHBoxLayout,QHeaderView,QLabel,QPushButton,
    QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget
)

from table_productivity import install_table_productivity


def _item(value):
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);t.setAlternatingRowColors(True)
    install_table_productivity(t,headers[0] if headers else "Notifications")
    return t


class NotificationCenter(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.rows=[]
        root=QVBoxLayout(self);head=QHBoxLayout()
        title=QLabel("Notifications");title.setStyleSheet("font-size:20pt;font-weight:800")
        self.unread_only=QCheckBox("Unread only");self.unread_only.setChecked(True);self.unread_only.stateChanged.connect(self.refresh)
        self.category=QComboBox();self.category.addItem("All categories","");self.category.currentIndexChanged.connect(self.refresh)
        mark=QPushButton("Mark Selected Read");mark.clicked.connect(self.mark_selected)
        mark_all=QPushButton("Mark All Read");mark_all.clicked.connect(self.mark_all)
        dismiss=QPushButton("Dismiss Selected");dismiss.clicked.connect(self.dismiss_selected)
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh)
        head.addWidget(title);head.addStretch(1);head.addWidget(self.category);head.addWidget(self.unread_only);head.addWidget(mark);head.addWidget(mark_all);head.addWidget(dismiss);head.addWidget(refresh);root.addLayout(head)
        self.summary=QLabel();self.summary.setStyleSheet("color:#647581");root.addWidget(self.summary)
        self.table=_table(["Time","Severity","Category","Title","Details","Equipment","Record Type","Record Key","Read"])
        self.table.doubleClicked.connect(self.open_selected);root.addWidget(self.table,1)
        self.refresh()

    def refresh(self):
        all_rows=self.db.list_notifications(self.user["username"],False,False,1000)
        categories=sorted({x.category for x in all_rows})
        current=str(self.category.currentData() or "")
        self.category.blockSignals(True);self.category.clear();self.category.addItem("All categories","")
        for value in categories:self.category.addItem(value.replace("_"," ").title(),value)
        idx=self.category.findData(current)
        if idx>=0:self.category.setCurrentIndex(idx)
        self.category.blockSignals(False)
        rows=all_rows
        if self.unread_only.isChecked():rows=[x for x in rows if x.read_at is None]
        category=str(self.category.currentData() or "")
        if category:rows=[x for x in rows if x.category==category]
        self.rows=rows;self.table.setRowCount(len(rows))
        for r,row in enumerate(rows):
            vals=[row.created_at,row.severity,row.category,row.title,row.body,row.equipment_id,row.entity_type,row.entity_key,"Yes" if row.read_at else "No"]
            for c,val in enumerate(vals):self.table.setItem(r,c,_item(val))
        unread=self.db.unread_notification_count(self.user["username"])
        self.summary.setText(f"{unread} unread · {len(all_rows)} active notification(s)")

    def _selected_rows(self):
        indexes=sorted({x.row() for x in self.table.selectedIndexes()})
        return [self.rows[i] for i in indexes if 0<=i<len(self.rows)]

    def mark_selected(self):
        for row in self._selected_rows():self.db.mark_notification_read(row.id,self.user["username"],True)
        self.refresh()

    def mark_all(self):
        self.db.mark_all_notifications_read(self.user["username"]);self.refresh()

    def dismiss_selected(self):
        for row in self._selected_rows():self.db.dismiss_notification(row.id,self.user["username"])
        self.refresh()

    def open_selected(self):
        rows=self._selected_rows()
        if not rows:return
        row=rows[0]
        self.db.mark_notification_read(row.id,self.user["username"],True)
        self.refresh()
        if row.entity_type and row.entity_key:self.open_entity.emit(row.entity_type,row.entity_key,row.equipment_id or "")
