from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,QHBoxLayout,QHeaderView,QLabel,QLineEdit,QPushButton,
    QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget,
)

from table_productivity import install_table_productivity
from feedback import notify


def _item(value):
    if isinstance(value,datetime):value=value.strftime("%Y-%m-%d %H:%M")
    return QTableWidgetItem("" if value is None else str(value))


class TroubleshootingLibrary(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.rows=[]
        root=QVBoxLayout(self);head=QHBoxLayout()
        title=QLabel("Troubleshooting History");title.setStyleSheet("font-size:20pt;font-weight:800")
        self.summary=QLabel();self.summary.setStyleSheet("color:#647581")
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh)
        head.addWidget(title);head.addWidget(self.summary);head.addStretch(1);head.addWidget(refresh);root.addLayout(head)
        controls=QHBoxLayout()
        self.search=QLineEdit();self.search.setPlaceholderText("Search symptom, alarm code, lot number, check, action, root cause, fix…")
        self.equipment=QLineEdit();self.equipment.setPlaceholderText("Optional equipment ID")
        controls.addWidget(self.search,3);controls.addWidget(self.equipment,1);root.addLayout(controls)
        self.table=QTableWidget(0,15);self.table.setHorizontalHeaderLabels([
            "Ticket","Equipment","Updated","Priority","Status","Symptom","Lot(s)","Alarm(s)",
            "Check","Result","Action","Root Cause","Final Fix","Images","Owner",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True);self.table.doubleClicked.connect(self.open_selected)
        install_table_productivity(self.table,"Troubleshooting_History");root.addWidget(self.table,1)
        self.hint=QLabel("Double-click a case to open the full incident, screenshots, investigation history, RCA and actions.")
        self.hint.setStyleSheet("color:#647581");root.addWidget(self.hint)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(350);self.timer.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda:self.timer.start());self.equipment.textChanged.connect(lambda:self.timer.start())
        self.refresh()

    def refresh(self):
        try:self.rows=self.db.search_troubleshooting_cases(self.search.text(),self.equipment.text(),250)
        except Exception as exc:
            self.rows=[];self.summary.setText(f"Search unavailable: {exc}");self.table.setRowCount(0);return
        self.summary.setText(f"{len(self.rows)} case(s) · newest relevant history first")
        self.table.setRowCount(len(self.rows))
        fields=[
            "ticket_no","equipment_id","updated_at","priority","status","title","lots","alarms",
            "last_check","last_result","last_action","root_cause","corrective_action","screenshot_count","owner",
        ]
        for r,row in enumerate(self.rows):
            for c,field in enumerate(fields):self.table.setItem(r,c,_item(row.get(field,"")))
        if not self.rows and (self.search.text().strip() or self.equipment.text().strip()):
            self.hint.setText("No troubleshooting cases matched the current search.")
        else:
            self.hint.setText("Double-click a case to open the full incident, screenshots, investigation history, RCA and actions.")

    def open_selected(self):
        r=self.table.currentRow()
        if 0<=r<len(self.rows):
            row=self.rows[r]
            self.open_entity.emit("TICKET",row["ticket_no"],row["equipment_id"])
            notify(f"Opening troubleshooting case {row['ticket_no']}.")
