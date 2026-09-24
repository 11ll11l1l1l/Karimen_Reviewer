from __future__ import annotations

import json
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,QFileDialog,QHBoxLayout,QHeaderView,QInputDialog,QLabel,
    QLineEdit,QMessageBox,QPushButton,QTableWidget,QTableWidgetItem,QTextEdit,
    QVBoxLayout,QWidget
)

from collaboration_panel import CollaborationPanel
from custom_field_panel import CustomFieldPanel
from domain import allowed_targets
from reporting import export_release_pptx, export_release_xlsx
from table_productivity import install_table_productivity
from workspaces import AttachmentPanel


CHECKS=[
    ("maintenance_complete","Maintenance complete"),
    ("measurements_pass","Measurements pass"),
    ("calibration_valid","Calibration valid"),
    ("safety_check","Safety check"),
    ("verification_run","Verification run"),
    ("critical_tickets_cleared","Critical tickets cleared"),
]


def _item(value):
    if isinstance(value,datetime):value=value.strftime("%Y-%m-%d %H:%M")
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);t.setAlternatingRowColors(True)
    install_table_productivity(t,headers[0] if headers else "Release")
    return t


class ReleaseWorkspace(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.release_id=0;self.release=None;self.rows=[]
        root=QVBoxLayout(self);head=QHBoxLayout()
        self.title=QLabel("Release / Return to Service");self.title.setStyleSheet("font-size:20pt;font-weight:800")
        self.status=QLabel();self.status.setStyleSheet("font-size:12pt;font-weight:700")
        new=QPushButton("New Request");new.clicked.connect(self.new_request)
        self.open_eq=QPushButton("Open Equipment");self.open_eq.clicked.connect(self.open_equipment)
        self.open_ticket=QPushButton("Open Incident");self.open_ticket.clicked.connect(self.open_incident)
        ppt=QPushButton("Report PPTX");ppt.clicked.connect(self.export_pptx)
        xlsx=QPushButton("Report Excel");xlsx.clicked.connect(self.export_xlsx)
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh)
        head.addWidget(self.title);head.addWidget(self.status);head.addStretch(1)
        for b in [new,self.open_eq,self.open_ticket,ppt,xlsx,refresh]:head.addWidget(b)
        root.addLayout(head)
        self.context=QLabel("Select a release request from Equipment 360 / My Work or create a request.");self.context.setStyleSheet("color:#647581");root.addWidget(self.context)

        split=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText("Filter equipment / ticket / status");self.search.textChanged.connect(self.refresh)
        self.request_table=_table(["ID","Equipment","Ticket","Status","Requested By","Verified By","Approved By","Requested","Approved","Ver"])
        self.request_table.itemSelectionChanged.connect(self._selection_changed)
        left=QVBoxLayout();left.addWidget(self.search);left.addWidget(self.request_table);split.addLayout(left,3)

        right=QVBoxLayout();self.precheck=QLabel("Precheck");self.precheck.setWordWrap(True);self.precheck.setStyleSheet("font-weight:600")
        pre=QPushButton("Refresh Precheck");pre.clicked.connect(self.refresh_precheck)
        self.check_table=QTableWidget(0,2);self.check_table.setHorizontalHeaderLabels(["Release Check","Pass"]);self.check_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.notes=QTextEdit();self.notes.setPlaceholderText("Release verification notes");self.notes.setMaximumHeight(100)
        verify=QPushButton("Verify Checklist");verify.clicked.connect(self.verify_release)
        approve=QPushButton("Approve Release");approve.clicked.connect(self.approve_release)
        returnb=QPushButton("Return to Service");returnb.clicked.connect(self.return_to_service)
        self.verify_button=verify;self.approve_button=approve;self.return_button=returnb
        right.addWidget(self.precheck);right.addWidget(pre);right.addWidget(self.check_table);right.addWidget(self.notes)
        btn=QHBoxLayout();btn.addWidget(verify);btn.addWidget(approve);btn.addWidget(returnb);right.addLayout(btn);split.addLayout(right,2)
        root.addLayout(split,2)

        self.attachments=AttachmentPanel(db,user);root.addWidget(self.attachments,1)
        self.collaboration=CollaborationPanel(db,user);root.addWidget(self.collaboration,1)
        self.custom_fields=CustomFieldPanel(db,user);root.addWidget(self.custom_fields,1)
        self.refresh()

    def set_release(self,release_id: str|int):
        try:self.release_id=int(release_id)
        except Exception:self.release_id=0
        self.refresh()

    def current(self):
        return self.release

    def refresh(self):
        q=self.search.text().strip().lower() if hasattr(self,"search") else ""
        rows=self.db.list_release_requests()
        if q:rows=[x for x in rows if q in f"{x.id} {x.equipment_id} {x.related_ticket} {x.status}".lower()]
        self.rows=rows
        self.request_table.setRowCount(len(rows))
        for r,row in enumerate(rows):
            vals=[row.id,row.equipment_id,row.related_ticket,row.status,row.requested_by,row.verified_by,row.approved_by,row.requested_at,row.approved_at,row.version]
            for col,val in enumerate(vals):self.request_table.setItem(r,col,_item(val))
        if self.release_id:
            for i,row in enumerate(rows):
                if row.id==self.release_id:self.request_table.selectRow(i);break
        elif rows and self.request_table.currentRow()<0:self.request_table.selectRow(0)
        self._selection_changed()

    def _selection_changed(self):
        idx=self.request_table.currentRow()
        self.release=self.rows[idx] if 0<=idx<len(self.rows) else None
        if not self.release:
            self.title.setText("Release / Return to Service");self.status.setText("");self.context.setText("Select a release request.")
            self.check_table.setRowCount(0);self.attachments.set_entity("","");self.collaboration.set_entity("","");self.custom_fields.set_entity("","");return
        r=self.release;self.release_id=r.id;self.title.setText(f"Release #{r.id} · {r.equipment_id}");self.status.setText(r.status)
        eq=self.db.get_equipment(r.equipment_id);self.context.setText(f"Equipment state: {eq.status if eq else '—'}    Disposition: {eq.disposition if eq else '—'}    Related incident: {r.related_ticket or '—'}")
        checks=json.loads(r.checks_json or "{}");self.check_table.setRowCount(len(CHECKS))
        editable=r.status!="Approved / Released"
        for row,(key,label) in enumerate(CHECKS):
            label_item=QTableWidgetItem(label);pass_item=QTableWidgetItem()
            pass_item.setFlags(pass_item.flags()|Qt.ItemFlag.ItemIsUserCheckable|Qt.ItemFlag.ItemIsEnabled)
            pass_item.setCheckState(Qt.CheckState.Checked if checks.get(key) else Qt.CheckState.Unchecked)
            if not editable:pass_item.setFlags(pass_item.flags()&~Qt.ItemFlag.ItemIsEnabled)
            pass_item.setData(Qt.ItemDataRole.UserRole,key)
            self.check_table.setItem(row,0,label_item);self.check_table.setItem(row,1,pass_item)
        self.notes.setPlainText(r.notes or "");self.verify_button.setEnabled(r.status!="Approved / Released" and self.db.has_permission(self.user,"release.verify"))
        self.approve_button.setEnabled(r.status=="Verified" and self.db.has_permission(self.user,"release.approve"))
        self.return_button.setEnabled(r.status=="Approved / Released")
        self.open_ticket.setEnabled(bool(r.related_ticket))
        self.attachments.set_entity("RELEASE",str(r.id),r.equipment_id);self.collaboration.set_entity("RELEASE",str(r.id),r.equipment_id)
        self.custom_fields.set_entity("RELEASE",str(r.id),eq.equipment_type if eq else "")
        self.refresh_precheck()

    def check_data(self):
        out={}
        for row in range(self.check_table.rowCount()):
            item=self.check_table.item(row,1)
            if item:out[str(item.data(Qt.ItemDataRole.UserRole))]=item.checkState()==Qt.CheckState.Checked
        return out

    def refresh_precheck(self):
        if not self.release:return
        try:
            p=self.db.release_precheck(self.release.equipment_id)
            q="Not required" if not p["qualification_required"] else (f"PASS · {p['qualification_run_no']}" if p["qualification_valid"] else "REQUIRED / NOT APPROVED")
            self.precheck.setText(f"Open P1/P2: {p['critical_tickets_open']} · Overdue PM: {p['overdue_pm']} · Qualification: {q}")
        except Exception as exc:self.precheck.setText(f"Precheck unavailable: {exc}")

    def new_request(self):
        equipment,ok=QInputDialog.getText(self,"Release request","Equipment ID")
        if not ok or not equipment.strip():return
        if not self.db.get_equipment(equipment.strip()):QMessageBox.warning(self,"Release","Equipment not found.");return
        ticket,ok=QInputDialog.getText(self,"Release request","Related incident / ticket (optional)")
        if not ok:return
        notes,ok=QInputDialog.getMultiLineText(self,"Release request","Request notes")
        if not ok:return
        checks={key:False for key,_ in CHECKS}
        try:
            row=self.db.create_release_request(equipment.strip(),ticket.strip(),checks,notes,self.user["username"],"RELEASE-WORKSPACE")
            self.set_release(row.id)
        except Exception as exc:QMessageBox.critical(self,"Release",str(exc))

    def verify_release(self):
        if not self.release:return
        try:
            row=self.db.verify_release(
                self.release.id,self.check_data(),self.user["username"],self.release.version,
                "RELEASE-WORKSPACE",notes=self.notes.toPlainText().strip()
            )
            self.set_release(row.id)
        except Exception as exc:QMessageBox.critical(self,"Release verification",str(exc))

    def approve_release(self):
        if not self.release:return
        if QMessageBox.question(self,"Approve Release",f"Approve release of {self.release.equipment_id}?")!=QMessageBox.StandardButton.Yes:return
        try:
            row=self.db.approve_release(self.release.id,self.user["username"],self.release.version,"RELEASE-WORKSPACE")
            self.set_release(row.id)
        except Exception as exc:QMessageBox.critical(self,"Release approval",str(exc))

    def return_to_service(self):
        if not self.release:return
        eq=self.db.get_equipment(self.release.equipment_id)
        if not eq:return
        targets=[x for x in allowed_targets(eq.status) if x in {"Available","Production"}]
        if not targets:
            QMessageBox.information(self,"Return to Service",f"Release is approved, but {eq.status} cannot transition directly to Available/Production. Complete the governed intermediate state first.")
            return
        target,ok=QInputDialog.getItem(self,"Return to Service","Target operating state",targets,0,False)
        if not ok:return
        try:
            self.db.transition_equipment_state(eq.equipment_id,target,reason_code="RELEASED",reason_text=f"Release #{self.release.id} approved",related_ticket=self.release.related_ticket,user=self.user["username"],workstation="RELEASE-WORKSPACE",expected_version=eq.version)
            QMessageBox.information(self,"Return to Service",f"{eq.equipment_id} transitioned to {target}.");self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Return to Service",str(exc))

    def open_equipment(self):
        if self.release:self.open_entity.emit("EQUIPMENT",self.release.equipment_id,self.release.equipment_id)

    def open_incident(self):
        if self.release and self.release.related_ticket:self.open_entity.emit("TICKET",self.release.related_ticket,self.release.equipment_id)

    def export_pptx(self):
        if not self.release:return
        path,_=QFileDialog.getSaveFileName(self,"Export Release PowerPoint",f"{self.release.equipment_id}_Release_{self.release.id}.pptx","PowerPoint (*.pptx)")
        if not path:return
        if not path.lower().endswith(".pptx"):path+=".pptx"
        try:export_release_pptx(self.db,self.release.id,path);QMessageBox.information(self,"Release report",f"Editable deck created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"Release report",str(exc))

    def export_xlsx(self):
        if not self.release:return
        path,_=QFileDialog.getSaveFileName(self,"Export Release Excel",f"{self.release.equipment_id}_Release_{self.release.id}.xlsx","Excel Workbook (*.xlsx)")
        if not path:return
        if not path.lower().endswith(".xlsx"):path+=".xlsx"
        try:export_release_xlsx(self.db,self.release.id,path);QMessageBox.information(self,"Release report",f"Workbook created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"Release report",str(exc))
