from __future__ import annotations

import json
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,QCheckBox,QComboBox,QDialog,QDialogButtonBox,QFormLayout,
    QHBoxLayout,QHeaderView,QInputDialog,QLabel,QLineEdit,QMessageBox,QPushButton,
    QSpinBox,QTabWidget,QTableWidget,QTableWidgetItem,QTextEdit,QVBoxLayout,QWidget,
)

from integrations import dispatch_pending, transform_event_payload
from orchestration import process_pending_rules
from table_productivity import install_table_productivity


def _item(value):
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setAlternatingRowColors(True);t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    install_table_productivity(t,headers[0] if headers else "Integration Studio")
    return t


def _fill(table,rows,fields):
    table.setRowCount(len(rows))
    for r,row in enumerate(rows):
        for c,field in enumerate(fields):
            value=row.get(field,"") if isinstance(row,dict) else getattr(row,field,"")
            table.setItem(r,c,_item(value))


def _selected(table,rows):
    i=table.currentRow()
    return rows[i] if 0<=i<len(rows) else None


class EndpointDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Integration Endpoint");self.setMinimumWidth(620)
        f=QFormLayout(self)
        self.endpoint=QLineEdit();self.name=QLineEdit();self.adapter=QComboBox();self.adapter.addItems(["FILE","HTTP"])
        self.target=QLineEdit();self.topics=QLineEdit("*");self.auth=QLineEdit();self.enabled=QCheckBox();self.enabled.setChecked(True)
        self.target.setPlaceholderText("FILE: shared/drop folder path · HTTP: https://host/path")
        self.topics.setPlaceholderText("Comma-separated exact topics or *")
        self.auth.setPlaceholderText("Environment variable containing Authorization header value")
        for label,w in [("Endpoint ID",self.endpoint),("Name",self.name),("Adapter",self.adapter),("Target",self.target),("Topics",self.topics),("Auth env",self.auth),("Enabled",self.enabled)]:f.addRow(label,w)
        if row:
            self.endpoint.setText(row.endpoint_id);self.endpoint.setReadOnly(True);self.name.setText(row.name);self.adapter.setCurrentText(row.adapter_type)
            self.target.setText(row.target);self.topics.setText(row.topics);self.auth.setText(row.auth_env);self.enabled.setChecked(row.enabled)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)

    def data(self):
        return {
            "endpoint_id":self.endpoint.text().strip(),"name":self.name.text().strip(),
            "adapter_type":self.adapter.currentText(),"target":self.target.text().strip(),
            "topics":self.topics.text().strip() or "*","auth_env":self.auth.text().strip(),
            "enabled":self.enabled.isChecked(),
        }


class MappingDialog(QDialog):
    def __init__(self,endpoint_id: str,current=None,parent=None):
        super().__init__(parent);self.endpoint_id=endpoint_id;self.setWindowTitle(f"Mapping · {endpoint_id}");self.resize(760,600)
        v=QVBoxLayout(self)
        note=QLabel(
            'Map outbound top-level field names to event-envelope paths. Example:\n'
            '{"tool_id":"payload.equipment_id","event_type":"topic","source_id":"event_id"}\n'
            'Defaults are merged first. Leave mapping {} to send the normal EMS envelope.'
        );note.setWordWrap(True);v.addWidget(note)
        v.addWidget(QLabel("Mapping JSON"));self.mapping=QTextEdit();v.addWidget(self.mapping,2)
        v.addWidget(QLabel("Default / constant JSON"));self.defaults=QTextEdit();v.addWidget(self.defaults,1)
        if current:
            self.mapping.setPlainText(json.dumps(json.loads(current.mapping_json or "{}"),indent=2,sort_keys=True))
            self.defaults.setPlainText(json.dumps(json.loads(current.defaults_json or "{}"),indent=2,sort_keys=True))
        else:
            self.mapping.setPlainText("{}");self.defaults.setPlainText("{}")
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self._accept);b.rejected.connect(self.reject);v.addWidget(b)

    def _accept(self):
        try:
            mapping=json.loads(self.mapping.toPlainText() or "{}");defaults=json.loads(self.defaults.toPlainText() or "{}")
            if not isinstance(mapping,dict) or not isinstance(defaults,dict):raise ValueError("Both values must be JSON objects.")
        except Exception as exc:QMessageBox.critical(self,"Mapping",str(exc));return
        self.accept()

    def values(self):
        return json.loads(self.mapping.toPlainText() or "{}"),json.loads(self.defaults.toPlainText() or "{}")


class RuleDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Orchestration Rule");self.resize(720,620)
        f=QFormLayout(self)
        self.rule=QLineEdit();self.name=QLineEdit();self.topic=QLineEdit("equipment.alarm.active")
        self.condition=QTextEdit();self.action=QComboBox();self.action.addItems(["CREATE_INCIDENT_FROM_ALARM","CREATE_WORK_ORDER_FROM_TICKET","SET_DISPOSITION"])
        self.action_json=QTextEdit();self.priority=QSpinBox();self.priority.setRange(1,10000);self.priority.setValue(100);self.enabled=QCheckBox();self.enabled.setChecked(True)
        self.condition.setPlaceholderText('{"payload.severity":{"in":["Critical","Fatal"]}}')
        self.action_json.setPlaceholderText('Examples: {"actor":"engineer_username","owner":"engineer_username"} · {"actor":"engineer_username","state":"Hold","reason":"Critical alarm","release_criteria":"Engineering review"}')
        for label,w in [("Rule ID",self.rule),("Name",self.name),("Topic pattern",self.topic),("Condition JSON",self.condition),("Action",self.action),("Action JSON",self.action_json),("Priority",self.priority),("Enabled",self.enabled)]:f.addRow(label,w)
        if row:
            self.rule.setText(row.rule_id);self.rule.setReadOnly(True);self.name.setText(row.name);self.topic.setText(row.topic_pattern)
            self.condition.setPlainText(json.dumps(json.loads(row.condition_json or "{}"),indent=2,sort_keys=True))
            self.action.setCurrentText(row.action_type);self.action_json.setPlainText(json.dumps(json.loads(row.action_json or "{}"),indent=2,sort_keys=True))
            self.priority.setValue(row.priority);self.enabled.setChecked(row.enabled)
        else:
            self.condition.setPlainText("{}");self.action_json.setPlainText("{}")
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self._accept);b.rejected.connect(self.reject);f.addRow(b)

    def _accept(self):
        try:
            json.loads(self.condition.toPlainText() or "{}");json.loads(self.action_json.toPlainText() or "{}")
        except Exception as exc:QMessageBox.critical(self,"Rule",f"Invalid JSON: {exc}");return
        self.accept()

    def data(self):
        return {
            "rule_id":self.rule.text().strip(),"name":self.name.text().strip(),
            "topic_pattern":self.topic.text().strip(),"condition_json":self.condition.toPlainText().strip() or "{}",
            "action_type":self.action.currentText(),"action_json":self.action_json.toPlainText().strip() or "{}",
            "priority":self.priority.value(),"enabled":self.enabled.isChecked(),
        }


class IntegrationStudioWorkspace(QWidget):
    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.endpoints=[];self.deliveries=[];self.events=[];self.rules=[];self.executions=[];self.receipts=[]
        root=QVBoxLayout(self);head=QHBoxLayout()
        title=QLabel("Integration Studio");title.setStyleSheet("font-size:20pt;font-weight:800")
        self.summary=QLabel();self.summary.setStyleSheet("color:#647581")
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh)
        dispatch=QPushButton("Dispatch Now");dispatch.clicked.connect(self.dispatch_now)
        orchestrate=QPushButton("Run Rules Now");orchestrate.clicked.connect(self.run_rules)
        head.addWidget(title);head.addWidget(self.summary);head.addStretch(1);head.addWidget(dispatch);head.addWidget(orchestrate);head.addWidget(refresh);root.addLayout(head)
        tabs=QTabWidget();root.addWidget(tabs,1)

        ep=QWidget();ev=QVBoxLayout(ep);eh=QHBoxLayout()
        add=QPushButton("New Endpoint");edit=QPushButton("Edit Endpoint");mapping=QPushButton("New Mapping Revision");validate=QPushButton("Validate Target")
        add.clicked.connect(self.add_endpoint);edit.clicked.connect(self.edit_endpoint);mapping.clicked.connect(self.edit_mapping);validate.clicked.connect(self.validate_endpoint)
        for b in [add,edit,mapping,validate]:eh.addWidget(b)
        eh.addStretch(1);ev.addLayout(eh)
        self.endpoint_table=_table(["Endpoint","Name","Adapter","Target","Topics","Auth Env","Enabled","Ver"]);self.endpoint_table.itemSelectionChanged.connect(self.load_endpoint_detail);ev.addWidget(self.endpoint_table,2)
        self.mapping_table=_table(["Endpoint","Revision","Active","Created By","Created","Ver"]);ev.addWidget(QLabel("Mapping revisions"));ev.addWidget(self.mapping_table,1);tabs.addTab(ep,"Endpoints / Mappings")

        monitor=QWidget();mv=QVBoxLayout(monitor);mh=QHBoxLayout()
        replay=QPushButton("Replay Selected");replay.clicked.connect(self.replay_delivery)
        mh.addWidget(replay);mh.addStretch(1);mv.addLayout(mh)
        self.delivery_table=_table(["ID","Event","Endpoint","Topic","Entity","Key","Status","Attempts","Next Attempt","Sent","Last Error"]);mv.addWidget(self.delivery_table);tabs.addTab(monitor,"Delivery Monitor")

        preview=QWidget();pv=QVBoxLayout(preview);ph=QHBoxLayout()
        self.preview_endpoint=QComboBox();show=QPushButton("Preview Selected Event");show.clicked.connect(self.preview_event)
        ph.addWidget(QLabel("Endpoint mapping"));ph.addWidget(self.preview_endpoint);ph.addWidget(show);ph.addStretch(1);pv.addLayout(ph)
        self.event_table=_table(["Event","Topic","Entity","Key","Created"]);pv.addWidget(self.event_table,2)
        self.preview_text=QTextEdit();self.preview_text.setReadOnly(True);pv.addWidget(self.preview_text,1);tabs.addTab(preview,"Payload Preview")

        rules=QWidget();rv=QVBoxLayout(rules);rh=QHBoxLayout()
        addr=QPushButton("New Rule");editr=QPushButton("Edit Rule");addr.clicked.connect(self.add_rule);editr.clicked.connect(self.edit_rule)
        rh.addWidget(addr);rh.addWidget(editr);rh.addStretch(1);rv.addLayout(rh)
        self.rule_table=_table(["Rule","Name","Topic","Action","Enabled","Priority","Ver"]);rv.addWidget(self.rule_table,2)
        self.execution_table=_table(["Time","Event","Rule","Status","Detail"]);rv.addWidget(QLabel("Rule execution history"));rv.addWidget(self.execution_table,1);tabs.addTab(rules,"Orchestration Rules")

        inbound=QWidget();iv=QVBoxLayout(inbound)
        self.receipt_table=_table(["Source","External Event","Topic","Entity","Key","Received","Internal Event"]);iv.addWidget(self.receipt_table);tabs.addTab(inbound,"Inbound Receipts")
        self.refresh()

    def refresh(self):
        self.endpoints=self.db.list_integration_endpoints();_fill(self.endpoint_table,self.endpoints,["endpoint_id","name","adapter_type","target","topics","auth_env","enabled","version"])
        self.deliveries=self.db.integration_delivery_details(1000);_fill(self.delivery_table,self.deliveries,["id","event_id","endpoint_id","topic","entity_type","entity_key","status","attempts","next_attempt_at","sent_at","last_error"])
        self.events=self.db.list_integration_events(500);_fill(self.event_table,self.events,["event_id","topic","entity_type","entity_key","created_at"])
        self.rules=self.db.list_orchestration_rules();_fill(self.rule_table,self.rules,["rule_id","name","topic_pattern","action_type","enabled","priority","version"])
        self.executions=self.db.list_orchestration_executions(500);_fill(self.execution_table,self.executions,["executed_at","event_id","rule_id","status","detail"])
        self.receipts=self.db.list_inbound_receipts(500);_fill(self.receipt_table,self.receipts,["source_id","external_event_id","topic","entity_type","entity_key","received_at","internal_event_id"])
        selected=self.preview_endpoint.currentText();self.preview_endpoint.clear();self.preview_endpoint.addItems([x.endpoint_id for x in self.endpoints])
        if selected:self.preview_endpoint.setCurrentText(selected)
        self.load_endpoint_detail()
        dead=sum(1 for x in self.deliveries if x["status"]=="Dead Letter");retry=sum(1 for x in self.deliveries if x["status"]=="Retry")
        self.summary.setText(f"{len(self.endpoints)} endpoints · {retry} retry · {dead} dead-letter · {len(self.rules)} rules")

    def current_endpoint(self):
        return _selected(self.endpoint_table,self.endpoints)

    def load_endpoint_detail(self):
        row=self.current_endpoint()
        mappings=self.db.list_integration_mappings(row.endpoint_id) if row else []
        _fill(self.mapping_table,mappings,["endpoint_id","revision","active","created_by","created_at","version"])

    def add_endpoint(self):
        d=EndpointDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_integration_endpoint(d.data());self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Endpoint",str(exc))

    def edit_endpoint(self):
        row=self.current_endpoint()
        if not row:return
        d=EndpointDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_integration_endpoint(d.data(),row.version);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Endpoint",str(exc))

    def edit_mapping(self):
        row=self.current_endpoint()
        if not row:return
        current=self.db.active_integration_mapping(row.endpoint_id)
        d=MappingDialog(row.endpoint_id,current,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            mapping,defaults=d.values()
            try:self.db.save_integration_mapping(row.endpoint_id,mapping,defaults,self.user["username"],True);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Mapping",str(exc))

    def validate_endpoint(self):
        row=self.current_endpoint()
        if not row:return
        try:
            if row.adapter_type=="FILE":
                root=Path(row.target).expanduser();root.mkdir(parents=True,exist_ok=True)
                with tempfile.NamedTemporaryFile(prefix=".ems_probe_",dir=str(root),delete=True) as fh:fh.write(b"EMS")
                detail=f"Writable FILE target: {root.resolve()}"
            else:
                parsed=urlparse(row.target)
                if parsed.scheme not in {"http","https"} or not parsed.netloc:raise ValueError("HTTP target must be an http(s) URL.")
                detail="HTTP configuration is syntactically valid. Live POST validation is intentionally not sent by this button."
            QMessageBox.information(self,"Endpoint validation",detail)
        except Exception as exc:QMessageBox.critical(self,"Endpoint validation",str(exc))

    def dispatch_now(self):
        try:
            result=dispatch_pending(self.db,500);QMessageBox.information(self,"Dispatch",json.dumps(result,indent=2));self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Dispatch",str(exc))

    def replay_delivery(self):
        row=_selected(self.delivery_table,self.deliveries)
        if not row:return
        try:self.db.replay_integration_delivery(int(row["id"]));self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Replay",str(exc))

    def preview_event(self):
        event=_selected(self.event_table,self.events)
        endpoint_id=self.preview_endpoint.currentText()
        if not event:return
        try:
            mapping=self.db.active_integration_mapping(endpoint_id) if endpoint_id else None
            payload=transform_event_payload(event,mapping)
            self.preview_text.setPlainText(json.dumps(payload,indent=2,ensure_ascii=False,sort_keys=True))
        except Exception as exc:QMessageBox.critical(self,"Payload preview",str(exc))

    def add_rule(self):
        d=RuleDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_orchestration_rule(d.data());self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Rule",str(exc))

    def edit_rule(self):
        row=_selected(self.rule_table,self.rules)
        if not row:return
        d=RuleDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_orchestration_rule(d.data(),row.version);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Rule",str(exc))

    def run_rules(self):
        try:
            result=process_pending_rules(self.db,500);QMessageBox.information(self,"Orchestration",json.dumps(result,indent=2));self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Orchestration",str(exc))
