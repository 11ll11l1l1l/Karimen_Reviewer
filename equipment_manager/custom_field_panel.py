from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,QHeaderView,QInputDialog,QLabel,QMessageBox,QPushButton,
    QTableWidget,QTableWidgetItem,QVBoxLayout,QHBoxLayout,QWidget
)
from table_productivity import install_table_productivity


def _item(value):
    return QTableWidgetItem("" if value is None else str(value))


class CustomFieldPanel(QWidget):
    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.entity_type="";self.entity_key="";self.applies_to="";self.rows=[]
        root=QVBoxLayout(self);head=QHBoxLayout()
        self.title=QLabel("Configured Fields");self.title.setStyleSheet("font-weight:700")
        edit=QPushButton("Edit selected");edit.clicked.connect(self.edit_selected)
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh)
        head.addWidget(self.title);head.addStretch(1);head.addWidget(edit);head.addWidget(refresh);root.addLayout(head)
        self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(["Field","Value","Type","Required","Updated By","Updated"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True);self.table.doubleClicked.connect(self.edit_selected);install_table_productivity(self.table,"Custom Fields")
        root.addWidget(self.table)
        self.note=QLabel("No configured fields for this record.");self.note.setStyleSheet("color:#647581");root.addWidget(self.note)

    def set_entity(self,entity_type: str,entity_key: str,applies_to: str=""):
        self.entity_type=(entity_type or "").upper();self.entity_key=str(entity_key or "");self.applies_to=applies_to or "";self.refresh()

    def refresh(self):
        self.rows=self.db.custom_field_values(self.entity_type,self.entity_key,self.applies_to) if self.entity_type and self.entity_key else []
        self.table.setRowCount(len(self.rows))
        for r,row in enumerate(self.rows):
            vals=[row["label"],row["value"],row["data_type"],"Yes" if row["required"] else "No",row["updated_by"],row["updated_at"]]
            for c,val in enumerate(vals):self.table.setItem(r,c,_item(val))
        self.note.setVisible(not self.rows)

    def edit_selected(self):
        idx=self.table.currentRow()
        if not (0<=idx<len(self.rows)):return
        row=self.rows[idx];current=row["value"]
        if row["data_type"]=="BOOLEAN":
            value,ok=QInputDialog.getItem(self,row["label"],row["label"],["true","false"],0 if current is not False else 1,False)
        elif row["data_type"]=="CHOICE":
            choices=[str(x) for x in row["choices"]]
            start=choices.index(str(current)) if current is not None and str(current) in choices else 0
            value,ok=QInputDialog.getItem(self,row["label"],row["label"],choices,start,False)
        else:
            value,ok=QInputDialog.getText(self,row["label"],f"{row['label']} ({row['data_type']})",text="" if current is None else str(current))
        if not ok:return
        try:self.db.set_custom_field_value(self.entity_type,self.entity_key,row["field_key"],value,self.user["username"],self.applies_to);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Configured field",str(exc))
