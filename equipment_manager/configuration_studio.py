from __future__ import annotations

import json
from PySide6.QtWidgets import (
    QAbstractItemView,QCheckBox,QComboBox,QDialog,QDialogButtonBox,QFormLayout,
    QHBoxLayout,QHeaderView,QLabel,QLineEdit,QMessageBox,QPushButton,QSpinBox,
    QTabWidget,QTableWidget,QTableWidgetItem,QTextEdit,QVBoxLayout,QWidget
)
from table_productivity import install_table_productivity


def _item(value):return QTableWidgetItem("" if value is None else str(value))
def _selected(table,rows):
    i=table.currentRow();return rows[i] if 0<=i<len(rows) else None
def _fill(table,rows,fields):
    table.setRowCount(len(rows))
    for r,row in enumerate(rows):
        for c,field in enumerate(fields):table.setItem(r,c,_item(getattr(row,field,"")))


def _table(headers):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers);t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);t.setAlternatingRowColors(True)
    install_table_productivity(t,headers[0] if headers else "Configuration");return t


class FieldDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Custom Field Definition");self.setMinimumWidth(620)
        f=QFormLayout(self);self.entity=QComboBox();self.entity.addItems(["EQUIPMENT","TICKET","WORK_ORDER","PM_TASK","PM_EXECUTION","QUALIFICATION","RELEASE","ENDORSEMENT"])
        self.key=QLineEdit();self.scope=QLineEdit();self.label=QLineEdit();self.dtype=QComboBox();self.dtype.addItems(["TEXT","NUMBER","BOOLEAN","CHOICE","DATE"])
        self.choices=QLineEdit();self.required=QCheckBox();self.active=QCheckBox();self.active.setChecked(True);self.order=QSpinBox();self.order.setRange(0,9999);self.order.setValue(100)
        self.scope.setPlaceholderText("Optional equipment type / local scope");self.choices.setPlaceholderText('For CHOICE: ["Option A","Option B"]')
        for label,w in [("Entity",self.entity),("Field key",self.key),("Applies to",self.scope),("Label",self.label),("Type",self.dtype),("Choices JSON",self.choices),("Required",self.required),("Active",self.active),("Sort order",self.order)]:f.addRow(label,w)
        if row:
            self.entity.setCurrentText(row.entity_type);self.entity.setEnabled(False);self.key.setText(row.field_key);self.key.setReadOnly(True);self.scope.setText(row.applies_to);self.scope.setReadOnly(True)
            self.label.setText(row.label);self.dtype.setCurrentText(row.data_type);self.choices.setText(row.choices_json);self.required.setChecked(row.required);self.active.setChecked(row.active);self.order.setValue(row.sort_order)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
    def data(self):
        return {"entity_type":self.entity.currentText(),"field_key":self.key.text().strip(),"applies_to":self.scope.text().strip(),"label":self.label.text().strip(),"data_type":self.dtype.currentText(),"choices_json":self.choices.text().strip() or "[]","required":self.required.isChecked(),"active":self.active.isChecked(),"sort_order":self.order.value()}


class TemplateDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Record Template");self.resize(720,600)
        f=QFormLayout(self);self.template=QLineEdit();self.entity=QComboBox();self.entity.addItems(["TICKET","WORK_ORDER","PM_TASK","QUALIFICATION"])
        self.name=QLineEdit();self.scope=QLineEdit();self.payload=QTextEdit();self.active=QCheckBox();self.active.setChecked(True)
        self.payload.setPlaceholderText('{"title":"Vacuum instability","priority":"P2","owner":"..."}')
        for label,w in [("Template ID",self.template),("Entity",self.entity),("Name",self.name),("Applies to",self.scope),("Payload JSON",self.payload),("Active",self.active)]:f.addRow(label,w)
        if row:
            self.template.setText(row.template_id);self.template.setReadOnly(True);self.entity.setCurrentText(row.entity_type);self.name.setText(row.name);self.scope.setText(row.applies_to);self.payload.setPlainText(json.dumps(json.loads(row.payload_json or "{}"),indent=2,sort_keys=True));self.active.setChecked(row.active)
        else:self.payload.setPlainText("{}")
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self._accept);b.rejected.connect(self.reject);f.addRow(b)
    def _accept(self):
        try:
            value=json.loads(self.payload.toPlainText() or "{}")
            if not isinstance(value,dict):raise ValueError("Template payload must be an object.")
        except Exception as exc:QMessageBox.critical(self,"Template",str(exc));return
        self.accept()
    def data(self):
        return {"template_id":self.template.text().strip(),"entity_type":self.entity.currentText(),"name":self.name.text().strip(),"applies_to":self.scope.text().strip(),"payload_json":self.payload.toPlainText().strip() or "{}","active":self.active.isChecked(),"created_by":""}


class ConfigurationStudioWorkspace(QWidget):
    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.fields=[];self.templates=[]
        root=QVBoxLayout(self);head=QHBoxLayout();title=QLabel("Configuration Studio");title.setStyleSheet("font-size:20pt;font-weight:800")
        note=QLabel("Adapt local forms and reusable record defaults without changing Python source.");note.setStyleSheet("color:#647581")
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh);head.addWidget(title);head.addWidget(note);head.addStretch(1);head.addWidget(refresh);root.addLayout(head)
        tabs=QTabWidget();root.addWidget(tabs,1)
        fw=QWidget();fv=QVBoxLayout(fw);fh=QHBoxLayout();add=QPushButton("New Field");edit=QPushButton("Edit Field");add.clicked.connect(self.add_field);edit.clicked.connect(self.edit_field);fh.addWidget(add);fh.addWidget(edit);fh.addStretch(1);fv.addLayout(fh)
        self.field_table=_table(["Entity","Key","Scope","Label","Type","Choices","Required","Active","Order","Ver"]);fv.addWidget(self.field_table);tabs.addTab(fw,"Custom Fields")
        tw=QWidget();tv=QVBoxLayout(tw);th=QHBoxLayout();addt=QPushButton("New Template");editt=QPushButton("Edit Template");addt.clicked.connect(self.add_template);editt.clicked.connect(self.edit_template);th.addWidget(addt);th.addWidget(editt);th.addStretch(1);tv.addLayout(th)
        self.template_table=_table(["Template","Entity","Name","Scope","Active","Created By","Ver"]);tv.addWidget(self.template_table);tabs.addTab(tw,"Record Templates")
        self.refresh()
    def refresh(self):
        self.fields=self.db.list_custom_field_definitions(active_only=False);_fill(self.field_table,self.fields,["entity_type","field_key","applies_to","label","data_type","choices_json","required","active","sort_order","version"])
        self.templates=self.db.list_record_templates(active_only=False);_fill(self.template_table,self.templates,["template_id","entity_type","name","applies_to","active","created_by","version"])
    def add_field(self):
        d=FieldDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_custom_field_definition(d.data());self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Custom field",str(exc))
    def edit_field(self):
        row=_selected(self.field_table,self.fields)
        if not row:return
        d=FieldDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_custom_field_definition(d.data(),row.version);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Custom field",str(exc))
    def add_template(self):
        d=TemplateDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            data=d.data();data["created_by"]=self.user["username"]
            try:self.db.save_record_template(data);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Template",str(exc))
    def edit_template(self):
        row=_selected(self.template_table,self.templates)
        if not row:return
        d=TemplateDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            data=d.data();data["created_by"]=row.created_by or self.user["username"]
            try:self.db.save_record_template(data,row.version);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Template",str(exc))
