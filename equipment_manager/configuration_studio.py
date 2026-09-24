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


class EntityTemplateDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Entity Template");self.resize(650,520)
        f=QFormLayout(self);self.template_id=QLineEdit();self.entity=QComboBox();self.entity.addItems(["EQUIPMENT","TICKET","WORK_ORDER","PM_DEFINITION","QUALIFICATION_PROTOCOL"]);self.name=QLineEdit();self.applies=QLineEdit();self.defaults=QTextEdit();self.defaults.setPlaceholderText('{"equipment_type":"Etch","criticality":"High","area":"ETCH"}');self.active=QCheckBox("Active");self.active.setChecked(True)
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


class NumberingSchemeDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Numbering Scheme")
        f=QFormLayout(self);self.entity=QComboBox();self.entity.addItems(["TICKET","WORK_ORDER","ENDORSEMENT","QUALIFICATION"])
        self.prefix=QLineEdit();self.date_format=QLineEdit("%Y%m%d");self.separator=QLineEdit("-");self.padding=QDoubleSpinBox();self.padding.setDecimals(0);self.padding.setRange(1,12);self.padding.setValue(4);self.reset=QComboBox();self.reset.addItems(["DAY","MONTH","YEAR","NEVER"]);self.active=QCheckBox("Active");self.active.setChecked(True)
        for label,w in [("Entity",self.entity),("Prefix",self.prefix),("Date format",self.date_format),("Separator",self.separator),("Sequence padding",self.padding),("Reset",self.reset),("",self.active)]:f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:self.entity.setCurrentText(row.entity_type);self.entity.setEnabled(False);self.prefix.setText(row.prefix);self.date_format.setText(row.date_format);self.separator.setText(row.separator);self.padding.setValue(row.padding);self.reset.setCurrentText(row.reset_period);self.active.setChecked(row.active)
    def data(self):
        return {"entity_type":self.entity.currentText(),"prefix":self.prefix.text().strip(),"date_format":self.date_format.text().strip(),"separator":self.separator.text(),"padding":int(self.padding.value()),"reset_period":self.reset.currentText(),"active":self.active.isChecked()}


class AssignmentRuleDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Default Assignment Rule");self.resize(620,450)
        f=QFormLayout(self);self.rule=QLineEdit();self.entity=QComboBox();self.entity.addItems(["TICKET","WORK_ORDER","PM_TASK"]);self.name=QLineEdit();self.match=QTextEdit();self.match.setPlaceholderText('{"area":"ETCH","priority":["P1","P2"]}');self.owner=QLineEdit();self.team=QLineEdit();self.priority=QDoubleSpinBox();self.priority.setDecimals(0);self.priority.setRange(1,10000);self.priority.setValue(100);self.active=QCheckBox("Active");self.active.setChecked(True)
        for label,w in [("Rule ID",self.rule),("Entity type",self.entity),("Name",self.name),("Match JSON",self.match),("Default owner",self.owner),("Default team",self.team),("Rule priority",self.priority),("",self.active)]:f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self._accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:self.rule.setText(row.rule_id);self.rule.setReadOnly(True);self.entity.setCurrentText(row.entity_type);self.name.setText(row.name);self.match.setPlainText(row.match_json);self.owner.setText(row.owner);self.team.setText(row.team);self.priority.setValue(row.priority);self.active.setChecked(row.active)
    def _accept(self):
        try:
            x=json.loads(self.match.toPlainText() or "{}")
            if not isinstance(x,dict):raise ValueError("Match must be a JSON object.")
        except Exception as exc:QMessageBox.warning(self,"Assignment rule",str(exc));return
        self.accept()
    def data(self):
        return {"rule_id":self.rule.text().strip(),"entity_type":self.entity.currentText(),"name":self.name.text().strip(),"match_json":self.match.toPlainText().strip() or "{}","owner":self.owner.text().strip(),"team":self.team.text().strip(),"priority":int(self.priority.value()),"active":self.active.isChecked()}


class SLATemplateDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Incident SLA Template");self.resize(620,450)
        f=QFormLayout(self);self.template=QLineEdit();self.name=QLineEdit();self.match=QTextEdit();self.match.setPlaceholderText('{"priority":"P1"}');self.response=QDoubleSpinBox();self.containment=QDoubleSpinBox();self.resolution=QDoubleSpinBox();self.priority=QDoubleSpinBox()
        for w in [self.response,self.containment,self.resolution]:w.setDecimals(0);w.setRange(0,525600);w.setSuffix(" min")
        self.priority.setDecimals(0);self.priority.setRange(1,10000);self.priority.setValue(100);self.active=QCheckBox("Active");self.active.setChecked(True)
        for label,w in [("Template ID",self.template),("Name",self.name),("Match JSON",self.match),("Response due",self.response),("Containment due",self.containment),("Resolution due",self.resolution),("Rule priority",self.priority),("",self.active)]:f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self._accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:self.template.setText(row.template_id);self.template.setReadOnly(True);self.name.setText(row.name);self.match.setPlainText(row.match_json);self.response.setValue(row.response_minutes);self.containment.setValue(row.containment_minutes);self.resolution.setValue(row.resolution_minutes);self.priority.setValue(row.priority);self.active.setChecked(row.active)
    def _accept(self):
        try:
            x=json.loads(self.match.toPlainText() or "{}")
            if not isinstance(x,dict):raise ValueError("Match must be a JSON object.")
        except Exception as exc:QMessageBox.warning(self,"SLA template",str(exc));return
        self.accept()
    def data(self):
        return {"template_id":self.template.text().strip(),"name":self.name.text().strip(),"match_json":self.match.toPlainText().strip() or "{}","response_minutes":int(self.response.value()),"containment_minutes":int(self.containment.value()),"resolution_minutes":int(self.resolution.value()),"priority":int(self.priority.value()),"active":self.active.isChecked()}


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

        ow=QWidget();ov=QVBoxLayout(ow);oh=QHBoxLayout();self.category=QComboBox();self.category.addItems(["EQUIPMENT_CRITICALITY","TICKET_SEVERITY","TICKET_PRIORITY","DISPOSITION_STATE","INVENTORY_CONDITION","WORK_TYPE","EQUIPMENT_REASON_LABEL","TICKET_REASON_LABEL"]);self.category.currentTextChanged.connect(self.refresh_options);add=QPushButton("Add option");edit=QPushButton("Edit selected");add.clicked.connect(self.add_option);edit.clicked.connect(self.edit_option);oh.addWidget(QLabel("Category"));oh.addWidget(self.category);oh.addWidget(add);oh.addWidget(edit);oh.addStretch(1);ov.addLayout(oh);self.option_table=_table(["Code","Label","Order","Active","System","Metadata","Ver"]);ov.addWidget(self.option_table);tabs.addTab(ow,"Reference Options")

        tw=QWidget();tv=QVBoxLayout(tw);th=QHBoxLayout();addt=QPushButton("New template");editt=QPushButton("Edit selected");addt.clicked.connect(self.add_template);editt.clicked.connect(self.edit_template);th.addWidget(addt);th.addWidget(editt);th.addStretch(1);tv.addLayout(th);self.template_table=_table(["Template","Entity","Name","Applies To","Active","Created By","Ver"]);tv.addWidget(self.template_table);tabs.addTab(tw,"Entity Templates")

        fw=QWidget();fv=QVBoxLayout(fw);fh=QHBoxLayout();addf=QPushButton("New custom field");editf=QPushButton("Edit selected");addf.clicked.connect(self.add_field);editf.clicked.connect(self.edit_field);fh.addWidget(addf);fh.addWidget(editf);fh.addStretch(1);fv.addLayout(fh);self.field_table=_table(["Field","Entity","Applies To","Label","Type","Required","Order","Active","Ver"]);fv.addWidget(self.field_table);tabs.addTab(fw,"Custom Fields")

        nw=QWidget();nv=QVBoxLayout(nw);nh=QHBoxLayout();addn=QPushButton("New scheme");editn=QPushButton("Edit selected");addn.clicked.connect(self.add_numbering);editn.clicked.connect(self.edit_numbering);nh.addWidget(addn);nh.addWidget(editn);nh.addStretch(1);nv.addLayout(nh);self.number_table=_table(["Entity","Prefix","Date Format","Separator","Padding","Reset","Next","Active","Ver"]);nv.addWidget(self.number_table);tabs.addTab(nw,"Numbering")

        aw=QWidget();av=QVBoxLayout(aw);ah=QHBoxLayout();adda=QPushButton("New assignment rule");edita=QPushButton("Edit selected");adda.clicked.connect(self.add_assignment);edita.clicked.connect(self.edit_assignment);ah.addWidget(adda);ah.addWidget(edita);ah.addStretch(1);av.addLayout(ah);self.assignment_table=_table(["Rule","Entity","Name","Match","Owner","Team","Priority","Active","Ver"]);av.addWidget(self.assignment_table);tabs.addTab(aw,"Default Assignment")

        sw=QWidget();sv=QVBoxLayout(sw);sh=QHBoxLayout();adds=QPushButton("New SLA template");edits=QPushButton("Edit selected");adds.clicked.connect(self.add_sla);edits.clicked.connect(self.edit_sla);sh.addWidget(adds);sh.addWidget(edits);sh.addStretch(1);sv.addLayout(sh);self.sla_table=_table(["Template","Name","Match","Response min","Containment min","Resolution min","Priority","Active","Ver"]);sv.addWidget(self.sla_table);tabs.addTab(sw,"Incident SLA")
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

    def refresh(self):self.refresh_options();self.refresh_templates();self.refresh_fields();self.refresh_runtime_rules()
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
    def refresh_runtime_rules(self):
        self.numbering=self.db.list_numbering_schemes();self.number_table.setRowCount(len(self.numbering))
        for r,row in enumerate(self.numbering):
            for col,val in enumerate([row.entity_type,row.prefix,row.date_format,row.separator,row.padding,row.reset_period,row.next_value,row.active,row.version]):self.number_table.setItem(r,col,_item(val))
        self.assignments=self.db.list_default_assignment_rules();self.assignment_table.setRowCount(len(self.assignments))
        for r,row in enumerate(self.assignments):
            for col,val in enumerate([row.rule_id,row.entity_type,row.name,row.match_json,row.owner,row.team,row.priority,row.active,row.version]):self.assignment_table.setItem(r,col,_item(val))
        self.slas=self.db.list_sla_templates();self.sla_table.setRowCount(len(self.slas))
        for r,row in enumerate(self.slas):
            for col,val in enumerate([row.template_id,row.name,row.match_json,row.response_minutes,row.containment_minutes,row.resolution_minutes,row.priority,row.active,row.version]):self.sla_table.setItem(r,col,_item(val))

    def add_numbering(self):
        d=NumberingSchemeDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_numbering_scheme(d.data());self.refresh_runtime_rules()
            except Exception as exc:QMessageBox.critical(self,"Numbering",str(exc))
    def edit_numbering(self):
        row=_selected(self.number_table,self.numbering)
        if not row:return
        d=NumberingSchemeDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_numbering_scheme(d.data(),row.version);self.refresh_runtime_rules()
            except Exception as exc:QMessageBox.critical(self,"Numbering",str(exc))
    def add_assignment(self):
        d=AssignmentRuleDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_default_assignment_rule(d.data());self.refresh_runtime_rules()
            except Exception as exc:QMessageBox.critical(self,"Assignment rule",str(exc))
    def edit_assignment(self):
        row=_selected(self.assignment_table,self.assignments)
        if not row:return
        d=AssignmentRuleDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_default_assignment_rule(d.data(),row.version);self.refresh_runtime_rules()
            except Exception as exc:QMessageBox.critical(self,"Assignment rule",str(exc))
    def add_sla(self):
        d=SLATemplateDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_sla_template(d.data());self.refresh_runtime_rules()
            except Exception as exc:QMessageBox.critical(self,"SLA template",str(exc))
    def edit_sla(self):
        row=_selected(self.sla_table,self.slas)
        if not row:return
        d=SLATemplateDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_sla_template(d.data(),row.version);self.refresh_runtime_rules()
            except Exception as exc:QMessageBox.critical(self,"SLA template",str(exc))

    def add_option(self):
        d=ConfigOptionDialog(parent=self);d.category.setText(self.category.currentText())
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_config_option(d.data());self.refresh_options()
            except Exception as exc:QMessageBox.critical(self,"Configuration",str(exc))
    def edit_option(self):
        row=_selected(self.option_table,self.options)
        if not row:return
        d=ConfigOptionDialog(row,self)
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
