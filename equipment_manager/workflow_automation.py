from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
    QHeaderView, QAbstractItemView,
)

from table_productivity import install_table_productivity


def _item(value):
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);t.setAlternatingRowColors(True)
    install_table_productivity(t,headers[0] if headers else "Automation")
    return t


class WorkflowRuleDialog(QDialog):
    TEMPLATES={
        "Critical alarm → incident + hold":[
            {"severity":["Critical","Fatal"]},
            [
                {"type":"CREATE_INCIDENT","priority":"P1","severity":"S1","title":"Critical equipment alarm"},
                {"type":"SET_DISPOSITION","state":"Hold","reason":"Critical alarm automation"},
                {"type":"CREATE_HANDOVER","pending_work":"Critical alarm requires follow-up"},
            ],
        ],
        "PM abnormal → incident + work order":[
            {},
            [
                {"type":"CREATE_INCIDENT","priority":"P2","severity":"S2","title":"PM abnormal result"},
                {"type":"CREATE_WORK_ORDER","priority":"High","title":"Investigate abnormal PM result","qualification_required":True,"release_required":True},
            ],
        ],
        "Qualification approved → handover":[
            {},
            [{"type":"CREATE_HANDOVER","condition":"Qualification approved","next_action":"Proceed with release workflow"}],
        ],
        "Release approved → handover":[
            {},
            [{"type":"CREATE_HANDOVER","condition":"Equipment released","next_action":"Return equipment to production per shift plan"}],
        ],
    }

    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Workflow Automation Rule");self.resize(760,640)
        f=QFormLayout(self)
        self.rule_id=QLineEdit();self.name=QLineEdit();self.trigger=QComboBox()
        self.trigger.addItems(["ALARM_ACTIVE","PM_ABNORMAL_RESULT","QUALIFICATION_APPROVED","RELEASE_APPROVED"])
        self.priority=QSpinBox();self.priority.setRange(1,10000);self.priority.setValue(100)
        self.enabled=QCheckBox("Enabled");self.enabled.setChecked(True)
        self.template=QComboBox();self.template.addItems(["<custom>"]+list(self.TEMPLATES));self.template.currentTextChanged.connect(self.apply_template)
        self.match=QTextEdit();self.actions=QTextEdit()
        self.match.setPlaceholderText('{"severity":["Critical","Fatal"],"alarm_code":"E123"}')
        self.actions.setPlaceholderText('[{"type":"CREATE_INCIDENT","priority":"P1"}]')
        f.addRow("Rule ID",self.rule_id);f.addRow("Name",self.name);f.addRow("Trigger",self.trigger)
        f.addRow("Priority",self.priority);f.addRow("",self.enabled);f.addRow("Template",self.template)
        f.addRow("Match JSON",self.match);f.addRow("Actions JSON",self.actions)
        help_text=QLabel("Supported actions: CREATE_INCIDENT, CREATE_WORK_ORDER, CREATE_HANDOVER, SET_DISPOSITION. Match keys compare against event context; string values may use contains:text.")
        help_text.setWordWrap(True);f.addRow("",help_text)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.validate_and_accept);buttons.rejected.connect(self.reject);f.addRow(buttons)
        if row:
            self.rule_id.setText(row.rule_id);self.rule_id.setEnabled(False);self.name.setText(row.name)
            self.trigger.setCurrentText(row.trigger);self.priority.setValue(row.priority);self.enabled.setChecked(row.enabled)
            self.match.setPlainText(row.match_json);self.actions.setPlainText(row.actions_json)

    def apply_template(self,name):
        if name not in self.TEMPLATES:return
        match,actions=self.TEMPLATES[name]
        self.match.setPlainText(json.dumps(match,indent=2))
        self.actions.setPlainText(json.dumps(actions,indent=2))
        if name.startswith("Critical alarm"):self.trigger.setCurrentText("ALARM_ACTIVE")
        elif name.startswith("PM abnormal"):self.trigger.setCurrentText("PM_ABNORMAL_RESULT")
        elif name.startswith("Qualification"):self.trigger.setCurrentText("QUALIFICATION_APPROVED")
        elif name.startswith("Release"):self.trigger.setCurrentText("RELEASE_APPROVED")

    def validate_and_accept(self):
        if not self.rule_id.text().strip() or not self.name.text().strip():
            QMessageBox.warning(self,"Automation","Rule ID and name are required.");return
        try:
            match=json.loads(self.match.toPlainText() or "{}");actions=json.loads(self.actions.toPlainText() or "[]")
            if not isinstance(match,dict):raise ValueError("Match must be a JSON object.")
            if not isinstance(actions,list) or not actions:raise ValueError("Actions must be a non-empty JSON array.")
        except Exception as exc:
            QMessageBox.warning(self,"Automation",f"Invalid JSON: {exc}");return
        self.accept()

    def data(self):
        return {
            "rule_id":self.rule_id.text().strip(),"name":self.name.text().strip(),
            "trigger":self.trigger.currentText(),"priority":self.priority.value(),
            "enabled":self.enabled.isChecked(),"match_json":self.match.toPlainText().strip() or "{}",
            "actions_json":self.actions.toPlainText().strip() or "[]",
        }


class WorkflowAutomationStudio(QWidget):
    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.rules=[];self.executions=[]
        root=QVBoxLayout(self);head=QHBoxLayout()
        title=QLabel("Workflow Automation Studio");title.setStyleSheet("font-size:20pt;font-weight:800")
        subtitle=QLabel("Connect alarms, PM failures, qualification and release to downstream work without Python changes.")
        subtitle.setStyleSheet("color:#647581;")
        head.addWidget(title);head.addWidget(subtitle);head.addStretch(1)
        add=QPushButton("New rule");edit=QPushButton("Edit selected");toggle=QPushButton("Enable / Disable");refresh=QPushButton("Refresh")
        add.clicked.connect(self.add_rule);edit.clicked.connect(self.edit_rule);toggle.clicked.connect(self.toggle_rule);refresh.clicked.connect(self.refresh)
        for b in [add,edit,toggle,refresh]:head.addWidget(b)
        root.addLayout(head)
        tabs=QTabWidget();root.addWidget(tabs,1)
        rw=QWidget();rv=QVBoxLayout(rw);self.rule_table=_table(["Rule","Name","Trigger","Priority","Enabled","Match","Actions","Version"]);rv.addWidget(self.rule_table);tabs.addTab(rw,"Rules")
        ew=QWidget();ev=QVBoxLayout(ew);self.exec_table=_table(["Time","Rule","Trigger","Entity","Key","Equipment","Status","Error","Result"]);ev.addWidget(self.exec_table);tabs.addTab(ew,"Execution History")
        self.refresh()

    def refresh(self):
        self.rules=self.db.list_workflow_rules()
        self.rule_table.setRowCount(len(self.rules))
        fields=["rule_id","name","trigger","priority","enabled","match_json","actions_json","version"]
        for r,row in enumerate(self.rules):
            for c,field in enumerate(fields):self.rule_table.setItem(r,c,_item(getattr(row,field,"")))
        self.executions=self.db.list_workflow_automation_executions(1000)
        self.exec_table.setRowCount(len(self.executions))
        fields=["executed_at","rule_id","trigger","entity_type","entity_key","equipment_id","status","error","result_json"]
        for r,row in enumerate(self.executions):
            for c,field in enumerate(fields):self.exec_table.setItem(r,c,_item(getattr(row,field,"")))

    def selected_rule(self):
        i=self.rule_table.currentRow()
        return self.rules[i] if 0<=i<len(self.rules) else None

    def add_rule(self):
        d=WorkflowRuleDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_workflow_rule(d.data(),self.user["username"]);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Automation",str(exc))

    def edit_rule(self):
        row=self.selected_rule()
        if not row:return
        d=WorkflowRuleDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_workflow_rule(d.data(),self.user["username"],row.version);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Automation",str(exc))

    def toggle_rule(self):
        row=self.selected_rule()
        if not row:return
        data={
            "rule_id":row.rule_id,"name":row.name,"trigger":row.trigger,"match_json":row.match_json,
            "actions_json":row.actions_json,"enabled":not row.enabled,"priority":row.priority,
            "created_by":row.created_by,
        }
        try:self.db.save_workflow_rule(data,self.user["username"],row.version);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Automation",str(exc))
