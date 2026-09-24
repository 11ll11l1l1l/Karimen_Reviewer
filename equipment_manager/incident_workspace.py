from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget, QInputDialog,
)

from table_productivity import install_table_productivity
from workspaces import AttachmentPanel
from collaboration_panel import CollaborationPanel
from configuration_studio import CustomFieldsPanel
from reporting import export_incident_pptx, export_incident_xlsx


def _item(value):
    if isinstance(value,datetime):value=value.strftime("%Y-%m-%d %H:%M")
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);t.setAlternatingRowColors(True)
    install_table_productivity(t,headers[0] if headers else "Incident")
    return t


def _fill(table,rows,fields):
    table.setRowCount(len(rows))
    for r,row in enumerate(rows):
        for c,field in enumerate(fields):table.setItem(r,c,_item(getattr(row,field,"") if not isinstance(row,dict) else row.get(field,"")))


def _selected(table,rows):
    i=table.currentRow()
    return rows[i] if 0<=i<len(rows) else None


class IncidentActionDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Incident Action")
        f=QFormLayout(self);self.type=QComboBox();self.type.addItems(["Containment","Corrective","Preventive","Follow-up"])
        self.description=QTextEdit();self.owner=QLineEdit();self.due=QDateTimeEdit();self.due.setCalendarPopup(True);self.due.setDateTime(datetime.now());self.criteria=QTextEdit()
        f.addRow("Type",self.type);f.addRow("Action",self.description);f.addRow("Owner",self.owner);f.addRow("Due",self.due);f.addRow("Effectiveness criteria",self.criteria)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:
            self.type.setCurrentText(row.action_type);self.description.setPlainText(row.description);self.owner.setText(row.owner);self.criteria.setPlainText(row.effectiveness_criteria)
            if row.due_at:self.due.setDateTime(row.due_at)

    def data(self):
        return {"action_type":self.type.currentText(),"description":self.description.toPlainText().strip(),"owner":self.owner.text().strip(),"due_at":self.due.dateTime().toPython(),"effectiveness_criteria":self.criteria.toPlainText().strip()}


class CausalFactorDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Causal Factor")
        f=QFormLayout(self);self.category=QComboBox();self.category.addItems(["Man","Machine","Method","Material","Measurement","Environment","Software","Process","Other"])
        self.factor_type=QComboBox();self.factor_type.addItems(["Suspected","Contributing","Verified Root Cause","Ruled Out"])
        self.description=QTextEdit();self.evidence=QTextEdit();self.status=QComboBox();self.status.addItems(["Open","Under Review","Confirmed","Closed"])
        f.addRow("Category",self.category);f.addRow("Type",self.factor_type);f.addRow("Description",self.description);f.addRow("Evidence / counterevidence",self.evidence);f.addRow("Status",self.status)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:
            self.category.setCurrentText(row.category);self.factor_type.setCurrentText(row.factor_type);self.description.setPlainText(row.description);self.evidence.setPlainText(row.evidence);self.status.setCurrentText(row.status)

    def data(self):
        return {"category":self.category.currentText(),"factor_type":self.factor_type.currentText(),"description":self.description.toPlainText().strip(),"evidence":self.evidence.toPlainText().strip(),"status":self.status.currentText()}


class IncidentWorkspace(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.ticket_no="";self.ticket=None
        self.whys=[];self.factors=[];self.actions=[];self.similar=[];self.lifecycle=[];self.investigations=[];self.escalations=[]
        root=QVBoxLayout(self);head=QHBoxLayout()
        self.title=QLabel("Incident Workspace");self.title.setStyleSheet("font-size:20pt;font-weight:800")
        self.status=QLabel();self.status.setStyleSheet("font-size:12pt;font-weight:700")
        self.open_eq=QPushButton("Open Equipment");self.open_eq.clicked.connect(self.open_equipment)
        self.work_order_button=QPushButton("Create / Open Work Order");self.work_order_button.clicked.connect(self.open_work_order)
        ppt=QPushButton("Export PPTX");ppt.clicked.connect(self.export_pptx)
        xlsx=QPushButton("Export Excel");xlsx.clicked.connect(self.export_xlsx)
        legacy=QPushButton("Lifecycle / troubleshooting editor");legacy.clicked.connect(self.open_legacy)
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh)
        head.addWidget(self.title);head.addWidget(self.status);head.addStretch(1);head.addWidget(self.open_eq);head.addWidget(self.work_order_button);head.addWidget(ppt);head.addWidget(xlsx);head.addWidget(legacy);head.addWidget(refresh);root.addLayout(head)
        self.context=QLabel("Select an incident from Global Search, My Work, or Equipment 360.");self.context.setWordWrap(True);self.context.setStyleSheet("color:#647581;");root.addWidget(self.context)

        self.tabs=QTabWidget();root.addWidget(self.tabs,1)
        overview=QWidget();ov=QVBoxLayout(overview);self.description=QTextEdit();self.root_cause=QTextEdit();self.corrective=QTextEdit();self.verification=QTextEdit()
        for label,widget in [("Problem / description",self.description),("Root cause summary",self.root_cause),("Corrective action summary",self.corrective),("Verification summary",self.verification)]:
            ov.addWidget(QLabel(label));ov.addWidget(widget)
        save=QPushButton("Save incident summary");save.clicked.connect(self.save_summary);ov.addWidget(save);self.tabs.addTab(overview,"Incident Summary")

        ops=QWidget();opv=QVBoxLayout(ops);self.control_table=_table(["Containment","Production Impact","Affected Lots","Safety/Quality Risk","Response Due","Containment Due","Resolution Due","Esc Level","Esc Reason"]);opv.addWidget(self.control_table)
        self.escalation_table=_table(["From","To","Reason","User","Time"]);opv.addWidget(QLabel("Escalation history"));opv.addWidget(self.escalation_table);self.tabs.addTab(ops,"Containment / SLA")

        activity=QWidget();av=QVBoxLayout(activity);self.lifecycle_table=_table(["From","To","Reason","Note","Owner","Changed by","Time"]);self.investigation_table=_table(["#","Observation","Check","Result","Conclusion","Action","By","Time"])
        av.addWidget(QLabel("Lifecycle"));av.addWidget(self.lifecycle_table,1);av.addWidget(QLabel("Troubleshooting / investigation"));av.addWidget(self.investigation_table,1);self.tabs.addTab(activity,"Activity")

        why=QWidget();wv=QVBoxLayout(why);wh=QHBoxLayout();editwhy=QPushButton("Edit selected Why");editwhy.clicked.connect(self.edit_why);nextwhy=QPushButton("Add next Why");nextwhy.clicked.connect(self.add_next_why);wh.addWidget(editwhy);wh.addWidget(nextwhy);wh.addStretch(1);wv.addLayout(wh)
        self.why_table=_table(["Why #","Question","Answer","Updated by","Updated","Ver"]);wv.addWidget(self.why_table);self.tabs.addTab(why,"5-Why")

        factors=QWidget();fv=QVBoxLayout(factors);fh=QHBoxLayout();addf=QPushButton("Add factor");editf=QPushButton("Edit selected");addf.clicked.connect(self.add_factor);editf.clicked.connect(self.edit_factor);fh.addWidget(addf);fh.addWidget(editf);fh.addStretch(1);fv.addLayout(fh)
        self.factor_table=_table(["ID","Category","Type","Description","Evidence / Counterevidence","Status","Created by","Ver"]);fv.addWidget(self.factor_table);self.tabs.addTab(factors,"Causal Factors")

        actions=QWidget();actv=QVBoxLayout(actions);ah=QHBoxLayout();adda=QPushButton("Add action");edita=QPushButton("Edit selected");complete=QPushButton("Complete");verify=QPushButton("Verify effectiveness")
        adda.clicked.connect(self.add_action);edita.clicked.connect(self.edit_action);complete.clicked.connect(self.complete_action);verify.clicked.connect(self.verify_action)
        for b in [adda,edita,complete,verify]:ah.addWidget(b)
        ah.addStretch(1);actv.addLayout(ah);self.action_table=_table(["ID","Type","Action","Owner","Due","Status","Effectiveness criteria","Completed by","Completed","Verified by","Verified","Ver"]);actv.addWidget(self.action_table);self.tabs.addTab(actions,"CAPA / Actions")

        history=QWidget();hv=QVBoxLayout(history);self.similar_table=_table(["Ticket","Title","Priority","Status","Owner","Created","Updated"]);self.similar_table.doubleClicked.connect(self.open_similar);hv.addWidget(QLabel("Other incidents on the same equipment"));hv.addWidget(self.similar_table);self.tabs.addTab(history,"Recurrence History")

        self.attachments=AttachmentPanel(db,user);self.tabs.addTab(self.attachments,"Evidence / Attachments")
        self.collaboration=CollaborationPanel(db,user);self.tabs.addTab(self.collaboration,"Comments / Watchers")
        self.custom_fields=CustomFieldsPanel(db,user);self.tabs.addTab(self.custom_fields,"Custom Fields")
        self._set_enabled(False)

    def _set_enabled(self,enabled):
        self.open_eq.setEnabled(enabled)
        for w in [self.description,self.root_cause,self.corrective,self.verification]:w.setEnabled(enabled)

    def set_ticket(self,ticket_no: str):
        self.ticket_no=(ticket_no or "").strip();self.refresh()

    def refresh(self):
        if not self.ticket_no:
            self.ticket=None;self._set_enabled(False);self.attachments.set_entity("","");self.collaboration.set_entity("","");self.custom_fields.set_entity("","");return
        self.ticket=next((x for x in self.db.list_tickets() if x.ticket_no==self.ticket_no),None)
        if not self.ticket:
            self.title.setText("Incident not found");self._set_enabled(False);return
        t=self.ticket;self._set_enabled(True)
        self.db.record_recent_item(self.user["username"],"TICKET",t.ticket_no,f"{t.ticket_no} — {t.title}",t.equipment_id)
        self.title.setText(f"{t.ticket_no} · {t.title}");self.status.setText(f"{t.priority} · {t.status}")
        self.context.setText(f"{t.equipment_id}    Severity: {t.severity}    Owner: {t.owner or '—'}    Created by: {t.created_by}")
        self.description.setPlainText(t.description or "");self.root_cause.setPlainText(t.root_cause or "");self.corrective.setPlainText(t.corrective_action or "");self.verification.setPlainText(t.verification or "")
        control=self.db.ticket_operational_control(t.ticket_no);_fill(self.control_table,[control] if control else [],["containment","production_impact","affected_lots","safety_quality_risk","response_due_at","containment_due_at","resolution_due_at","escalation_level","escalation_reason"])
        self.escalations=self.db.list_ticket_escalations(t.ticket_no);_fill(self.escalation_table,self.escalations,["from_level","to_level","reason","user","occurred_at"])
        self.lifecycle=self.db.list_ticket_state_events(t.ticket_no);_fill(self.lifecycle_table,self.lifecycle,["from_state","to_state","reason_code","note","owner","changed_by","changed_at"])
        self.investigations=self.db.list_ticket_investigations(t.ticket_no);_fill(self.investigation_table,self.investigations,["sequence","observation","check_performed","result","conclusion","action","entered_by","entered_at"])
        self.whys=self.db.list_incident_whys(t.ticket_no);_fill(self.why_table,self.whys,["sequence","question","answer","updated_by","updated_at","version"])
        self.factors=self.db.list_incident_causal_factors(t.ticket_no);_fill(self.factor_table,self.factors,["id","category","factor_type","description","evidence","status","created_by","version"])
        self.actions=self.db.list_incident_actions(t.ticket_no);_fill(self.action_table,self.actions,["id","action_type","description","owner","due_at","status","effectiveness_criteria","completed_by","completed_at","verified_by","verified_at","version"])
        self.similar=self.db.incident_similar_history(t.ticket_no);_fill(self.similar_table,self.similar,["ticket_no","title","priority","status","owner","created_at","updated_at"])
        self.attachments.set_entity("TICKET",t.ticket_no,t.equipment_id)
        self.collaboration.set_entity("TICKET",t.ticket_no,t.equipment_id)
        equipment=self.db.get_equipment(t.equipment_id)
        self.custom_fields.set_entity("TICKET",t.ticket_no,equipment.equipment_type if equipment else "")

    def save_summary(self):
        if not self.ticket:return
        t=self.ticket
        data={"ticket_no":t.ticket_no,"equipment_id":t.equipment_id,"title":t.title,"description":self.description.toPlainText().strip(),"severity":t.severity,"priority":t.priority,"owner":t.owner,"root_cause":self.root_cause.toPlainText().strip(),"corrective_action":self.corrective.toPlainText().strip(),"verification":self.verification.toPlainText().strip(),"created_by":t.created_by}
        try:self.db.save_ticket(data,t.version,workstation="INCIDENT-WORKSPACE");self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Incident",str(exc))

    def edit_why(self):
        row=_selected(self.why_table,self.whys)
        if not row:return
        q,ok=QInputDialog.getMultiLineText(self,"5-Why",f"Question / prompt for Why {row.sequence}",row.question or f"Why {row.sequence}?")
        if not ok:return
        a,ok=QInputDialog.getMultiLineText(self,"5-Why","Answer",row.answer)
        if not ok:return
        try:self.db.save_incident_why(self.ticket_no,row.sequence,q,a,self.user["username"],row.version);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"5-Why",str(exc))

    def add_next_why(self):
        seq=max([x.sequence for x in self.whys],default=0)+1
        if seq>10:QMessageBox.information(self,"5-Why","Maximum 10 Why levels supported.");return
        q,ok=QInputDialog.getMultiLineText(self,"5-Why",f"Question / prompt for Why {seq}",f"Why {seq}?")
        if not ok:return
        a,ok=QInputDialog.getMultiLineText(self,"5-Why","Answer")
        if not ok:return
        try:self.db.save_incident_why(self.ticket_no,seq,q,a,self.user["username"]);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"5-Why",str(exc))

    def add_factor(self):
        d=CausalFactorDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_incident_causal_factor(self.ticket_no,d.data(),self.user["username"]);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Causal factor",str(exc))

    def edit_factor(self):
        row=_selected(self.factor_table,self.factors)
        if not row:return
        d=CausalFactorDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_incident_causal_factor(self.ticket_no,d.data(),self.user["username"],row.id,row.version);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Causal factor",str(exc))

    def add_action(self):
        d=IncidentActionDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_incident_action(self.ticket_no,d.data(),self.user["username"]);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Incident action",str(exc))

    def edit_action(self):
        row=_selected(self.action_table,self.actions)
        if not row:return
        d=IncidentActionDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_incident_action(self.ticket_no,d.data(),self.user["username"],row.id,row.version);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Incident action",str(exc))

    def complete_action(self):
        row=_selected(self.action_table,self.actions)
        if not row:return
        note,ok=QInputDialog.getMultiLineText(self,"Complete action","Completion result / evidence summary")
        if not ok:return
        try:self.db.complete_incident_action(row.id,self.user["username"],note,row.version);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Incident action",str(exc))

    def verify_action(self):
        row=_selected(self.action_table,self.actions)
        if not row:return
        note,ok=QInputDialog.getMultiLineText(self,"Verify effectiveness","Effectiveness verification")
        if not ok:return
        try:self.db.verify_incident_action(row.id,self.user["username"],note,row.version);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Incident action",str(exc))

    def export_pptx(self):
        if not self.ticket:return
        default=f"{self.ticket.ticket_no}_Incident_Review.pptx"
        path,_=QFileDialog.getSaveFileName(self,"Export Incident PowerPoint",default,"PowerPoint (*.pptx)")
        if not path:return
        if not path.lower().endswith(".pptx"):path+=".pptx"
        try:export_incident_pptx(self.db,self.ticket.ticket_no,path);QMessageBox.information(self,"PowerPoint",f"Editable incident review deck created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"PowerPoint",str(exc))

    def export_xlsx(self):
        if not self.ticket:return
        default=f"{self.ticket.ticket_no}_Incident_Data.xlsx"
        path,_=QFileDialog.getSaveFileName(self,"Export Incident Excel",default,"Excel Workbook (*.xlsx)")
        if not path:return
        if not path.lower().endswith(".xlsx"):path+=".xlsx"
        try:export_incident_xlsx(self.db,self.ticket.ticket_no,path);QMessageBox.information(self,"Excel",f"Incident workbook created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"Excel",str(exc))

    def open_work_order(self):
        if not self.ticket:return
        try:
            row=self.db.create_work_order_from_ticket(self.ticket.ticket_no,self.user["username"],"INCIDENT-WORKSPACE")
            self.open_entity.emit("WORK_ORDER",row.work_order_no,row.equipment_id)
        except Exception as exc:QMessageBox.critical(self,"Work order",str(exc))

    def open_equipment(self):
        if self.ticket:self.open_entity.emit("EQUIPMENT",self.ticket.equipment_id,self.ticket.equipment_id)

    def open_legacy(self):
        if self.ticket:self.open_entity.emit("TICKET_LEGACY",self.ticket.ticket_no,self.ticket.equipment_id)

    def open_similar(self):
        row=_selected(self.similar_table,self.similar)
        if row:self.set_ticket(row.ticket_no)
