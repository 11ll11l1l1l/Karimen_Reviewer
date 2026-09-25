from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,QCheckBox,QComboBox,QFileDialog,QGridLayout,QHBoxLayout,QHeaderView,
    QInputDialog,QLabel,QLineEdit,QMessageBox,QPushButton,QSpinBox,QSplitter,QTableWidget,
    QTableWidgetItem,QTabWidget,QTextEdit,QVBoxLayout,QWidget,
)

from attachment_store import default_file_root, store_attachment_file
from collaboration_panel import CollaborationPanel
from feedback import notify
from pdf_reporting import export_qualification_pdf, export_release_pdf
from reporting import (
    export_qualification_pptx,export_qualification_xlsx,
    export_release_pptx,export_release_xlsx,
)
from table_productivity import install_table_productivity
from workspaces import AttachmentPanel

FILE_ROOT=default_file_root()
RELEASE_CHECKS=[
    ("maintenance_complete","Maintenance complete"),
    ("measurements_pass","Measurements pass"),
    ("calibration_valid","Calibration valid"),
    ("safety_check","Safety check"),
    ("verification_run","Verification run"),
    ("critical_tickets_cleared","Critical tickets cleared"),
]


def _item(value):
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setAlternatingRowColors(True);t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    install_table_productivity(t,headers[0] if headers else "Return to Service")
    return t


def _selected(table,rows):
    i=table.currentRow();return rows[i] if 0<=i<len(rows) else None


class ReturnToServiceWorkspace(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.equipment_id="";self.run_no="";self.release_id=0
        self.runs=[];self.releases=[];self.run=None;self.release=None;self.checks=[];self.results={}
        root=QVBoxLayout(self);head=QHBoxLayout()
        title=QLabel("Return to Service");title.setStyleSheet("font-size:20pt;font-weight:800")
        self.equipment=QLineEdit();self.equipment.setPlaceholderText("Equipment ID");self.equipment.returnPressed.connect(self.load_equipment)
        open_eq=QPushButton("Open Equipment");open_eq.clicked.connect(self.open_equipment)
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh)
        head.addWidget(title);head.addStretch(1);head.addWidget(self.equipment);head.addWidget(open_eq);head.addWidget(refresh);root.addLayout(head)
        self.status=QLabel("Select equipment or open a qualification/release from My Work, Work Orders or Equipment 360.")
        self.status.setWordWrap(True);self.status.setStyleSheet("color:#647581");root.addWidget(self.status)
        tabs=QTabWidget();self.tabs=tabs;root.addWidget(tabs,1)

        # Qualification
        qw=QWidget();qv=QVBoxLayout(qw)
        qtop=QHBoxLayout();self.protocol=QComboBox();start=QPushButton("Start Qualification");start.clicked.connect(self.start_run)
        submit=QPushButton("Submit");submit.clicked.connect(self.submit_run)
        verify=QPushButton("Verify");verify.clicked.connect(self.verify_run)
        approve=QPushButton("Approve");approve.clicked.connect(self.approve_run)
        reject=QPushButton("Reject");reject.clicked.connect(self.reject_run)
        for w in [QLabel("Protocol"),self.protocol,start,submit,verify,approve,reject]:qtop.addWidget(w)
        qtop.addStretch(1);qv.addLayout(qtop)
        qsplit=QSplitter()
        left=QWidget();lv=QVBoxLayout(left)
        self.run_table=_table(["Run","Protocol","Rev","Status","Started By","Submitted By","Verified By","Approved By","Expires"])
        self.run_table.itemSelectionChanged.connect(self.load_run);lv.addWidget(self.run_table)
        qsplit.addWidget(left)
        right=QWidget();rv=QVBoxLayout(right)
        self.run_summary=QLabel("No qualification run selected.");self.run_summary.setWordWrap(True);self.run_summary.setStyleSheet("background:#f8fafb;border:1px solid #d7dfe5;padding:8px;");rv.addWidget(self.run_summary)
        self.check_table=_table(["Check","Description","Acceptance","Result","Comment","Entered By"])
        self.check_table.itemSelectionChanged.connect(self.load_check);rv.addWidget(self.check_table,2)
        self.check_title=QLabel("Select a qualification check");self.check_title.setStyleSheet("font-weight:700");self.check_title.setWordWrap(True);rv.addWidget(self.check_title)
        form=QHBoxLayout();self.check_result=QComboBox();self.check_result.addItems(["PASS","FAIL","NA"]);self.check_comment=QLineEdit();self.check_comment.setPlaceholderText("Observation / comment")
        save=QPushButton("Save Result");save.clicked.connect(self.save_check);evidence=QPushButton("Attach Check Evidence");evidence.clicked.connect(self.attach_check_evidence)
        form.addWidget(QLabel("Result"));form.addWidget(self.check_result);form.addWidget(self.check_comment,1);form.addWidget(evidence);form.addWidget(save);rv.addLayout(form)
        qsplit.addWidget(right);qsplit.setStretchFactor(0,1);qsplit.setStretchFactor(1,2);qv.addWidget(qsplit,3)
        self.qual_attachments=AttachmentPanel(db,user);qv.addWidget(self.qual_attachments,2)
        qreport=QHBoxLayout();qppt=QPushButton("Qualification PPTX");qxlsx=QPushButton("Qualification Excel");qpdf=QPushButton("Qualification PDF")
        qppt.clicked.connect(self.export_qual_pptx);qxlsx.clicked.connect(self.export_qual_xlsx);qpdf.clicked.connect(self.export_qual_pdf)
        for b in [qppt,qxlsx,qpdf]:qreport.addWidget(b)
        qreport.addStretch(1);qv.addLayout(qreport)
        tabs.addTab(qw,"Qualification")

        # Release
        rw=QWidget();rr=QVBoxLayout(rw)
        rtop=QHBoxLayout();new=QPushButton("New Release Request");new.clicked.connect(self.new_release);verifyrel=QPushButton("Verify Checklist");verifyrel.clicked.connect(self.verify_release);approverel=QPushButton("Approve / Release");approverel.clicked.connect(self.approve_release)
        for b in [new,verifyrel,approverel]:rtop.addWidget(b)
        rtop.addStretch(1);rr.addLayout(rtop)
        self.precheck=QLabel();self.precheck.setWordWrap(True);self.precheck.setStyleSheet("background:#f8fafb;border:1px solid #d7dfe5;padding:8px;");rr.addWidget(self.precheck)
        rsplit=QSplitter();rleft=QWidget();rlv=QVBoxLayout(rleft)
        self.release_table=_table(["ID","Status","Ticket","Requested By","Verified By","Approved By","Requested","Approved"])
        self.release_table.itemSelectionChanged.connect(self.load_release);rlv.addWidget(self.release_table);rsplit.addWidget(rleft)
        rright=QWidget();rrv=QVBoxLayout(rright)
        self.release_context=QLabel("No release request selected.");self.release_context.setWordWrap(True);rrv.addWidget(self.release_context)
        self.release_checks={}
        checks=QGridLayout()
        for i,(key,label) in enumerate(RELEASE_CHECKS):
            box=QCheckBox(label);self.release_checks[key]=box;checks.addWidget(box,i//2,i%2)
        rrv.addLayout(checks)
        self.release_ticket=QLineEdit();self.release_ticket.setPlaceholderText("Related ticket (optional)")
        self.release_notes=QTextEdit();self.release_notes.setPlaceholderText("Release notes / verification context");self.release_notes.setMaximumHeight(90)
        rrv.addWidget(self.release_ticket);rrv.addWidget(self.release_notes)
        rsplit.addWidget(rright);rsplit.setStretchFactor(0,1);rsplit.setStretchFactor(1,1);rr.addWidget(rsplit,2)
        self.release_attachments=AttachmentPanel(db,user);rr.addWidget(self.release_attachments,2)
        rreport=QHBoxLayout();rppt=QPushButton("Release PPTX");rxlsx=QPushButton("Release Excel");rpdf=QPushButton("Release PDF")
        rppt.clicked.connect(self.export_release_pptx);rxlsx.clicked.connect(self.export_release_xlsx);rpdf.clicked.connect(self.export_release_pdf)
        for b in [rppt,rxlsx,rpdf]:rreport.addWidget(b)
        rreport.addStretch(1);rr.addLayout(rreport)
        tabs.addTab(rw,"Release")

        self.collaboration=CollaborationPanel(db,user);tabs.addTab(self.collaboration,"Comments / Watchers")

        submit.setEnabled(db.has_permission(user,"qualification.execute"));start.setEnabled(db.has_permission(user,"qualification.execute"))
        verify.setEnabled(db.has_permission(user,"qualification.verify"));approve.setEnabled(db.has_permission(user,"qualification.approve"))
        reject.setEnabled(db.has_permission(user,"qualification.verify") or db.has_permission(user,"qualification.approve"))
        verifyrel.setEnabled(db.has_permission(user,"release.verify"));approverel.setEnabled(db.has_permission(user,"release.approve"))
        new.setEnabled(db.has_permission(user,"release.verify") or db.has_permission(user,"disposition.edit"))

    def set_equipment(self,equipment_id: str):
        self.equipment_id=(equipment_id or "").strip();self.equipment.setText(self.equipment_id);self.refresh()

    def set_qualification(self,run_no: str,equipment_id: str=""):
        self.run_no=str(run_no or "");self.equipment_id=(equipment_id or "").strip()
        if self.equipment_id:self.equipment.setText(self.equipment_id)
        self.refresh()
        for i,row in enumerate(self.runs):
            if row.run_no==self.run_no:self.run_table.selectRow(i);break

    def set_release(self,release_id: int,equipment_id: str=""):
        self.release_id=int(release_id or 0);self.equipment_id=(equipment_id or "").strip()
        if self.equipment_id:self.equipment.setText(self.equipment_id)
        self.refresh()
        for i,row in enumerate(self.releases):
            if row.id==self.release_id:self.release_table.selectRow(i);break

    def load_equipment(self):
        self.set_equipment(self.equipment.text().strip())

    def refresh(self):
        if not self.equipment_id:self.equipment_id=self.equipment.text().strip()
        if not self.equipment_id:
            self.status.setText("Select equipment or open a qualification/release from another workspace.");return
        eq=self.db.get_equipment(self.equipment_id)
        if not eq:
            self.status.setText("Equipment not found.");return
        self.status.setText(f"{eq.equipment_id} · {eq.name}    State: {eq.status}    Disposition: {eq.disposition}    Owner: {eq.owner or '—'}")
        protocols=self.db.applicable_qualification_protocols(eq.equipment_id)
        current_protocol=self.protocol.currentData()
        self.protocol.clear()
        for p in protocols:self.protocol.addItem(f"{p.protocol_id} R{p.revision} — {p.name}",p.protocol_id)
        if current_protocol:
            idx=self.protocol.findData(current_protocol)
            if idx>=0:self.protocol.setCurrentIndex(idx)
        self.runs=self.db.list_qualification_runs(eq.equipment_id)
        self.run_table.setRowCount(len(self.runs))
        for r,row in enumerate(self.runs):
            vals=[row.run_no,row.protocol_id,row.protocol_revision,row.status,row.started_by,row.submitted_by,row.verified_by,row.approved_by,row.expires_at]
            for col,val in enumerate(vals):self.run_table.setItem(r,col,_item(val))
        self.releases=[x for x in self.db.list_release_requests() if x.equipment_id==eq.equipment_id]
        self.release_table.setRowCount(len(self.releases))
        for r,row in enumerate(self.releases):
            vals=[row.id,row.status,row.related_ticket,row.requested_by,row.verified_by,row.approved_by,row.requested_at,row.approved_at]
            for col,val in enumerate(vals):self.release_table.setItem(r,col,_item(val))
        pre=self.db.release_precheck(eq.equipment_id)
        self.precheck.setText(
            f"Release precheck — P1/P2 open: {pre['critical_tickets_open']} · Overdue PM: {pre['overdue_pm']} · "
            f"Qualification required: {'Yes' if pre['qualification_required'] else 'No'} · "
            f"Valid qualification: {pre['qualification_run_no'] or 'None'}"
        )
        if self.run_no:
            for i,row in enumerate(self.runs):
                if row.run_no==self.run_no:self.run_table.selectRow(i);break
        if self.release_id:
            for i,row in enumerate(self.releases):
                if row.id==self.release_id:self.release_table.selectRow(i);break
        if self.run_table.currentRow()<0 and self.runs:self.run_table.selectRow(0)
        if self.release_table.currentRow()<0 and self.releases:self.release_table.selectRow(0)
        self.load_run();self.load_release()
        self.collaboration.set_entity("EQUIPMENT",eq.equipment_id,eq.equipment_id)

    def start_run(self):
        if not self.equipment_id:return
        protocol_id=self.protocol.currentData()
        if not protocol_id:
            QMessageBox.warning(self,"Qualification","No applicable active qualification protocol.");return
        try:
            run=self.db.start_qualification_run(self.equipment_id,str(protocol_id),self.user["username"],workstation="RETURN-TO-SERVICE")
            self.run_no=run.run_no;self.refresh();notify(f"Qualification {run.run_no} started.")
        except Exception as exc:QMessageBox.critical(self,"Qualification",str(exc))

    def load_run(self):
        self.run=_selected(self.run_table,self.runs)
        if not self.run:
            self.checks=[];self.results={};self.check_table.setRowCount(0);self.qual_attachments.set_entity("","");self.run_summary.setText("No qualification run selected.");return
        self.run_no=self.run.run_no
        self.checks=json.loads(self.run.frozen_checks_json or "[]");self.results=json.loads(self.run.results_json or "{}")
        self.check_table.setRowCount(len(self.checks))
        for r,check in enumerate(self.checks):
            cid=str(check.get("check_id",""));result=self.results.get(cid,{})
            vals=[cid,check.get("name") or check.get("description",""),check.get("acceptance",""),result.get("result",""),result.get("comment",""),result.get("entered_by","")]
            for col,val in enumerate(vals):self.check_table.setItem(r,col,_item(val))
        self.run_summary.setText(
            f"{self.run.run_no} · {self.run.protocol_name} R{self.run.protocol_revision} · {self.run.status}\n"
            f"Started: {self.run.started_by} · Submitted: {self.run.submitted_by or '—'} · Verified: {self.run.verified_by or '—'} · Approved: {self.run.approved_by or '—'}"
        )
        self.qual_attachments.set_entity("QUALIFICATION",self.run.run_no,self.run.equipment_id)
        if self.check_table.currentRow()<0 and self.checks:self.check_table.selectRow(0)
        self.load_check()

    def selected_check(self):
        i=self.check_table.currentRow();return self.checks[i] if 0<=i<len(self.checks) else None

    def load_check(self):
        check=self.selected_check()
        if not check:self.check_title.setText("Select a qualification check");return
        cid=str(check.get("check_id",""));result=self.results.get(cid,{})
        self.check_title.setText(f"{cid} — {check.get('name') or check.get('description','')}\nAcceptance: {check.get('acceptance','')}")
        if result.get("result"):self.check_result.setCurrentText(result["result"])
        self.check_comment.setText(str(result.get("comment","")))

    def save_check(self):
        if not self.run or self.run.status!="In Progress":return
        check=self.selected_check()
        if not check:return
        cid=str(check.get("check_id",""))
        evidence=str(self.results.get(cid,{}).get("evidence_path",""))
        try:
            self.db.save_qualification_result(self.run.id,cid,self.check_result.currentText(),self.check_comment.text(),self.user["username"],evidence,"RETURN-TO-SERVICE",self.run.version)
            self.refresh();notify(f"Qualification check {cid} saved.")
        except Exception as exc:QMessageBox.critical(self,"Qualification result",str(exc))

    def attach_check_evidence(self):
        if not self.run or self.run.status!="In Progress":return
        check=self.selected_check()
        if not check:return
        source,_=QFileDialog.getOpenFileName(self,"Attach qualification check evidence")
        if not source:return
        try:
            stored=store_attachment_file(source,FILE_ROOT,"QUALIFICATION",self.run.run_no)
            row=self.db.add_attachment("QUALIFICATION",self.run.run_no,stored["stored_path"],original_name=stored["original_name"],media_type=stored["media_type"],category="Check Evidence",caption=str(check.get("name") or check.get("description","")),equipment_id=self.run.equipment_id,created_by=self.user["username"])
            cid=str(check.get("check_id",""));current=self.results.get(cid,{})
            self.db.save_qualification_result(self.run.id,cid,current.get("result") or self.check_result.currentText(),current.get("comment") or self.check_comment.text(),self.user["username"],row.stored_path,"RETURN-TO-SERVICE",self.run.version)
            self.refresh();notify("Qualification evidence attached.")
        except Exception as exc:QMessageBox.critical(self,"Qualification evidence",str(exc))

    def submit_run(self):
        if not self.run:return
        conclusion,ok=QInputDialog.getMultiLineText(self,"Submit Qualification","Conclusion",self.run.conclusion or "")
        if not ok:return
        try:self.db.submit_qualification_run(self.run.id,self.user["username"],conclusion,"RETURN-TO-SERVICE",self.run.version);self.refresh();notify("Qualification submitted for independent verification.")
        except Exception as exc:QMessageBox.critical(self,"Qualification",str(exc))

    def verify_run(self):
        if not self.run:return
        note,ok=QInputDialog.getText(self,"Verify Qualification","Verification note")
        if not ok:return
        try:self.db.verify_qualification_run(self.run.id,self.user["username"],note,"RETURN-TO-SERVICE",self.run.version);self.refresh();notify("Qualification verified.")
        except Exception as exc:QMessageBox.critical(self,"Qualification",str(exc))

    def approve_run(self):
        if not self.run:return
        days,ok=QInputDialog.getInt(self,"Approve Qualification","Validity days (0 = no expiry)",30,0,3650)
        if not ok:return
        note,ok=QInputDialog.getText(self,"Approve Qualification","Approval note")
        if not ok:return
        try:self.db.approve_qualification_run(self.run.id,self.user["username"],days or None,note,"RETURN-TO-SERVICE",self.run.version);self.refresh();notify("Qualification approved.")
        except Exception as exc:QMessageBox.critical(self,"Qualification",str(exc))

    def reject_run(self):
        if not self.run:return
        reason,ok=QInputDialog.getMultiLineText(self,"Reject Qualification","Reason")
        if not ok or not reason.strip():return
        try:self.db.reject_qualification_run(self.run.id,self.user["username"],reason,"RETURN-TO-SERVICE",self.run.version);self.refresh();notify("Qualification rejected.")
        except Exception as exc:QMessageBox.critical(self,"Qualification",str(exc))

    def new_release(self):
        if not self.equipment_id:return
        checks={key:False for key,_ in RELEASE_CHECKS}
        try:
            row=self.db.create_release_request(self.equipment_id,self.release_ticket.text().strip(),checks,self.release_notes.toPlainText().strip(),self.user["username"],"RETURN-TO-SERVICE")
            self.release_id=row.id;self.refresh();notify(f"Release request #{row.id} created.")
        except Exception as exc:QMessageBox.critical(self,"Release",str(exc))

    def load_release(self):
        self.release=_selected(self.release_table,self.releases)
        if not self.release:
            self.release_context.setText("No release request selected.");self.release_attachments.set_entity("","");return
        self.release_id=self.release.id
        try:checks=json.loads(self.release.checks_json or "{}")
        except Exception:checks={}
        for key,box in self.release_checks.items():box.setChecked(bool(checks.get(key,False)))
        self.release_ticket.setText(self.release.related_ticket or "");self.release_notes.setPlainText(self.release.notes or "")
        self.release_context.setText(
            f"Release #{self.release.id} · {self.release.status}\nRequested: {self.release.requested_by or '—'} · Verified: {self.release.verified_by or '—'} · Approved: {self.release.approved_by or '—'}"
        )
        self.release_attachments.set_entity("RELEASE",str(self.release.id),self.release.equipment_id)

    def check_data(self):
        return {key:box.isChecked() for key,box in self.release_checks.items()}

    def verify_release(self):
        if not self.release:return
        try:self.db.verify_release(self.release.id,self.check_data(),self.user["username"],self.release.version,"RETURN-TO-SERVICE");self.refresh();notify("Release checklist verified.")
        except Exception as exc:QMessageBox.critical(self,"Release verification",str(exc))

    def approve_release(self):
        if not self.release:return
        if QMessageBox.question(self,"Approve Release",f"Release {self.release.equipment_id} to service?")!=QMessageBox.StandardButton.Yes:return
        try:self.db.approve_release(self.release.id,self.user["username"],self.release.version,"RETURN-TO-SERVICE");self.refresh();notify("Equipment release approved.")
        except Exception as exc:QMessageBox.critical(self,"Release approval",str(exc))

    def open_equipment(self):
        if self.equipment_id:self.open_entity.emit("EQUIPMENT",self.equipment_id,self.equipment_id)

    def export_qual_pptx(self):
        if not self.run:return
        path,_=QFileDialog.getSaveFileName(self,"Qualification PowerPoint",f"{self.run.equipment_id}_{self.run.run_no}.pptx","PowerPoint (*.pptx)")
        if not path:return
        if not path.lower().endswith(".pptx"):path+=".pptx"
        try:export_qualification_pptx(self.db,self.run.run_no,path,self.db.resolve_report_template("QUALIFICATION",self.run.equipment_id));notify(f"Qualification PowerPoint created: {path}")
        except Exception as exc:QMessageBox.critical(self,"Qualification report",str(exc))

    def export_qual_xlsx(self):
        if not self.run:return
        path,_=QFileDialog.getSaveFileName(self,"Qualification Excel",f"{self.run.equipment_id}_{self.run.run_no}.xlsx","Excel (*.xlsx)")
        if not path:return
        if not path.lower().endswith(".xlsx"):path+=".xlsx"
        try:export_qualification_xlsx(self.db,self.run.run_no,path);notify(f"Qualification workbook created: {path}")
        except Exception as exc:QMessageBox.critical(self,"Qualification report",str(exc))

    def export_qual_pdf(self):
        if not self.run:return
        path,_=QFileDialog.getSaveFileName(self,"Qualification PDF",f"{self.run.equipment_id}_{self.run.run_no}.pdf","PDF (*.pdf)")
        if not path:return
        if not path.lower().endswith(".pdf"):path+=".pdf"
        try:export_qualification_pdf(self.db,self.run.run_no,path);notify(f"Qualification PDF created: {path}")
        except Exception as exc:QMessageBox.critical(self,"Qualification report",str(exc))

    def export_release_pptx(self):
        if not self.release:return
        path,_=QFileDialog.getSaveFileName(self,"Release PowerPoint",f"{self.release.equipment_id}_Release_{self.release.id}.pptx","PowerPoint (*.pptx)")
        if not path:return
        if not path.lower().endswith(".pptx"):path+=".pptx"
        try:export_release_pptx(self.db,self.release.id,path,self.db.resolve_report_template("RELEASE",self.release.equipment_id));notify(f"Release PowerPoint created: {path}")
        except Exception as exc:QMessageBox.critical(self,"Release report",str(exc))

    def export_release_xlsx(self):
        if not self.release:return
        path,_=QFileDialog.getSaveFileName(self,"Release Excel",f"{self.release.equipment_id}_Release_{self.release.id}.xlsx","Excel (*.xlsx)")
        if not path:return
        if not path.lower().endswith(".xlsx"):path+=".xlsx"
        try:export_release_xlsx(self.db,self.release.id,path);notify(f"Release workbook created: {path}")
        except Exception as exc:QMessageBox.critical(self,"Release report",str(exc))

    def export_release_pdf(self):
        if not self.release:return
        path,_=QFileDialog.getSaveFileName(self,"Release PDF",f"{self.release.equipment_id}_Release_{self.release.id}.pdf","PDF (*.pdf)")
        if not path:return
        if not path.lower().endswith(".pdf"):path+=".pdf"
        try:export_release_pdf(self.db,self.release.id,path);notify(f"Release PDF created: {path}")
        except Exception as exc:QMessageBox.critical(self,"Release report",str(exc))
