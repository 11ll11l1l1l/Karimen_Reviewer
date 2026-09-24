from __future__ import annotations

import json
from datetime import datetime

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QAbstractItemView,QCheckBox,QComboBox,QDateEdit,QDialog,QDialogButtonBox,
    QDoubleSpinBox,QFileDialog,QFormLayout,QHBoxLayout,QHeaderView,QInputDialog,QLabel,QLineEdit,
    QMessageBox,QPushButton,QTableWidget,QTableWidgetItem,QTabWidget,QTextEdit,
    QVBoxLayout,QWidget,
)

from table_productivity import install_table_productivity


def _item(value):
    if isinstance(value,datetime):value=value.strftime("%Y-%m-%d %H:%M")
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);t.setAlternatingRowColors(True)
    install_table_productivity(t,headers[0] if headers else "Configuration")
    return t


def _selected(table,rows):
    i=table.currentRow();return rows[i] if 0<=i<len(rows) else None


class ConfigOptionDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Configuration Option")
        f=QFormLayout(self);self.category=QLineEdit();self.code=QLineEdit();self.label=QLineEdit();self.order=QDoubleSpinBox();self.order.setDecimals(0);self.order.setRange(0,99999);self.active=QCheckBox("Active");self.active.setChecked(True);self.meta=QTextEdit();self.meta.setPlaceholderText("{}")
        for label,w in [("Category",self.category),("Code",self.code),("Label",self.label),("Sort order",self.order),("",self.active),("Metadata JSON",self.meta)]:f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:
            self.category.setText(row.category);self.code.setText(row.code);self.label.setText(row.label);self.order.setValue(row.sort_order);self.active.setChecked(row.active);self.meta.setPlainText(row.metadata_json or "{}")
            self.category.setReadOnly(True);self.code.setReadOnly(True)
    def data(self):
        return {"category":self.category.text().strip(),"code":self.code.text().strip(),"label":self.label.text().strip(),"sort_order":int(self.order.value()),"active":self.active.isChecked(),"metadata_json":self.meta.toPlainText().strip() or "{}"}


class PolicyOptionDialog(QDialog):
    def __init__(self,category: str,row=None,parent=None):
        super().__init__(parent);self.category=category;self.row=row;self.setWindowTitle(category.replace("_"," ").title());self.resize(620,520)
        f=QFormLayout(self)
        self.code=QLineEdit();self.label=QLineEdit();self.entity=QComboBox();self.entity.addItems(["TICKET","WORK_ORDER","QUALIFICATION"])
        self.equipment_type=QLineEdit();self.area=QLineEdit();self.priority=QLineEdit();self.severity=QLineEdit()
        f.addRow("Policy code",self.code);f.addRow("Label",self.label);f.addRow("Entity type",self.entity)
        f.addRow("Match equipment type",self.equipment_type);f.addRow("Match area",self.area);f.addRow("Match priority",self.priority);f.addRow("Match severity",self.severity)
        self.extra={}
        if category=="NUMBERING_SCHEME":
            prefix=QLineEdit();datefmt=QLineEdit("%Y%m%d");width=QSpinBox();width.setRange(1,12);width.setValue(5);reset=QComboBox();reset.addItems(["DAILY","MONTHLY","YEARLY","NEVER"]);sep=QLineEdit("-")
            for label,w in [("Prefix",prefix),("Date format",datefmt),("Sequence width",width),("Reset",reset),("Separator",sep)]:f.addRow(label,w)
            self.extra={"prefix":prefix,"date_format":datefmt,"width":width,"reset":reset,"separator":sep}
        elif category=="DEFAULT_OWNER_RULE":
            owner=QLineEdit();f.addRow("Default owner / username",owner);self.extra={"owner":owner}
        elif category=="SLA_POLICY":
            response=QSpinBox();response.setRange(0,1_000_000);containment=QSpinBox();containment.setRange(0,1_000_000);resolution=QSpinBox();resolution.setRange(0,1_000_000)
            for label,w in [("Response minutes",response),("Containment minutes",containment),("Resolution minutes",resolution)]:f.addRow(label,w)
            self.extra={"response_minutes":response,"containment_minutes":containment,"resolution_minutes":resolution}
        self.order=QSpinBox();self.order.setRange(0,99999);self.order.setValue(100);self.active=QCheckBox("Active");self.active.setChecked(True)
        f.addRow("Priority order",self.order);f.addRow("",self.active)
        note=QLabel("Blank match fields mean this policy applies broadly. More specific matching policies take precedence over broad policies.");note.setWordWrap(True);note.setStyleSheet("color:#647581");f.addRow("",note)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:
            self.code.setText(row.code);self.code.setReadOnly(True);self.label.setText(row.label);self.order.setValue(row.sort_order);self.active.setChecked(row.active)
            try:meta=json.loads(row.metadata_json or "{}")
            except Exception:meta={}
            match=meta.get("match",{}) if isinstance(meta,dict) else {}
            self.entity.setCurrentText(str(match.get("entity_type",meta.get("entity_type","TICKET"))))
            self.equipment_type.setText(str(match.get("equipment_type","")));self.area.setText(str(match.get("area","")));self.priority.setText(str(match.get("priority","")));self.severity.setText(str(match.get("severity","")))
            for key,w in self.extra.items():
                value=meta.get(key)
                if value is None:continue
                if isinstance(w,QLineEdit):w.setText(str(value))
                elif isinstance(w,QSpinBox):w.setValue(int(value))
                elif isinstance(w,QComboBox):w.setCurrentText(str(value))

    def data(self):
        match={"entity_type":self.entity.currentText()}
        for key,w in [("equipment_type",self.equipment_type),("area",self.area),("priority",self.priority),("severity",self.severity)]:
            value=w.text().strip()
            if value:match[key]=value
        meta={"match":match}
        for key,w in self.extra.items():
            if isinstance(w,QLineEdit):meta[key]=w.text().strip()
            elif isinstance(w,QSpinBox):meta[key]=w.value()
            elif isinstance(w,QComboBox):meta[key]=w.currentText()
        return {"category":self.category,"code":self.code.text().strip(),"label":self.label.text().strip(),"sort_order":self.order.value(),"active":self.active.isChecked(),"metadata_json":json.dumps(meta,sort_keys=True)}


class ReportTemplateDialog(QDialog):
    TYPES=[
        "WEEKLY_ENGINEERING","EQUIPMENT","INCIDENT","PM_EXECUTION",
        "WORK_ORDER","WORK_ORDER_CLOSEOUT","QUALIFICATION","RELEASE",
    ]
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Report Template Policy");self.resize(650,420)
        f=QFormLayout(self)
        self.code=QLineEdit();self.label=QLineEdit();self.report_type=QComboBox();self.report_type.addItems(self.TYPES)
        self.equipment_type=QLineEdit();self.area=QLineEdit();self.path=QLineEdit()
        browse=QPushButton("Browse…");browse.clicked.connect(self.browse)
        ph=QHBoxLayout();ph.addWidget(self.path,1);ph.addWidget(browse)
        self.order=QSpinBox();self.order.setRange(0,99999);self.order.setValue(100);self.active=QCheckBox("Active");self.active.setChecked(True)
        f.addRow("Policy code",self.code);f.addRow("Label",self.label);f.addRow("Report type",self.report_type)
        f.addRow("Match equipment type",self.equipment_type);f.addRow("Match area",self.area);f.addRow("PowerPoint template",ph)
        f.addRow("Priority order",self.order);f.addRow("",self.active)
        note=QLabel("Leave equipment type/area blank for a site-wide default. More specific matching templates take precedence.");note.setWordWrap(True);note.setStyleSheet("color:#647581");f.addRow("",note)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:
            self.code.setText(row.code);self.code.setReadOnly(True);self.label.setText(row.label);self.order.setValue(row.sort_order);self.active.setChecked(row.active)
            try:meta=json.loads(row.metadata_json or "{}")
            except Exception:meta={}
            match=meta.get("match",{}) if isinstance(meta,dict) else {}
            self.report_type.setCurrentText(str(match.get("report_type","WEEKLY_ENGINEERING")))
            self.equipment_type.setText(str(match.get("equipment_type","")));self.area.setText(str(match.get("area","")));self.path.setText(str(meta.get("path","")))

    def browse(self):
        path,_=QFileDialog.getOpenFileName(self,"Select PowerPoint Template","","PowerPoint (*.pptx *.potx)")
        if path:self.path.setText(path)

    def data(self):
        match={"report_type":self.report_type.currentText()}
        if self.equipment_type.text().strip():match["equipment_type"]=self.equipment_type.text().strip()
        if self.area.text().strip():match["area"]=self.area.text().strip()
        meta={"match":match,"path":self.path.text().strip()}
        return {"category":"REPORT_TEMPLATE","code":self.code.text().strip(),"label":self.label.text().strip(),"sort_order":self.order.value(),"active":self.active.isChecked(),"metadata_json":json.dumps(meta,sort_keys=True)}


class EntityTemplateDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Entity Template");self.resize(650,520)
        f=QFormLayout(self);self.template_id=QLineEdit();self.entity=QComboBox();self.entity.addItems(["EQUIPMENT","TICKET","WORK_ORDER","PM_DEFINITION"]);self.name=QLineEdit();self.applies=QLineEdit();self.defaults=QTextEdit();self.defaults.setPlaceholderText('{"equipment_type":"Etch","criticality":"High","area":"ETCH"}');self.active=QCheckBox("Active");self.active.setChecked(True)
        for label,w in [("Template ID",self.template_id),("Entity type",self.entity),("Name",self.name),("Applies to / equipment type",self.applies),("Default values JSON",self.defaults),("",self.active)]:f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self._accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:
            self.template_id.setText(row.template_id);self.template_id.setReadOnly(True);self.entity.setCurrentText(row.entity_type);self.name.setText(row.name);self.applies.setText(row.applies_to);self.defaults.setPlainText(row.defaults_json);self.active.setChecked(row.active)
    def _accept(self):
        try:
            value=json.loads(self.defaults.toPlainText() or "{}")
            if not isinstance(value,dict):raise ValueError("Defaults must be a JSON object.")
        except Exception as exc:QMessageBox.warning(self,"Template",str(exc));return
        self.accept()
    def data(self):
        return {"template_id":self.template_id.text().strip(),"entity_type":self.entity.currentText(),"name":self.name.text().strip(),"applies_to":self.applies.text().strip(),"defaults_json":self.defaults.toPlainText().strip() or "{}","active":self.active.isChecked()}


class CustomFieldDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Custom Field")
        f=QFormLayout(self);self.field_id=QLineEdit();self.entity=QComboBox();self.entity.addItems(["EQUIPMENT","TICKET","WORK_ORDER","PM_TASK","QUALIFICATION"]);self.applies=QLineEdit();self.label=QLineEdit();self.type=QComboBox();self.type.addItems(["TEXT","MULTILINE","NUMBER","BOOLEAN","DATE","CHOICE"]);self.options=QTextEdit();self.options.setPlaceholderText('["Option A","Option B"]');self.required=QCheckBox("Required");self.active=QCheckBox("Active");self.active.setChecked(True);self.order=QDoubleSpinBox();self.order.setDecimals(0);self.order.setRange(0,99999)
        for label,w in [("Field ID",self.field_id),("Entity type",self.entity),("Applies to / equipment type",self.applies),("Label",self.label),("Field type",self.type),("Choice options JSON",self.options),("",self.required),("",self.active),("Sort order",self.order)]:f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self._accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:
            self.field_id.setText(row.field_id);self.field_id.setReadOnly(True);self.entity.setCurrentText(row.entity_type);self.applies.setText(row.applies_to);self.label.setText(row.label);self.type.setCurrentText(row.field_type);self.options.setPlainText(row.options_json);self.required.setChecked(row.required);self.active.setChecked(row.active);self.order.setValue(row.sort_order)
    def _accept(self):
        if self.type.currentText()=="CHOICE":
            try:
                value=json.loads(self.options.toPlainText() or "[]")
                if not isinstance(value,list) or not value:raise ValueError("Choice fields require a non-empty JSON array.")
            except Exception as exc:QMessageBox.warning(self,"Custom field",str(exc));return
        self.accept()
    def data(self):
        return {"field_id":self.field_id.text().strip(),"entity_type":self.entity.currentText(),"applies_to":self.applies.text().strip(),"label":self.label.text().strip(),"field_type":self.type.currentText(),"options_json":self.options.toPlainText().strip() or "[]","required":self.required.isChecked(),"active":self.active.isChecked(),"sort_order":int(self.order.value())}


class CustomFieldsPanel(QWidget):
    def __init__(self,db,user,entity_type="",entity_key="",applies_to="",parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.entity_type="";self.entity_key="";self.applies_to="";self.defs=[];self.widgets={}
        self.root=QVBoxLayout(self);self.form=QFormLayout();self.root.addLayout(self.form);self.save=QPushButton("Save custom fields");self.save.clicked.connect(self.save_values);self.root.addWidget(self.save);self.root.addStretch(1)
        self.set_entity(entity_type,entity_key,applies_to)
    def _clear(self):
        while self.form.rowCount():self.form.removeRow(0)
        self.widgets={}
    def set_entity(self,entity_type,entity_key,applies_to=""):
        self.entity_type=(entity_type or "").strip().upper();self.entity_key=str(entity_key or "");self.applies_to=applies_to or "";self.refresh()
    def refresh(self):
        self._clear();enabled=bool(self.entity_type and self.entity_key);self.save.setEnabled(enabled)
        if not enabled:return
        self.defs=self.db.list_custom_field_definitions(self.entity_type,self.applies_to)
        values=self.db.custom_field_values(self.entity_type,self.entity_key)
        for definition in self.defs:
            value=values.get(definition.field_id)
            if definition.field_type=="MULTILINE":
                w=QTextEdit();w.setMaximumHeight(90);w.setPlainText("" if value is None else str(value))
            elif definition.field_type=="NUMBER":
                w=QDoubleSpinBox();w.setRange(-1e12,1e12);w.setDecimals(6);w.setValue(float(value or 0))
            elif definition.field_type=="BOOLEAN":
                w=QCheckBox();w.setChecked(bool(value))
            elif definition.field_type=="DATE":
                w=QDateEdit();w.setCalendarPopup(True)
                if value:
                    q=QDate.fromString(str(value),"yyyy-MM-dd")
                    if q.isValid():w.setDate(q)
            elif definition.field_type=="CHOICE":
                w=QComboBox();w.addItems([str(x) for x in json.loads(definition.options_json or "[]")])
                if value is not None:w.setCurrentText(str(value))
            else:
                w=QLineEdit("" if value is None else str(value))
            self.widgets[definition.field_id]=w
            self.form.addRow(definition.label+(" *" if definition.required else ""),w)
        if not self.defs:self.form.addRow("",QLabel("No custom fields configured for this record type."))
    def save_values(self):
        values={}
        for definition in self.defs:
            w=self.widgets[definition.field_id]
            if isinstance(w,QTextEdit):value=w.toPlainText().strip()
            elif isinstance(w,QDoubleSpinBox):value=w.value()
            elif isinstance(w,QCheckBox):value=w.isChecked()
            elif isinstance(w,QDateEdit):value=w.date().toString("yyyy-MM-dd")
            elif isinstance(w,QComboBox):value=w.currentText()
            else:value=w.text().strip()
            values[definition.field_id]=value
        try:self.db.save_custom_field_values(self.entity_type,self.entity_key,values,self.user["username"],self.applies_to);QMessageBox.information(self,"Custom fields","Saved.");self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Custom fields",str(exc))


class ConfigurationStudio(QWidget):
    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.options=[];self.templates=[];self.fields=[]
        root=QVBoxLayout(self);head=QHBoxLayout();title=QLabel("Configuration Studio");title.setStyleSheet("font-size:20pt;font-weight:800");note=QLabel("Adapt plant-facing lists, templates and custom fields without editing Python.");note.setStyleSheet("color:#647581");exportb=QPushButton("Export package");importb=QPushButton("Import package");exportb.clicked.connect(self.export_package);importb.clicked.connect(self.import_package);head.addWidget(title);head.addWidget(note);head.addStretch(1);head.addWidget(exportb);head.addWidget(importb);root.addLayout(head)
        tabs=QTabWidget();root.addWidget(tabs,1)

        ow=QWidget();ov=QVBoxLayout(ow);oh=QHBoxLayout();self.category=QComboBox();self.category.addItems(["EQUIPMENT_CRITICALITY","TICKET_SEVERITY","TICKET_PRIORITY","DISPOSITION_STATE","INVENTORY_CONDITION","WORK_TYPE","ALARM_BURST_POLICY","NUMBERING_SCHEME","DEFAULT_OWNER_RULE","SLA_POLICY","REPORT_TEMPLATE","EQUIPMENT_REASON_LABEL","TICKET_REASON_LABEL"]);self.category.currentTextChanged.connect(self.refresh_options);add=QPushButton("Add option");edit=QPushButton("Edit selected");add.clicked.connect(self.add_option);edit.clicked.connect(self.edit_option);oh.addWidget(QLabel("Category"));oh.addWidget(self.category);oh.addWidget(add);oh.addWidget(edit);oh.addStretch(1);ov.addLayout(oh);self.option_table=_table(["Code","Label","Order","Active","System","Metadata","Ver"]);ov.addWidget(self.option_table);tabs.addTab(ow,"Reference Options")

        tw=QWidget();tv=QVBoxLayout(tw);th=QHBoxLayout();addt=QPushButton("New template");editt=QPushButton("Edit selected");addt.clicked.connect(self.add_template);editt.clicked.connect(self.edit_template);th.addWidget(addt);th.addWidget(editt);th.addStretch(1);tv.addLayout(th);self.template_table=_table(["Template","Entity","Name","Applies To","Active","Created By","Ver"]);tv.addWidget(self.template_table);tabs.addTab(tw,"Entity Templates")

        fw=QWidget();fv=QVBoxLayout(fw);fh=QHBoxLayout();addf=QPushButton("New custom field");editf=QPushButton("Edit selected");addf.clicked.connect(self.add_field);editf.clicked.connect(self.edit_field);fh.addWidget(addf);fh.addWidget(editf);fh.addStretch(1);fv.addLayout(fh);self.field_table=_table(["Field","Entity","Applies To","Label","Type","Required","Order","Active","Ver"]);fv.addWidget(self.field_table);tabs.addTab(fw,"Custom Fields")
        self.refresh()

    def export_package(self):
        path,_=QFileDialog.getSaveFileName(self,"Export EMS Configuration","EMS_Configuration.json","JSON (*.json)")
        if not path:return
        if not path.lower().endswith(".json"):path+=".json"
        try:
            with open(path,"w",encoding="utf-8") as handle:json.dump(self.db.export_configuration_bundle(),handle,indent=2,ensure_ascii=False)
            QMessageBox.information(self,"Configuration",f"Configuration package exported.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"Configuration export",str(exc))

    def import_package(self):
        path,_=QFileDialog.getOpenFileName(self,"Import EMS Configuration","","JSON (*.json)")
        if not path:return
        try:
            with open(path,"r",encoding="utf-8") as handle:bundle=json.load(handle)
            preview=self.db.import_configuration_bundle(bundle,self.user["username"],True)
            lines=[]
            for section in ["config_options","entity_templates","custom_fields","workflow_rules"]:
                lines.append(f"{section}: {preview['creates'][section]} create / {preview['updates'][section]} update")
            if QMessageBox.question(self,"Configuration Import Preview","Apply this validated package?\n\n"+"\n".join(lines))!=QMessageBox.StandardButton.Yes:return
            self.db.import_configuration_bundle(bundle,self.user["username"],False)
            self.refresh();QMessageBox.information(self,"Configuration","Configuration package applied.")
        except Exception as exc:QMessageBox.critical(self,"Configuration import",str(exc))

    def refresh(self):self.refresh_options();self.refresh_templates();self.refresh_fields()
    def refresh_options(self):
        self.options=self.db.list_config_options(self.category.currentText(),False);self.option_table.setRowCount(len(self.options))
        for r,row in enumerate(self.options):
            for c,val in enumerate([row.code,row.label,row.sort_order,row.active,row.system_locked,row.metadata_json,row.version]):self.option_table.setItem(r,c,_item(val))
    def refresh_templates(self):
        self.templates=self.db.list_entity_templates(active_only=False);self.template_table.setRowCount(len(self.templates))
        for r,row in enumerate(self.templates):
            for c,val in enumerate([row.template_id,row.entity_type,row.name,row.applies_to,row.active,row.created_by,row.version]):self.template_table.setItem(r,c,_item(val))
    def refresh_fields(self):
        rows=[]
        for entity in ["EQUIPMENT","TICKET","WORK_ORDER","PM_TASK","QUALIFICATION"]:rows.extend(self.db.list_custom_field_definitions(entity,active_only=False))
        self.fields=sorted(rows,key=lambda x:(x.entity_type,x.sort_order,x.label));self.field_table.setRowCount(len(self.fields))
        for r,row in enumerate(self.fields):
            for c,val in enumerate([row.field_id,row.entity_type,row.applies_to,row.label,row.field_type,row.required,row.sort_order,row.active,row.version]):self.field_table.setItem(r,c,_item(val))
    def add_option(self):
        category=self.category.currentText()
        if category in {"NUMBERING_SCHEME","DEFAULT_OWNER_RULE","SLA_POLICY"}:
            d=PolicyOptionDialog(category,parent=self)
        elif category=="REPORT_TEMPLATE":
            d=ReportTemplateDialog(parent=self)
        else:
            d=ConfigOptionDialog(parent=self);d.category.setText(category)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_config_option(d.data());self.refresh_options()
            except Exception as exc:QMessageBox.critical(self,"Configuration",str(exc))
    def edit_option(self):
        row=_selected(self.option_table,self.options)
        if not row:return
        if row.category in {"NUMBERING_SCHEME","DEFAULT_OWNER_RULE","SLA_POLICY"}:d=PolicyOptionDialog(row.category,row,self)
        elif row.category=="REPORT_TEMPLATE":d=ReportTemplateDialog(row,self)
        else:d=ConfigOptionDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_config_option(d.data(),row.version);self.refresh_options()
            except Exception as exc:QMessageBox.critical(self,"Configuration",str(exc))
    def add_template(self):
        d=EntityTemplateDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_entity_template(d.data(),self.user["username"]);self.refresh_templates()
            except Exception as exc:QMessageBox.critical(self,"Template",str(exc))
    def edit_template(self):
        row=_selected(self.template_table,self.templates)
        if not row:return
        d=EntityTemplateDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_entity_template(d.data(),self.user["username"],row.version);self.refresh_templates()
            except Exception as exc:QMessageBox.critical(self,"Template",str(exc))
    def add_field(self):
        d=CustomFieldDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_custom_field_definition(d.data());self.refresh_fields()
            except Exception as exc:QMessageBox.critical(self,"Custom field",str(exc))
    def edit_field(self):
        row=_selected(self.field_table,self.fields)
        if not row:return
        d=CustomFieldDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_custom_field_definition(d.data(),row.version);self.refresh_fields()
            except Exception as exc:QMessageBox.critical(self,"Custom field",str(exc))
