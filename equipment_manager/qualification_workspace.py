from __future__ import annotations

import json
from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,QAbstractItemView,QComboBox,QFileDialog,QHBoxLayout,QHeaderView,
    QInputDialog,QLabel,QLineEdit,QMessageBox,QPushButton,QSpinBox,QSplitter,
    QTableWidget,QTableWidgetItem,QTabWidget,QTextEdit,QVBoxLayout,QWidget
)

from attachment_store import store_attachment_file
from collaboration_panel import CollaborationPanel
from custom_field_panel import CustomFieldPanel
from reporting import export_qualification_pptx, export_qualification_xlsx
from table_productivity import install_table_productivity
from workspaces import AttachmentPanel

FILE_ROOT = __import__("os").getenv("EMS_FILE_ROOT",str(__import__("pathlib").Path.cwd()/"equipment_files"))


def _item(value):
    if isinstance(value,datetime):value=value.strftime("%Y-%m-%d %H:%M")
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);t.setAlternatingRowColors(True)
    install_table_productivity(t,headers[0] if headers else "Qualification")
    return t


class QualificationWorkspace(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.run_no="";self.run=None;self.checks=[];self.results={};self._pending_evidence=""
        root=QVBoxLayout(self);head=QHBoxLayout()
        self.title=QLabel("Qualification Runner");self.title.setStyleSheet("font-size:20pt;font-weight:800")
        self.status=QLabel();self.status.setStyleSheet("font-size:12pt;font-weight:700")
        start=QPushButton("Start New");start.clicked.connect(self.start_new)
        self.open_eq=QPushButton("Open Equipment");self.open_eq.clicked.connect(self.open_equipment)
        ppt=QPushButton("Report PPTX");ppt.clicked.connect(self.export_pptx)
        xlsx=QPushButton("Report Excel");xlsx.clicked.connect(self.export_xlsx)
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh)
        head.addWidget(self.title);head.addWidget(self.status);head.addStretch(1)
        for b in [start,self.open_eq,ppt,xlsx,refresh]:head.addWidget(b)
        root.addLayout(head)
        self.context=QLabel("Select a qualification run from My Work or Equipment 360, or start a new run.");self.context.setStyleSheet("color:#647581");root.addWidget(self.context)

        action=QHBoxLayout()
        self.submit=QPushButton("Submit");self.submit.clicked.connect(self.submit_run)
        self.verify=QPushButton("Verify");self.verify.clicked.connect(self.verify_run)
        self.approve=QPushButton("Approve");self.approve.clicked.connect(self.approve_run)
        self.reject=QPushButton("Reject");self.reject.clicked.connect(self.reject_run)
        self.paste=QPushButton("Paste Results from Excel");self.paste.clicked.connect(self.paste_results)
        for b in [self.paste,self.submit,self.verify,self.approve,self.reject]:action.addWidget(b)
        action.addStretch(1);root.addLayout(action)

        self.tabs=QTabWidget();root.addWidget(self.tabs,1)
        runner=QWidget();rv=QVBoxLayout(runner);split=QSplitter()
        self.check_table=_table(["Check ID","Check","Acceptance","Result","Comment","Evidence","Entered By","Entered"])
        self.check_table.itemSelectionChanged.connect(self.load_selected_check);split.addWidget(self.check_table)
        inspector=QWidget();iv=QVBoxLayout(inspector)
        self.check_title=QLabel("Select a qualification check");self.check_title.setStyleSheet("font-size:13pt;font-weight:700");self.check_title.setWordWrap(True)
        self.acceptance=QLabel();self.acceptance.setWordWrap(True);self.result=QComboBox();self.result.addItems(["PASS","FAIL","NA"])
        self.comment=QTextEdit();self.comment.setMaximumHeight(120);self.comment.setPlaceholderText("Observation / evidence summary")
        self.evidence=QLabel("No check evidence selected");self.evidence.setWordWrap(True)
        attach=QPushButton("Attach Evidence to Check");attach.clicked.connect(self.attach_check_evidence)
        save=QPushButton("Save Check Result");save.clicked.connect(self.save_check)
        iv.addWidget(self.check_title);iv.addWidget(self.acceptance);iv.addWidget(QLabel("Result"));iv.addWidget(self.result);iv.addWidget(QLabel("Comment"));iv.addWidget(self.comment);iv.addWidget(self.evidence);iv.addWidget(attach);iv.addWidget(save);iv.addStretch(1)
        split.addWidget(inspector);split.setStretchFactor(0,3);split.setStretchFactor(1,2);rv.addWidget(split);self.tabs.addTab(runner,"Check Runner")

        history=QWidget();hv=QVBoxLayout(history);self.event_table=_table(["Action","User","Detail","Workstation","Time"]);hv.addWidget(self.event_table);self.tabs.addTab(history,"Lifecycle")
        self.attachments=AttachmentPanel(db,user);self.tabs.addTab(self.attachments,"Evidence / Attachments")
        self.collaboration=CollaborationPanel(db,user);self.tabs.addTab(self.collaboration,"Discussion / Team")
        self.custom_fields=CustomFieldPanel(db,user);self.tabs.addTab(self.custom_fields,"Configured Fields")
        self._set_controls(False)

    def _set_controls(self,has_run):
        self.open_eq.setEnabled(has_run);self.paste.setEnabled(has_run and self.run and self.run.status=="In Progress")
        self.submit.setEnabled(has_run and self.run and self.run.status=="In Progress" and self.db.has_permission(self.user,"qualification.execute"))
        self.verify.setEnabled(has_run and self.run and self.run.status=="Submitted" and self.db.has_permission(self.user,"qualification.verify"))
        self.approve.setEnabled(has_run and self.run and self.run.status=="Verified" and self.db.has_permission(self.user,"qualification.approve"))
        self.reject.setEnabled(has_run and self.run and self.run.status in {"Submitted","Verified"} and (self.db.has_permission(self.user,"qualification.verify") or self.db.has_permission(self.user,"qualification.approve")))

    def set_run(self,run_no: str):
        self.run_no=(run_no or "").strip();self.refresh()

    def refresh(self):
        self.run=next((x for x in self.db.list_qualification_runs() if x.run_no==self.run_no),None) if self.run_no else None
        if not self.run:
            self.title.setText("Qualification Runner");self.status.setText("");self.context.setText("Select a qualification run from My Work or Equipment 360, or start a new run.")
            self.checks=[];self.results={};self.check_table.setRowCount(0);self.event_table.setRowCount(0);self.attachments.set_entity("","");self.collaboration.set_entity("","");self.custom_fields.set_entity("","");self._set_controls(False);return
        r=self.run;self.title.setText(f"{r.run_no} · {r.protocol_name}");self.status.setText(r.status)
        self.context.setText(f"{r.equipment_id}    Protocol: {r.protocol_id} R{r.protocol_revision}    Started by: {r.started_by}    Expires: {r.expires_at or '—'}")
        self.checks,self.results=self.db.qualification_run_checks(r.id)
        self.check_table.setRowCount(len(self.checks))
        for row,check in enumerate(self.checks):
            cid=str(check.get("check_id",""));result=self.results.get(cid,{})
            vals=[cid,check.get("label",""),check.get("acceptance",""),result.get("result",""),result.get("comment",""),result.get("evidence_path",""),result.get("entered_by",""),result.get("entered_at","")]
            for col,val in enumerate(vals):self.check_table.setItem(row,col,_item(val))
        events=self.db.list_qualification_events(r.run_no)
        self.event_table.setRowCount(len(events))
        for row,event in enumerate(events):
            for col,val in enumerate([event.action,event.user,event.detail,event.workstation,event.occurred_at]):self.event_table.setItem(row,col,_item(val))
        self.attachments.set_entity("QUALIFICATION",r.run_no,r.equipment_id);self.collaboration.set_entity("QUALIFICATION",r.run_no,r.equipment_id)
        eq=self.db.get_equipment(r.equipment_id);self.custom_fields.set_entity("QUALIFICATION",r.run_no,eq.equipment_type if eq else "")
        self._set_controls(True)
        if self.checks and self.check_table.currentRow()<0:self.check_table.selectRow(0)

    def selected_check(self):
        idx=self.check_table.currentRow();return self.checks[idx] if 0<=idx<len(self.checks) else None

    def load_selected_check(self):
        check=self.selected_check()
        if not check:return
        cid=str(check.get("check_id",""));current=self.results.get(cid,{})
        self.check_title.setText(f"{cid} · {check.get('label','')}");self.acceptance.setText("Acceptance: "+str(check.get("acceptance","") or "—"))
        self.result.setCurrentText(str(current.get("result","PASS") or "PASS"));self.comment.setPlainText(str(current.get("comment","") or ""))
        self._pending_evidence=str(current.get("evidence_path","") or "");self.evidence.setText(self._pending_evidence or "No check evidence selected")

    def attach_check_evidence(self):
        if not self.run:return
        source,_=QFileDialog.getOpenFileName(self,"Qualification check evidence")
        if not source:return
        try:
            stored=store_attachment_file(source,FILE_ROOT,"QUALIFICATION",self.run.run_no)
            row=self.db.add_attachment("QUALIFICATION",self.run.run_no,stored["stored_path"],original_name=stored["original_name"],media_type=stored["media_type"],category="Check Evidence",caption=self.check_title.text(),equipment_id=self.run.equipment_id,created_by=self.user["username"])
            self._pending_evidence=row.stored_path;self.evidence.setText(row.stored_path);self.attachments.refresh()
        except Exception as exc:QMessageBox.critical(self,"Qualification evidence",str(exc))

    def save_check(self):
        if not self.run or self.run.status!="In Progress":return
        check=self.selected_check()
        if not check:return
        try:
            self.run=self.db.save_qualification_result(self.run.id,str(check["check_id"]),self.result.currentText(),self.comment.toPlainText(),self.user["username"],self._pending_evidence,"QUALIFICATION-RUNNER",self.run.version)
            self.run_no=self.run.run_no;self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Qualification result",str(exc))

    def paste_results(self):
        if not self.run or self.run.status!="In Progress":return
        text=QApplication.clipboard().text().strip()
        if not text:QMessageBox.information(self,"Paste results","Clipboard is empty.");return
        lines=[x for x in text.splitlines() if x.strip()];updates=[];errors=[]
        valid={str(x.get("check_id","")) for x in self.checks}
        for n,line in enumerate(lines,1):
            cols=line.split("\t")
            if n==1 and cols[0].strip().lower() in {"check","check_id","check id"}:continue
            if len(cols)<2:errors.append(f"Row {n}: need Check ID and Result");continue
            cid=cols[0].strip();result=cols[1].strip().upper();comment=cols[2].strip() if len(cols)>2 else ""
            if cid not in valid:errors.append(f"Row {n}: unknown check {cid}");continue
            if result not in {"PASS","FAIL","NA"}:errors.append(f"Row {n}: result must be PASS/FAIL/NA");continue
            updates.append((cid,result,comment))
        if errors:
            QMessageBox.warning(self,"Paste results","Validation failed; nothing was committed.\n" + "\n".join(errors[:20]));return
        if not updates:return
        if QMessageBox.question(self,"Paste results",f"Apply {len(updates)} qualification result(s)?")!=QMessageBox.StandardButton.Yes:return
        try:
            current=self.run
            for cid,result,comment in updates:
                existing=self.results.get(cid,{})
                current=self.db.save_qualification_result(current.id,cid,result,comment,self.user["username"],str(existing.get("evidence_path","") or ""),"QUALIFICATION-PASTE",current.version)
            self.run=current;self.run_no=current.run_no;self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Paste results",str(exc))

    def start_new(self):
        equipment,ok=QInputDialog.getText(self,"Start qualification","Equipment ID")
        if not ok or not equipment.strip():return
        eq=self.db.get_equipment(equipment.strip())
        if not eq:QMessageBox.warning(self,"Qualification","Equipment not found.");return
        protocols=[x for x in self.db.list_qualification_protocols(True) if (not x.equipment_id or x.equipment_id==eq.equipment_id) and (not x.equipment_type or x.equipment_type==eq.equipment_type)]
        if not protocols:QMessageBox.warning(self,"Qualification","No applicable active qualification protocol.");return
        labels=[f"{x.protocol_id} R{x.revision} — {x.name}" for x in protocols]
        choice,ok=QInputDialog.getItem(self,"Start qualification","Protocol",labels,0,False)
        if not ok:return
        protocol=protocols[labels.index(choice)]
        try:
            run=self.db.start_qualification_run(eq.equipment_id,protocol.protocol_id,self.user["username"],workstation="QUALIFICATION-RUNNER")
            self.set_run(run.run_no)
        except Exception as exc:QMessageBox.critical(self,"Qualification",str(exc))

    def submit_run(self):
        if not self.run:return
        conclusion,ok=QInputDialog.getMultiLineText(self,"Submit qualification","Conclusion")
        if not ok:return
        try:self.run=self.db.submit_qualification_run(self.run.id,self.user["username"],conclusion,"QUALIFICATION-RUNNER",self.run.version);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Qualification",str(exc))

    def verify_run(self):
        if not self.run:return
        note,ok=QInputDialog.getMultiLineText(self,"Verify qualification","Independent verification note")
        if not ok:return
        try:self.run=self.db.verify_qualification_run(self.run.id,self.user["username"],note,"QUALIFICATION-RUNNER",self.run.version);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Qualification",str(exc))

    def approve_run(self):
        if not self.run:return
        days,ok=QInputDialog.getInt(self,"Approve qualification","Validity days (0 = no expiry)",30,0,3650)
        if not ok:return
        note,ok=QInputDialog.getMultiLineText(self,"Approve qualification","Approval note")
        if not ok:return
        try:self.run=self.db.approve_qualification_run(self.run.id,self.user["username"],days or None,note,"QUALIFICATION-RUNNER",self.run.version);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Qualification",str(exc))

    def reject_run(self):
        if not self.run:return
        reason,ok=QInputDialog.getMultiLineText(self,"Reject qualification","Rejection reason")
        if not ok or not reason.strip():return
        try:self.run=self.db.reject_qualification_run(self.run.id,self.user["username"],reason,"QUALIFICATION-RUNNER",self.run.version);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Qualification",str(exc))

    def export_pptx(self):
        if not self.run:return
        path,_=QFileDialog.getSaveFileName(self,"Export Qualification PowerPoint",f"{self.run.run_no}_Qualification.pptx","PowerPoint (*.pptx)")
        if not path:return
        if not path.lower().endswith(".pptx"):path+=".pptx"
        try:export_qualification_pptx(self.db,self.run.run_no,path);QMessageBox.information(self,"Qualification report",f"Editable deck created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"Qualification report",str(exc))

    def export_xlsx(self):
        if not self.run:return
        path,_=QFileDialog.getSaveFileName(self,"Export Qualification Excel",f"{self.run.run_no}_Qualification.xlsx","Excel Workbook (*.xlsx)")
        if not path:return
        if not path.lower().endswith(".xlsx"):path+=".xlsx"
        try:export_qualification_xlsx(self.db,self.run.run_no,path);QMessageBox.information(self,"Qualification report",f"Workbook created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"Qualification report",str(exc))

    def open_equipment(self):
        if self.run:self.open_entity.emit("EQUIPMENT",self.run.equipment_id,self.run.equipment_id)
