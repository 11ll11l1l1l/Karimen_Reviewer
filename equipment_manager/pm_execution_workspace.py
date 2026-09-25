from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget, QInputDialog,
)

from attachment_store import default_file_root, store_attachment_file, store_clipboard_image
from services import readonly_open_copy
from table_productivity import install_table_productivity
from feedback import notify
from workspaces import AttachmentPanel
from collaboration_panel import CollaborationPanel
from reporting import export_pm_execution_pptx, export_pm_execution_xlsx
from pdf_reporting import export_pm_execution_pdf
from instruction_resolver import preferred_openable_instruction, resolve_pm_instruction
from PySide6.QtWidgets import QApplication

FILE_ROOT=default_file_root()


def _item(value):
    if isinstance(value,datetime):value=value.strftime("%Y-%m-%d %H:%M")
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setAlternatingRowColors(True);t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    install_table_productivity(t,headers[0] if headers else "PM Execution")
    return t


def _selected(table,rows):
    i=table.currentRow()
    return rows[i] if 0<=i<len(rows) else None


class PMExecutionWorkspace(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.task_id=0;self.task=None;self.execution=None
        self.specs=[];self.results={};self.requirements=[];self.acks={};self.focus_mode=False;self.pending_evidence={}
        root=QVBoxLayout(self);head=QHBoxLayout()
        self.title=QLabel("Technician PM Runner");self.title.setStyleSheet("font-size:20pt;font-weight:800")
        self.state=QLabel();self.state.setStyleSheet("font-size:12pt;font-weight:700")
        self.start_button=QPushButton("Start / Resume");self.start_button.clicked.connect(self.start_resume)
        self.pause_button=QPushButton("Pause / Carry Over");self.pause_button.clicked.connect(self.pause_execution)
        self.complete_button=QPushButton("Complete PM");self.complete_button.clicked.connect(self.complete_pm)
        self.open_eq=QPushButton("Open Equipment");self.open_eq.clicked.connect(self.open_equipment)
        self.work_order_button=QPushButton("Create / Open Work Order");self.work_order_button.clicked.connect(self.open_work_order)
        ppt=QPushButton("PM PPTX");ppt.clicked.connect(self.export_pptx)
        xlsx=QPushButton("PM Excel");xlsx.clicked.connect(self.export_xlsx)
        pdf=QPushButton("PM PDF");pdf.clicked.connect(self.export_pdf)
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh)
        head.addWidget(self.title);head.addWidget(self.state);head.addStretch(1)
        for b in [self.open_eq,self.work_order_button,ppt,xlsx,pdf,self.start_button,self.pause_button,self.complete_button,refresh]:head.addWidget(b)
        root.addLayout(head)
        self.context=QLabel("Select a PM task from Maintenance Planner, My Work, Search, or Equipment 360.");self.context.setWordWrap(True);self.context.setStyleSheet("color:#647581;");root.addWidget(self.context)
        self.progress=QLabel();self.progress.setStyleSheet("font-weight:700;");root.addWidget(self.progress)

        tabs=QTabWidget();root.addWidget(tabs,1)
        execute=QWidget();ev=QVBoxLayout(execute);split=QSplitter()
        self.step_table=_table(["Step","Activity","Method","Input","Unit","Result","Value","By","Evidence"])
        self.step_table.itemSelectionChanged.connect(self.load_step);split.addWidget(self.step_table)
        inspector=QWidget();iv=QVBoxLayout(inspector)
        self.step_title=QLabel("Select a checklist step");self.step_title.setWordWrap(True);self.step_title.setStyleSheet("font-size:15pt;font-weight:800")
        self.step_counter=QLabel("Step — / —");self.step_counter.setStyleSheet("font-weight:700;color:#526471")
        self.instruction_source=QLabel("Instruction source: —");self.instruction_source.setWordWrap(True);self.instruction_source.setStyleSheet("color:#526471")
        self.method=QLabel();self.method.setWordWrap(True);self.specification=QLabel();self.specification.setWordWrap(True);self.reaction=QLabel();self.reaction.setWordWrap(True)
        self.history_summary=QLabel("Previous results: —");self.history_summary.setWordWrap(True);self.history_summary.setStyleSheet("color:#526471;font-weight:600;")
        self.history_table=_table(["Date","Result","Value","By","Comment"]);self.history_table.setMaximumHeight(170)
        self.text_value=QLineEdit();self.text_value.setPlaceholderText("Enter result / value")
        self.pass_fail=QComboBox();self.pass_fail.addItems(["PASS","FAIL"])
        self.comment=QTextEdit();self.comment.setPlaceholderText("Comment / observation");self.comment.setMaximumHeight(100)
        nav_buttons=QHBoxLayout()
        prev=QPushButton("Previous");prev.clicked.connect(self.previous_step)
        nxt=QPushButton("Next");nxt.clicked.connect(self.next_step)
        focus=QPushButton("Focus Step");focus.clicked.connect(self.toggle_focus_mode)
        nav_buttons.addWidget(prev);nav_buttons.addWidget(nxt);nav_buttons.addStretch(1);nav_buttons.addWidget(focus)
        buttons=QHBoxLayout();save=QPushButton("Save step");save.clicked.connect(self.save_step);paste=QPushButton("Paste screenshot");paste.clicked.connect(self.paste_screenshot);fileb=QPushButton("Attach file");fileb.clicked.connect(self.attach_file);sop=QPushButton("Open Instruction");sop.clicked.connect(self.open_instruction)
        for b in [save,paste,fileb,sop]:buttons.addWidget(b)
        iv.addWidget(self.step_counter);iv.addWidget(self.step_title);iv.addWidget(self.instruction_source);iv.addLayout(nav_buttons);iv.addWidget(self.method);iv.addWidget(self.specification);iv.addWidget(self.reaction)
        iv.addWidget(self.history_summary);iv.addWidget(self.history_table)
        iv.addWidget(self.text_value);iv.addWidget(self.pass_fail);iv.addWidget(QLabel("Comment"));iv.addWidget(self.comment);iv.addLayout(buttons);iv.addStretch(1)
        split.addWidget(inspector);split.setStretchFactor(0,3);split.setStretchFactor(1,2);ev.addWidget(split);tabs.addTab(execute,"Checklist Runner")

        req=QWidget();rv=QVBoxLayout(req);rh=QHBoxLayout();ack=QPushButton("Acknowledge selected requirement");ack.clicked.connect(self.ack_requirement)
        reserve=QPushButton("Reserve required parts");reserve.clicked.connect(self.reserve_parts);reserve.setEnabled(db.has_permission(user,"inventory.reserve"))
        consume=QPushButton("Consume reserved parts");consume.clicked.connect(self.consume_parts);consume.setEnabled(db.has_permission(user,"inventory.consume") or db.has_permission(user,"inventory.edit"))
        rh.addWidget(ack);rh.addWidget(reserve);rh.addWidget(consume);rh.addStretch(1);rv.addLayout(rh)
        self.readiness=QLabel();self.readiness.setWordWrap(True);self.readiness.setStyleSheet("color:#526471;font-weight:600;");rv.addWidget(self.readiness)
        self.req_table=_table(["Requirement","Type","Key","Description","Qty","Mandatory","Acknowledged by","Time"]);rv.addWidget(self.req_table,2)
        self.reservation_table=_table(["ID","Part","Location","Qty","Status","Reserved By","Time"]);rv.addWidget(QLabel("PM part reservations"));rv.addWidget(self.reservation_table,1);tabs.addTab(req,"Requirements / Readiness")

        sessions=QWidget();sv=QVBoxLayout(sessions)
        self.session_summary=QLabel("No execution sessions yet.");self.session_summary.setWordWrap(True);sv.addWidget(self.session_summary)
        self.work_session_table=_table(["Worker","Started","Ended","Minutes","Status","Note"]);sv.addWidget(QLabel("Work sessions"));sv.addWidget(self.work_session_table,1)
        self.pause_table=_table(["Paused","Reason","Note","Paused By","Resumed","Resumed By"]);sv.addWidget(QLabel("Pause / carry-over history"));sv.addWidget(self.pause_table,1)
        tabs.addTab(sessions,"Work Sessions")

        self.attachments=AttachmentPanel(db,user);tabs.addTab(self.attachments,"Execution Evidence")
        self.collaboration=CollaborationPanel(db,user);tabs.addTab(self.collaboration,"Comments / Watchers")
        self._enable_execution(False)

    def _enable_execution(self,enabled):
        active=bool(enabled and self.execution and self.execution.status=="In Progress")
        self.complete_button.setEnabled(active)
        self.pause_button.setEnabled(active)
        self.start_button.setEnabled(bool(self.task and (not self.execution or self.execution.status!="Completed")))
        self.step_table.setEnabled(active);self.req_table.setEnabled(active)

    def set_task(self,task_id: int):
        self.task_id=int(task_id or 0);self.execution=None;self.pending_evidence={};self.refresh()

    def refresh(self):
        self.task=self.db.get_pm_task(self.task_id) if self.task_id else None
        if not self.task:
            self.title.setText("Technician PM Runner");self.state.setText("");self.context.setText("Select a PM task from Maintenance Planner, My Work, Search, or Equipment 360.");self.attachments.set_entity("","");self.collaboration.set_entity("","");self._enable_execution(False);return
        t=self.task;self.title.setText(f"{t.pm_id} · {t.pm_name}")
        schedule=self.db.get_pm_task_schedule(t.id)
        slot_start=schedule.scheduled_start_at if schedule and schedule.scheduled_start_at else (t.scheduled_date or t.original_due_date)
        slot_end=schedule.scheduled_end_at if schedule else None
        self.state.setText(t.status)
        self.context.setText(
            f"{t.equipment_id}    Calendar: {slot_start or '—'}"
            + (f" → {slot_end}" if slot_end else "")
            + f"    Controlled due: {t.original_due_date or '—'}    Assigned: {t.assigned_to or 'UNASSIGNED'}    Priority: {t.priority}"
        )
        # Viewing a task must not mutate its lifecycle. Existing execution is discovered read-only.
        if self.execution is None:self.execution=self.db.get_pm_execution_for_task(t.id)
        if self.execution:
            self.specs=self.db.list_pm_execution_specs(self.execution.id);self.results={x.step_no:x for x in self.db.list_pm_results(self.execution.id)}
            self.requirements=self.db.list_pm_execution_requirements(self.execution.id);self.acks={x.requirement_id:x for x in self.db.list_pm_requirement_acks(self.execution.id)}
            self.state.setText(f"{t.status} · Execution {self.execution.status}")
            self.fill_tables();self.fill_work_sessions()
            self.attachments.set_entity("PM_EXECUTION",str(self.execution.id),t.equipment_id);self.collaboration.set_entity("PM_EXECUTION",str(self.execution.id),t.equipment_id);self._enable_execution(self.execution.status!="Completed")
        else:
            self.specs=[];self.results={};self.requirements=[];self.acks={};self.step_table.setRowCount(0);self.req_table.setRowCount(0);self.work_session_table.setRowCount(0);self.pause_table.setRowCount(0);self.session_summary.setText("No execution sessions yet.");self.progress.setText("Not started in this workspace. Click Start / Resume.");self.attachments.set_entity("PM_TASK",str(t.id),t.equipment_id);self.collaboration.set_entity("PM_TASK",str(t.id),t.equipment_id);self._enable_execution(False)
        self.open_eq.setEnabled(True)

    def start_resume(self):
        if not self.task:return
        try:
            self.execution=self.db.start_pm_execution(self.task.id,self.user["username"])
            try:self.db.start_work_log("PM_EXECUTION",str(self.execution.id),self.task.equipment_id,self.user["username"],"Maintenance",f"{self.task.pm_id} execution")
            except Exception:pass
            self.refresh()
        except Exception as exc:QMessageBox.critical(self,"PM execution",str(exc))

    def pause_execution(self):
        if not self.execution or self.execution.status!="In Progress":return
        reasons=["Production Request","Waiting Parts","Waiting Engineer","Waiting Vendor","Tool Unavailable","Shift End","Safety Hold","Other"]
        reason,ok=QInputDialog.getItem(self,"Pause / Carry Over PM","Reason",reasons,0,False)
        if not ok:return
        note,ok=QInputDialog.getMultiLineText(self,"Pause / Carry Over PM","Optional note / next action")
        if not ok:return
        try:
            self.db.pause_pm_execution(
                self.execution.id,self.user["username"],reason,note,
                workstation="PM-RUNNER",
            )
            for log in self.db.list_work_logs(self.task.equipment_id,True,200):
                if log.username==self.user["username"] and log.entity_type=="PM_EXECUTION" and log.entity_key==str(self.execution.id):
                    try:self.db.stop_work_log(log.id,self.user["username"],f"Paused: {reason}. {note}".strip())
                    except Exception:pass
            notify(f"PM paused / carried over: {reason}.")
            self.execution=self.db.get_pm_execution_for_task(self.task.id)
            self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Pause PM",str(exc))

    def fill_work_sessions(self):
        if not self.execution or not self.task:return
        logs=[
            x for x in self.db.list_work_logs(self.task.equipment_id,False,500)
            if x.entity_type=="PM_EXECUTION" and x.entity_key==str(self.execution.id)
        ]
        self.work_session_table.setRowCount(len(logs))
        for r,row in enumerate(logs):
            vals=[row.username,row.started_at,row.ended_at,row.duration_minutes,row.status,row.note]
            for col,val in enumerate(vals):self.work_session_table.setItem(r,col,_item(val))
        pauses=self.db.list_pm_execution_pauses(self.execution.id)
        self.pause_table.setRowCount(len(pauses))
        for r,row in enumerate(pauses):
            vals=[row.paused_at,row.reason,row.note,row.paused_by,row.resumed_at,row.resumed_by]
            for col,val in enumerate(vals):self.pause_table.setItem(r,col,_item(val))
        total=sum(float(x.duration_minutes or 0) for x in logs if x.status=="Completed")
        active=sum(1 for x in logs if x.status=="Active")
        self.session_summary.setText(
            f"Execution {self.execution.status} · {len(logs)} work session(s) · "
            f"{total/60:.2f} recorded h" + (f" · {active} active" if active else "")
        )

    def fill_tables(self):
        self.step_table.setRowCount(len(self.specs))
        for r,spec in enumerate(self.specs):
            result=self.results.get(spec.step_no)
            value=result.value_text if result and result.value_text else (result.value_numeric if result else "")
            vals=[spec.step_no,spec.activity,spec.method,spec.input_type,spec.unit,result.result if result else "",value,result.entered_by if result else "",result.evidence_path if result else ""]
            for c,val in enumerate(vals):self.step_table.setItem(r,c,_item(val))
        self.req_table.setRowCount(len(self.requirements))
        for r,req in enumerate(self.requirements):
            ack=self.acks.get(req.requirement_id)
            vals=[req.requirement_id,req.requirement_type,req.requirement_key,req.description,req.quantity,req.mandatory,ack.acknowledged_by if ack else "",ack.acknowledged_at if ack else ""]
            for c,val in enumerate(vals):self.req_table.setItem(r,c,_item(val))
        reservations=[x for x in self.db.list_reservations() if x.pm_task_id==self.task.id]
        self.reservation_table.setRowCount(len(reservations))
        for r,row in enumerate(reservations):
            vals=[row.id,row.part_number,row.location_code,row.quantity,row.status,row.reserved_by,row.reserved_at]
            for col,val in enumerate(vals):self.reservation_table.setItem(r,col,_item(val))
        try:
            ready=self.db.pm_task_readiness(self.task.id)
            part_detail="; ".join(f"{x['part_number']} short {x['shortage']:g}" for x in ready["part_shortages"])
            cert_detail=", ".join(ready["missing_certifications"])
            self.readiness.setText(
                f"Parts: {ready['parts_status']}" + (f" ({part_detail})" if part_detail else "") +
                f"    Certifications: {ready['certification_status']}" + (f" ({cert_detail})" if cert_detail else "")
            )
        except Exception as exc:self.readiness.setText(f"Readiness unavailable: {exc}")
        completed=len(self.results);total=len(self.specs);failed=sum(1 for x in self.results.values() if x.result in {"SPECIFICATION FAILURE","CONTROL FAILURE","FAIL","INVALID"})
        req_done=sum(1 for x in self.requirements if x.requirement_type=="CERTIFICATION" or x.requirement_id in self.acks)
        self.progress.setText(f"Checklist {completed}/{total} · Requirements {req_done}/{len(self.requirements)} · Blocking results {failed}")
        if self.specs and self.step_table.currentRow()<0:self.step_table.selectRow(0)

    def selected_spec(self):
        return _selected(self.step_table,self.specs)

    def load_step(self):
        spec=self.selected_spec()
        if not spec:
            self.step_counter.setText("Step — / —");self.step_title.setText("Select a checklist step");self.instruction_source.setText("Instruction source: —");return
        current=self.results.get(spec.step_no)
        index=self.specs.index(spec) if spec in self.specs else self.step_table.currentRow()
        self.step_counter.setText(f"Step {max(0,index)+1} / {len(self.specs)}")
        self.step_title.setText(f"Step {spec.step_no} — {spec.activity}")
        sources=resolve_pm_instruction(self.db,self.task,spec)
        source_text=" · ".join(x.label+(f" ({x.locator})" if x.locator else "") for x in sources[:3])
        self.instruction_source.setText("Instruction source: "+(source_text or "EMS checklist only"))
        self.method.setText(f"Method: {spec.method or '—'}")
        limits=[]
        for label,val in [("Target",spec.target),("Warn L",spec.warning_low),("Warn H",spec.warning_high),("Control L",spec.control_low),("Control H",spec.control_high),("Spec L",spec.spec_low),("Spec H",spec.spec_high)]:
            if val is not None:limits.append(f"{label} {val:g}")
        if spec.acceptance_text:limits.append(spec.acceptance_text)
        self.specification.setText("Acceptance: "+(" · ".join(limits) if limits else "recorded value / text"))
        completion=[]
        if getattr(spec,"screenshot_required",False):completion.append("screenshot required")
        if getattr(spec,"comment_required",False):completion.append("comment required")
        self.reaction.setText(
            "Reaction plan: "+(spec.reaction_plan or "No reaction plan defined.")
            + ("\nCompletion proof: "+", ".join(completion) if completion else "")
        )
        history=self.db.pm_step_history(
            self.task.equipment_id,self.task.pm_id,spec.step_no,12,
            self.execution.id if self.execution else None,
        )
        self.history_table.setRowCount(len(history))
        numeric=[]
        for r,row in enumerate(history):
            value=row["value_numeric"] if row["value_numeric"] is not None else row["value_text"]
            vals=[row["entered_at"],row["result"],value,row["entered_by"],row["comment"]]
            for col,val in enumerate(vals):self.history_table.setItem(r,col,_item(val))
            if row["value_numeric"] is not None:numeric.append(float(row["value_numeric"]))
        if numeric:
            last=numeric[0];avg=sum(numeric)/len(numeric);lo=min(numeric);hi=max(numeric)
            delta=(last-numeric[1]) if len(numeric)>1 else 0.0
            self.history_summary.setText(f"Previous numeric results ({len(numeric)}): last {last:g} · avg {avg:.3g} · range {lo:g}–{hi:g} · last delta {delta:+.3g}")
        elif history:
            self.history_summary.setText(f"Previous results ({len(history)}): last {history[0]['result']} · value {history[0]['value_text'] or '—'} · by {history[0]['entered_by'] or '—'}")
        else:self.history_summary.setText("Previous results: none for this equipment / PM / step")
        self.pass_fail.setVisible(spec.input_type=="Pass / Fail");self.text_value.setVisible(spec.input_type!="Pass / Fail")
        if current:
            self.text_value.setText(current.value_text or (str(current.value_numeric) if current.value_numeric is not None else ""));self.comment.setPlainText(current.comment or "")
            if spec.input_type=="Pass / Fail":self.pass_fail.setCurrentText("PASS" if current.result=="PASS" else "FAIL")
        else:self.text_value.clear();self.comment.clear()

    def save_step(self):
        spec=self.selected_spec()
        if not spec or not self.execution:return
        current=self.results.get(spec.step_no);value_text="";value_numeric=None
        if spec.input_type=="Pass / Fail":value_text=self.pass_fail.currentText()
        elif spec.input_type=="Numeric":
            raw=self.text_value.text().strip()
            try:value_numeric=float(raw)
            except Exception:QMessageBox.warning(self,"PM step","Enter a valid numeric value.");return
            value_text=raw
        else:value_text=self.text_value.text().strip()
        evidence=(current.evidence_path if current else "") or self.pending_evidence.get(spec.step_no,"")
        try:
            comment=self.comment.toPlainText().strip()
            if getattr(spec,"comment_required",False) and not comment:
                QMessageBox.warning(self,"PM step","This step requires a comment before it can be completed.");return
            if getattr(spec,"screenshot_required",False) and not evidence:
                QMessageBox.warning(self,"PM step","This step requires screenshot evidence. Paste or attach the screenshot first.");return
            saved=self.db.save_pm_result(self.execution.id,spec.step_no,{"value_text":value_text,"value_numeric":value_numeric,"comment":comment,"result":"","entered_by":self.user["username"],"evidence_path":evidence},current.version if current else None)
            self.pending_evidence.pop(spec.step_no,None)
            self.refresh()
            if saved.result in {"SPECIFICATION FAILURE","CONTROL FAILURE","FAIL"}:
                self.offer_incident(spec,saved)
        except Exception as exc:QMessageBox.critical(self,"PM step",str(exc))

    def paste_screenshot(self):
        spec=self.selected_spec()
        if not spec or not self.execution:return
        image=QApplication.clipboard().image()
        if image.isNull():QMessageBox.information(self,"Clipboard","Clipboard does not contain an image.");return
        try:
            stored=store_clipboard_image(image,FILE_ROOT,"PM_EXECUTION",str(self.execution.id))
            att=self.db.add_attachment("PM_EXECUTION",str(self.execution.id),stored["stored_path"],original_name=stored["original_name"],media_type=stored["media_type"],category="Screenshot",caption=f"Step {spec.step_no} — {spec.activity}",equipment_id=self.task.equipment_id,created_by=self.user["username"])
            current=self.results.get(spec.step_no)
            if current:self.db.save_pm_result(self.execution.id,spec.step_no,{"value_text":current.value_text,"value_numeric":current.value_numeric,"comment":current.comment,"result":current.result,"entered_by":self.user["username"],"evidence_path":att.stored_path},current.version)
            else:self.pending_evidence[spec.step_no]=att.stored_path
            notify(f"Screenshot attached to PM step {spec.step_no}.")
            self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Screenshot",str(exc))

    def attach_file(self):
        spec=self.selected_spec()
        if not spec or not self.execution:return
        source,_=QFileDialog.getOpenFileName(self,"Attach PM step evidence")
        if not source:return
        try:
            stored=store_attachment_file(source,FILE_ROOT,"PM_EXECUTION",str(self.execution.id))
            att=self.db.add_attachment("PM_EXECUTION",str(self.execution.id),stored["stored_path"],original_name=stored["original_name"],media_type=stored["media_type"],category="Step Evidence",caption=f"Step {spec.step_no} — {spec.activity}",equipment_id=self.task.equipment_id,created_by=self.user["username"])
            current=self.results.get(spec.step_no)
            if current:self.db.save_pm_result(self.execution.id,spec.step_no,{"value_text":current.value_text,"value_numeric":current.value_numeric,"comment":current.comment,"result":current.result,"entered_by":self.user["username"],"evidence_path":att.stored_path},current.version)
            else:self.pending_evidence[spec.step_no]=att.stored_path
            notify(f"Evidence attached to PM step {spec.step_no}.")
            self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Evidence",str(exc))

    def previous_step(self):
        if not self.specs:return
        row=self.step_table.currentRow()
        self.step_table.selectRow(max(0,row-1 if row>=0 else 0))

    def next_step(self):
        if not self.specs:return
        row=self.step_table.currentRow()
        self.step_table.selectRow(min(len(self.specs)-1,row+1 if row>=0 else 0))

    def toggle_focus_mode(self):
        self.focus_mode=not self.focus_mode
        self.step_table.setVisible(not self.focus_mode)
        notify("PM Focus Step mode enabled." if self.focus_mode else "PM checklist overview restored.")

    def open_instruction(self):
        spec=self.selected_spec()
        if not spec or not self.task:return
        source=preferred_openable_instruction(self.db,self.task,spec)
        if not source:
            notify("This step is fully instructed in EMS; no external instruction file is required.")
            return
        try:
            readonly_open_copy(source.path)
            detail=source.label+(f" · {source.locator}" if source.locator else "")
            notify(f"Opened read-only instruction: {detail}")
        except Exception as exc:QMessageBox.critical(self,"Instruction",str(exc))

    def ack_requirement(self):
        req=_selected(self.req_table,self.requirements)
        if not req or not self.execution:return
        if req.requirement_type=="CERTIFICATION":QMessageBox.information(self,"Requirement","Certification is validated automatically at PM start.");return
        if req.requirement_id in self.acks:QMessageBox.information(self,"Requirement","Already acknowledged.");return
        note,ok=QInputDialog.getMultiLineText(self,"Acknowledge requirement",req.description)
        if not ok:return
        evidence=""
        if QMessageBox.question(self,"Requirement","Attach evidence file?")==QMessageBox.StandardButton.Yes:
            source,_=QFileDialog.getOpenFileName(self,"Requirement evidence")
            if source:
                stored=store_attachment_file(source,FILE_ROOT,"PM_EXECUTION",str(self.execution.id));evidence=stored["stored_path"]
                self.db.add_attachment("PM_EXECUTION",str(self.execution.id),evidence,original_name=stored["original_name"],media_type=stored["media_type"],category="Requirement Evidence",caption=req.description,equipment_id=self.task.equipment_id,created_by=self.user["username"])
        try:self.db.acknowledge_pm_requirement(self.execution.id,req.requirement_id,self.user["username"],note,evidence);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Requirement",str(exc))

    def reserve_parts(self):
        if not self.task:return
        try:
            created=self.db.reserve_pm_required_parts(self.task.id,self.user["username"],"PM-RUNNER")
            notify(f"PM parts: created {len(created)} reservation(s)." if created else "PM parts: already fully reserved or no required parts.")
            self.refresh()
        except Exception as exc:QMessageBox.critical(self,"PM parts",str(exc))

    def consume_parts(self):
        if not self.execution:return
        if QMessageBox.question(self,"Consume PM parts","Consume all active part reservations for this PM execution from inventory?")!=QMessageBox.StandardButton.Yes:return
        try:
            tx=self.db.consume_pm_reserved_parts(self.execution.id,self.user["username"],"PM-RUNNER")
            notify(f"PM parts: consumed {len(tx)} inventory line(s)." if tx else "PM parts: no active reservations to consume.")
            self.refresh()
        except Exception as exc:QMessageBox.critical(self,"PM parts",str(exc))

    def offer_incident(self,spec,result):
        if QMessageBox.question(self,"Abnormal PM result",f"{result.result} on step {spec.step_no}.\nCreate an incident linked to this equipment now?")!=QMessageBox.StandardButton.Yes:return
        no=f"PM-{self.task.id}-{spec.step_no}-{datetime.now():%Y%m%d%H%M%S}"
        try:
            self.db.save_ticket({"ticket_no":no,"equipment_id":self.task.equipment_id,"title":f"PM abnormal result — {self.task.pm_id} step {spec.step_no}","description":f"{spec.activity}\nResult: {result.result}\nValue: {result.value_text or result.value_numeric}\nReaction plan: {spec.reaction_plan}","severity":"S2","priority":"P2","owner":self.user["username"],"root_cause":"","corrective_action":"","verification":"","created_by":self.user["username"]})
            self.open_entity.emit("TICKET",no,self.task.equipment_id)
        except Exception as exc:QMessageBox.critical(self,"Create incident",str(exc))

    def complete_pm(self):
        if not self.execution:return
        try:
            self.db.complete_pm_execution(self.execution.id,self.user["username"])
            for log in self.db.list_work_logs(self.task.equipment_id,True,200):
                if log.username==self.user["username"] and log.entity_type=="PM_EXECUTION" and log.entity_key==str(self.execution.id):
                    try:self.db.stop_work_log(log.id,self.user["username"],"PM execution completed")
                    except Exception:pass
            notify("PM completed successfully.");self.execution.status="Completed";self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Complete PM",str(exc))

    def open_work_order(self):
        if not self.task:return
        try:
            row=self.db.create_work_order_from_pm(self.task.id,self.user["username"],"PM-RUNNER")
            self.open_entity.emit("WORK_ORDER",row.work_order_no,row.equipment_id)
        except Exception as exc:QMessageBox.critical(self,"Work order",str(exc))

    def export_pptx(self):
        if not self.task:return
        path,_=QFileDialog.getSaveFileName(self,"Export PM Review PowerPoint",f"{self.task.equipment_id}_{self.task.pm_id}_PM_Review.pptx","PowerPoint (*.pptx)")
        if not path:return
        if not path.lower().endswith(".pptx"):path+=".pptx"
        try:export_pm_execution_pptx(self.db,self.task.id,path,self.db.resolve_report_template("PM_EXECUTION",self.task.equipment_id));notify(f"Editable PM review deck created: {path}")
        except Exception as exc:QMessageBox.critical(self,"PowerPoint",str(exc))

    def export_pdf(self):
        if not self.task:return
        path,_=QFileDialog.getSaveFileName(self,"Export PM PDF",f"{self.task.equipment_id}_{self.task.pm_id}_{self.task.id}.pdf","PDF (*.pdf)")
        if not path:return
        if not path.lower().endswith(".pdf"):path+=".pdf"
        try:export_pm_execution_pdf(self.db,self.task.id,path);notify(f"Controlled PM execution PDF created: {path}")
        except Exception as exc:QMessageBox.critical(self,"PDF",str(exc))

    def export_xlsx(self):
        if not self.task:return
        path,_=QFileDialog.getSaveFileName(self,"Export PM Review Excel",f"{self.task.equipment_id}_{self.task.pm_id}_PM_Review.xlsx","Excel Workbook (*.xlsx)")
        if not path:return
        if not path.lower().endswith(".xlsx"):path+=".xlsx"
        try:export_pm_execution_xlsx(self.db,self.task.id,path);notify(f"PM review workbook created: {path}")
        except Exception as exc:QMessageBox.critical(self,"Excel",str(exc))

    def open_equipment(self):
        if self.task:self.open_entity.emit("EQUIPMENT",self.task.equipment_id,self.task.equipment_id)
