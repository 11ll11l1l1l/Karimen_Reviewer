from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,QDialog,QDialogButtonBox,QFormLayout,QLabel,QLineEdit,QTextEdit,
)


class QuickCreateDialog(QDialog):
    def __init__(self,db,user,parent=None,default_equipment: str=""):
        super().__init__(parent);self.db=db;self.user=user;self.created_entity=None
        self.setWindowTitle("Quick Create");self.resize(650,520)
        f=QFormLayout(self)
        self.kind=QComboBox();self.kind.addItems(["Incident","Engineering Work Order"]);self.kind.currentTextChanged.connect(self.refresh_preview)
        self.equipment=QLineEdit(default_equipment);self.equipment.textChanged.connect(self.refresh_preview)
        self.number_preview=QLabel("Auto");self.number_preview.setStyleSheet("color:#647581")
        self.title=QLineEdit();self.description=QTextEdit()
        self.priority=QComboBox();self.priority.addItems(["P1","P2","P3","P4","Normal","High","Critical"])
        self.severity=QComboBox();self.severity.addItems(["S1","S2","S3","S4"])
        self.owner=QLineEdit();self.owner.setPlaceholderText("Leave blank to use configured default owner")
        f.addRow("Type",self.kind);f.addRow("Equipment",self.equipment);f.addRow("Generated number",self.number_preview)
        f.addRow("Title",self.title);f.addRow("Description / scope",self.description);f.addRow("Priority",self.priority);f.addRow("Severity",self.severity);f.addRow("Owner",self.owner)
        self.policy=QLabel();self.policy.setWordWrap(True);self.policy.setStyleSheet("background:#f8fafb;border:1px solid #d7dfe5;padding:8px;color:#526471");f.addRow("Policy preview",self.policy)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.create);buttons.rejected.connect(self.reject);f.addRow(buttons)
        self.refresh_preview()

    def refresh_preview(self):
        equipment=self.equipment.text().strip();kind=self.kind.currentText()
        entity="TICKET" if kind=="Incident" else "WORK_ORDER"
        context={"priority":self.priority.currentText(),"severity":self.severity.currentText()}
        try:number=self.db.preview_configured_number(entity,equipment,context)
        except Exception:number="Auto"
        try:owner=self.db.resolve_default_owner(entity,equipment,context) if equipment else ""
        except Exception:owner=""
        try:sla=self.db.resolve_sla_policy(equipment,context) if entity=="TICKET" and equipment else {}
        except Exception:sla={}
        self.number_preview.setText(number)
        if entity=="TICKET":
            self.severity.setEnabled(True)
            sla_text=", ".join(f"{k.replace('_minutes','')}: {v} min" for k,v in sla.items()) or "No matching SLA policy"
            self.policy.setText(f"Default owner: {owner or 'None'} | {sla_text}")
        else:
            self.severity.setEnabled(False)
            self.policy.setText(f"Default owner: {owner or 'None'}")

    def create(self):
        equipment=self.equipment.text().strip();title=self.title.text().strip()
        if not equipment or not title:return
        owner=self.owner.text().strip()
        try:
            if self.kind.currentText()=="Incident":
                row=self.db.save_ticket({
                    "ticket_no":"","equipment_id":equipment,"title":title,
                    "description":self.description.toPlainText().strip(),
                    "severity":self.severity.currentText(),"priority":self.priority.currentText(),
                    "owner":owner,"root_cause":"","corrective_action":"","verification":"",
                    "created_by":self.user["username"],
                },workstation="QUICK-CREATE")
                self.created_entity=("TICKET",row.ticket_no,row.equipment_id)
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
