from __future__ import annotations

import json
from datetime import datetime

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,QComboBox,QDateEdit,QDialog,QDialogButtonBox,QDoubleSpinBox,
    QFormLayout,QHBoxLayout,QHeaderView,QInputDialog,QLabel,QLineEdit,QMessageBox,
    QPushButton,QSpinBox,QTableWidget,QTableWidgetItem,QTabWidget,QTextEdit,
    QVBoxLayout,QWidget,QAbstractItemView,
)

from table_productivity import install_table_productivity


def _item(value):
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setAlternatingRowColors(True)
    install_table_productivity(t,headers[0] if headers else "Configuration")
    return t


class CustomFieldDefinitionDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Custom Field Definition");self.resize(620,560)
        f=QFormLayout(self)
        self.field_id=QLineEdit();self.entity_type=QComboBox();self.entity_type.addItems(["EQUIPMENT","TICKET","WORK_ORDER","PM_TASK","QUALIFICATION","RELEASE","ENDORSEMENT"])
        self.label=QLineEdit();self.data_type=QComboBox();self.data_type.addItems(["TEXT","NUMBER","BOOLEAN","DATE","CHOICE"])
        self.scope_type=QComboBox();self.scope_type.addItems(["GLOBAL","EQUIPMENT_TYPE","AREA"]);self.scope_key=QLineEdit()
        self.required=QCheckBox("Required");self.choices=QTextEdit();self.choices.setPlaceholderText('["Option A","Option B"]')
        self.default=QLineEdit();self.default.setPlaceholderText("JSON value, e.g. null, 0, true, or \"Option A\"")
        self.help=QTextEdit();self.order=QSpinBox();self.order.setRange(0,10000);self.order.setValue(100);self.active=QCheckBox("Active");self.active.setChecked(True)
        for label,w in [("Field ID",self.field_id),("Entity",self.entity_type),("Label",self.label),("Data type",self.data_type),("Scope",self.scope_type),("Scope key",self.scope_key),("",self.required),("Choices JSON",self.choices),("Default JSON",self.default),("Help text",self.help),("Display order",self.order),("",self.active)]:f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:
            self.field_id.setText(row.field_id);self.field_id.setEnabled(False);self.entity_type.setCurrentText(row.entity_type);self.label.setText(row.label);self.data_type.setCurrentText(row.data_type)
            self.scope_type.setCurrentText(row.scope_type);self.scope_key.setText(row.scope_key);self.required.setChecked(row.required)
            self.choices.setPlainText(row.choices_json or "[]");self.default.setText(row.default_json or "null");self.help.setPlainText(row.help_text);self.order.setValue(row.display_order);self.active.setChecked(row.active)

    def data(self):
        return {
            "field_id":self.field_id.text().strip(),"entity_type":self.entity_type.currentText(),"label":self.label.text().strip(),
            "data_type":self.data_type.currentText(),"scope_type":self.scope_type.currentText(),"scope_key":self.scope_key.text().strip(),
            "required":self.required.isChecked(),"choices_json":self.choices.toPlainText().strip() or "[]",
            "default_json":self.default.text().strip() or "null","help_text":self.help.toPlainText().strip(),
            "display_order":self.order.value(),"active":self.active.isChecked(),
        }


class RecordTemplateDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Record Template");self.resize(700,580)
        f=QFormLayout(self)
        self.template_id=QLineEdit();self.entity_type=QComboBox();self.entity_type.addItems(["EQUIPMENT","TICKET","WORK_ORDER","PM_TASK","QUALIFICATION","RELEASE","ENDORSEMENT"])
        self.name=QLineEdit();self.scope_type=QComboBox();self.scope_type.addItems(["GLOBAL","EQUIPMENT_TYPE","AREA"]);self.scope_key=QLineEdit()
        self.payload=QTextEdit();self.payload.setPlaceholderText('{"priority":"P2","owner":"Equipment Engineering"}');self.active=QCheckBox("Active");self.active.setChecked(True)
        for label,w in [("Template ID",self.template_id),("Entity",self.entity_type),("Name",self.name),("Scope",self.scope_type),("Scope key",self.scope_key),("Payload JSON",self.payload),("",self.active)]:f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.validate_accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:
            self.template_id.setText(row.template_id);self.template_id.setEnabled(False);self.entity_type.setCurrentText(row.entity_type);self.name.setText(row.name);self.scope_type.setCurrentText(row.scope_type);self.scope_key.setText(row.scope_key);self.payload.setPlainText(row.payload_json);self.active.setChecked(row.active)

    def validate_accept(self):
        try:
            payload=json.loads(self.payload.toPlainText() or "{}")
            if not isinstance(payload,dict):raise ValueError("Payload must be a JSON object.")
        except Exception as exc:QMessageBox.warning(self,"Template",str(exc));return
        self.accept()

    def data(self):
        return {
            "template_id":self.template_id.text().strip(),"entity_type":self.entity_type.currentText(),"name":self.name.text().strip(),
            "scope_type":self.scope_type.currentText(),"scope_key":self.scope_key.text().strip(),"payload_json":self.payload.toPlainText().strip() or "{}",
            "active":self.active.isChecked(),
        }


class CustomFieldsPanel(QWidget):
    def __init__(self,db,user,entity_type="",entity_key="",equipment_id="",parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.entity_type=entity_type;self.entity_key=str(entity_key);self.equipment_id=equipment_id;self.definitions=[];self.widgets={}
        self.root=QVBoxLayout(self);self.form_widget=QWidget();self.form=QFormLayout(self.form_widget);self.root.addWidget(self.form_widget)
        self.save_button=QPushButton("Save custom fields");self.save_button.clicked.connect(self.save);self.root.addWidget(self.save_button);self.root.addStretch(1)
        self.refresh()

    def set_entity(self,entity_type,entity_key,equipment_id=""):
        self.entity_type=(entity_type or "").upper();self.entity_key=str(entity_key or "");self.equipment_id=equipment_id or "";self.refresh()

    def _clear_form(self):
        while self.form.rowCount():self.form.removeRow(0)
        self.widgets={}

    def refresh(self):
        self._clear_form()
        enabled=bool(self.entity_type and self.entity_key);self.save_button.setEnabled(enabled)
        if not enabled:return
        self.definitions=self.db.resolve_custom_field_definitions(self.entity_type,self.equipment_id)
        values=self.db.get_custom_field_values(self.entity_type,self.entity_key)
        if not self.definitions:
            self.form.addRow(QLabel("No custom fields are configured for this record context."));return
        for definition in self.definitions:
            value=values.get(definition.field_id)
            if value is None:
                try:value=json.loads(definition.default_json or "null")
                except Exception:value=None
            kind=definition.data_type
            if kind=="NUMBER":
                w=QDoubleSpinBox();w.setRange(-1e15,1e15);w.setDecimals(6);w.setValue(float(value or 0))
            elif kind=="BOOLEAN":
                w=QCheckBox();w.setChecked(bool(value))
            elif kind=="DATE":
                w=QDateEdit();w.setCalendarPopup(True)
                try:w.setDate(QDate.fromString(str(value),"yyyy-MM-dd") if value else QDate.currentDate())
                except Exception:w.setDate(QDate.currentDate())
            elif kind=="CHOICE":
                w=QComboBox();choices=json.loads(definition.choices_json or "[]");w.addItems([str(x) for x in choices])
                if value is not None:w.setCurrentText(str(value))
            else:
                w=QLineEdit();w.setText("" if value is None else str(value))
            if definition.help_text:w.setToolTip(definition.help_text)
            label=definition.label+(" *" if definition.required else "")
            self.form.addRow(label,w);self.widgets[definition.field_id]=(definition,w)

    def values(self):
        out={}
        for field_id,(definition,w) in self.widgets.items():
            if definition.data_type=="NUMBER":value=w.value()
            elif definition.data_type=="BOOLEAN":value=w.isChecked()
            elif definition.data_type=="DATE":value=w.date().toString("yyyy-MM-dd")
            elif definition.data_type=="CHOICE":value=w.currentText()
            else:value=w.text().strip()
            out[field_id]=value
        return out

    def save(self):
        if not self.entity_key:return
        try:
            self.db.set_custom_field_values(self.entity_type,self.entity_key,self.values(),self.user["username"],self.equipment_id,"CUSTOM-FIELDS")
            QMessageBox.information(self,"Custom fields","Saved.")
        except Exception as exc:QMessageBox.critical(self,"Custom fields",str(exc))


class ConfigurationStudio(QWidget):
    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.fields=[];self.templates=[]
        root=QVBoxLayout(self);head=QHBoxLayout();title=QLabel("Configuration Studio");title.setStyleSheet("font-size:20pt;font-weight:800")
        subtitle=QLabel("Add plant/area-specific fields and reusable record templates without editing Python.");subtitle.setStyleSheet("color:#647581")
        head.addWidget(title);head.addWidget(subtitle);head.addStretch(1);root.addLayout(head)
        tabs=QTabWidget();root.addWidget(tabs,1)
        fw=QWidget();fv=QVBoxLayout(fw);fh=QHBoxLayout();addf=QPushButton("New custom field");editf=QPushButton("Edit selected");addf.clicked.connect(self.add_field);editf.clicked.connect(self.edit_field);fh.addWidget(addf);fh.addWidget(editf);fh.addStretch(1);fv.addLayout(fh)
        self.field_table=_table(["Field ID","Entity","Label","Type","Scope","Scope Key","Required","Order","Active","Version"]);fv.addWidget(self.field_table);tabs.addTab(fw,"Custom Fields")
        tw=QWidget();tv=QVBoxLayout(tw);th=QHBoxLayout();addt=QPushButton("New template");editt=QPushButton("Edit selected");addt.clicked.connect(self.add_template);editt.clicked.connect(self.edit_template);th.addWidget(addt);th.addWidget(editt);th.addStretch(1);tv.addLayout(th)
        self.template_table=_table(["Template ID","Entity","Name","Scope","Scope Key","Active","Payload","Version"]);tv.addWidget(self.template_table);tabs.addTab(tw,"Record Templates")
        self.refresh()

    def refresh(self):
        self.fields=self.db.list_custom_field_definitions();self.field_table.setRowCount(len(self.fields))
        for r,row in enumerate(self.fields):
            vals=[row.field_id,row.entity_type,row.label,row.data_type,row.scope_type,row.scope_key,row.required,row.display_order,row.active,row.version]
            for c,v in enumerate(vals):self.field_table.setItem(r,c,_item(v))
        self.templates=self.db.list_record_templates();self.template_table.setRowCount(len(self.templates))
        for r,row in enumerate(self.templates):
            vals=[row.template_id,row.entity_type,row.name,row.scope_type,row.scope_key,row.active,row.payload_json,row.version]
            for c,v in enumerate(vals):self.template_table.setItem(r,c,_item(v))

    def add_field(self):
        d=CustomFieldDefinitionDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_custom_field_definition(d.data(),self.user["username"]);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Custom field",str(exc))

    def edit_field(self):
        i=self.field_table.currentRow()
        if not 0<=i<len(self.fields):return
        row=self.fields[i];d=CustomFieldDefinitionDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_custom_field_definition(d.data(),self.user["username"],row.version);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Custom field",str(exc))

    def add_template(self):
        d=RecordTemplateDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_record_template(d.data(),self.user["username"]);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Template",str(exc))

    def edit_template(self):
        i=self.template_table.currentRow()
        if not 0<=i<len(self.templates):return
        row=self.templates[i];d=RecordTemplateDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_record_template(d.data(),self.user["username"],row.version);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Template",str(exc))
