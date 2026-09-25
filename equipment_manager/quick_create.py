from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt\nfrom PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,QComboBox,QDialog,QDialogButtonBox,QFormLayout,QHBoxLayout,QLabel,
    QLineEdit,QPushButton,QTextEdit,QWidget,
)

from attachment_store import store_clipboard_image


class QuickCreateDialog(QDialog):
    """Fast frontline entry: report an issue first, create an engineering WO second."""

    def __init__(self,db,user,parent=None,default_equipment: str=""):
        super().__init__(parent)
        self.db=db;self.user=user;self.created_entity=None;self.pending_image=None
        self.setWindowTitle("Report Issue / Quick Create");self.resize(690,650)
        f=QFormLayout(self)

        self.kind=QComboBox();self.kind.addItems(["Report Issue","Engineering Work Order"])
        self.equipment=QLineEdit(default_equipment)
        self.equipment.setPlaceholderText("Equipment / tool ID")
        self.number_preview=QLabel("Auto");self.number_preview.setStyleSheet("color:#647581")
        self.title=QLineEdit();self.title.setPlaceholderText("What happened?")
        self.description=QTextEdit();self.description.setPlaceholderText("Optional details, checks already made, or current condition")

        self.impact=QComboBox();self.impact.addItems(["Observation","Degraded","Production Stop"])
        self.lots=QTextEdit();self.lots.setMaximumHeight(76)
        self.lots.setPlaceholderText("Optional running lot(s) — one per line, or separated by comma/semicolon")
        self.alarm_code=QLineEdit();self.alarm_code.setPlaceholderText("Optional manual alarm/error code")

        self.priority=QComboBox();self.priority.addItems(["P3","P2","P1","P4","Normal","High","Critical"])
        self.owner=QLineEdit();self.owner.setPlaceholderText("Optional — leave blank for configured default owner")

        self.labels={}
        def row(key,label,widget):
            lab=QLabel(label);self.labels[key]=lab;f.addRow(lab,widget)
        row("kind","Type",self.kind);row("equipment","Equipment",self.equipment)
        row("number","Generated number",self.number_preview);row("title","Problem / symptom",self.title)
        row("description","Details",self.description);row("impact","Impact",self.impact)
        row("lots","Running lot(s)",self.lots);row("alarm","Alarm / error code",self.alarm_code)
        row("priority","Priority",self.priority);row("owner","Owner",self.owner)

        evidence=QWidget();eh=QHBoxLayout(evidence);eh.setContentsMargins(0,0,0,0)
        self.paste_button=QPushButton("Paste screenshot (Ctrl+V)")
        self.paste_button.clicked.connect(self.capture_clipboard_image)
        self.image_status=QLabel("No screenshot attached")
        self.image_status.setStyleSheet("color:#647581")
        eh.addWidget(self.paste_button);eh.addWidget(self.image_status,1)
        row("evidence","Screenshot",evidence)

        self.policy=QLabel();self.policy.setWordWrap(True)
        self.policy.setStyleSheet("background:#f8fafb;border:1px solid #d7dfe5;padding:8px;color:#526471")
        row("policy","",self.policy)

        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.create);buttons.rejected.connect(self.reject);f.addRow(buttons)

        self.paste_shortcut=QShortcut(QKeySequence.Paste,self)
        self.paste_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.paste_shortcut.activated.connect(self._paste_shortcut)

        self.kind.currentTextChanged.connect(self.refresh_preview)
        self.equipment.textChanged.connect(self.refresh_preview)
        self.impact.currentTextChanged.connect(self.refresh_preview)
        self.priority.currentTextChanged.connect(self.refresh_preview)
        self.refresh_preview()

    def _paste_shortcut(self):
        clipboard=QApplication.clipboard()
        if not clipboard.image().isNull():
            self.capture_clipboard_image()
            return
        focus=QApplication.focusWidget()
        if focus and hasattr(focus,"paste"):
            focus.paste()

    def capture_clipboard_image(self):
        image=QApplication.clipboard().image()
        if image.isNull():
            self.image_status.setText("Clipboard does not contain an image")
            return
        self.pending_image=image.copy()
        self.image_status.setText(f"Screenshot ready · {image.width()}×{image.height()}")

    def _set_issue_rows(self,issue: bool):
        for key in ["impact","lots","alarm","evidence"]:
            self.labels[key].setVisible(issue)
        self.impact.setVisible(issue);self.lots.setVisible(issue);self.alarm_code.setVisible(issue)
        self.paste_button.parentWidget().setVisible(issue)
        self.labels["priority"].setVisible(not issue);self.priority.setVisible(not issue)
        self.labels["description"].setText("Details" if issue else "Description / scope")
        self.labels["title"].setText("Problem / symptom" if issue else "Title")
        self.title.setPlaceholderText("What happened?" if issue else "Engineering work order title")

    def refresh_preview(self):
        equipment=self.equipment.text().strip()
        issue=self.kind.currentText()=="Report Issue"
        self._set_issue_rows(issue)
        entity="TICKET" if issue else "WORK_ORDER"
        if issue:
            mapping={"Observation":("P3","S3"),"Degraded":("P2","S2"),"Production Stop":("P1","S1")}
            priority,severity=mapping.get(self.impact.currentText(),("P3","S3"))
            context={"priority":priority,"severity":severity}
        else:
            context={"priority":self.priority.currentText()}
        try:number=self.db.preview_configured_number(entity,equipment,context)
        except Exception:number="Auto"
        try:owner=self.db.resolve_default_owner(entity,equipment,context) if equipment else ""
        except Exception:owner=""
        try:sla=self.db.resolve_sla_policy(equipment,context) if issue and equipment else {}
        except Exception:sla={}
        self.number_preview.setText(number)
        if issue:
            sla_text=", ".join(f"{k.replace('_minutes','')}: {v} min" for k,v in sla.items()) or "No matching SLA policy"
            self.policy.setText(
                f"Fast manual issue · default owner: {owner or 'None'} · {sla_text}. "
                "Only equipment and problem/symptom are required."
            )
        else:
            self.policy.setText(f"Engineering work order · default owner: {owner or 'None'}")

    def _lot_values(self):
        text=self.lots.toPlainText().strip()
        if not text:return []
        import re
        return [x.strip() for x in re.split(r"[\\n,;\\t]+",text) if x.strip()]

    def create(self):
        equipment=self.equipment.text().strip();title=self.title.text().strip()
        if not equipment:
            self.policy.setText("Equipment is required.");return
        if not title:
            self.policy.setText("Problem / symptom or work-order title is required.");return
        owner=self.owner.text().strip()
        try:
            if self.kind.currentText()=="Report Issue":
                ticket,alarm=self.db.create_manual_issue({
                    "equipment_id":equipment,"title":title,
                    "description":self.description.toPlainText().strip(),
                    "impact":self.impact.currentText(),
                    "lot_numbers":self._lot_values(),
                    "alarm_code":self.alarm_code.text().strip(),
                    "owner":owner,
                },self.user["username"],"QUICK-CREATE")
                if self.pending_image is not None and not self.pending_image.isNull():
                    root=os.getenv("EMS_FILE_ROOT",str(Path.cwd()/"equipment_files"))
                    stored=store_clipboard_image(self.pending_image,root,"TICKET",ticket.ticket_no)
                    self.db.add_attachment(
                        "TICKET",ticket.ticket_no,stored["stored_path"],
                        original_name=stored["original_name"],media_type=stored["media_type"],
                        category="Screenshot",caption=title,equipment_id=equipment,
                        created_by=self.user["username"],
                    )
                self.created_entity=("TICKET",ticket.ticket_no,ticket.equipment_id)
            else:
                row=self.db.create_work_order({
                    "work_order_no":"","equipment_id":equipment,"source_type":"ENGINEERING",
                    "title":title,"description":self.description.toPlainText().strip(),
                    "priority":self.priority.currentText(),"owner":owner,
                },self.user["username"],"QUICK-CREATE")
                self.created_entity=("WORK_ORDER",row.work_order_no,row.equipment_id)
            self.accept()
        except Exception as exc:
            self.policy.setText(f"Cannot create: {exc}")
