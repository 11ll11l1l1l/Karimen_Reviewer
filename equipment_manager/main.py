from __future__ import annotations

import json
import os
import socket
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDateEdit, QDateTimeEdit, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene,
    QGraphicsTextItem, QGraphicsView, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMessageBox, QPushButton, QSpinBox, QStackedWidget, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QInputDialog,
)

from database import Database, PERMISSIONS, ROLE_PERMISSIONS
from backup import create_backup, verify_backup
from attachment_store import store_attachment_file
from logging_config import configure_logging, install_exception_hook
from version import __version__
from domain import REASON_CODES, TICKET_REASON_CODES, allowed_targets, allowed_ticket_targets
from workspaces import AttachmentPanel
from table_productivity import configure_productivity_context, install_table_productivity
from excel_import_studio import run_mapping_studio
from excel_reconcile import (
    apply_extended_reconciliation, confirm_reconciliation, dataframe_rows,
    endorsement_export_rows, qualification_protocol_export_rows,
    reconcile_endorsements, reconcile_equipment, reconcile_inventory,
    reconcile_qualification_protocols, reconcile_tickets,
)
from alarm_correlation import correlate_alarm_bursts
from integrations import dispatch_pending
from inbound_integrations import process_inbound_endpoint, process_inbound_file
from reporting import export_qualification_pptx, export_qualification_xlsx, export_release_pptx, export_release_xlsx
from pdf_reporting import export_qualification_pdf, export_release_pdf
from services import (
    auto_mapping, calculate_next_due, copy_clipboard_image, dataframe_to_equipment, dataframe_to_inventory, dataframe_to_tickets, dataframe_to_pm_backlog,
    dataframe_to_pm_specs, evaluate_measurement, pm_parts_readiness, read_clipboard_table,
    read_table, readonly_open_copy, workbook_sheets, workload_by_day,
)

APP_TITLE = f"Equipment Management System {__version__}"
WORKSTATION = socket.gethostname()
FILE_ROOT = os.getenv("EMS_FILE_ROOT", str(Path.cwd() / "equipment_files"))

STYLE = """
QWidget { font-size: 10.5pt; }
QMainWindow, QDialog { background: #f4f6f8; }
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QDateEdit, QTextEdit {
  background: white; border: 1px solid #c8ced6; border-radius: 4px; padding: 5px;
}
QPushButton { background: #1f5f8b; color: white; border: 0; border-radius: 4px; padding: 7px 11px; }
QPushButton:disabled { background: #aeb7bf; }
QTableWidget { background: white; border: 1px solid #d9dee3; gridline-color: #e7eaed; }
QHeaderView::section { background: #e9edf1; padding: 6px; border: 0; border-right: 1px solid #d0d6dc; font-weight: 600; }
QListWidget { background: #172431; color: white; border: 0; padding: 8px; }
QListWidget::item { padding: 10px; border-radius: 4px; }
QListWidget::item:selected { background: #2a6f9e; }
"""


def ti(value: Any) -> QTableWidgetItem:
    if isinstance(value, datetime): return QTableWidgetItem(value.strftime("%Y-%m-%d %H:%M"))
    return QTableWidgetItem("" if value is None else str(value))


def fill_table(table: QTableWidget, rows: list[Any], fields: list[str]):
    table.setRowCount(len(rows))
    for r, obj in enumerate(rows):
        for c, field in enumerate(fields): table.setItem(r, c, ti(getattr(obj, field, "")))


def selected_row(table: QTableWidget, rows: list[Any]):
    r = table.currentRow()
    return rows[r] if 0 <= r < len(rows) else None


def config_option_values(db,category: str,fallback: list[str]) -> list[str]:
    if db is None:return list(fallback)
    try:
        rows=db.list_config_options(category,True)
        values=[x.code for x in rows]
        return values or list(fallback)
    except Exception:return list(fallback)


def populate_reason_combo(combo: QComboBox,db,category: str,fallback: dict[str,str]):
    rows=[]
    if db is not None:
        try:rows=db.list_config_options(category,True)
        except Exception:rows=[]
    entries=[(x.code,x.label) for x in rows] or list(fallback.items())
    for code,label in entries:combo.addItem(f"{code} — {label}",code)


def reason_label(combo: QComboBox) -> str:
    text=combo.currentText()
    return text.split(" — ",1)[1] if " — " in text else text


def make_table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(); t.setColumnCount(len(headers)); t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    t.setAlternatingRowColors(True)
    install_table_productivity(t,headers[0] if headers else "EMS Export")
    return t


class FirstAdminDialog(QDialog):
    def __init__(self, db: Database):
        super().__init__(); self.db = db; self.setWindowTitle("Create first administrator")
        f = QFormLayout(self); self.username = QLineEdit("admin"); self.name = QLineEdit(); self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password); self.confirm = QLineEdit(); self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        f.addRow("Username", self.username); f.addRow("Display name", self.name); f.addRow("Password", self.password); f.addRow("Confirm", self.confirm)
        b = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel); b.accepted.connect(self.create); b.rejected.connect(self.reject); f.addRow(b)
    def create(self):
        if self.password.text() != self.confirm.text(): QMessageBox.warning(self, "Password", "Passwords do not match."); return
        try: self.db.create_user(self.username.text(), self.name.text(), self.password.text(), "Administrator"); self.accept()
        except Exception as exc: QMessageBox.critical(self, "Create administrator", str(exc))


class LoginDialog(QDialog):
    def __init__(self, db: Database):
        super().__init__(); self.db = db; self.user = None; self.setWindowTitle(APP_TITLE + " - Login"); self.setMinimumWidth(430)
        v = QVBoxLayout(self); title = QLabel("EQUIPMENT MANAGEMENT"); title.setStyleSheet("font-size:20pt;font-weight:700;color:#16354b"); v.addWidget(title)
        ok, status = db.health(); h = QLabel(f"Database: {'Connected' if ok else 'Offline'} — {status}"); h.setStyleSheet("color:#26734d" if ok else "color:#a62b2b"); v.addWidget(h)
        f = QFormLayout(); self.username = QLineEdit(); self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password); f.addRow("Username", self.username); f.addRow("Password", self.password); v.addLayout(f)
        b = QPushButton("Login"); b.clicked.connect(self.login); v.addWidget(b); self.password.returnPressed.connect(self.login)
    def login(self):
        user = self.db.authenticate(self.username.text(), self.password.text(), workstation=WORKSTATION)
        if not user: QMessageBox.warning(self, "Login", "Invalid username/password or inactive account."); return
        self.user = user; self.db.audit(user["username"], "LOGIN", "SESSION", WORKSTATION, workstation=WORKSTATION); self.accept()


class MetricCard(QWidget):
    def __init__(self, label: str):
        super().__init__(); self.setStyleSheet("background:white;border:1px solid #d9dee3;border-radius:6px;")
        v = QVBoxLayout(self); self.value = QLabel("0"); self.value.setStyleSheet("font-size:24pt;font-weight:700;color:#16354b;border:0"); t = QLabel(label); t.setStyleSheet("color:#5a6670;border:0"); v.addWidget(self.value); v.addWidget(t)


class DashboardPage(QWidget):
    def __init__(self, db: Database):
        super().__init__(); self.db=db; self.attention=[]
        v=QVBoxLayout(self)
        top=QHBoxLayout(); title=QLabel("Operations Command Center"); title.setStyleSheet("font-size:20pt;font-weight:700")
        self.updated=QLabel(); refresh=QPushButton("Refresh"); refresh.clicked.connect(self.refresh)
        top.addWidget(title); top.addStretch(1); top.addWidget(self.updated); top.addWidget(refresh); v.addLayout(top)

        g=QGridLayout(); v.addLayout(g)
        defs=[
            ("equipment_down","Tools Down"),("equipment_hold","Tools on Hold"),("pm_overdue","PM Overdue"),
            ("tickets_critical","P1/P2 Incidents"),("alarms_active","Active Alarms"),("release_pending","Release Pending"),("endorsements_open","Shift Handovers"),
            ("inventory_low","Low Stock"),("reservations_active","Part Reservations"),
        ]
        self.cards={}
        for i,(key,label) in enumerate(defs):
            self.cards[key]=MetricCard(label);g.addWidget(self.cards[key],i//4,i%4)

        section=QLabel("WHAT REQUIRES ATTENTION");section.setStyleSheet("font-size:13pt;font-weight:700;margin-top:8px");v.addWidget(section)
        self.attention_table=make_table(["Severity","Type","Equipment","Key","Action / Condition","Owner","Age (h)"])
        v.addWidget(self.attention_table,3)

        lower=QHBoxLayout()
        note=QLabel("Priority queue is derived from governed equipment states, incident SLA/escalation, overdue PM, qualification/release status and shift handovers.")
        note.setWordWrap(True);note.setStyleSheet("color:#5a6670")
        lower.addWidget(note,1)
        v.addLayout(lower)
        self.refresh()

    def refresh(self):
        counts=self.db.dashboard_counts()
        for key,card in self.cards.items():card.value.setText(str(counts.get(key,0)))
        self.attention=self.db.operations_attention_queue()
        self.attention_table.setRowCount(len(self.attention))
        fields=["severity","kind","equipment_id","key","summary","owner","age_hours"]
        for r,row in enumerate(self.attention):
            for col,field in enumerate(fields):
                value=row.get(field,"")
                if field=="age_hours":value=f"{float(value or 0):.1f}"
                self.attention_table.setItem(r,col,ti(value))
        self.updated.setText("Updated "+datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class EquipmentDialog(QDialog):
    """Equipment master-data editor. Operational state is intentionally read-only here."""
    def __init__(self, row=None, parent=None, db=None, initial=None):
        super().__init__(parent); self.row = row; self.db=db; self.setWindowTitle("Equipment Master Data"); f = QFormLayout(self); self.fields = {}
        for k, label in [("equipment_id","Equipment ID"),("name","Name"),("equipment_type","Type"),("manufacturer","Manufacturer"),("model","Model"),("serial_number","Serial"),("asset_number","Asset Number"),("site","Site"),("building","Building"),("floor","Floor"),("area","Area"),("line_cell","Line / Bay / Cell"),("owner","Owner")]:
            w = QLineEdit(); self.fields[k] = w; f.addRow(label, w)
        self.criticality = QComboBox(); self.criticality.addItems(config_option_values(db,"EQUIPMENT_CRITICALITY",["Low","Normal","High","Critical"]))
        self.x = QDoubleSpinBox(); self.y = QDoubleSpinBox(); self.x.setRange(-100000,100000); self.y.setRange(-100000,100000)
        f.addRow("Criticality", self.criticality); f.addRow("Map X", self.x); f.addRow("Map Y", self.y)
        if row:
            state = QLabel(row.status); disposition = QLabel(row.disposition)
            state.setStyleSheet("font-weight:700"); disposition.setStyleSheet("font-weight:700")
            f.addRow("Operational State", state); f.addRow("Disposition", disposition)
            note = QLabel("State and disposition are controlled workflows and cannot be edited as master data.")
            note.setWordWrap(True); note.setStyleSheet("color:#7a4b00")
            f.addRow("", note)
        b = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b)
        if row:
            for k, w in self.fields.items(): w.setText(str(getattr(row,k,"") or ""))
            self.fields["equipment_id"].setReadOnly(True); self.criticality.setCurrentText(row.criticality); self.x.setValue(row.map_x); self.y.setValue(row.map_y)
        elif initial:
            for k,w in self.fields.items():w.setText(str(initial.get(k,"") or ""))
            self.criticality.setCurrentText(str(initial.get("criticality","Normal") or "Normal"))
            self.x.setValue(float(initial.get("map_x",0) or 0));self.y.setValue(float(initial.get("map_y",0) or 0))

    def data(self):
        d = {k:w.text().strip() for k,w in self.fields.items()}
        d.update(criticality=self.criticality.currentText(), map_x=self.x.value(), map_y=self.y.value())
        return d


class EquipmentStateDialog(QDialog):
    def __init__(self, row, parent=None, db=None):
        super().__init__(parent); self.row=row;self.db=db; self.setWindowTitle(f"Change Equipment State — {row.equipment_id}"); self.setMinimumWidth(560)
        f=QFormLayout(self)
        current=QLabel(row.status); current.setStyleSheet("font-weight:700")
        self.target=QComboBox(); self.target.addItems(allowed_targets(row.status))
        self.reason=QComboBox();populate_reason_combo(self.reason,db,"EQUIPMENT_REASON_LABEL",REASON_CODES)
        self.reason_help=QLabel(); self.reason_help.setWordWrap(True); self.reason_help.setStyleSheet("color:#5a6670")
        self.reason.currentIndexChanged.connect(lambda *_:self.reason_help.setText(reason_label(self.reason)))
        self.owner=QLineEdit(row.owner or ""); self.ticket=QLineEdit(); self.pm_task=QSpinBox(); self.pm_task.setRange(0,2_000_000_000); self.pm_task.setSpecialValueText("None")
        self.detail=QTextEdit(); self.detail.setPlaceholderText("Describe the actual condition, trigger, containment, or release basis.")
        f.addRow("Current State",current); f.addRow("Target State",self.target); f.addRow("Reason Code",self.reason); f.addRow("",self.reason_help)
        f.addRow("Accountable Owner",self.owner); f.addRow("Related Ticket",self.ticket); f.addRow("Related PM Task ID",self.pm_task); f.addRow("Detailed Reason",self.detail)
        warning=QLabel("This action creates an equipment state event and audit record. It is not a simple field edit.")
        warning.setWordWrap(True); warning.setStyleSheet("color:#7a4b00")
        f.addRow("",warning)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b)
        self.reason_help.setText(reason_label(self.reason))

    def data(self):
        pm_id=self.pm_task.value() or None
        return {
            "target_state":self.target.currentText(),
            "reason_code":str(self.reason.currentData() or self.reason.currentText()).split(" — ",1)[0],
            "reason_text":self.detail.toPlainText().strip(),
            "related_ticket":self.ticket.text().strip(),
            "related_pm_task_id":pm_id,
            "owner":self.owner.text().strip(),
        }


class ComponentDialog(QDialog):
    def __init__(self,equipment_id,row=None,parent=None):
        super().__init__(parent); self.row=row; self.equipment_id=equipment_id; self.setWindowTitle("Equipment Component")
        f=QFormLayout(self)
        self.component_id=QLineEdit(); self.parent_id=QLineEdit(); self.name=QLineEdit(); self.type=QLineEdit(); self.mfg=QLineEdit(); self.model=QLineEdit(); self.serial=QLineEdit(); self.part=QLineEdit()
        self.life=QDoubleSpinBox(); self.life.setRange(0,1e15); self.life.setSpecialValueText("Not set")
        self.life_unit=QLineEdit(); self.usage=QDoubleSpinBox(); self.usage.setRange(0,1e15); self.notes=QTextEdit()
        f.addRow("Equipment",QLabel(equipment_id))
        for label,w in [("Component ID",self.component_id),("Parent Component",self.parent_id),("Name",self.name),("Type",self.type),("Manufacturer",self.mfg),("Model",self.model),("Serial",self.serial),("Part Number",self.part),("Life Limit",self.life),("Life Limit Unit",self.life_unit),("Usage",self.usage),("Notes",self.notes)]:f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:
            self.component_id.setText(row.component_id);self.component_id.setReadOnly(True)
            self.parent_id.setText(row.parent_component_id);self.parent_id.setReadOnly(True)
            self.name.setText(row.name);self.type.setText(row.component_type);self.mfg.setText(row.manufacturer);self.model.setText(row.model);self.serial.setText(row.serial_number);self.part.setText(row.part_number)
            self.life.setValue(row.life_limit_value or 0);self.life_unit.setText(row.life_limit_unit);self.usage.setValue(row.usage_value or 0);self.notes.setPlainText(row.notes)

    def data(self):
        return {
            "component_id":self.component_id.text().strip(),
            "equipment_id":self.equipment_id,
            "parent_component_id":self.parent_id.text().strip(),
            "name":self.name.text().strip(),
            "component_type":self.type.text().strip(),
            "manufacturer":self.mfg.text().strip(),
            "model":self.model.text().strip(),
            "serial_number":self.serial.text().strip(),
            "part_number":self.part.text().strip(),
            "life_limit_value":self.life.value() or None,
            "life_limit_unit":self.life_unit.text().strip(),
            "usage_value":self.usage.value(),
            "notes":self.notes.toPlainText().strip(),
        }


class ComponentRemoveDialog(QDialog):
    def __init__(self,row,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle(f"Remove Component — {row.component_id}")
        f=QFormLayout(self);self.reason=QTextEdit();self.ticket=QLineEdit();self.pm=QSpinBox();self.pm.setRange(0,2_000_000_000);self.pm.setSpecialValueText("None")
        f.addRow("Reason",self.reason);f.addRow("Related Ticket",self.ticket);f.addRow("Related PM Task ID",self.pm)
        note=QLabel("Removal is permanent history. The component remains traceable but is no longer active on the equipment.");note.setWordWrap(True);note.setStyleSheet("color:#7a4b00");f.addRow("",note)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)


class MeterDialog(QDialog):
    def __init__(self,equipment_id,row=None,parent=None):
        super().__init__(parent);self.row=row;self.equipment_id=equipment_id;self.setWindowTitle("Equipment Usage Meter")
        f=QFormLayout(self);self.code=QLineEdit();self.name=QLineEdit();self.unit=QLineEdit();self.mode=QComboBox();self.mode.addItems(["COUNTER","GAUGE"]);self.initial=QDoubleSpinBox();self.initial.setRange(-1e15,1e15);self.active=QCheckBox("Active");self.active.setChecked(True)
        f.addRow("Equipment",QLabel(equipment_id));f.addRow("Meter Code",self.code);f.addRow("Name",self.name);f.addRow("Unit",self.unit);f.addRow("Mode",self.mode);f.addRow("Initial Value",self.initial);f.addRow("",self.active)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:
            self.code.setText(row.meter_code);self.code.setReadOnly(True);self.name.setText(row.name);self.unit.setText(row.unit);self.mode.setCurrentText("COUNTER");self.initial.setValue(row.current_value);self.initial.setEnabled(False);self.active.setChecked(row.active)
    def data(self):
        return {"equipment_id":self.equipment_id,"meter_code":self.code.text().strip(),"name":self.name.text().strip(),"unit":self.unit.text().strip(),"meter_mode":self.mode.currentText(),"current_value":self.initial.value(),"active":self.active.isChecked()}


class MeterReadingDialog(QDialog):
    def __init__(self,row,reset=False,parent=None):
        super().__init__(parent);self.row=row;self.reset=reset;self.setWindowTitle(("Reset" if reset else "Record")+" Meter — "+row.meter_code)
        f=QFormLayout(self);self.value=QDoubleSpinBox();self.value.setRange(0,1e15);self.value.setDecimals(3);self.value.setValue(0 if reset else row.current_value);self.note=QTextEdit()
        f.addRow("Current",QLabel(f"{row.current_value:g} {row.unit}"));f.addRow("New Value",self.value);f.addRow("Note",self.note)
        if reset:
            note=QLabel("Reset rebases all active PM usage thresholds for this meter.");note.setWordWrap(True);note.setStyleSheet("color:#7a4b00");f.addRow("",note)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)


class EquipmentPage(QWidget):
    def __init__(self, db, user):
        super().__init__(); self.db=db; self.user=user; self.rows=[]; self.history=[]; self.components=[]; self.component_events=[]; self.meters=[]; self.meter_readings=[]
        v=QVBoxLayout(self); h=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Search equipment..."); self.search.textChanged.connect(self.refresh)
        add=QPushButton("Add");template=QPushButton("Add from Template");edit=QPushButton("Edit Master Data"); transition=QPushButton("Change State");imp=QPushButton("Import Excel/CSV");paste=QPushButton("Paste from Excel");bulk=QPushButton("Bulk Edit Selected")
        add.clicked.connect(self.add);template.clicked.connect(self.add_from_template); edit.clicked.connect(self.edit); transition.clicked.connect(self.change_state);imp.clicked.connect(self.import_equipment);paste.clicked.connect(self.paste_equipment);bulk.clicked.connect(self.bulk_edit)
        canedit=db.has_permission(user,"equipment.edit");add.setEnabled(canedit);template.setEnabled(canedit);edit.setEnabled(canedit);imp.setEnabled(canedit);paste.setEnabled(canedit);bulk.setEnabled(canedit);transition.setEnabled(db.has_permission(user,"equipment.transition"))
        h.addWidget(self.search,1); h.addWidget(add);h.addWidget(template); h.addWidget(edit);h.addWidget(imp);h.addWidget(paste);h.addWidget(bulk); h.addWidget(transition); v.addLayout(h)
        self.table=make_table(["ID","Name","Type","Area","Line/Cell","Status","Disposition","Owner","Criticality","Ver"])
        self.table.doubleClicked.connect(self.edit); self.table.itemSelectionChanged.connect(self.load_details); v.addWidget(self.table,2)

        tabs=QTabWidget()
        ws=QWidget();vs=QVBoxLayout(ws);self.history_table=make_table(["From","To","Class","Reason","Detail","Ticket","PM Task","Owner","Changed By","Time"]);vs.addWidget(self.history_table);tabs.addTab(ws,"State Timeline")

        wc=QWidget();vc=QVBoxLayout(wc);hc=QHBoxLayout();addc=QPushButton("Add Component");editc=QPushButton("Edit Component");removec=QPushButton("Remove Component")
        addc.clicked.connect(self.add_component);editc.clicked.connect(self.edit_component);removec.clicked.connect(self.remove_component)
        cancomp=db.has_permission(user,"equipment.component.edit");addc.setEnabled(cancomp);editc.setEnabled(cancomp);removec.setEnabled(cancomp)
        hc.addWidget(addc);hc.addWidget(editc);hc.addWidget(removec);hc.addStretch(1);vc.addLayout(hc)
        self.component_table=make_table(["Component ID","Parent","Name","Type","Part","Serial","Status","Life Limit","Unit","Usage","Installed","Removed","Ver"])
        self.component_table.itemSelectionChanged.connect(self.load_component_events);vc.addWidget(self.component_table,2)
        vc.addWidget(QLabel("Component History"))
        self.component_event_table=make_table(["Component","Event","Parent","Reason","Ticket","PM Task","User","Time"]);vc.addWidget(self.component_event_table,1)
        tabs.addTab(wc,"Components / Modules")

        wm=QWidget();vm=QVBoxLayout(wm);hm=QHBoxLayout();addm=QPushButton("Add Meter");readm=QPushButton("Record Reading");resetm=QPushButton("Reset Counter")
        addm.clicked.connect(self.add_meter);readm.clicked.connect(lambda:self.record_meter(False));resetm.clicked.connect(lambda:self.record_meter(True))
        addm.setEnabled(db.has_permission(user,"equipment.edit"));canmeter=db.has_permission(user,"equipment.meter.record");readm.setEnabled(canmeter);resetm.setEnabled(canmeter)
        hm.addWidget(addm);hm.addWidget(readm);hm.addWidget(resetm);hm.addStretch(1);vm.addLayout(hm)
        self.meter_table=make_table(["Code","Name","Unit","Current","Last Reading","Active","Ver"]);self.meter_table.itemSelectionChanged.connect(self.load_meter_readings);vm.addWidget(self.meter_table,1)
        self.meter_reading_table=make_table(["Meter","Value","Type","Note","Recorded By","Time"]);vm.addWidget(self.meter_reading_table,1)
        tabs.addTab(wm,"Usage / Counters")
        v.addWidget(tabs,1); self.refresh()

    def refresh(self):
        current=selected_row(self.table,self.rows)
        current_id=current.equipment_id if current else ""
        self.rows=self.db.list_equipment(self.search.text().strip())
        fill_table(self.table,self.rows,["equipment_id","name","equipment_type","area","line_cell","status","disposition","owner","criticality","version"])
        if current_id:
            for i,row in enumerate(self.rows):
                if row.equipment_id==current_id:
                    self.table.selectRow(i); break
        self.load_details()

    def bulk_edit(self):
        selected=sorted({idx.row() for idx in self.table.selectedIndexes()})
        rows=[self.rows[i] for i in selected if 0<=i<len(self.rows)]
        if not rows:
            QMessageBox.information(self,"Bulk edit","Select one or more equipment rows.");return
        field,ok=QInputDialog.getItem(self,"Bulk edit equipment","Field",["Owner","Criticality"],0,False)
        if not ok:return
        if field=="Owner":
            value,ok=QInputDialog.getText(self,"Bulk edit equipment",f"New owner for {len(rows)} equipment")
        else:
            values=config_option_values(self.db,"EQUIPMENT_CRITICALITY",["Low","Normal","High","Critical"])
            value,ok=QInputDialog.getItem(self,"Bulk edit equipment","Criticality",values,values.index("Normal") if "Normal" in values else 0,False)
        if not ok:return
        if QMessageBox.question(self,"Confirm bulk edit",f"Update {field} on {len(rows)} equipment record(s)?")!=QMessageBox.StandardButton.Yes:return
        failures=[];updated=0
        for row in rows:
            data={
                "equipment_id":row.equipment_id,"name":row.name,"equipment_type":row.equipment_type,
                "manufacturer":row.manufacturer,"model":row.model,"serial_number":row.serial_number,
                "asset_number":row.asset_number,"site":row.site,"building":row.building,"floor":row.floor,
                "area":row.area,"line_cell":row.line_cell,"owner":value.strip() if field=="Owner" else row.owner,
                "criticality":value if field=="Criticality" else row.criticality,
                "map_x":row.map_x,"map_y":row.map_y,
            }
            try:self.db.save_equipment(data,row.version,user=self.user["username"],workstation=WORKSTATION);updated+=1
            except Exception as exc:failures.append(f"{row.equipment_id}: {exc}")
        self.refresh()
        text=f"Updated {updated}/{len(rows)} equipment record(s)."
        if failures:text+="\n"+"\n".join(failures[:12])
        QMessageBox.information(self,"Bulk edit",text)

    def _equipment_import_df(self,df):
        fields=[
            ("equipment_id","Equipment ID"),("name","Name"),("equipment_type","Equipment type"),("manufacturer","Manufacturer"),
            ("model","Model"),("serial_number","Serial number"),("asset_number","Asset number"),("site","Site"),("building","Building"),
            ("floor","Floor"),("area","Area"),("line_cell","Line / Bay / Cell"),("owner","Owner"),("criticality","Criticality"),
        ]
        mapping=run_mapping_studio(self,self.db,self.user["username"],"excel_mapping.equipment_master",df,fields,auto_mapping(list(df.columns)),{"equipment_id"},"Equipment Master Import Studio")
        if mapping is None:return
        rows,errors=dataframe_to_equipment(df,mapping)
        if not rows:QMessageBox.warning(self,"Equipment import","No valid rows.\n"+"\n".join(errors[:20]));return
        actions=reconcile_equipment(self.db,rows,mapping)
        if not any(x["status"] in {"CREATE","UPDATE"} for x in actions):
            QMessageBox.information(self,"Equipment import","No changes detected.");return
        if not confirm_reconciliation(self,"Equipment Master Reconciliation",actions):return
        imported=0;failures=[]
        for action in actions:
            if action["status"]=="UNCHANGED":continue
            data=action["data"];current=action["current"]
            try:
                self.db.save_equipment(data,current.version if current else None,user=self.user["username"],workstation=WORKSTATION);imported+=1
            except Exception as exc:failures.append(f"{data.get('equipment_id')}: {exc}")
        self.refresh();detail=f"Applied {imported} equipment create/update row(s). Source warnings: {len(errors)}. Failures: {len(failures)}."
        if failures:detail+="\n"+"\n".join(failures[:12])
        QMessageBox.information(self,"Equipment import",detail)

    def import_equipment(self):
        path,_=QFileDialog.getOpenFileName(self,"Import Equipment Master","","Excel/CSV (*.xlsx *.xlsm *.csv)")
        if not path:return
        try:
            sheets=workbook_sheets(path);sheet=sheets[0]
            if len(sheets)>1:
                sheet,ok=QInputDialog.getItem(self,"Import Equipment","Sheet",sheets,0,False)
                if not ok:return
            self._equipment_import_df(read_table(path,sheet))
        except Exception as exc:QMessageBox.critical(self,"Equipment import",str(exc))

    def paste_equipment(self):
        try:self._equipment_import_df(read_clipboard_table(QApplication.clipboard().text()))
        except Exception as exc:QMessageBox.critical(self,"Equipment paste",str(exc))

    def select_equipment(self,equipment_id: str):
        self.search.setText("")
        self.refresh()
        for i,row in enumerate(self.rows):
            if row.equipment_id==equipment_id:
                self.table.selectRow(i)
                item=self.table.item(i,0)
                if item:self.table.scrollToItem(item)
                self.load_details()
                break

    def add_from_template(self):
        templates=self.db.list_entity_templates("EQUIPMENT")
        if not templates:
            QMessageBox.information(self,"Equipment Template","No active equipment templates are configured.");return
        labels=[f"{x.name} ({x.template_id})" for x in templates]
        choice,ok=QInputDialog.getItem(self,"Equipment Template","Template",labels,0,False)
        if not ok:return
        template=templates[labels.index(choice)]
        try:initial=self.db.apply_entity_template(template.template_id)
        except Exception as exc:QMessageBox.critical(self,"Equipment Template",str(exc));return
        d=EquipmentDialog(parent=self,db=self.db,initial=initial)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                row=self.db.save_equipment(d.data(),user=self.user["username"],workstation=WORKSTATION)
                self.db.audit(self.user["username"],"CREATE_FROM_TEMPLATE","EQUIPMENT",row.equipment_id,template.template_id,WORKSTATION);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Equipment",str(exc))

    def add(self):
        d=EquipmentDialog(parent=self,db=self.db)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                row=self.db.save_equipment(d.data(), user=self.user["username"], workstation=WORKSTATION)
                self.db.audit(self.user["username"],"CREATE","EQUIPMENT",row.equipment_id,workstation=WORKSTATION)
                self.refresh()
            except Exception as exc: QMessageBox.critical(self,"Equipment",str(exc))

    def edit(self):
        row=selected_row(self.table,self.rows)
        if not row:return
        d=EquipmentDialog(row,self,db=self.db)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                self.db.save_equipment(d.data(),row.version,user=self.user["username"],workstation=WORKSTATION)
                self.db.audit(self.user["username"],"UPDATE_MASTER","EQUIPMENT",row.equipment_id,workstation=WORKSTATION)
                self.refresh()
            except Exception as exc: QMessageBox.critical(self,"Equipment",str(exc))

    def change_state(self):
        row=selected_row(self.table,self.rows)
        if not row:return
        d=EquipmentStateDialog(row,self,db=self.db)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                self.db.transition_equipment_state(
                    row.equipment_id,
                    user=self.user["username"],
                    workstation=WORKSTATION,
                    expected_version=row.version,
                    **d.data(),
                )
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self,"Equipment State",str(exc))

    def load_details(self):
        row=selected_row(self.table,self.rows)
        self.history=self.db.list_equipment_state_events(row.equipment_id) if row else []
        self.components=self.db.list_components(row.equipment_id) if row else []
        self.meters=self.db.list_meters(row.equipment_id) if row else []
        fill_table(self.history_table,self.history,["from_state","to_state","state_class","reason_code","reason_text","related_ticket","related_pm_task_id","owner","changed_by","changed_at"])
        fill_table(self.component_table,self.components,["component_id","parent_component_id","name","component_type","part_number","serial_number","status","life_limit_value","life_limit_unit","usage_value","installed_at","removed_at","version"])
        fill_table(self.meter_table,self.meters,["meter_code","name","unit","current_value","last_reading_at","active","version"])
        self.load_component_events();self.load_meter_readings()

    def load_component_events(self):
        component=selected_row(self.component_table,self.components)
        equipment=selected_row(self.table,self.rows)
        self.component_events=self.db.list_component_events(component_id=component.component_id) if component else (self.db.list_component_events(equipment_id=equipment.equipment_id) if equipment else [])
        fill_table(self.component_event_table,self.component_events,["component_id","event_type","parent_component_id","reason","related_ticket","related_pm_task_id","user","occurred_at"])

    def add_component(self):
        equipment=selected_row(self.table,self.rows)
        if not equipment:return
        d=ComponentDialog(equipment.equipment_id,parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                self.db.save_component(d.data(),user=self.user["username"],workstation=WORKSTATION)
                self.load_details()
            except Exception as exc:QMessageBox.critical(self,"Component",str(exc))

    def edit_component(self):
        row=selected_row(self.component_table,self.components)
        if not row:return
        d=ComponentDialog(row.equipment_id,row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                self.db.save_component(d.data(),row.version,user=self.user["username"],workstation=WORKSTATION)
                self.load_details()
            except Exception as exc:QMessageBox.critical(self,"Component",str(exc))

    def remove_component(self):
        row=selected_row(self.component_table,self.components)
        if not row:return
        d=ComponentRemoveDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                self.db.remove_component(
                    row.component_id,
                    d.reason.toPlainText().strip(),
                    self.user["username"],
                    related_ticket=d.ticket.text().strip(),
                    related_pm_task_id=d.pm.value() or None,
                    workstation=WORKSTATION,
                    expected_version=row.version,
                )
                self.load_details()
            except Exception as exc:QMessageBox.critical(self,"Component",str(exc))

    def load_meter_readings(self):
        meter=selected_row(self.meter_table,self.meters)
        equipment=selected_row(self.table,self.rows)
        self.meter_readings=self.db.list_meter_readings(equipment.equipment_id,meter.meter_code) if meter and equipment else []
        fill_table(self.meter_reading_table,self.meter_readings,["meter_code","value","reading_type","note","recorded_by","recorded_at"])

    def add_meter(self):
        equipment=selected_row(self.table,self.rows)
        if not equipment:return
        d=MeterDialog(equipment.equipment_id,parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_meter(d.data());self.load_details()
            except Exception as exc:QMessageBox.critical(self,"Meter",str(exc))

    def record_meter(self,reset=False):
        meter=selected_row(self.meter_table,self.meters)
        if not meter:return
        d=MeterReadingDialog(meter,reset,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                reading,tasks=self.db.record_meter_reading(
                    meter.equipment_id,meter.meter_code,d.value.value(),self.user["username"],
                    note=d.note.toPlainText().strip(),reset=reset,workstation=WORKSTATION,expected_version=meter.version,
                )
                self.load_details()
                if tasks:QMessageBox.information(self,"Usage PM",f"Created {len(tasks)} PM task(s) from usage threshold.")
            except Exception as exc:QMessageBox.critical(self,"Meter Reading",str(exc))


class MapNode(QGraphicsRectItem):
    def __init__(self, entity_type, key, version, x, y, label, brush):
        super().__init__(0,0,130,52); self.entity_type=entity_type; self.key=key; self.version=version; self.setPos(x,y); self.setBrush(brush); self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,True); self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,True); text=QGraphicsTextItem(label,self); text.setPos(5,5)


class LayoutPage(QWidget):
    def __init__(self, db, user):
        super().__init__(); self.db=db; self.user=user; self.nodes=[]; self.highlight_part=""; v=QVBoxLayout(self); h=QHBoxLayout(); self.building=QLineEdit(); self.building.setPlaceholderText("Building filter"); self.floor=QLineEdit(); self.floor.setPlaceholderText("Floor filter"); load=QPushButton("Load"); load.clicked.connect(self.refresh); save=QPushButton("Save Positions"); save.clicked.connect(self.save_positions); bg=QPushButton("Set Background"); bg.clicked.connect(self.set_background); self.part=QLineEdit(); self.part.setPlaceholderText("Highlight inventory part"); self.part.returnPressed.connect(lambda:self.highlight_inventory(self.part.text()))
        save.setEnabled(db.has_permission(user,"layout.edit") or db.has_permission(user,"equipment.edit")); bg.setEnabled(save.isEnabled())
        for w in [self.building,self.floor,load,save,bg,self.part]:h.addWidget(w)
        v.addLayout(h); self.scene=QGraphicsScene(); self.view=QGraphicsView(self.scene); self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag); v.addWidget(self.view); self.refresh()
    def scope_key(self): return f"{self.building.text().strip()}|{self.floor.text().strip()}"
    def refresh(self):
        self.scene.clear(); self.nodes=[]; building=self.building.text().strip(); floor=self.floor.text().strip(); bgpath=self.db.get_layout_background(self.scope_key())
        if bgpath and Path(bgpath).exists():
            pix=QPixmap(bgpath); item=QGraphicsPixmapItem(pix); item.setZValue(-20); self.scene.addItem(item)
        matching_locs=set()
        if self.highlight_part:
            matching_locs={i.location_code for i in self.db.list_inventory(self.highlight_part) if self.highlight_part.lower() in (i.part_number or "").lower()}
        for e in self.db.list_equipment():
            if building and e.building!=building:continue
            if floor and e.floor!=floor:continue
            brush=QBrush(QColor("#dceaf3")); n=MapNode("equipment",e.equipment_id,e.version,e.map_x,e.map_y,f"{e.equipment_id}\n{e.status}",brush); self.scene.addItem(n); self.nodes.append(n)
        for s in self.db.list_storage_locations():
            if building and s.building!=building:continue
            if floor and s.floor!=floor:continue
            brush=QBrush(QColor("#f3dfb6" if s.location_code not in matching_locs else "#f7a35c")); n=MapNode("storage",s.location_code,s.version,s.map_x,s.map_y,f"{s.location_code}\nStorage",brush); self.scene.addItem(n); self.nodes.append(n)
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-100,-100,300,300))
    def save_positions(self):
        try:
            for n in self.nodes:self.db.update_map_position(n.entity_type,n.key,n.pos().x(),n.pos().y(),n.version)
            self.db.audit(self.user["username"],"UPDATE","LAYOUT",self.scope_key(),workstation=WORKSTATION); self.refresh(); QMessageBox.information(self,"Layout","Positions saved.")
        except Exception as exc: QMessageBox.critical(self,"Layout",str(exc)); self.refresh()
    def set_background(self):
        path,_=QFileDialog.getOpenFileName(self,"Layout background","","Images (*.png *.jpg *.jpeg *.bmp)")
        if path:self.db.set_layout_background(self.scope_key(),path,self.user["username"]); self.refresh()
    def highlight_inventory(self, part: str): self.highlight_part=part.strip(); self.part.setText(self.highlight_part); self.refresh()


class PMDefinitionDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent); self.row=row; self.setWindowTitle("PM Definition"); f=QFormLayout(self); self.pm=QLineEdit(); self.name=QLineEdit(); self.eq=QLineEdit(); self.type=QComboBox(); self.type.addItems(["Interval","One Time","Event Triggered"]); self.freq=QDoubleSpinBox(); self.freq.setRange(0,1000000); self.unit=QComboBox(); self.unit.addItems(["days","weeks","months","years","hours","cycles"]); self.anchor=QComboBox(); self.anchor.addItems(["Original Due","Last Completion"]); self.early=QSpinBox(); self.early.setRange(0,3650); self.grace=QSpinBox(); self.grace.setRange(0,3650); self.hours=QDoubleSpinBox(); self.hours.setRange(0,10000); self.people=QSpinBox(); self.people.setRange(1,100); self.skill=QLineEdit(); self.parts=QLineEdit(); self.parts.setPlaceholderText("PART-A:2; FILTER-B:1"); self.sop=QLineEdit()
        for label,w in [("PM ID",self.pm),("Name",self.name),("Equipment ID",self.eq),("Schedule Type",self.type),("Frequency",self.freq),("Unit",self.unit),("Anchor",self.anchor),("Early Window Days",self.early),("Grace Days",self.grace),("Estimated Hours",self.hours),("Required People",self.people),("Required Skill",self.skill),("Required Parts",self.parts),("SOP Path",self.sop)]:f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b)
        if row:
            self.pm.setText(row.pm_id); self.pm.setReadOnly(True); self.name.setText(row.name); self.eq.setText(row.equipment_id); self.type.setCurrentText(row.schedule_type); self.freq.setValue(row.frequency_value or 0); self.unit.setCurrentText(row.frequency_unit); self.anchor.setCurrentText(row.anchor_mode); self.early.setValue(row.early_window_days); self.grace.setValue(row.grace_days); self.hours.setValue(row.estimated_hours); self.people.setValue(row.required_people); self.skill.setText(row.required_skill); self.parts.setText(row.required_parts); self.sop.setText(row.sop_path)
    def data(self):return {"pm_id":self.pm.text().strip(),"name":self.name.text().strip(),"equipment_id":self.eq.text().strip(),"schedule_type":self.type.currentText(),"frequency_value":self.freq.value(),"frequency_unit":self.unit.currentText(),"anchor_mode":self.anchor.currentText(),"early_window_days":self.early.value(),"grace_days":self.grace.value(),"estimated_hours":self.hours.value(),"required_people":self.people.value(),"required_skill":self.skill.text().strip(),"required_parts":self.parts.text().strip(),"sop_path":self.sop.text().strip(),"active":True}


class PMRequirementDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle("PM Execution Requirement");f=QFormLayout(self)
        self.req=QLineEdit();self.pm=QLineEdit();self.type=QComboBox();self.type.addItems(["CERTIFICATION","LOTO","SAFETY","TOOL","PART","DOCUMENT"])
        self.key=QLineEdit();self.desc=QTextEdit();self.qty=QDoubleSpinBox();self.qty.setRange(0.001,1e9);self.qty.setValue(1);self.mandatory=QCheckBox("Mandatory");self.mandatory.setChecked(True)
        for label,w in [("Requirement ID",self.req),("PM ID",self.pm),("Type",self.type),("Key / Code",self.key),("Description",self.desc),("Quantity",self.qty)]:f.addRow(label,w)
        f.addRow("",self.mandatory)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
    def data(self):
        return {"requirement_id":self.req.text().strip(),"pm_id":self.pm.text().strip(),"requirement_type":self.type.currentText(),"requirement_key":self.key.text().strip(),"description":self.desc.toPlainText().strip(),"quantity":self.qty.value(),"mandatory":self.mandatory.isChecked(),"active":True}


class PMExecutionDialog(QDialog):
    def __init__(self,db,user,task,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.task=task
        self.execrow=db.start_pm_execution(task.id,user["username"])
        self.specs=db.list_pm_execution_specs(self.execrow.id);self.requirements=db.list_pm_execution_requirements(self.execrow.id)
        self.results={r.step_no:r for r in db.list_pm_results(self.execrow.id)};self.acks={a.requirement_id:a for a in db.list_pm_requirement_acks(self.execrow.id)}
        self.setWindowTitle(f"Execute PM — {task.equipment_id} / {task.pm_id}");self.resize(1100,720);v=QVBoxLayout(self)
        tabs=QTabWidget()
        ws=QWidget();vs=QVBoxLayout(ws);self.table=make_table(["Step","Activity","Type","Target","Low","High","Value","Result","Evidence"]);self.table.doubleClicked.connect(self.enter_result);vs.addWidget(self.table)
        hs=QHBoxLayout();enter=QPushButton("Enter Selected Result");enter.clicked.connect(self.enter_result);paste=QPushButton("Paste Image Evidence");paste.clicked.connect(self.paste_evidence);hs.addWidget(enter);hs.addWidget(paste);hs.addStretch(1);vs.addLayout(hs);tabs.addTab(ws,"Measurements / Checklist")
        wr=QWidget();vr=QVBoxLayout(wr);self.req_table=make_table(["Requirement","Type","Key","Description","Qty","Mandatory","Status","By","Evidence"]);vr.addWidget(self.req_table)
        hr=QHBoxLayout();ack=QPushButton("Acknowledge Selected Requirement");ack.clicked.connect(self.ack_requirement);hr.addWidget(ack);hr.addStretch(1);vr.addLayout(hr);tabs.addTab(wr,"Execution Requirements")
        v.addWidget(tabs,1)
        h=QHBoxLayout();complete=QPushButton("Complete PM");complete.clicked.connect(self.complete);h.addStretch(1);h.addWidget(complete);v.addLayout(h);self.refresh()

    def refresh(self):
        self.results={r.step_no:r for r in self.db.list_pm_results(self.execrow.id)};self.acks={a.requirement_id:a for a in self.db.list_pm_requirement_acks(self.execrow.id)}
        self.table.setRowCount(len(self.specs))
        for r,s in enumerate(self.specs):
            res=self.results.get(s.step_no);vals=[s.step_no,s.activity,s.input_type,s.target,s.spec_low,s.spec_high,res.value_text if res else "",res.result if res else "",Path(res.evidence_path).name if res and res.evidence_path else ""]
            for col,val in enumerate(vals):self.table.setItem(r,col,ti(val))
        self.req_table.setRowCount(len(self.requirements))
        for r,req in enumerate(self.requirements):
            ack=self.acks.get(req.requirement_id)
            status="AUTO-VALIDATED" if req.requirement_type=="CERTIFICATION" else ("ACKNOWLEDGED" if ack else "PENDING")
            vals=[req.requirement_id,req.requirement_type,req.requirement_key,req.description,req.quantity,req.mandatory,status,ack.acknowledged_by if ack else "",Path(ack.evidence_path).name if ack and ack.evidence_path else ""]
            for col,val in enumerate(vals):self.req_table.setItem(r,col,ti(val))

    def selected_spec(self):
        r=self.table.currentRow();return self.specs[r] if 0<=r<len(self.specs) else None

    def selected_requirement(self):
        r=self.req_table.currentRow();return self.requirements[r] if 0<=r<len(self.requirements) else None

    def enter_result(self):
        spec=self.selected_spec()
        if not spec:return
        current=self.results.get(spec.step_no);prompt="Numeric value" if spec.input_type=="Numeric" else "Result / text"
        val,ok=QInputDialog.getText(self,"PM Result",prompt,text=current.value_text if current else "")
        if not ok:return
        num=None
        if spec.input_type=="Numeric":
            try:num=float(val)
            except Exception:QMessageBox.warning(self,"PM","Numeric value required.");return
        result=evaluate_measurement(spec,val,num)
        try:self.db.save_pm_result(self.execrow.id,spec.step_no,{"value_text":val,"value_numeric":num,"result":result,"entered_by":self.user["username"],"evidence_path":current.evidence_path if current else ""},current.version if current else None);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"PM",str(exc))

    def paste_evidence(self):
        spec=self.selected_spec()
        if not spec:return
        img=QApplication.clipboard().image()
        if img.isNull():QMessageBox.warning(self,"Clipboard","Clipboard does not contain an image.");return
        try:
            path=copy_clipboard_image(img,FILE_ROOT,"PM",f"{self.task.id}_step_{spec.step_no}");current=self.results.get(spec.step_no)
            self.db.add_attachment("PM_EXECUTION",str(self.execrow.id),path,original_name=Path(path).name,media_type="image/png",category="Screenshot",caption=f"{self.task.pm_id} step {spec.step_no}: {spec.activity}",equipment_id=self.task.equipment_id,created_by=self.user["username"])
            data={"value_text":current.value_text if current else "Evidence attached","value_numeric":current.value_numeric if current else None,"result":current.result if current else "RECORDED","entered_by":self.user["username"],"evidence_path":path}
            self.db.save_pm_result(self.execrow.id,spec.step_no,data,current.version if current else None);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Evidence",str(exc))

    def ack_requirement(self):
        req=self.selected_requirement()
        if not req:return
        if req.requirement_type=="CERTIFICATION":
            QMessageBox.information(self,"PM Requirement","Certification was validated automatically when the PM execution started.");return
        note,ok=QInputDialog.getText(self,"Acknowledge Requirement",req.description)
        if not ok:return
        evidence=""
        if QMessageBox.question(self,"Evidence","Attach evidence file?")==QMessageBox.StandardButton.Yes:
            source,_=QFileDialog.getOpenFileName(self,"Requirement Evidence")
            if source:
                stored=store_attachment_file(source,FILE_ROOT,"PM_EXECUTION",str(self.execrow.id));evidence=stored["stored_path"]
                self.db.add_attachment("PM_EXECUTION",str(self.execrow.id),evidence,original_name=stored["original_name"],media_type=stored["media_type"],category="Requirement Evidence",caption=req.description,equipment_id=self.task.equipment_id,created_by=self.user["username"])
        try:self.db.acknowledge_pm_requirement(self.execrow.id,req.requirement_id,self.user["username"],note,evidence);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"PM Requirement",str(exc))

    def complete(self):
        try:self.db.complete_pm_execution(self.execrow.id,self.user["username"]);self.accept()
        except Exception as exc:QMessageBox.critical(self,"Complete PM",str(exc))


class PMDeferralRequestDialog(QDialog):
    def __init__(self, task, parent=None):
        super().__init__(parent); self.task=task; self.setWindowTitle(f"Request PM Deferral — {task.equipment_id} / {task.pm_id}"); self.setMinimumWidth(620)
        f=QFormLayout(self)
        due=task.original_due_date.date() if task.original_due_date else datetime.now().date()
        self.new_due=QDateEdit(); self.new_due.setCalendarPopup(True); self.new_due.setDate(due); self.new_due.setMinimumDate(due)
        self.reason=QTextEdit(); self.risk=QTextEdit(); self.mitigation=QTextEdit()
        self.reason.setPlaceholderText("Why the PM cannot be completed by its controlled due date.")
        self.risk.setPlaceholderText("What equipment/process/quality/safety risk exists during the extension.")
        self.mitigation.setPlaceholderText("Temporary controls, inspections, restrictions, monitoring, or contingency actions.")
        f.addRow("Original Due",QLabel(str(task.original_due_date.date()) if task.original_due_date else ""))
        f.addRow("Requested Due",self.new_due); f.addRow("Reason",self.reason); f.addRow("Risk Assessment",self.risk); f.addRow("Mitigation",self.mitigation)
        note=QLabel("Submitting does not change the PM due date. A different authorized reviewer must approve it."); note.setWordWrap(True); note.setStyleSheet("color:#7a4b00"); f.addRow("",note)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b)

    def data(self):
        d=self.new_due.date()
        return {
            "requested_due_date":datetime(d.year(),d.month(),d.day()),
            "reason":self.reason.toPlainText().strip(),
            "risk_assessment":self.risk.toPlainText().strip(),
            "mitigation":self.mitigation.toPlainText().strip(),
        }


class PMDeferralReviewDialog(QDialog):
    def __init__(self,row,approve,parent=None):
        super().__init__(parent); self.row=row; self.approve=approve; self.setWindowTitle(("Approve" if approve else "Reject")+f" PM Deferral #{row.id}")
        f=QFormLayout(self)
        for label,value in [
            ("Equipment",row.equipment_id),("PM",row.pm_id),("Original Due",row.original_due_date),
            ("Requested Due",row.requested_due_date),("Requested By",row.requested_by),
            ("Reason",row.reason),("Risk",row.risk_assessment),("Mitigation",row.mitigation),
        ]:
            w=QLabel(str(value or "")); w.setWordWrap(True); f.addRow(label,w)
        self.note=QTextEdit(); self.note.setPlaceholderText("Reviewer decision basis / conditions")
        f.addRow("Review Note",self.note)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b)


class PMUsageTriggerDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle("Usage / Cycle PM Trigger");f=QFormLayout(self)
        self.trigger=QLineEdit();self.eq=QLineEdit();self.pm=QLineEdit();self.meter=QLineEdit();self.interval=QDoubleSpinBox();self.interval.setRange(0.001,1e15);self.interval.setDecimals(3)
        for label,w in [("Trigger ID",self.trigger),("Equipment",self.eq),("PM ID",self.pm),("Meter Code",self.meter),("Interval",self.interval)]:f.addRow(label,w)
        note=QLabel("The first threshold starts from the meter's current value. Each threshold creates at most one open PM task.");note.setWordWrap(True);note.setStyleSheet("color:#5a6670");f.addRow("",note)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
    def data(self):
        return {"trigger_id":self.trigger.text().strip(),"equipment_id":self.eq.text().strip(),"pm_id":self.pm.text().strip(),"meter_code":self.meter.text().strip(),"interval_value":self.interval.value(),"active":True}


class PMConditionTriggerDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle("Condition-Based PM Trigger");f=QFormLayout(self)
        self.trigger=QLineEdit();self.eq=QLineEdit();self.pm=QLineEdit();self.meter=QLineEdit();self.comp=QComboBox();self.comp.addItems([">",">=","<","<="])
        self.threshold=QDoubleSpinBox();self.threshold.setRange(-1e15,1e15);self.threshold.setDecimals(4)
        self.use_reset=QCheckBox("Use reset threshold");self.reset=QDoubleSpinBox();self.reset.setRange(-1e15,1e15);self.reset.setDecimals(4)
        for label,w in [("Trigger ID",self.trigger),("Equipment",self.eq),("PM ID",self.pm),("Meter Code",self.meter),("Comparator",self.comp),("Threshold",self.threshold),("",self.use_reset),("Reset Threshold",self.reset)]:f.addRow(label,w)
        note=QLabel("Trigger latches after activation. It rearms only after the reading returns past the reset threshold, preventing repeated task creation from noisy values.");note.setWordWrap(True);note.setStyleSheet("color:#5a6670");f.addRow("",note)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
    def data(self):
        return {"trigger_id":self.trigger.text().strip(),"equipment_id":self.eq.text().strip(),"pm_id":self.pm.text().strip(),"meter_code":self.meter.text().strip(),"comparator":self.comp.currentText(),"threshold":self.threshold.value(),"reset_threshold":self.reset.value() if self.use_reset.isChecked() else None,"active":True}


class PMPage(QWidget):
    def __init__(self,db,user):
        super().__init__(); self.db=db; self.user=user; self.defs=[]; self.tasks=[]; self.specrows=[]; self.requirements=[]; self.deferrals=[]; self.usage_triggers=[]; self.usage_occurrences=[]; self.condition_triggers=[]; self.condition_occurrences=[]; v=QVBoxLayout(self); self.tabs=QTabWidget(); v.addWidget(self.tabs)
        wd=QWidget(); vd=QVBoxLayout(wd); hd=QHBoxLayout(); add=QPushButton("Add Definition"); edit=QPushButton("Edit Definition"); gen=QPushButton("Generate Next PM"); ready=QPushButton("Parts Readiness"); add.clicked.connect(self.add_def); edit.clicked.connect(self.edit_def); gen.clicked.connect(self.generate_next); ready.clicked.connect(self.parts_ready); canedit=db.has_permission(user,"pm.edit"); add.setEnabled(canedit); edit.setEnabled(canedit); gen.setEnabled(canedit); hd.addWidget(add);hd.addWidget(edit);hd.addWidget(gen);hd.addWidget(ready);hd.addStretch(1);vd.addLayout(hd);self.def_table=make_table(["PM ID","Name","Equipment","Type","Frequency","Unit","Anchor","Early","Grace","Hours","Parts","Ver"]);vd.addWidget(self.def_table);self.tabs.addTab(wd,"Definitions")
        wb=QWidget(); vb=QVBoxLayout(wb); hb=QHBoxLayout(); imp=QPushButton("Import Excel/CSV"); paste=QPushButton("Paste from Excel"); execute=QPushButton("Execute Selected"); defer=QPushButton("Request Deferral"); forecast=QPushButton("Workload Forecast"); imp.clicked.connect(self.import_backlog); paste.clicked.connect(self.paste_backlog); execute.clicked.connect(self.execute); defer.clicked.connect(self.request_deferral); forecast.clicked.connect(self.forecast); imp.setEnabled(canedit); paste.setEnabled(canedit); execute.setEnabled(db.has_permission(user,"pm.execute")); defer.setEnabled(db.has_permission(user,"pm.defer")); [hb.addWidget(x) for x in [imp,paste,execute,defer,forecast]];hb.addStretch(1);vb.addLayout(hb);self.task_table=make_table(["Equipment","PM ID","PM Name","Original Due","Scheduled","Status","Assigned","Hours","Priority","Ver"]);vb.addWidget(self.task_table);self.tabs.addTab(wb,"Backlog / Schedule")
        ws=QWidget(); vs=QVBoxLayout(ws); hs=QHBoxLayout(); ispec=QPushButton("Import Steps / Specs"); pspec=QPushButton("Paste Steps / Specs"); ispec.clicked.connect(self.import_specs); pspec.clicked.connect(self.paste_specs); ispec.setEnabled(canedit); pspec.setEnabled(canedit); hs.addWidget(ispec);hs.addWidget(pspec);hs.addStretch(1);vs.addLayout(hs);self.spec_table=make_table(["PM ID","Step","Activity","Method","Type","Unit","Target","CL","CH","LSL","USL","Rev"]);vs.addWidget(self.spec_table);self.tabs.addTab(ws,"Checklist / Specs")
        wreq=QWidget();vreq=QVBoxLayout(wreq);hreq=QHBoxLayout();addreq=QPushButton("Add Requirement");revreq=QPushButton("Revise Selected");addreq.clicked.connect(self.add_requirement);revreq.clicked.connect(self.revise_requirement);addreq.setEnabled(canedit);revreq.setEnabled(canedit);hreq.addWidget(addreq);hreq.addWidget(revreq);hreq.addStretch(1);vreq.addLayout(hreq);self.requirement_table=make_table(["Requirement","PM ID","Type","Key","Description","Qty","Mandatory","Revision","Active"]);vreq.addWidget(self.requirement_table);self.tabs.addTab(wreq,"Execution Requirements")
        wf=QWidget(); vf=QVBoxLayout(wf); hf=QHBoxLayout(); approve=QPushButton("Approve Selected"); reject=QPushButton("Reject Selected"); approve.clicked.connect(lambda:self.review_deferral(True)); reject.clicked.connect(lambda:self.review_deferral(False)); canreview=db.has_permission(user,"pm.defer.approve"); approve.setEnabled(canreview); reject.setEnabled(canreview); hf.addWidget(approve);hf.addWidget(reject);hf.addStretch(1);vf.addLayout(hf);self.deferral_table=make_table(["ID","Equipment","PM","Original Due","Requested Due","Status","Requested By","Reviewed By","Review Note","Ver"]);vf.addWidget(self.deferral_table);self.tabs.addTab(wf,"PM Deferrals")
        wu=QWidget();vu=QVBoxLayout(wu);hu=QHBoxLayout();addu=QPushButton("Add Usage Trigger");addu.clicked.connect(self.add_usage_trigger);addu.setEnabled(canedit);hu.addWidget(addu);hu.addStretch(1);vu.addLayout(hu)
        self.usage_trigger_table=make_table(["Trigger","Equipment","PM","Meter","Interval","Last Trigger","Next Trigger","Active","Ver"]);self.usage_trigger_table.itemSelectionChanged.connect(self.load_usage_occurrences);vu.addWidget(self.usage_trigger_table,2)
        self.usage_occurrence_table=make_table(["Trigger","Task ID","Equipment","PM","Meter","Threshold","Reading","Created"]);vu.addWidget(self.usage_occurrence_table,1);self.tabs.addTab(wu,"Usage Triggers")
        wcnd=QWidget();vcnd=QVBoxLayout(wcnd);hcnd=QHBoxLayout();addcnd=QPushButton("Add Condition Trigger");addcnd.clicked.connect(self.add_condition_trigger);addcnd.setEnabled(canedit);hcnd.addWidget(addcnd);hcnd.addStretch(1);vcnd.addLayout(hcnd)
        self.condition_trigger_table=make_table(["Trigger","Equipment","PM","Meter","Comparator","Threshold","Reset","Latched","Active","Ver"]);self.condition_trigger_table.itemSelectionChanged.connect(self.load_condition_occurrences);vcnd.addWidget(self.condition_trigger_table,2)
        self.condition_occurrence_table=make_table(["Trigger","Task ID","Equipment","PM","Meter","Threshold","Reading","Event","Created"]);vcnd.addWidget(self.condition_occurrence_table,1);self.tabs.addTab(wcnd,"Condition Triggers")
        self.refresh()
    def refresh(self):
        self.defs=self.db.list_pm_definitions(); fill_table(self.def_table,self.defs,["pm_id","name","equipment_id","schedule_type","frequency_value","frequency_unit","anchor_mode","early_window_days","grace_days","estimated_hours","required_parts","version"])
        self.tasks=self.db.list_pm_tasks(); fill_table(self.task_table,self.tasks,["equipment_id","pm_id","pm_name","original_due_date","scheduled_date","status","assigned_to","estimated_hours","priority","version"])
        self.specrows=self.db.list_pm_specs(); fill_table(self.spec_table,self.specrows,["pm_id","step_no","activity","method","input_type","unit","target","control_low","control_high","spec_low","spec_high","revision"])
        self.requirements=self.db.list_pm_requirements(active_only=False);fill_table(self.requirement_table,self.requirements,["requirement_id","pm_id","requirement_type","requirement_key","description","quantity","mandatory","revision","active"])
        self.deferrals=self.db.list_pm_deferrals(); fill_table(self.deferral_table,self.deferrals,["id","equipment_id","pm_id","original_due_date","requested_due_date","status","requested_by","reviewed_by","review_note","version"])
        self.usage_triggers=self.db.list_pm_usage_triggers(); fill_table(self.usage_trigger_table,self.usage_triggers,["trigger_id","equipment_id","pm_id","meter_code","interval_value","last_trigger_value","next_trigger_value","active","version"])
        self.load_usage_occurrences()
        self.condition_triggers=self.db.list_pm_condition_triggers();fill_table(self.condition_trigger_table,self.condition_triggers,["trigger_id","equipment_id","pm_id","meter_code","comparator","threshold","reset_threshold","latched","active","version"])
        self.load_condition_occurrences()
    def select_task(self,task_id: int):
        self.refresh();self.tabs.setCurrentIndex(1)
        for i,row in enumerate(self.tasks):
            if row.id==task_id:
                self.task_table.selectRow(i)
                item=self.task_table.item(i,0)
                if item:self.task_table.scrollToItem(item)
                break

    def add_def(self):
        d=PMDefinitionDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_pm_definition(d.data());self.refresh()
            except Exception as exc:QMessageBox.critical(self,"PM Definition",str(exc))
    def edit_def(self):
        row=selected_row(self.def_table,self.defs)
        if not row:return
        d=PMDefinitionDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_pm_definition(d.data(),row.version);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"PM Definition",str(exc))
    def generate_next(self):
        d=selected_row(self.def_table,self.defs)
        if not d:return
        previous=[t for t in self.tasks if t.pm_id==d.pm_id and (not d.equipment_id or t.equipment_id==d.equipment_id)]
        previous.sort(key=lambda x:x.original_due_date or datetime.min)
        last=previous[-1] if previous else None
        if not last:
            text,ok=QInputDialog.getText(self,"Initial due date","No previous task exists. Enter initial due date YYYY-MM-DD:")
            if not ok:return
            try:due=datetime.strptime(text.strip(),"%Y-%m-%d")
            except Exception:QMessageBox.warning(self,"PM","Invalid date.");return
        else:
            due=calculate_next_due(d.schedule_type,d.frequency_value,d.frequency_unit,d.anchor_mode,last.original_due_date,last.last_completion_date or last.original_due_date)
        if not due:QMessageBox.warning(self,"PM","Could not calculate next due date.");return
        try:self.db.upsert_pm_task({"equipment_id":d.equipment_id or (last.equipment_id if last else ""),"pm_id":d.pm_id,"pm_name":d.name,"original_due_date":due,"scheduled_date":due,"status":"Scheduled","estimated_hours":d.estimated_hours,"priority":"Normal","sop_path":d.sop_path});self.refresh()
        except Exception as exc:QMessageBox.critical(self,"PM",str(exc))
    def parts_ready(self):
        d=selected_row(self.def_table,self.defs)
        if not d:return
        rows=pm_parts_readiness(d,self.db.inventory_available)
        if not rows:QMessageBox.information(self,"Parts Readiness","No required parts configured.");return
        text="\n".join(f"{'READY' if r['ready'] else 'SHORT'}  {r['part_number']}: need {r['required']:g}, available {r['available']:g}" for r in rows); QMessageBox.information(self,"Parts Readiness",text)
    def choose_sheet(self,path):
        sheets=workbook_sheets(path)
        if len(sheets)==1:return 0
        x,ok=QInputDialog.getItem(self,"Worksheet","Choose worksheet",sheets,0,False);return x if ok else None
    def _import_backlog_df(self,df):
        fields=[
            ("equipment_id","Equipment ID"),("pm_id","PM ID"),("pm_name","PM name"),
            ("original_due_date","Original due date"),("scheduled_date","Scheduled date"),("last_completion_date","Last completion"),
            ("status","Status"),("assigned_to","Assigned to"),("estimated_hours","Estimated hours"),("priority","Priority"),
            ("deferral_reason","Deferral reason"),("sop_path","SOP path"),("report_path","Report path"),
        ]
        mapping=run_mapping_studio(
            self,self.db,self.user["username"],"excel_mapping.pm_backlog",df,fields,
            auto_mapping(list(df.columns)),{"equipment_id"},"PM Backlog Import Studio",
        )
        if mapping is None:return
        rows,errors=dataframe_to_pm_backlog(df,mapping)
        if not rows:QMessageBox.warning(self,"Import","No valid rows.\n"+"\n".join(errors[:20]));return
        sample="\n".join(errors[:10])
        prompt=f"Validated {len(rows)} row(s). {len(errors)} row warning/error(s).\n\n{sample}\n\nCommit import?"
        if QMessageBox.question(self,"Import preview",prompt)!=QMessageBox.StandardButton.Yes:return
        imported=0;failures=[]
        for row in rows:
            try:self.db.upsert_pm_task(row);imported+=1
            except Exception as exc:failures.append(f"{row.get('equipment_id')} / {row.get('pm_id')}: {exc}")
        self.refresh()
        detail=f"Imported {imported} row(s). Source validation warnings: {len(errors)}. Commit failures: {len(failures)}."
        if failures:detail+="\n"+"\n".join(failures[:12])
        QMessageBox.information(self,"Import complete",detail)
    def import_backlog(self):
        path,_=QFileDialog.getOpenFileName(self,"Import PM Backlog","","Excel/CSV (*.xlsx *.xlsm *.csv)")
        if not path:return
        try:s=self.choose_sheet(path); self._import_backlog_df(read_table(path,s)) if s is not None else None
        except Exception as exc:QMessageBox.critical(self,"Import",str(exc))
    def paste_backlog(self):
        try:self._import_backlog_df(read_clipboard_table(QApplication.clipboard().text()))
        except Exception as exc:QMessageBox.critical(self,"Paste",str(exc))
    def _import_specs_df(self,df):
        fields=[
            ("pm_id","PM ID"),("step_no","Step number"),("activity","Activity / check item"),("method","Method"),
            ("spec","Specification / acceptance"),("unit","Unit"),("target","Target"),("warning_low","Warning low"),
            ("warning_high","Warning high"),("control_low","Control low"),("control_high","Control high"),
            ("spec_low","Spec low"),("spec_high","Spec high"),("reaction_plan","Reaction plan"),
            ("sop_path","SOP path"),("sop_page","SOP page"),("sop_section","SOP section"),
        ]
        mapping=run_mapping_studio(
            self,self.db,self.user["username"],"excel_mapping.pm_specs",df,fields,
            auto_mapping(list(df.columns)),{"activity"},"PM Checklist / Specification Import Studio",
        )
        if mapping is None:return
        default=""
        if "pm_id" not in mapping:
            default,ok=QInputDialog.getText(self,"PM ID","No PM ID column is mapped. Apply all imported steps to PM ID:")
            if not ok or not default.strip():return
        rows,warns=dataframe_to_pm_specs(df,mapping,default.strip())
        if not rows:QMessageBox.warning(self,"Import","No valid steps.\n"+"\n".join(warns[:20]));return
        revise=QMessageBox.question(self,"Controlled revision",f"Validated {len(rows)} step(s), warnings: {len(warns)}.\nCreate controlled revisions for existing steps?")==QMessageBox.StandardButton.Yes
        imported=0;failures=[]
        for row in rows:
            try:self.db.upsert_pm_spec(row,revise);imported+=1
            except Exception as exc:failures.append(f"{row.get('pm_id')} step {row.get('step_no')}: {exc}")
        self.refresh()
        detail=f"Imported {imported} step(s). Validation warnings: {len(warns)}. Commit failures: {len(failures)}."
        if failures:detail+="\n"+"\n".join(failures[:12])
        QMessageBox.information(self,"Import complete",detail)
    def import_specs(self):
        path,_=QFileDialog.getOpenFileName(self,"Import PM Specs","","Excel/CSV (*.xlsx *.xlsm *.csv)")
        if not path:return
        try:s=self.choose_sheet(path); self._import_specs_df(read_table(path,s)) if s is not None else None
        except Exception as exc:QMessageBox.critical(self,"Import",str(exc))
    def paste_specs(self):
        try:self._import_specs_df(read_clipboard_table(QApplication.clipboard().text()))
        except Exception as exc:QMessageBox.critical(self,"Paste",str(exc))
    def add_requirement(self):
        d=PMRequirementDialog(self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.upsert_pm_requirement(d.data());self.refresh()
            except Exception as exc:QMessageBox.critical(self,"PM Requirement",str(exc))

    def revise_requirement(self):
        row=selected_row(self.requirement_table,self.requirements)
        if not row:return
        d=PMRequirementDialog(self);d.req.setText(row.requirement_id);d.req.setReadOnly(True);d.pm.setText(row.pm_id);d.type.setCurrentText(row.requirement_type);d.key.setText(row.requirement_key);d.desc.setPlainText(row.description);d.qty.setValue(row.quantity);d.mandatory.setChecked(row.mandatory)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.upsert_pm_requirement(d.data(),create_revision=True);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"PM Requirement",str(exc))

    def add_usage_trigger(self):
        d=PMUsageTriggerDialog(self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_pm_usage_trigger(d.data());self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Usage Trigger",str(exc))

    def load_usage_occurrences(self):
        row=selected_row(self.usage_trigger_table,self.usage_triggers)
        self.usage_occurrences=self.db.list_pm_usage_occurrences(row.trigger_id) if row else []
        fill_table(self.usage_occurrence_table,self.usage_occurrences,["trigger_id","task_id","equipment_id","pm_id","meter_code","trigger_value","reading_value","created_at"])

    def add_condition_trigger(self):
        d=PMConditionTriggerDialog(self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_pm_condition_trigger(d.data());self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Condition Trigger",str(exc))

    def load_condition_occurrences(self):
        row=selected_row(self.condition_trigger_table,self.condition_triggers)
        self.condition_occurrences=self.db.list_pm_condition_occurrences(row.trigger_id) if row else []
        fill_table(self.condition_occurrence_table,self.condition_occurrences,["trigger_id","task_id","equipment_id","pm_id","meter_code","threshold","reading_value","event_type","created_at"])

    def request_deferral(self):
        row=selected_row(self.task_table,self.tasks)
        if not row:return
        d=PMDeferralRequestDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                self.db.request_pm_deferral(
                    row.id,
                    user=self.user["username"],
                    workstation=WORKSTATION,
                    expected_task_version=row.version,
                    **d.data(),
                )
                self.refresh()
            except Exception as exc:QMessageBox.critical(self,"PM Deferral",str(exc))

    def review_deferral(self,approve):
        row=selected_row(self.deferral_table,self.deferrals)
        if not row:return
        if row.status!="Pending":
            QMessageBox.information(self,"PM Deferral","Selected request is already reviewed.");return
        d=PMDeferralReviewDialog(row,approve,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                self.db.review_pm_deferral(
                    row.id,
                    approve,
                    self.user["username"],
                    d.note.toPlainText().strip(),
                    workstation=WORKSTATION,
                    expected_version=row.version,
                )
                self.refresh()
            except Exception as exc:QMessageBox.critical(self,"PM Deferral",str(exc))

    def execute(self):
        row=selected_row(self.task_table,self.tasks)
        if not row:return
        d=PMExecutionDialog(self.db,self.user,row,self)
        if d.exec()==QDialog.DialogCode.Accepted:self.refresh()
    def forecast(self):
        data=workload_by_day([t for t in self.tasks if t.status not in {"Completed","Cancelled"}]); text="\n".join(f"{d}: {h:.1f} hr" for d,h in sorted(data.items())[:60]) or "No scheduled workload"; QMessageBox.information(self,"PM Workload Forecast",text)


class TicketDialog(QDialog):
    """Issue content editor. Lifecycle state is controlled separately."""
    def __init__(self,row=None,parent=None,db=None,initial=None):
        super().__init__(parent);self.row=row;self.db=db;self.setWindowTitle("Issue Ticket");f=QFormLayout(self)
        self.no=QLineEdit();self.eq=QLineEdit();self.title=QLineEdit();self.desc=QTextEdit()
        self.sev=QComboBox();self.sev.addItems(config_option_values(db,"TICKET_SEVERITY",["S1","S2","S3","S4"]))
        self.prio=QComboBox();self.prio.addItems(config_option_values(db,"TICKET_PRIORITY",["P1","P2","P3","P4"]))
        self.owner=QLineEdit();self.root=QTextEdit();self.action=QTextEdit();self.verify=QTextEdit()
        for label,w in [("Ticket No",self.no),("Equipment ID",self.eq),("Title",self.title),("Description",self.desc),("Severity",self.sev),("Priority",self.prio),("Owner",self.owner),("Root Cause",self.root),("Corrective Action",self.action),("Verification",self.verify)]:f.addRow(label,w)
        if row:
            state=QLabel(row.status);state.setStyleSheet("font-weight:700");f.addRow("Lifecycle State",state)
            note=QLabel("Ticket state is controlled by the lifecycle workflow, not this edit form.");note.setWordWrap(True);note.setStyleSheet("color:#7a4b00");f.addRow("",note)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:
            self.no.setText(row.ticket_no);self.no.setReadOnly(True);self.eq.setText(row.equipment_id);self.eq.setReadOnly(True)
            self.title.setText(row.title);self.desc.setPlainText(row.description);self.sev.setCurrentText(row.severity);self.prio.setCurrentText(row.priority);self.owner.setText(row.owner)
            self.root.setPlainText(row.root_cause);self.action.setPlainText(row.corrective_action);self.verify.setPlainText(row.verification)
        elif initial:
            self.no.setText(str(initial.get("ticket_no","") or ""));self.eq.setText(str(initial.get("equipment_id","") or ""));self.title.setText(str(initial.get("title","") or ""));self.desc.setPlainText(str(initial.get("description","") or ""))
            self.sev.setCurrentText(str(initial.get("severity","S3") or "S3"));self.prio.setCurrentText(str(initial.get("priority","P3") or "P3"));self.owner.setText(str(initial.get("owner","") or ""))
            self.root.setPlainText(str(initial.get("root_cause","") or ""));self.action.setPlainText(str(initial.get("corrective_action","") or ""));self.verify.setPlainText(str(initial.get("verification","") or ""))

    def data(self,user):
        return {
            "ticket_no":self.no.text().strip(),
            "equipment_id":self.eq.text().strip(),
            "title":self.title.text().strip(),
            "description":self.desc.toPlainText().strip(),
            "severity":self.sev.currentText(),
            "priority":self.prio.currentText(),
            "owner":self.owner.text().strip(),
            "root_cause":self.root.toPlainText().strip(),
            "corrective_action":self.action.toPlainText().strip(),
            "verification":self.verify.toPlainText().strip(),
            "created_by":getattr(self.row,"created_by","") or user,
        }


class TicketStateDialog(QDialog):
    def __init__(self,row,parent=None,db=None):
        super().__init__(parent);self.row=row;self.db=db;self.setWindowTitle(f"Change Ticket State — {row.ticket_no}");self.setMinimumWidth(560)
        f=QFormLayout(self)
        current=QLabel(row.status);current.setStyleSheet("font-weight:700")
        self.target=QComboBox();self.target.addItems(allowed_ticket_targets(row.status))
        self.reason=QComboBox();populate_reason_combo(self.reason,db,"TICKET_REASON_LABEL",TICKET_REASON_CODES)
        self.help=QLabel();self.help.setWordWrap(True);self.help.setStyleSheet("color:#5a6670")
        self.owner=QLineEdit(row.owner or "");self.note=QTextEdit();self.note.setPlaceholderText("Lifecycle note, verification outcome, cancellation basis, or reopen reason.")
        f.addRow("Current State",current);f.addRow("Target State",self.target);f.addRow("Reason Code",self.reason);f.addRow("",self.help);f.addRow("Accountable Owner",self.owner);f.addRow("Lifecycle Note",self.note)
        warning=QLabel("Resolution requires documented root cause and corrective action. Closure additionally requires verification.");warning.setWordWrap(True);warning.setStyleSheet("color:#7a4b00");f.addRow("",warning)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        self.reason.currentIndexChanged.connect(lambda *_:self.help.setText(reason_label(self.reason)))
        self.target.currentTextChanged.connect(self._suggest_reason)
        self._suggest_reason(self.target.currentText())

    def _suggest_reason(self,target):
        preferred={
            "Assigned":"ASSIGN","Waiting Parts":"WAIT_PARTS","Waiting Vendor":"WAIT_VENDOR","Waiting Production":"WAIT_PRODUCTION",
            "Monitoring":"MONITOR","Resolved":"RESOLVE","Verification":"VERIFY_START","Closed":"VERIFY_PASS","Cancelled":"CANCEL",
        }.get(target)
        if target=="Investigation":
            if self.row.status=="Verification":preferred="VERIFY_FAIL"
            elif self.row.status in {"Resolved","Closed"}:preferred="REOPEN"
            else:preferred="START_INVESTIGATION"
        if preferred:
            idx=self.reason.findData(preferred)
            if idx>=0:self.reason.setCurrentIndex(idx)
        self.help.setText(reason_label(self.reason))

    def data(self):
        return {
            "target_state":self.target.currentText(),
            "reason_code":str(self.reason.currentData() or self.reason.currentText()).split(" — ",1)[0],
            "note":self.note.toPlainText().strip(),
            "owner":self.owner.text().strip(),
        }


class TicketOperationalControlDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Incident Operational Control");self.setMinimumWidth(650)
        f=QFormLayout(self)
        self.containment=QTextEdit();self.impact=QTextEdit();self.lots=QTextEdit();self.risk=QTextEdit()
        self.deadlines={}
        for key,label in [("response_due_at","Response Due"),("containment_due_at","Containment Due"),("resolution_due_at","Resolution Due")]:
            box=QCheckBox("Set");dt=QDateTimeEdit();dt.setCalendarPopup(True);dt.setDateTime(datetime.now());dt.setDisplayFormat("yyyy-MM-dd HH:mm")
            rowbox=QHBoxLayout();rowbox.addWidget(box);rowbox.addWidget(dt,1);f.addRow(label,rowbox);self.deadlines[key]=(box,dt)
        f.insertRow(0,"Containment",self.containment);f.insertRow(1,"Production Impact",self.impact);f.insertRow(2,"Affected Lots / Material",self.lots);f.insertRow(3,"Safety / Quality Risk",self.risk)
        if row:
            self.containment.setPlainText(row.containment);self.impact.setPlainText(row.production_impact);self.lots.setPlainText(row.affected_lots);self.risk.setPlainText(row.safety_quality_risk)
            for key,(box,dt) in self.deadlines.items():
                value=getattr(row,key,None)
                if value:
                    box.setChecked(True);dt.setDateTime(value)
        note=QLabel("Overdue response, containment, and resolution deadlines automatically raise escalation levels and appear on the Operations Command Center.")
        note.setWordWrap(True);note.setStyleSheet("color:#5a6670");f.addRow("",note)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)

    def data(self):
        payload={
            "containment":self.containment.toPlainText().strip(),
            "production_impact":self.impact.toPlainText().strip(),
            "affected_lots":self.lots.toPlainText().strip(),
            "safety_quality_risk":self.risk.toPlainText().strip(),
        }
        for key,(box,dt) in self.deadlines.items():
            payload[key]=dt.dateTime().toPython() if box.isChecked() else None
        return payload


class InvestigationDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle("Investigation Step");f=QFormLayout(self);self.obs=QTextEdit();self.check=QTextEdit();self.result=QTextEdit();self.concl=QTextEdit();self.action=QTextEdit();self.evidence=QLineEdit();browse=QPushButton("Browse");browse.clicked.connect(self.browse);hb=QHBoxLayout();hb.addWidget(self.evidence);hb.addWidget(browse)
        for label,w in [("Observation",self.obs),("Check Performed",self.check),("Result",self.result),("Conclusion",self.concl),("Action",self.action)]:f.addRow(label,w)
        f.addRow("Evidence",hb);b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)

    def browse(self):
        path,_=QFileDialog.getOpenFileName(self,"Evidence");self.evidence.setText(path)

    def data(self,user):
        return {"observation":self.obs.toPlainText().strip(),"check_performed":self.check.toPlainText().strip(),"result":self.result.toPlainText().strip(),"conclusion":self.concl.toPlainText().strip(),"action":self.action.toPlainText().strip(),"evidence_path":self.evidence.text().strip(),"entered_by":user}


class TicketPage(QWidget):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.rows=[];self.inv=[];self.lifecycle=[];self.control=None;self.escalations=[]
        v=QVBoxLayout(self);h=QHBoxLayout()
        add=QPushButton("New Ticket");template=QPushButton("New from Template");edit=QPushButton("Edit Details");imp=QPushButton("Import Excel/CSV");paste=QPushButton("Paste from Excel");state=QPushButton("Change Status");invest=QPushButton("Add Investigation Step");control=QPushButton("Operational Control")
        add.clicked.connect(self.add);template.clicked.connect(self.add_from_template);edit.clicked.connect(self.edit);imp.clicked.connect(self.import_tickets);paste.clicked.connect(self.paste_tickets);state.clicked.connect(self.change_state);invest.clicked.connect(self.add_investigation);control.clicked.connect(self.edit_operational_control)
        allowed=db.has_permission(user,"ticket.edit");add.setEnabled(allowed);template.setEnabled(allowed);edit.setEnabled(allowed);imp.setEnabled(allowed);paste.setEnabled(allowed);state.setEnabled(allowed);invest.setEnabled(allowed);control.setEnabled(allowed)
        h.addWidget(add);h.addWidget(template);h.addWidget(edit);h.addWidget(imp);h.addWidget(paste);h.addWidget(state);h.addWidget(invest);h.addWidget(control);h.addStretch(1);v.addLayout(h)
        self.table=make_table(["Ticket","Equipment","Title","Severity","Priority","Status","Owner","Updated","Ver"]);self.table.itemSelectionChanged.connect(self.load_details);v.addWidget(self.table,2)

        tabs=QTabWidget();self.tabs=tabs
        wi=QWidget();vi=QVBoxLayout(wi);self.invtable=make_table(["#","Observation","Check","Result","Conclusion","Action","By","Time"]);vi.addWidget(self.invtable);tabs.addTab(wi,"Troubleshooting History")
        wl=QWidget();vl=QVBoxLayout(wl);self.lifetable=make_table(["From","To","Reason","Note","Owner","Changed By","Time"]);vl.addWidget(self.lifetable);tabs.addTab(wl,"Lifecycle History")
        wo=QWidget();vo=QVBoxLayout(wo);self.control_table=make_table(["Containment","Production Impact","Affected Lots","Safety/Quality Risk","Response Due","Containment Due","Resolution Due","Esc Level","Esc Reason"]);vo.addWidget(self.control_table,1)
        self.escalation_table=make_table(["From Level","To Level","Reason","User","Time"]);vo.addWidget(self.escalation_table,1);tabs.addTab(wo,"Operational Control / SLA")
        self.attachments=AttachmentPanel(db,user);tabs.addTab(self.attachments,"Evidence / Attachments")
        v.addWidget(tabs,1);self.refresh()

    def refresh(self):
        current=selected_row(self.table,self.rows);current_no=current.ticket_no if current else ""
        self.rows=self.db.list_tickets();fill_table(self.table,self.rows,["ticket_no","equipment_id","title","severity","priority","status","owner","updated_at","version"])
        if current_no:
            for i,row in enumerate(self.rows):
                if row.ticket_no==current_no:self.table.selectRow(i);break
        self.load_details()

    def select_ticket(self,ticket_no: str):
        self.refresh()
        for i,row in enumerate(self.rows):
            if row.ticket_no==ticket_no:
                self.table.selectRow(i)
                item=self.table.item(i,0)
                if item:self.table.scrollToItem(item)
                break

    def _ticket_import_df(self,df):
        fields=[
            ("ticket_no","Ticket number"),("equipment_id","Equipment ID"),("title","Title"),("description","Description"),
            ("severity","Severity"),("priority","Priority"),("owner","Owner"),("root_cause","Root cause"),
            ("corrective_action","Corrective action"),("verification","Verification"),
        ]
        mapping=run_mapping_studio(
            self,self.db,self.user["username"],"excel_mapping.tickets",df,fields,
            auto_mapping(list(df.columns)),{"ticket_no","equipment_id"},"Incident / Ticket Import Studio",
        )
        if mapping is None:return
        rows,errors=dataframe_to_tickets(df,mapping)
        if not rows:
            QMessageBox.warning(self,"Incident import","No valid rows.\n"+"\n".join(errors[:20]));return
        actions=reconcile_tickets(self.db,rows,mapping)
        if not any(x["status"] in {"CREATE","UPDATE"} for x in actions):
            QMessageBox.information(self,"Incident import","No changes detected.");return
        if not confirm_reconciliation(self,"Incident / Ticket Reconciliation",actions):return
        applied=0;failures=[]
        for action in actions:
            if action["status"]=="UNCHANGED":continue
            data=dict(action["data"]);current=action["current"];data["created_by"]=data.get("created_by") or self.user["username"]
            try:
                self.db.save_ticket(data,current.version if current else None,workstation=WORKSTATION);applied+=1
            except Exception as exc:failures.append(f"{data.get('ticket_no')}: {exc}")
        self.refresh()
        detail=f"Applied {applied} incident create/update row(s). Lifecycle status was not imported. Source warnings: {len(errors)}. Failures: {len(failures)}."
        if failures:detail+="\n"+"\n".join(failures[:12])
        QMessageBox.information(self,"Incident import",detail)

    def import_tickets(self):
        path,_=QFileDialog.getOpenFileName(self,"Import Incidents / Tickets","","Excel/CSV (*.xlsx *.xlsm *.csv)")
        if not path:return
        try:
            sheets=workbook_sheets(path);sheet=sheets[0]
            if len(sheets)>1:
                sheet,ok=QInputDialog.getItem(self,"Import Incidents","Sheet",sheets,0,False)
                if not ok:return
            self._ticket_import_df(read_table(path,sheet))
        except Exception as exc:QMessageBox.critical(self,"Incident import",str(exc))

    def paste_tickets(self):
        try:self._ticket_import_df(read_clipboard_table(QApplication.clipboard().text()))
        except Exception as exc:QMessageBox.critical(self,"Incident paste",str(exc))

    def add_from_template(self):
        templates=self.db.list_entity_templates("TICKET")
        if not templates:
            QMessageBox.information(self,"Incident Template","No active incident/ticket templates are configured.");return
        labels=[f"{x.name} ({x.template_id})" for x in templates]
        choice,ok=QInputDialog.getItem(self,"Incident Template","Template",labels,0,False)
        if not ok:return
        template=templates[labels.index(choice)]
        try:initial=self.db.apply_entity_template(template.template_id)
        except Exception as exc:QMessageBox.critical(self,"Incident Template",str(exc));return
        if not initial.get("ticket_no"):initial["ticket_no"]="INC-"+datetime.now().strftime("%Y%m%d-%H%M%S")
        d=TicketDialog(parent=self,db=self.db,initial=initial)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                row=self.db.save_ticket(d.data(self.user["username"]),workstation=WORKSTATION)
                self.db.audit(self.user["username"],"CREATE_FROM_TEMPLATE","TICKET",row.ticket_no,template.template_id,WORKSTATION);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Ticket",str(exc))

    def add(self):
        d=TicketDialog(parent=self,db=self.db)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                row=self.db.save_ticket(d.data(self.user["username"]),workstation=WORKSTATION)
                self.db.audit(self.user["username"],"CREATE","TICKET",row.ticket_no,workstation=WORKSTATION)
                self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Ticket",str(exc))

    def edit(self):
        row=selected_row(self.table,self.rows)
        if not row:return
        d=TicketDialog(row,self,db=self.db)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                self.db.save_ticket(d.data(self.user["username"]),row.version,workstation=WORKSTATION)
                self.db.audit(self.user["username"],"UPDATE_DETAILS","TICKET",row.ticket_no,workstation=WORKSTATION)
                self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Ticket",str(exc))

    def change_state(self):
        row=selected_row(self.table,self.rows)
        if not row:return
        targets=allowed_ticket_targets(row.status)
        if not targets:
            QMessageBox.information(self,"Ticket Lifecycle",f"{row.status} is a terminal state. No further lifecycle transition is available.")
            return
        d=TicketStateDialog(row,self,db=self.db)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                self.db.transition_ticket_state(
                    row.ticket_no,
                    user=self.user["username"],
                    workstation=WORKSTATION,
                    expected_version=row.version,
                    **d.data(),
                )
                self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Ticket Lifecycle",str(exc))

    def load_details(self):
        row=selected_row(self.table,self.rows)
        self.inv=self.db.list_ticket_investigations(row.ticket_no) if row else []
        self.lifecycle=self.db.list_ticket_state_events(row.ticket_no) if row else []
        self.control=self.db.ticket_operational_control(row.ticket_no) if row else None
        self.escalations=self.db.list_ticket_escalations(row.ticket_no) if row else []
        fill_table(self.invtable,self.inv,["sequence","observation","check_performed","result","conclusion","action","entered_by","entered_at"])
        fill_table(self.lifetable,self.lifecycle,["from_state","to_state","reason_code","note","owner","changed_by","changed_at"])
        controls=[self.control] if self.control else []
        fill_table(self.control_table,controls,["containment","production_impact","affected_lots","safety_quality_risk","response_due_at","containment_due_at","resolution_due_at","escalation_level","escalation_reason"])
        fill_table(self.escalation_table,self.escalations,["from_level","to_level","reason","user","occurred_at"])
        self.attachments.set_entity("TICKET",row.ticket_no,row.equipment_id) if row else self.attachments.set_entity("","")

    def edit_operational_control(self):
        row=selected_row(self.table,self.rows)
        if not row:return
        current=self.db.ticket_operational_control(row.ticket_no)
        d=TicketOperationalControlDialog(current,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                self.db.save_ticket_operational_control(
                    row.ticket_no,d.data(),self.user["username"],WORKSTATION,
                    current.version if current else None,
                )
                self.db.evaluate_ticket_escalations()
                self.load_details()
            except Exception as exc:QMessageBox.critical(self,"Operational Control",str(exc))

    def add_investigation(self):
        row=selected_row(self.table,self.rows)
        if not row:return
        d=InvestigationDialog(self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                payload=d.data(self.user["username"])
                source=payload.get("evidence_path","")
                if source:
                    stored=store_attachment_file(source,FILE_ROOT,"TICKET",row.ticket_no);payload["evidence_path"]=stored["stored_path"]
                    self.db.add_attachment("TICKET",row.ticket_no,stored["stored_path"],original_name=stored["original_name"],media_type=stored["media_type"],category="Investigation Evidence",caption=payload.get("observation",""),equipment_id=row.equipment_id,created_by=self.user["username"])
                self.db.add_ticket_investigation(row.ticket_no,payload)
                self.db.audit(self.user["username"],"ADD_INVESTIGATION","TICKET",row.ticket_no,workstation=WORKSTATION)
                self.load_details()
            except Exception as exc:QMessageBox.critical(self,"Investigation",str(exc))


class QualificationProtocolDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Qualification Protocol")
        f=QFormLayout(self);self.protocol=QLineEdit();self.name=QLineEdit();self.eq=QLineEdit();self.eqtype=QLineEdit();self.checks=QTextEdit()
        self.checks.setPlaceholderText("One required qualification check per line")
        for label,w in [("Protocol ID",self.protocol),("Name",self.name),("Equipment ID (optional)",self.eq),("Equipment Type (optional)",self.eqtype),("Checks",self.checks)]:f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:
            self.protocol.setText(row.protocol_id);self.protocol.setReadOnly(True);self.name.setText(row.name);self.eq.setText(row.equipment_id);self.eqtype.setText(row.equipment_type)
            try:
                checks=json.loads(row.checks_json or "[]")
                self.checks.setPlainText("\n".join(str(x.get("label","")) for x in checks))
            except Exception:pass
    def data(self):
        checks=[x.strip() for x in self.checks.toPlainText().splitlines() if x.strip()]
        return {"protocol_id":self.protocol.text().strip(),"name":self.name.text().strip(),"equipment_id":self.eq.text().strip(),"equipment_type":self.eqtype.text().strip(),"checks":checks}


class QualificationPage(QWidget):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.protocols=[];self.runs=[];self.check_rows=[];self.check_results={}
        v=QVBoxLayout(self);tabs=QTabWidget();self.tabs=tabs;v.addWidget(tabs)

        wp=QWidget();vp=QVBoxLayout(wp);hp=QHBoxLayout();newp=QPushButton("New Protocol");revp=QPushButton("New Revision");exportp=QPushButton("Export Round-trip Excel");importp=QPushButton("Import Excel/CSV");pastep=QPushButton("Paste from Excel")
        newp.clicked.connect(self.new_protocol);revp.clicked.connect(self.revise_protocol);exportp.clicked.connect(self.export_protocols_roundtrip);importp.clicked.connect(self.import_protocols);pastep.clicked.connect(self.paste_protocols)
        canedit=db.has_permission(user,"qualification.edit");newp.setEnabled(canedit);revp.setEnabled(canedit);importp.setEnabled(canedit);pastep.setEnabled(canedit)
        for x in [newp,revp,exportp,importp,pastep]:hp.addWidget(x)
        hp.addStretch(1);vp.addLayout(hp)
        self.ptable=make_table(["Protocol","Revision","Name","Equipment","Type","Active","Created By","Created","Ver"]);vp.addWidget(self.ptable);tabs.addTab(wp,"Protocols")

        wr=QWidget();vr=QVBoxLayout(wr);hr=QHBoxLayout()
        start=QPushButton("Start Run");result=QPushButton("Enter Result");submit=QPushButton("Submit");verify=QPushButton("Verify");approve=QPushButton("Approve");reject=QPushButton("Reject");ppt=QPushButton("Qualification PPTX");xlsx=QPushButton("Qualification Excel");pdf=QPushButton("Qualification PDF")
        start.clicked.connect(self.start_run);result.clicked.connect(self.enter_result);submit.clicked.connect(self.submit_run);verify.clicked.connect(self.verify_run);approve.clicked.connect(self.approve_run);reject.clicked.connect(self.reject_run);ppt.clicked.connect(self.export_pptx);xlsx.clicked.connect(self.export_xlsx);pdf.clicked.connect(self.export_pdf)
        start.setEnabled(db.has_permission(user,"qualification.execute"));result.setEnabled(db.has_permission(user,"qualification.execute"));submit.setEnabled(db.has_permission(user,"qualification.execute"))
        verify.setEnabled(db.has_permission(user,"qualification.verify"));approve.setEnabled(db.has_permission(user,"qualification.approve"));reject.setEnabled(db.has_permission(user,"qualification.verify") or db.has_permission(user,"qualification.approve"))
        for x in [start,result,submit,verify,approve,reject,ppt,xlsx,pdf]:hr.addWidget(x)
        hr.addStretch(1);vr.addLayout(hr)
        self.rtable=make_table(["Run","Equipment","Protocol","Rev","Status","Started By","Submitted By","Verified By","Approved By","Expires","Ver"]);self.rtable.itemSelectionChanged.connect(self.load_checks);vr.addWidget(self.rtable,2)
        self.ctable=make_table(["Check ID","Check","Acceptance","Result","Comment","Evidence","Entered By"]);vr.addWidget(self.ctable,1)
        tabs.addTab(wr,"Qualification Runs")
        self.attachments=AttachmentPanel(db,user);tabs.addTab(self.attachments,"Evidence / Attachments")
        self.refresh()

    def refresh(self):
        self.protocols=self.db.list_qualification_protocols(active_only=False)
        fill_table(self.ptable,self.protocols,["protocol_id","revision","name","equipment_id","equipment_type","active","created_by","created_at","version"])
        current=selected_row(self.rtable,self.runs);run_no=current.run_no if current else ""
        self.runs=self.db.list_qualification_runs()
        fill_table(self.rtable,self.runs,["run_no","equipment_id","protocol_id","protocol_revision","status","started_by","submitted_by","verified_by","approved_by","expires_at","version"])
        if run_no:
            for i,row in enumerate(self.runs):
                if row.run_no==run_no:self.rtable.selectRow(i);break
        self.load_checks()

    def selected_protocol(self):return selected_row(self.ptable,self.protocols)
    def selected_run(self):return selected_row(self.rtable,self.runs)

    def select_run(self,run_no: str):
        self.refresh();self.tabs.setCurrentIndex(1)
        for i,row in enumerate(self.runs):
            if row.run_no==run_no:
                self.rtable.selectRow(i);break

    def export_protocols_roundtrip(self):
        rows=qualification_protocol_export_rows(self.db)
        path,_=QFileDialog.getSaveFileName(self,"Export Qualification Protocols","Qualification_Protocols_RoundTrip.xlsx","Excel Workbook (*.xlsx)")
        if not path:return
        if not path.lower().endswith(".xlsx"):path+=".xlsx"
        try:
            pd.DataFrame(rows,columns=["protocol_id","name","equipment_id","equipment_type","revision","check_id","label","acceptance"]).to_excel(path,index=False)
            QMessageBox.information(self,"Qualification protocols",f"Round-trip workbook created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"Qualification protocols",str(exc))

    def _qualification_protocol_import_df(self,df):
        fields=[
            ("protocol_id","Protocol ID"),("name","Protocol name"),("equipment_id","Equipment ID"),
            ("equipment_type","Equipment type"),("check_id","Check ID"),("label","Check / requirement"),("acceptance","Acceptance"),
        ]
        mapping=run_mapping_studio(
            self,self.db,self.user["username"],"excel_mapping.qualification_protocols",df,fields,
            auto_mapping(list(df.columns)),{"protocol_id","name","check_id","label"},"Qualification Protocol / Checklist Import Studio",
        )
        if mapping is None:return
        rows=dataframe_rows(df,mapping)
        try:actions=reconcile_qualification_protocols(self.db,rows,mapping)
        except Exception as exc:QMessageBox.critical(self,"Qualification protocol reconciliation",str(exc));return
        if not confirm_reconciliation(self,"Qualification Protocol Reconciliation",actions):
            unchanged=all(x["status"]=="UNCHANGED" for x in actions)
            if unchanged:QMessageBox.information(self,"Qualification protocols","No changes detected.")
            return
        try:
            result=apply_extended_reconciliation(self.db,actions,entity="qualification_protocol",user=self.user["username"],workstation=WORKSTATION)
            self.refresh();QMessageBox.information(self,"Qualification protocols",f"Applied {result['applied']} protocol create/revision action(s).")
        except Exception as exc:QMessageBox.critical(self,"Qualification protocols",str(exc))

    def import_protocols(self):
        path,_=QFileDialog.getOpenFileName(self,"Import Qualification Protocols","","Excel/CSV (*.xlsx *.xlsm *.csv)")
        if not path:return
        try:
            sheets=workbook_sheets(path);sheet=sheets[0]
            if len(sheets)>1:
                sheet,ok=QInputDialog.getItem(self,"Qualification Protocol Import","Sheet",sheets,0,False)
                if not ok:return
            self._qualification_protocol_import_df(read_table(path,sheet))
        except Exception as exc:QMessageBox.critical(self,"Qualification protocol import",str(exc))

    def paste_protocols(self):
        try:self._qualification_protocol_import_df(read_clipboard_table(QApplication.clipboard().text()))
        except Exception as exc:QMessageBox.critical(self,"Qualification protocol paste",str(exc))

    def new_protocol(self):
        d=QualificationProtocolDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_qualification_protocol(user=self.user["username"],workstation=WORKSTATION,**d.data());self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Qualification Protocol",str(exc))

    def revise_protocol(self):
        row=self.selected_protocol()
        if not row:return
        d=QualificationProtocolDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_qualification_protocol(user=self.user["username"],workstation=WORKSTATION,create_revision=True,**d.data());self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Qualification Protocol",str(exc))

    def start_run(self):
        eq,ok=QInputDialog.getText(self,"Qualification Run","Equipment ID")
        if not ok or not eq.strip():return
        active=[p for p in self.db.list_qualification_protocols() if (not p.equipment_id or p.equipment_id==eq.strip())]
        if not active:QMessageBox.warning(self,"Qualification","No active qualification protocol available.");return
        labels=[f"{p.protocol_id} R{p.revision} — {p.name}" for p in active]
        choice,ok=QInputDialog.getItem(self,"Qualification Run","Protocol",labels,0,False)
        if not ok:return
        p=active[labels.index(choice)]
        try:self.db.start_qualification_run(eq.strip(),p.protocol_id,self.user["username"],workstation=WORKSTATION);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Qualification",str(exc))

    def load_checks(self):
        row=self.selected_run()
        if not row:
            self.check_rows=[];self.check_results={};self.ctable.setRowCount(0);self.attachments.set_entity("","");return
        self.attachments.set_entity("QUALIFICATION",row.run_no,row.equipment_id)
        try:self.check_rows,self.check_results=self.db.qualification_run_checks(row.id)
        except Exception:self.check_rows=[];self.check_results={}
        self.ctable.setRowCount(len(self.check_rows))
        for r,check in enumerate(self.check_rows):
            res=self.check_results.get(check["check_id"],{})
            vals=[check.get("check_id"),check.get("label"),check.get("acceptance"),res.get("result",""),res.get("comment",""),res.get("evidence_path",""),res.get("entered_by","")]
            for col,val in enumerate(vals):self.ctable.setItem(r,col,ti(val))

    def enter_result(self):
        run=self.selected_run();idx=self.ctable.currentRow()
        if not run or not (0<=idx<len(self.check_rows)):return
        check=self.check_rows[idx]
        value,ok=QInputDialog.getItem(self,"Qualification Result",check["label"],["PASS","FAIL","NA"],0,False)
        if not ok:return
        comment,ok=QInputDialog.getText(self,"Qualification Result","Comment")
        if not ok:return
        evidence=""
        if QMessageBox.question(self,"Evidence","Attach evidence file?")==QMessageBox.StandardButton.Yes:
            source,_=QFileDialog.getOpenFileName(self,"Evidence")
            if source:
                stored=store_attachment_file(source,FILE_ROOT,"QUALIFICATION",run.run_no);evidence=stored["stored_path"]
                self.db.add_attachment("QUALIFICATION",run.run_no,evidence,original_name=stored["original_name"],media_type=stored["media_type"],category="Qualification Evidence",caption=f"{check['check_id']} — {check['label']}",equipment_id=run.equipment_id,created_by=self.user["username"])
        try:
            self.db.save_qualification_result(run.id,check["check_id"],value,comment,self.user["username"],evidence,WORKSTATION,run.version)
            self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Qualification",str(exc))

    def submit_run(self):
        run=self.selected_run()
        if not run:return
        conclusion,ok=QInputDialog.getText(self,"Submit Qualification","Conclusion")
        if not ok:return
        try:self.db.submit_qualification_run(run.id,self.user["username"],conclusion,WORKSTATION,run.version);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Qualification",str(exc))

    def verify_run(self):
        run=self.selected_run()
        if not run:return
        note,ok=QInputDialog.getText(self,"Verify Qualification","Verification note")
        if not ok:return
        try:self.db.verify_qualification_run(run.id,self.user["username"],note,WORKSTATION,run.version);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Qualification",str(exc))

    def approve_run(self):
        run=self.selected_run()
        if not run:return
        days,ok=QInputDialog.getInt(self,"Approve Qualification","Validity days (0 = no expiry)",30,0,3650)
        if not ok:return
        note,ok=QInputDialog.getText(self,"Approve Qualification","Approval note")
        if not ok:return
        try:self.db.approve_qualification_run(run.id,self.user["username"],days or None,note,WORKSTATION,run.version);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Qualification",str(exc))

    def export_pptx(self):
        run=self.selected_run()
        if not run:return
        path,_=QFileDialog.getSaveFileName(self,"Export Qualification PowerPoint",f"{run.equipment_id}_{run.run_no}_Qualification.pptx","PowerPoint (*.pptx)")
        if not path:return
        if not path.lower().endswith(".pptx"):path+=".pptx"
        try:export_qualification_pptx(self.db,run.run_no,path,self.db.resolve_report_template("QUALIFICATION",run.equipment_id));QMessageBox.information(self,"PowerPoint",f"Editable qualification deck created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"PowerPoint",str(exc))

    def export_pdf(self):
        run=self.selected_run()
        if not run:return
        path,_=QFileDialog.getSaveFileName(self,"Export Qualification PDF",f"{run.equipment_id}_{run.run_no}_Qualification.pdf","PDF (*.pdf)")
        if not path:return
        if not path.lower().endswith(".pdf"):path+=".pdf"
        try:export_qualification_pdf(self.db,run.run_no,path);QMessageBox.information(self,"PDF",f"Controlled qualification PDF created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"PDF",str(exc))

    def export_xlsx(self):
        run=self.selected_run()
        if not run:return
        path,_=QFileDialog.getSaveFileName(self,"Export Qualification Excel",f"{run.equipment_id}_{run.run_no}_Qualification.xlsx","Excel Workbook (*.xlsx)")
        if not path:return
        if not path.lower().endswith(".xlsx"):path+=".xlsx"
        try:export_qualification_xlsx(self.db,run.run_no,path);QMessageBox.information(self,"Excel",f"Qualification workbook created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"Excel",str(exc))

    def reject_run(self):
        run=self.selected_run()
        if not run:return
        reason,ok=QInputDialog.getText(self,"Reject Qualification","Reason")
        if not ok:return
        try:self.db.reject_qualification_run(run.id,self.user["username"],reason,WORKSTATION,run.version);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Qualification",str(exc))


class DispositionDialog(QDialog):
    def __init__(self,db=None,parent=None):
        super().__init__(parent);self.setWindowTitle("Equipment Disposition");f=QFormLayout(self);self.eq=QLineEdit();self.state=QComboBox();self.state.addItems(config_option_values(db,"DISPOSITION_STATE",["Released With Conditions","Restricted Use","Engineering Use","Monitoring","Hold","PM Hold","Quality Hold","Safety Hold","Waiting Parts","Waiting Vendor","Qualification","Decommission","Scrap"]));self.reason=QTextEdit();self.rest=QTextEdit();self.criteria=QTextEdit();self.ticket=QLineEdit();f.addRow("Equipment",self.eq);f.addRow("State",self.state);f.addRow("Reason",self.reason);f.addRow("Restrictions",self.rest);f.addRow("Release Criteria",self.criteria);f.addRow("Related Ticket",self.ticket);b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
    def data(self,user):return {"equipment_id":self.eq.text().strip(),"state":self.state.currentText(),"reason":self.reason.toPlainText().strip(),"restrictions":self.rest.toPlainText().strip(),"release_criteria":self.criteria.toPlainText().strip(),"related_ticket":self.ticket.text().strip(),"created_by":user}


RELEASE_CHECKS=[("maintenance_complete","Maintenance / repair complete"),("measurements_pass","Required measurements within limits"),("calibration_valid","Required calibration valid"),("safety_check","Safety checks complete"),("verification_run","Verification run complete"),("critical_tickets_cleared","Critical tickets cleared")]

class ReleaseDialog(QDialog):
    def __init__(self,db,parent=None,existing=None):
        super().__init__(parent);self.db=db;self.existing=existing;self.setWindowTitle("Equipment Release Verification");v=QVBoxLayout(self);f=QFormLayout();self.eq=QLineEdit(existing.equipment_id if existing else "");self.ticket=QLineEdit(existing.related_ticket if existing else "");self.notes=QTextEdit(existing.notes if existing else "");f.addRow("Equipment",self.eq);f.addRow("Related Ticket",self.ticket);f.addRow("Notes",self.notes);v.addLayout(f);self.checks={};existing_checks=json.loads(existing.checks_json or "{}") if existing else {}
        for key,label in RELEASE_CHECKS:c=QCheckBox(label);c.setChecked(existing_checks.get(key,False));self.checks[key]=c;v.addWidget(c)
        if not existing:
            pre=QPushButton("Run Automatic Precheck");pre.clicked.connect(self.precheck);v.addWidget(pre)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);v.addWidget(b)
    def precheck(self):
        if not self.eq.text().strip():return
        p=self.db.release_precheck(self.eq.text().strip());self.checks["critical_tickets_cleared"].setChecked(p["critical_tickets_open"]==0);q=("Not required" if not p.get("qualification_required") else ("PASS — "+p.get("qualification_run_no","") if p.get("qualification_valid") else "REQUIRED / NOT APPROVED"));QMessageBox.information(self,"Precheck",f"Open P1/P2 tickets: {p['critical_tickets_open']}\nOverdue PM: {p['overdue_pm']}\nQualification: {q}")
    def check_data(self):return {k:c.isChecked() for k,c in self.checks.items()}


class ControlPage(QWidget):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.disp=[];self.rel=[];v=QVBoxLayout(self);tabs=QTabWidget();v.addWidget(tabs)
        wd=QWidget();vd=QVBoxLayout(wd);bd=QPushButton("New Disposition");bd.clicked.connect(self.new_disp);bd.setEnabled(db.has_permission(user,"disposition.edit"));vd.addWidget(bd);self.dtable=make_table(["Equipment","State","Reason","Restrictions","Criteria","Ticket","Created By","Approved By","Effective"]);vd.addWidget(self.dtable);tabs.addTab(wd,"Disposition")
        wr=QWidget();vr=QVBoxLayout(wr);hr=QHBoxLayout();new=QPushButton("New Release Request");verify=QPushButton("Verify Selected");approve=QPushButton("Approve / Release");ppt=QPushButton("Release PPTX");xlsx=QPushButton("Release Excel");pdfrel=QPushButton("Release PDF");new.clicked.connect(self.new_release);verify.clicked.connect(self.verify_release);approve.clicked.connect(self.approve_release);ppt.clicked.connect(self.export_release_pptx);xlsx.clicked.connect(self.export_release_xlsx);pdfrel.clicked.connect(self.export_release_pdf);new.setEnabled(db.has_permission(user,"release.verify") or db.has_permission(user,"disposition.edit"));verify.setEnabled(db.has_permission(user,"release.verify"));approve.setEnabled(db.has_permission(user,"release.approve"));hr.addWidget(new);hr.addWidget(verify);hr.addWidget(approve);hr.addWidget(ppt);hr.addWidget(xlsx);hr.addWidget(pdfrel);hr.addStretch(1);vr.addLayout(hr);self.rtable=make_table(["ID","Equipment","Ticket","Status","Requested By","Verified By","Approved By","Requested","Ver"]);self.rtable.itemSelectionChanged.connect(self.load_release_attachment);vr.addWidget(self.rtable,2);self.release_attachments=AttachmentPanel(db,user);vr.addWidget(self.release_attachments,1);tabs.addTab(wr,"Release Verification");self.refresh()
    def refresh(self):
        self.disp=self.db.list_dispositions();fill_table(self.dtable,self.disp,["equipment_id","state","reason","restrictions","release_criteria","related_ticket","created_by","approved_by","effective_at"])
        current=selected_row(self.rtable,self.rel);rid=current.id if current else None
        self.rel=self.db.list_release_requests();fill_table(self.rtable,self.rel,["id","equipment_id","related_ticket","status","requested_by","verified_by","approved_by","requested_at","version"])
        if rid is not None:
            for i,row in enumerate(self.rel):
                if row.id==rid:self.rtable.selectRow(i);break
        self.load_release_attachment()
    def load_release_attachment(self):
        row=selected_row(self.rtable,self.rel)
        self.release_attachments.set_entity("RELEASE",str(row.id),row.equipment_id) if row else self.release_attachments.set_entity("","")
    def new_disp(self):
        d=DispositionDialog(self.db,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.set_disposition(d.data(self.user["username"]));self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Disposition",str(exc))
    def new_release(self):
        d=ReleaseDialog(self.db,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.create_release_request(d.eq.text().strip(),d.ticket.text().strip(),d.check_data(),d.notes.toPlainText().strip(),self.user["username"],workstation=WORKSTATION);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Release",str(exc))
    def verify_release(self):
        row=selected_row(self.rtable,self.rel)
        if not row:return
        d=ReleaseDialog(self.db,self,row);d.eq.setReadOnly(True)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.verify_release(row.id,d.check_data(),self.user["username"],row.version,workstation=WORKSTATION);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Release",str(exc))
    def export_release_pptx(self):
        row=selected_row(self.rtable,self.rel)
        if not row:return
        path,_=QFileDialog.getSaveFileName(self,"Export Release PowerPoint",f"{row.equipment_id}_Release_{row.id}.pptx","PowerPoint (*.pptx)")
        if not path:return
        if not path.lower().endswith(".pptx"):path+=".pptx"
        try:export_release_pptx(self.db,row.id,path,self.db.resolve_report_template("RELEASE",row.equipment_id));QMessageBox.information(self,"PowerPoint",f"Editable release deck created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"PowerPoint",str(exc))

    def export_release_pdf(self):
        row=selected_row(self.rtable,self.rel)
        if not row:return
        path,_=QFileDialog.getSaveFileName(self,"Export Release PDF",f"{row.equipment_id}_Release_{row.id}.pdf","PDF (*.pdf)")
        if not path:return
        if not path.lower().endswith(".pdf"):path+=".pdf"
        try:export_release_pdf(self.db,row.id,path);QMessageBox.information(self,"PDF",f"Controlled release PDF created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"PDF",str(exc))

    def export_release_xlsx(self):
        row=selected_row(self.rtable,self.rel)
        if not row:return
        path,_=QFileDialog.getSaveFileName(self,"Export Release Excel",f"{row.equipment_id}_Release_{row.id}.xlsx","Excel Workbook (*.xlsx)")
        if not path:return
        if not path.lower().endswith(".xlsx"):path+=".xlsx"
        try:export_release_xlsx(self.db,row.id,path);QMessageBox.information(self,"Excel",f"Release workbook created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"Excel",str(exc))

    def approve_release(self):
        row=selected_row(self.rtable,self.rel)
        if not row:return
        if QMessageBox.question(self,"Approve Release",f"Release {row.equipment_id} to service?")!=QMessageBox.StandardButton.Yes:return
        try:self.db.approve_release(row.id,self.user["username"],row.version,workstation=WORKSTATION);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Release",str(exc))


class WorkLogPage(QWidget):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.rows=[]
        v=QVBoxLayout(self);h=QHBoxLayout();title=QLabel("Engineering Work / Labor");title.setStyleSheet("font-size:18pt;font-weight:700")
        start=QPushButton("Start Work");stop=QPushButton("Stop Selected");refresh=QPushButton("Refresh");self.active=QCheckBox("Active only")
        start.clicked.connect(self.start);stop.clicked.connect(self.stop);refresh.clicked.connect(self.refresh);self.active.stateChanged.connect(self.refresh)
        allowed=db.has_permission(user,"worklog.edit");start.setEnabled(allowed);stop.setEnabled(allowed)
        h.addWidget(title);h.addStretch(1);h.addWidget(self.active);h.addWidget(refresh);h.addWidget(start);h.addWidget(stop);v.addLayout(h)
        self.table=make_table(["ID","Equipment","Entity Type","Entity Key","Worker","Work Type","Started","Ended","Minutes","Status","Note"]);v.addWidget(self.table);self.refresh()

    def refresh(self):
        self.rows=self.db.list_work_logs(active_only=self.active.isChecked())
        fill_table(self.table,self.rows,["id","equipment_id","entity_type","entity_key","username","work_type","started_at","ended_at","duration_minutes","status","note"])

    def start(self):
        entity_type,ok=QInputDialog.getItem(self,"Start Work","Linked work type",["PM_TASK","TICKET","QUALIFICATION","EQUIPMENT","OTHER"],0,False)
        if not ok:return
        key,ok=QInputDialog.getText(self,"Start Work","Linked entity key / ID")
        if not ok:return
        eq,ok=QInputDialog.getText(self,"Start Work","Equipment ID")
        if not ok:return
        work_types=config_option_values(self.db,"WORK_TYPE",["Troubleshooting","Maintenance","Repair","Qualification","Engineering","Vendor Support","Other"])
        work_type,ok=QInputDialog.getItem(self,"Start Work","Labor type",work_types,0,False)
        if not ok:return
        note,ok=QInputDialog.getText(self,"Start Work","Initial note")
        if not ok:return
        try:self.db.start_work_log(entity_type,key.strip(),eq.strip(),self.user["username"],work_type,note);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Work Log",str(exc))

    def stop(self):
        row=selected_row(self.table,self.rows)
        if not row:return
        note,ok=QInputDialog.getText(self,"Stop Work","Completion note")
        if not ok:return
        try:self.db.stop_work_log(row.id,self.user["username"],note);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Work Log",str(exc))


class EndorsementDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle("Endorsement / Handover");f=QFormLayout(self);self.no=QLineEdit("END-"+datetime.now().strftime("%Y%m%d-%H%M%S"));self.eq=QLineEdit();self.condition=QTextEdit();self.done=QTextEdit();self.pending=QTextEdit();self.rest=QTextEdit();self.next=QTextEdit();self.owner=QLineEdit();
        for label,w in [("Endorsement No",self.no),("Equipment",self.eq),("Current Condition",self.condition),("Work Completed",self.done),("Pending Work",self.pending),("Restrictions",self.rest),("Next Action",self.next),("Next Owner",self.owner)]:f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
    def data(self,user):return {"endorsement_no":self.no.text().strip(),"equipment_id":self.eq.text().strip(),"current_condition":self.condition.toPlainText().strip(),"work_completed":self.done.toPlainText().strip(),"pending_work":self.pending.toPlainText().strip(),"restrictions":self.rest.toPlainText().strip(),"next_action":self.next.toPlainText().strip(),"next_owner":self.owner.text().strip(),"created_by":user}


class EndorsementPage(QWidget):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.rows=[];v=QVBoxLayout(self);h=QHBoxLayout();add=QPushButton("New Endorsement");ack=QPushButton("Acknowledge Selected");exportb=QPushButton("Export Round-trip Excel");importb=QPushButton("Import Excel/CSV");pasteb=QPushButton("Paste from Excel")
        add.clicked.connect(self.add);ack.clicked.connect(self.ack);exportb.clicked.connect(self.export_roundtrip);importb.clicked.connect(self.import_endorsements);pasteb.clicked.connect(self.paste_endorsements)
        allowed=db.has_permission(user,"endorsement.edit");add.setEnabled(allowed);ack.setEnabled(allowed);importb.setEnabled(allowed);pasteb.setEnabled(allowed)
        for x in [add,ack,exportb,importb,pasteb]:h.addWidget(x)
        h.addStretch(1);v.addLayout(h);self.table=make_table(["No","Equipment","Condition","Pending","Restrictions","Next Owner","Status","Created By","Ack By","Time"]);self.table.itemSelectionChanged.connect(self.load_attachments);v.addWidget(self.table,2);self.attachments=AttachmentPanel(db,user);v.addWidget(self.attachments,1);self.refresh()
    def refresh(self):
        current=selected_row(self.table,self.rows);key=current.endorsement_no if current else ""
        self.rows=self.db.list_endorsements();fill_table(self.table,self.rows,["endorsement_no","equipment_id","current_condition","pending_work","restrictions","next_owner","status","created_by","acknowledged_by","created_at"])
        if key:
            for i,row in enumerate(self.rows):
                if row.endorsement_no==key:self.table.selectRow(i);break
        self.load_attachments()
    def load_attachments(self):
        row=selected_row(self.table,self.rows)
        self.attachments.set_entity("ENDORSEMENT",row.endorsement_no,row.equipment_id) if row else self.attachments.set_entity("","")
    def select_endorsement(self,key: str):
        self.refresh()
        for i,row in enumerate(self.rows):
            if row.endorsement_no==key:self.table.selectRow(i);break
    def export_roundtrip(self):
        rows=endorsement_export_rows(self.db)
        path,_=QFileDialog.getSaveFileName(self,"Export Shift Handovers","Shift_Handovers_RoundTrip.xlsx","Excel Workbook (*.xlsx)")
        if not path:return
        if not path.lower().endswith(".xlsx"):path+=".xlsx"
        try:
            pd.DataFrame(rows).to_excel(path,index=False)
            QMessageBox.information(self,"Shift handover",f"Round-trip workbook created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"Shift handover",str(exc))

    def _endorsement_import_df(self,df):
        fields=[
            ("endorsement_no","Endorsement No"),("equipment_id","Equipment ID"),("current_condition","Current condition"),
            ("work_completed","Work completed"),("pending_work","Pending work"),("restrictions","Restrictions"),
            ("next_action","Next action"),("next_owner","Next owner"),
        ]
        mapping=run_mapping_studio(
            self,self.db,self.user["username"],"excel_mapping.endorsements",df,fields,
            auto_mapping(list(df.columns)),{"endorsement_no","equipment_id"},"Shift Handover Import Studio",
        )
        if mapping is None:return
        rows=dataframe_rows(df,mapping)
        try:actions=reconcile_endorsements(self.db,rows,mapping)
        except Exception as exc:QMessageBox.critical(self,"Shift handover reconciliation",str(exc));return
        if not confirm_reconciliation(self,"Shift Handover Reconciliation",actions):
            unchanged=all(x["status"]=="UNCHANGED" for x in actions)
            if unchanged:QMessageBox.information(self,"Shift handover","No changes detected.")
            return
        try:
            result=apply_extended_reconciliation(self.db,actions,entity="endorsement",user=self.user["username"],workstation=WORKSTATION)
            self.refresh();QMessageBox.information(self,"Shift handover",f"Applied {result['applied']} create/update action(s).")
        except Exception as exc:QMessageBox.critical(self,"Shift handover",str(exc))

    def import_endorsements(self):
        path,_=QFileDialog.getOpenFileName(self,"Import Shift Handovers","","Excel/CSV (*.xlsx *.xlsm *.csv)")
        if not path:return
        try:
            sheets=workbook_sheets(path);sheet=sheets[0]
            if len(sheets)>1:
                sheet,ok=QInputDialog.getItem(self,"Shift Handover Import","Sheet",sheets,0,False)
                if not ok:return
            self._endorsement_import_df(read_table(path,sheet))
        except Exception as exc:QMessageBox.critical(self,"Shift handover import",str(exc))

    def paste_endorsements(self):
        try:self._endorsement_import_df(read_clipboard_table(QApplication.clipboard().text()))
        except Exception as exc:QMessageBox.critical(self,"Shift handover paste",str(exc))

    def add(self):
        d=EndorsementDialog(self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_endorsement(d.data(self.user["username"]));self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Endorsement",str(exc))
    def ack(self):
        row=selected_row(self.table,self.rows)
        if row:
            try:self.db.acknowledge_endorsement(row.endorsement_no,self.user["username"]);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Endorsement",str(exc))


class StorageDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Storage Location");f=QFormLayout(self);self.fields={}
        for k,label in [("location_code","Code"),("name","Name"),("site","Site"),("building","Building"),("floor","Floor"),("area","Area"),("cabinet","Cabinet"),("shelf","Shelf"),("drawer_bin","Drawer / Bin"),("image_path","Location Image")]:w=QLineEdit();self.fields[k]=w;f.addRow(label,w)
        self.x=QDoubleSpinBox();self.y=QDoubleSpinBox();self.x.setRange(-100000,100000);self.y.setRange(-100000,100000);f.addRow("Map X",self.x);f.addRow("Map Y",self.y);b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:
            for k,w in self.fields.items():w.setText(str(getattr(row,k,"") or ""));self.fields["location_code"].setReadOnly(True);self.x.setValue(row.map_x);self.y.setValue(row.map_y)
    def data(self):d={k:w.text().strip() for k,w in self.fields.items()};d.update(map_x=self.x.value(),map_y=self.y.value());return d


class InventoryDialog(QDialog):
    def __init__(self,row=None,parent=None,db=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Inventory Item");f=QFormLayout(self);self.part=QLineEdit();self.desc=QLineEdit();self.cat=QLineEdit();self.mfg=QLineEdit();self.model=QLineEdit();self.compat=QLineEdit();self.qty=QDoubleSpinBox();self.qty.setRange(0,1e9);self.minq=QDoubleSpinBox();self.minq.setRange(0,1e9);self.unit=QLineEdit("pcs");self.cond=QComboBox();self.cond.addItems(config_option_values(db,"INVENTORY_CONDITION",["Available","Reserved","Installed","In Use","Repair","Quarantine","Inspection Required","Expired","Obsolete","Scrap","Vendor"]));self.loc=QLineEdit();self.image=QLineEdit();self.notes=QTextEdit()
        for label,w in [("Part Number",self.part),("Description",self.desc),("Category",self.cat),("Manufacturer",self.mfg),("Model",self.model),("Compatible Equipment",self.compat),("Quantity",self.qty),("Minimum",self.minq),("Unit",self.unit),("Condition",self.cond),("Location Code",self.loc),("Image Path",self.image),("Notes",self.notes)]:f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:self.part.setText(row.part_number);self.part.setReadOnly(True);self.desc.setText(row.description);self.cat.setText(row.category);self.mfg.setText(row.manufacturer);self.model.setText(row.model);self.compat.setText(row.compatible_equipment);self.qty.setValue(row.quantity);self.minq.setValue(row.min_quantity);self.unit.setText(row.unit);self.cond.setCurrentText(row.condition);self.loc.setText(row.location_code);self.loc.setReadOnly(True);self.image.setText(row.image_path);self.notes.setPlainText(row.notes)
    def data(self):return {"part_number":self.part.text().strip(),"description":self.desc.text().strip(),"category":self.cat.text().strip(),"manufacturer":self.mfg.text().strip(),"model":self.model.text().strip(),"compatible_equipment":self.compat.text().strip(),"quantity":self.qty.value(),"min_quantity":self.minq.value(),"unit":self.unit.text().strip() or "pcs","condition":self.cond.currentText(),"location_code":self.loc.text().strip(),"image_path":self.image.text().strip(),"notes":self.notes.toPlainText().strip()}


class InventoryPage(QWidget):
    show_map_part=Signal(str)
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.items=[];self.locs=[];self.res=[];v=QVBoxLayout(self);tabs=QTabWidget();v.addWidget(tabs)
        wi=QWidget();vi=QVBoxLayout(wi);hi=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText("Search part / description / location");self.search.textChanged.connect(self.refresh);add=QPushButton("Add Item");edit=QPushButton("Edit");imp=QPushButton("Import Excel/CSV");paste=QPushButton("Paste from Excel");bulk=QPushButton("Bulk Edit Selected");consume=QPushButton("Consume");reserve=QPushButton("Reserve");show=QPushButton("Show on Map");add.clicked.connect(self.add_item);edit.clicked.connect(self.edit_item);imp.clicked.connect(self.import_inventory);paste.clicked.connect(self.paste_inventory);bulk.clicked.connect(self.bulk_edit_inventory);consume.clicked.connect(self.consume);reserve.clicked.connect(self.reserve);show.clicked.connect(self.map_item);canedit=db.has_permission(user,"inventory.edit");add.setEnabled(canedit);edit.setEnabled(canedit);imp.setEnabled(canedit);paste.setEnabled(canedit);bulk.setEnabled(canedit);consume.setEnabled(db.has_permission(user,"inventory.consume") or canedit);reserve.setEnabled(db.has_permission(user,"inventory.reserve"));hi.addWidget(self.search,1);[hi.addWidget(x) for x in [add,edit,imp,paste,bulk,consume,reserve,show]];vi.addLayout(hi);self.itable=make_table(["Part","Description","Qty","Min","Unit","Condition","Location","Image","Ver"]);vi.addWidget(self.itable);tabs.addTab(wi,"Inventory")
        wl=QWidget();vl=QVBoxLayout(wl);addl=QPushButton("Add Storage Location");addl.clicked.connect(self.add_loc);addl.setEnabled(db.has_permission(user,"inventory.edit"));vl.addWidget(addl);self.ltable=make_table(["Code","Name","Building","Floor","Area","Cabinet","Shelf","Bin","Image","Ver"]);vl.addWidget(self.ltable);tabs.addTab(wl,"Storage Locations")
        wr=QWidget();vr=QVBoxLayout(wr);rel=QPushButton("Release Selected Reservation");rel.clicked.connect(self.release_res);rel.setEnabled(db.has_permission(user,"inventory.reserve"));vr.addWidget(rel);self.rtable=make_table(["ID","Part","Location","Qty","PM Task","Equipment","Status","Reserved By","Time","Ver"]);vr.addWidget(self.rtable);tabs.addTab(wr,"Reservations");self.refresh()
    def refresh(self):self.items=self.db.list_inventory(self.search.text().strip());fill_table(self.itable,self.items,["part_number","description","quantity","min_quantity","unit","condition","location_code","image_path","version"]);self.locs=self.db.list_storage_locations();fill_table(self.ltable,self.locs,["location_code","name","building","floor","area","cabinet","shelf","drawer_bin","image_path","version"]);self.res=self.db.list_reservations();fill_table(self.rtable,self.res,["id","part_number","location_code","quantity","pm_task_id","equipment_id","status","reserved_by","reserved_at","version"])
    def bulk_edit_inventory(self):
        selected=sorted({idx.row() for idx in self.itable.selectedIndexes()})
        rows=[self.items[i] for i in selected if 0<=i<len(self.items)]
        if not rows:
            QMessageBox.information(self,"Bulk edit","Select one or more inventory rows.");return
        field,ok=QInputDialog.getItem(self,"Bulk edit inventory","Field",["Condition","Minimum quantity","Unit"],0,False)
        if not ok:return
        if field=="Condition":
            value,ok=QInputDialog.getItem(self,"Bulk edit inventory","Condition",["Available","Reserved","Quarantine","Repair","Scrap"],0,False)
        elif field=="Minimum quantity":
            value,ok=QInputDialog.getDouble(self,"Bulk edit inventory","Minimum quantity",0,0,1e12,3)
        else:
            value,ok=QInputDialog.getText(self,"Bulk edit inventory","Unit")
        if not ok:return
        if QMessageBox.question(self,"Confirm bulk edit",f"Update {field} on {len(rows)} inventory record(s)?")!=QMessageBox.StandardButton.Yes:return
        failures=[];updated=0
        for row in rows:
            data={
                "part_number":row.part_number,"description":row.description,"quantity":row.quantity,
                "min_quantity":float(value) if field=="Minimum quantity" else row.min_quantity,
                "unit":value.strip() if field=="Unit" else row.unit,
                "condition":value if field=="Condition" else row.condition,
                "location_code":row.location_code,"image_path":row.image_path,
            }
            try:self.db.save_inventory_item(data,row.version);updated+=1
            except Exception as exc:failures.append(f"{row.part_number} @ {row.location_code}: {exc}")
        self.refresh()
        text=f"Updated {updated}/{len(rows)} inventory record(s)."
        if failures:text+="\n"+"\n".join(failures[:12])
        QMessageBox.information(self,"Bulk edit",text)

    def _inventory_import_df(self,df):
        fields=[
            ("part_number","Part number"),("description","Description"),("quantity","Quantity"),("min_quantity","Minimum quantity"),
            ("unit","Unit"),("condition","Condition"),("location_code","Location code"),("image_path","Image path"),
        ]
        mapping=run_mapping_studio(self,self.db,self.user["username"],"excel_mapping.inventory",df,fields,auto_mapping(list(df.columns)),{"part_number","location_code"},"Inventory Import Studio")
        if mapping is None:return
        rows,errors=dataframe_to_inventory(df,mapping)
        if not rows:QMessageBox.warning(self,"Inventory import","No valid rows.\n"+"\n".join(errors[:20]));return
        actions=reconcile_inventory(self.db,rows,mapping)
        if not any(x["status"] in {"CREATE","UPDATE"} for x in actions):
            QMessageBox.information(self,"Inventory import","No changes detected.");return
        if not confirm_reconciliation(self,"Inventory Reconciliation",actions):return
        imported=0;failures=[]
        for action in actions:
            if action["status"]=="UNCHANGED":continue
            data=action["data"];existing=action["current"]
            try:self.db.save_inventory_item(data,existing.version if existing else None);imported+=1
            except Exception as exc:failures.append(f"{data.get('part_number')} @ {data.get('location_code')}: {exc}")
        self.refresh();detail=f"Applied {imported} inventory create/update row(s). Source warnings: {len(errors)}. Failures: {len(failures)}."
        if failures:detail+="\n"+"\n".join(failures[:12])
        QMessageBox.information(self,"Inventory import",detail)

    def import_inventory(self):
        path,_=QFileDialog.getOpenFileName(self,"Import Inventory","","Excel/CSV (*.xlsx *.xlsm *.csv)")
        if not path:return
        try:
            sheets=workbook_sheets(path);sheet=sheets[0]
            if len(sheets)>1:
                sheet,ok=QInputDialog.getItem(self,"Import Inventory","Sheet",sheets,0,False)
                if not ok:return
            self._inventory_import_df(read_table(path,sheet))
        except Exception as exc:QMessageBox.critical(self,"Inventory import",str(exc))

    def paste_inventory(self):
        try:self._inventory_import_df(read_clipboard_table(QApplication.clipboard().text()))
        except Exception as exc:QMessageBox.critical(self,"Inventory paste",str(exc))

    def add_item(self):
        d=InventoryDialog(parent=self,db=self.db)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_inventory_item(d.data());self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Inventory",str(exc))
    def edit_item(self):
        row=selected_row(self.itable,self.items)
        if not row:return
        d=InventoryDialog(row,self,db=self.db)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_inventory_item(d.data(),row.version);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Inventory",str(exc))
    def add_loc(self):
        d=StorageDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_storage_location(d.data());self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Storage",str(exc))
    def consume(self):
        row=selected_row(self.itable,self.items)
        if not row:return
        qty,ok=QInputDialog.getDouble(self,"Consume",f"Quantity from {row.location_code}",1,0.0001,1e9,2)
        if ok:
            try:success,remaining=self.db.consume_inventory(row.part_number,row.location_code,qty,self.user["username"]);QMessageBox.information(self,"Inventory",f"Remaining: {remaining:g}" if success else f"Insufficient stock. Available: {remaining:g}");self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Inventory",str(exc))
    def reserve(self):
        row=selected_row(self.itable,self.items)
        if not row:return
        qty,ok=QInputDialog.getDouble(self,"Reserve",f"Reserve {row.part_number}",1,0.0001,1e9,2)
        if not ok:return
        task,ok2=QInputDialog.getInt(self,"PM Task","PM task ID (0 for none)",0,0,1_000_000)
        if not ok2:return
        try:success,val=self.db.reserve_inventory(row.part_number,qty,self.user["username"],task or None,"",row.location_code);QMessageBox.information(self,"Reservation",f"Reservation ID: {val}" if success else f"Insufficient unreserved stock. Available: {val:g}");self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Reservation",str(exc))
    def release_res(self):
        row=selected_row(self.rtable,self.res)
        if row:
            try:self.db.release_reservation(row.id,self.user["username"]);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Reservation",str(exc))
    def map_item(self):
        row=selected_row(self.itable,self.items)
        if row:self.show_map_part.emit(row.part_number)


class DocumentPage(QWidget):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.rows=[];self.cdocs=[];self.revisions=[]
        v=QVBoxLayout(self);h=QHBoxLayout();self.type=QLineEdit();self.type.setPlaceholderText("Entity type e.g. Equipment");self.key=QLineEdit();self.key.setPlaceholderText("Entity key");find=QPushButton("Filter");find.clicked.connect(self.refresh);h.addWidget(self.type);h.addWidget(self.key);h.addWidget(find);v.addLayout(h)
        tabs=QTabWidget()

        wl=QWidget();vl=QVBoxLayout(wl);hl=QHBoxLayout();add=QPushButton("Link File");openb=QPushButton("Open Read-Only");add.clicked.connect(self.add);openb.clicked.connect(self.open);add.setEnabled(db.has_permission(user,"document.link"));hl.addWidget(add);hl.addWidget(openb);hl.addStretch(1);vl.addLayout(hl)
        self.table=make_table(["Entity","Key","Type","Title","Revision","Status","Path","Added By","Time"]);vl.addWidget(self.table);tabs.addTab(wl,"Linked Files")

        wc=QWidget();vc=QVBoxLayout(wc);hc=QHBoxLayout();newdoc=QPushButton("New Controlled Document");addrev=QPushButton("Add Revision");approve=QPushButton("Approve Revision");reject=QPushButton("Reject Revision");open_eff=QPushButton("Open Effective");verify=QPushButton("Verify File")
        newdoc.clicked.connect(self.new_controlled);addrev.clicked.connect(self.add_revision);approve.clicked.connect(self.approve_revision);reject.clicked.connect(self.reject_revision);open_eff.clicked.connect(self.open_effective);verify.clicked.connect(self.verify_revision)
        cancontrol=db.has_permission(user,"document.control");[x.setEnabled(cancontrol) for x in [newdoc,addrev,approve,reject]]
        for x in [newdoc,addrev,approve,reject,open_eff,verify]:hc.addWidget(x)
        hc.addStretch(1);vc.addLayout(hc)
        self.cdoc_table=make_table(["Document ID","Entity","Key","Type","Title","Owner","Status","Current Revision","Created By","Ver"]);self.cdoc_table.itemSelectionChanged.connect(self.load_revisions);vc.addWidget(self.cdoc_table,1)
        self.rev_table=make_table(["ID","Revision","Status","SHA-256","Summary","Created By","Approved By","Effective","Expires","Path","Ver"]);vc.addWidget(self.rev_table,1)
        tabs.addTab(wc,"Controlled Documents")
        v.addWidget(tabs);self.refresh()

    def refresh(self):
        et=self.type.text().strip();ek=self.key.text().strip()
        self.rows=self.db.list_documents(et,ek);fill_table(self.table,self.rows,["entity_type","entity_key","document_type","title","revision","status","path","added_by","added_at"])
        self.cdocs=self.db.list_controlled_documents(et,ek);fill_table(self.cdoc_table,self.cdocs,["document_id","entity_type","entity_key","document_type","title","owner","status","current_revision","created_by","version"])
        self.load_revisions()

    def select_document(self,document_id: str):
        target=next((x for x in self.db.list_controlled_documents() if x.document_id==document_id),None)
        if not target:return
        self.type.setText(target.entity_type);self.key.setText(target.entity_key);self.refresh()
        for i,row in enumerate(self.cdocs):
            if row.document_id==document_id:
                self.cdoc_table.selectRow(i);self.load_revisions();break

    def add(self):
        p,_=QFileDialog.getOpenFileName(self,"Link Existing File")
        if not p:return
        title,ok=QInputDialog.getText(self,"Title","Document title",text=Path(p).name)
        if not ok:return
        dtype,ok=QInputDialog.getItem(self,"Type","Document type",["SOP","Manual","Drawing","Report","Engineering Analysis","Vendor Report","Calibration Certificate","Image","Log","Spreadsheet","Other"],0,False)
        if not ok:return
        try:self.db.add_document({"entity_type":self.type.text().strip() or "General","entity_key":self.key.text().strip(),"document_type":dtype,"title":title,"path":p,"status":"Active","added_by":self.user["username"]});self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Document",str(exc))

    def open(self):
        row=selected_row(self.table,self.rows)
        if row:
            try:readonly_open_copy(row.path)
            except Exception as exc:QMessageBox.critical(self,"Open",str(exc))

    def new_controlled(self):
        doc_id,ok=QInputDialog.getText(self,"Controlled Document","Document ID")
        if not ok or not doc_id.strip():return
        title,ok=QInputDialog.getText(self,"Controlled Document","Title")
        if not ok or not title.strip():return
        dtype,ok=QInputDialog.getItem(self,"Controlled Document","Type",["SOP","Specification","Work Instruction","Drawing","Calibration Procedure","Safety Procedure","Quality Procedure","Other"],0,False)
        if not ok:return
        owner,ok=QInputDialog.getText(self,"Controlled Document","Document owner")
        if not ok:return
        try:
            self.db.create_controlled_document({
                "document_id":doc_id.strip(),"entity_type":self.type.text().strip() or "General","entity_key":self.key.text().strip(),
                "document_type":dtype,"title":title.strip(),"owner":owner.strip(),
            },self.user["username"],WORKSTATION)
            self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Controlled Document",str(exc))

    def current_cdoc(self):return selected_row(self.cdoc_table,self.cdocs)
    def current_revision(self):return selected_row(self.rev_table,self.revisions)

    def load_revisions(self):
        doc=self.current_cdoc()
        self.revisions=self.db.list_controlled_revisions(doc.document_id) if doc else []
        fill_table(self.rev_table,self.revisions,["id","revision","status","file_sha256","change_summary","created_by","approved_by","effective_at","expires_at","path","version"])

    def add_revision(self):
        doc=self.current_cdoc()
        if not doc:return
        path,_=QFileDialog.getOpenFileName(self,"Controlled Revision File")
        if not path:return
        rev,ok=QInputDialog.getText(self,"Revision","Revision identifier")
        if not ok or not rev.strip():return
        summary,ok=QInputDialog.getText(self,"Revision","Change summary")
        if not ok:return
        try:self.db.add_controlled_revision(doc.document_id,rev,path,summary,self.user["username"],WORKSTATION);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Controlled Revision",str(exc))

    def approve_revision(self):
        row=self.current_revision()
        if not row:return
        if QMessageBox.question(self,"Approve Revision",f"Make {row.document_id} revision {row.revision} effective now?")!=QMessageBox.StandardButton.Yes:return
        try:self.db.approve_controlled_revision(row.id,self.user["username"],workstation=WORKSTATION,expected_version=row.version);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Controlled Revision",str(exc))

    def reject_revision(self):
        row=self.current_revision()
        if not row:return
        reason,ok=QInputDialog.getText(self,"Reject Revision","Reason")
        if not ok:return
        try:self.db.reject_controlled_revision(row.id,self.user["username"],reason,WORKSTATION,row.version);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Controlled Revision",str(exc))

    def open_effective(self):
        doc=self.current_cdoc()
        if not doc:return
        row=self.db.effective_controlled_revision(doc.document_id)
        if not row:QMessageBox.warning(self,"Controlled Document","No effective non-expired revision.");return
        ok,digest=self.db.verify_controlled_revision_file(row.id)
        if not ok:QMessageBox.critical(self,"Controlled Document",f"File integrity check failed: {digest}");return
        try:readonly_open_copy(row.path)
        except Exception as exc:QMessageBox.critical(self,"Open",str(exc))

    def verify_revision(self):
        row=self.current_revision()
        if not row:return
        ok,detail=self.db.verify_controlled_revision_file(row.id)
        QMessageBox.information(self,"Integrity","PASS — SHA-256 matches." if ok else f"FAIL — {detail}")


class InboundEndpointDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Inbound Integration Endpoint");self.resize(720,560)
        f=QFormLayout(self)
        self.endpoint=QLineEdit();self.name=QLineEdit();self.adapter=QComboBox();self.adapter.addItems(["FILE_JSON","FILE_CSV"])
        self.entity=QComboBox();self.entity.addItems(["ALARM","METER"]);self.source=QLineEdit();self.pattern=QLineEdit()
        self.mapping=QTextEdit();self.defaults=QTextEdit();self.archive=QLineEdit();self.quarantine=QLineEdit();self.enabled=QCheckBox("Enabled");self.enabled.setChecked(True)
        self.mapping.setPlaceholderText('{"equipment_id":"tool","alarm_code":"code","severity":"severity","message":"message"}')
        self.defaults.setPlaceholderText('{"state":"ACTIVE","source":"FDC"}')
        for label,w in [
            ("Endpoint ID",self.endpoint),("Name",self.name),("Adapter",self.adapter),("Target entity",self.entity),
            ("Source folder",self.source),("File pattern",self.pattern),("Field mapping JSON",self.mapping),
            ("Defaults JSON",self.defaults),("Archive folder",self.archive),("Quarantine folder",self.quarantine),
        ]:f.addRow(label,w)
        f.addRow("",self.enabled)
        note=QLabel("ALARM minimum mapping: equipment_id + alarm_code. METER minimum mapping: equipment_id + meter_code + value. JSON mappings may use dotted source keys.")
        note.setWordWrap(True);f.addRow("",note)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self._accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:
            self.endpoint.setText(row.endpoint_id);self.endpoint.setReadOnly(True);self.name.setText(row.name);self.adapter.setCurrentText(row.adapter_type)
            self.entity.setCurrentText(row.entity_type);self.source.setText(row.source_path);self.pattern.setText(row.file_pattern)
            self.mapping.setPlainText(row.mapping_json or "{}");self.defaults.setPlainText(row.defaults_json or "{}")
            self.archive.setText(row.archive_path);self.quarantine.setText(row.quarantine_path);self.enabled.setChecked(row.enabled)
        else:
            self.pattern.setText("*.json");self.mapping.setPlainText("{}");self.defaults.setPlainText("{}")

    def _accept(self):
        try:
            mapping=json.loads(self.mapping.toPlainText() or "{}");defaults=json.loads(self.defaults.toPlainText() or "{}")
            if not isinstance(mapping,dict) or not isinstance(defaults,dict):raise ValueError("Mapping and defaults must be JSON objects.")
        except Exception as exc:QMessageBox.warning(self,"Inbound Integration",str(exc));return
        if not self.endpoint.text().strip() or not self.source.text().strip():
            QMessageBox.warning(self,"Inbound Integration","Endpoint ID and source folder are required.");return
        self.accept()

    def data(self):
        return {
            "endpoint_id":self.endpoint.text().strip(),"name":self.name.text().strip(),
            "adapter_type":self.adapter.currentText(),"entity_type":self.entity.currentText(),
            "source_path":self.source.text().strip(),"file_pattern":self.pattern.text().strip(),
            "mapping_json":self.mapping.toPlainText().strip() or "{}","defaults_json":self.defaults.toPlainText().strip() or "{}",
            "archive_path":self.archive.text().strip(),"quarantine_path":self.quarantine.text().strip(),
            "enabled":self.enabled.isChecked(),
        }


class IntegrationEndpointDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Integration Endpoint");f=QFormLayout(self)
        self.endpoint=QLineEdit();self.name=QLineEdit();self.adapter=QComboBox();self.adapter.addItems(["FILE","HTTP"]);self.target=QLineEdit();self.topics=QLineEdit("*");self.auth=QLineEdit();self.enabled=QCheckBox("Enabled");self.enabled.setChecked(True)
        self.topics.setPlaceholderText("*, equipment.state.changed, incident.state.changed")
        for label,w in [("Endpoint ID",self.endpoint),("Name",self.name),("Adapter",self.adapter),("Target path / URL",self.target),("Topics",self.topics),("Auth environment variable",self.auth)]:f.addRow(label,w)
        f.addRow("",self.enabled)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:
            self.endpoint.setText(row.endpoint_id);self.endpoint.setReadOnly(True);self.name.setText(row.name);self.adapter.setCurrentText(row.adapter_type);self.target.setText(row.target);self.topics.setText(row.topics);self.auth.setText(row.auth_env);self.enabled.setChecked(row.enabled)
    def data(self):
        return {"endpoint_id":self.endpoint.text().strip(),"name":self.name.text().strip(),"adapter_type":self.adapter.currentText(),"target":self.target.text().strip(),"topics":self.topics.text().strip() or "*","auth_env":self.auth.text().strip(),"enabled":self.enabled.isChecked()}


class UserDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle("New User");f=QFormLayout(self);self.username=QLineEdit();self.name=QLineEdit();self.password=QLineEdit();self.password.setEchoMode(QLineEdit.EchoMode.Password);self.role=QComboBox();self.role.addItems(list(ROLE_PERMISSIONS));f.addRow("Username",self.username);f.addRow("Display Name",self.name);f.addRow("Password",self.password);f.addRow("Role",self.role);b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)


class AdminPage(QWidget):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.rows=[];self.attempts=[];self.scope_rows=[];self.cert_rows=[];self.integration_endpoints=[];self.integration_deliveries=[];self.inbound_endpoints=[];self.inbound_receipts=[];v=QVBoxLayout(self)
        h=QHBoxLayout();add=QPushButton("Add User");role=QPushButton("Change Role");toggle=QPushButton("Enable / Disable");reset=QPushButton("Reset Password");unlock=QPushButton("Unlock Login");override=QPushButton("Permission Override");scope=QPushButton("Access Scope");clearscope=QPushButton("Clear Scopes");cert=QPushButton("Certification");integration=QPushButton("Integration Endpoint");backupb=QPushButton("Create DB Backup");verifyb=QPushButton("Verify Backup")
        add.clicked.connect(self.add);role.clicked.connect(self.role);toggle.clicked.connect(self.toggle);reset.clicked.connect(self.reset);unlock.clicked.connect(self.unlock);override.clicked.connect(self.override);scope.clicked.connect(self.manage_scope);clearscope.clicked.connect(self.clear_scopes);cert.clicked.connect(self.manage_certification);integration.clicked.connect(self.manage_integration);backupb.clicked.connect(self.create_backup);verifyb.clicked.connect(self.verify_backup)
        allowed=db.has_permission(user,"user.admin") or user.get("role")=="Administrator";[x.setEnabled(allowed) for x in [add,role,toggle,reset,unlock,override,scope,clearscope,cert,integration,backupb,verifyb]];[h.addWidget(x) for x in [add,role,toggle,reset,unlock,override,scope,clearscope,cert,integration,backupb,verifyb]];h.addStretch(1);v.addLayout(h)
        tabs=QTabWidget()
        wu=QWidget();vu=QVBoxLayout(wu);self.table=make_table(["Username","Display Name","Role","Active","Last Login","Created"]);vu.addWidget(self.table);tabs.addTab(wu,"Users")
        ws=QWidget();vs=QVBoxLayout(ws);self.scope_table=make_table(["Username","Mode","Scope Type","Scope Key","Permission"]);vs.addWidget(self.scope_table);tabs.addTab(ws,"Access Scopes")
        wc=QWidget();vc=QVBoxLayout(wc);self.cert_table=make_table(["Username","Certification","Issuer","Issued","Expires","Active","Note","Ver"]);vc.addWidget(self.cert_table);tabs.addTab(wc,"Certifications")
        wi=QWidget();vi=QVBoxLayout(wi);ih=QHBoxLayout()
        dispatchb=QPushButton("Dispatch Pending Now");dispatchb.clicked.connect(self.dispatch_integrations)
        replayb=QPushButton("Replay Selected");replayb.clicked.connect(self.replay_delivery)
        deadb=QPushButton("Dead-letter Selected");deadb.clicked.connect(self.dead_letter_delivery)
        requeueb=QPushButton("Requeue Dead Letters");requeueb.clicked.connect(self.requeue_dead_letters)
        for x in [dispatchb,replayb,deadb,requeueb]:x.setEnabled(allowed);ih.addWidget(x)
        ih.addStretch(1);vi.addLayout(ih)
        self.integration_table=make_table(["Endpoint","Name","Adapter","Target","Topics","Auth Env","Enabled","Ver"])
        self.delivery_table=make_table(["ID","Topic","Entity","Key","Endpoint","Adapter","Target","Status","Attempts","Next Attempt","Last Error","Sent"])
        vi.addWidget(self.integration_table,1);vi.addWidget(self.delivery_table,2);tabs.addTab(wi,"Integrations / Outbox")
        win=QWidget();vin=QVBoxLayout(win);inh=QHBoxLayout()
        addin=QPushButton("New Inbound");editin=QPushButton("Edit Selected");processin=QPushButton("Process Selected Feed");replayin=QPushButton("Replay Selected Receipt")
        addin.clicked.connect(self.add_inbound_endpoint);editin.clicked.connect(self.edit_inbound_endpoint);processin.clicked.connect(self.process_inbound);replayin.clicked.connect(self.replay_inbound_receipt)
        for x in [addin,editin,processin,replayin]:x.setEnabled(allowed);inh.addWidget(x)
        inh.addStretch(1);vin.addLayout(inh)
        self.inbound_table=make_table(["Endpoint","Name","Adapter","Entity","Source","Pattern","Archive","Quarantine","Enabled","Ver"])
        self.receipt_table=make_table(["ID","Endpoint","Source","Status","Total","Applied","Rejected","Error","Processed"])
        vin.addWidget(self.inbound_table,1);vin.addWidget(self.receipt_table,2);tabs.addTab(win,"Inbound Integrations")
        wa=QWidget();va=QVBoxLayout(wa);self.attempt_table=make_table(["Username","Success","Reason","Workstation","Attempted"]);va.addWidget(self.attempt_table);tabs.addTab(wa,"Login Attempts")
        v.addWidget(tabs);self.refresh()

    def refresh(self):
        self.rows=self.db.list_users();fill_table(self.table,self.rows,["username","display_name","role","active","last_login","created_at"])
        self.attempts=self.db.list_login_attempts(limit=500);fill_table(self.attempt_table,self.attempts,["username","success","reason","workstation","attempted_at"])
        self.scope_rows=[]
        for u in self.rows:
            policy=self.db.user_access_policy(u.username);mode=policy.scope_mode if policy else "UNRESTRICTED"
            scopes=self.db.list_user_scopes(u.username)
            if scopes:
                for s in scopes:self.scope_rows.append({"username":u.username,"mode":mode,"scope_type":s.scope_type,"scope_key":s.scope_key,"permission":s.permission})
            else:self.scope_rows.append({"username":u.username,"mode":mode,"scope_type":"","scope_key":"","permission":""})
        self.scope_table.setRowCount(len(self.scope_rows))
        for r,row in enumerate(self.scope_rows):
            for col,key in enumerate(["username","mode","scope_type","scope_key","permission"]):self.scope_table.setItem(r,col,ti(row.get(key,"")))
        self.cert_rows=self.db.list_technician_certifications()
        fill_table(self.cert_table,self.cert_rows,["username","cert_code","issuer","issued_at","expires_at","active","note","version"])
        self.integration_endpoints=self.db.list_integration_endpoints()
        fill_table(self.integration_table,self.integration_endpoints,["endpoint_id","name","adapter_type","target","topics","auth_env","enabled","version"])
        self.integration_deliveries=self.db.integration_delivery_rows()
        self.delivery_table.setRowCount(len(self.integration_deliveries))
        fields=["id","topic","entity_type","entity_key","endpoint_id","adapter_type","target","status","attempts","next_attempt_at","last_error","sent_at"]
        for r,row in enumerate(self.integration_deliveries):
            for col,key in enumerate(fields):self.delivery_table.setItem(r,col,ti(row.get(key,"")))
        self.inbound_endpoints=self.db.list_inbound_endpoints()
        fill_table(self.inbound_table,self.inbound_endpoints,["endpoint_id","name","adapter_type","entity_type","source_path","file_pattern","archive_path","quarantine_path","enabled","version"])
        self.inbound_receipts=self.db.list_inbound_receipts(limit=1000)
        fill_table(self.receipt_table,self.inbound_receipts,["id","endpoint_id","source_name","status","records_total","records_applied","records_rejected","error","processed_at"])

    def selected_inbound_endpoint(self):
        return selected_row(self.inbound_table,self.inbound_endpoints)

    def selected_inbound_receipt(self):
        return selected_row(self.receipt_table,self.inbound_receipts)

    def add_inbound_endpoint(self):
        d=InboundEndpointDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_inbound_endpoint(d.data());self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Inbound Integration",str(exc))

    def edit_inbound_endpoint(self):
        row=self.selected_inbound_endpoint()
        if not row:return
        d=InboundEndpointDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_inbound_endpoint(d.data(),row.version);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Inbound Integration",str(exc))

    def process_inbound(self):
        row=self.selected_inbound_endpoint()
        if not row:return
        try:
            stats=process_inbound_endpoint(self.db,row.endpoint_id,200);self.refresh()
            QMessageBox.information(self,"Inbound Integration",f"Files: {stats['files']}\nProcessed: {stats['processed']}\nQuarantined/partial: {stats['quarantined']}\nDuplicates: {stats['duplicates']}\nRecords applied: {stats['applied']}\nRejected: {stats['rejected']}")
        except Exception as exc:QMessageBox.critical(self,"Inbound Integration",str(exc))

    def replay_inbound_receipt(self):
        row=self.selected_inbound_receipt()
        if not row:return
        try:detail=json.loads(row.detail_json or "{}")
        except Exception:detail={}
        path=str(detail.get("final_path") or "")
        if not path:
            QMessageBox.warning(self,"Inbound Replay","Receipt does not contain a replayable file path.");return
        if QMessageBox.question(self,"Inbound Replay",f"Replay receipt {row.id}?\n{path}")!=QMessageBox.StandardButton.Yes:return
        try:
            result=process_inbound_file(self.db,row.endpoint_id,path,replay=True);self.refresh()
            QMessageBox.information(self,"Inbound Replay",f"Status: {result['status']}\nApplied: {result['applied']}\nRejected: {result['rejected']}\nSkipped: {result['skipped']}")
        except Exception as exc:QMessageBox.critical(self,"Inbound Replay",str(exc))

    def selected_delivery(self):
        return selected_row(self.delivery_table,self.integration_deliveries)

    def dispatch_integrations(self):
        try:
            stats=dispatch_pending(self.db,500)
            self.refresh()
            QMessageBox.information(self,"Integration dispatch",f"Pending checked: {stats['pending']}\nSent: {stats['sent']}\nFailed: {stats['failed']}")
        except Exception as exc:QMessageBox.critical(self,"Integration dispatch",str(exc))

    def replay_delivery(self):
        row=self.selected_delivery()
        if not row:return
        if QMessageBox.question(self,"Replay integration",f"Requeue delivery {row['id']} to {row['endpoint_id']}?")!=QMessageBox.StandardButton.Yes:return
        try:self.db.requeue_integration_delivery(row["id"]);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Replay integration",str(exc))

    def dead_letter_delivery(self):
        row=self.selected_delivery()
        if not row:return
        reason,ok=QInputDialog.getText(self,"Dead-letter delivery","Reason / operator note")
        if not ok:return
        try:self.db.dead_letter_integration_delivery(row["id"],reason);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Dead-letter delivery",str(exc))

    def requeue_dead_letters(self):
        endpoint=""
        row=selected_row(self.integration_table,self.integration_endpoints)
        if row and QMessageBox.question(self,"Requeue Dead Letters",f"Requeue only dead letters for {row.endpoint_id}?\nChoose No to requeue all endpoints.")==QMessageBox.StandardButton.Yes:
            endpoint=row.endpoint_id
        try:
            count=self.db.requeue_dead_letters(endpoint);self.refresh()
            QMessageBox.information(self,"Requeue Dead Letters",f"Requeued {count} delivery(s).")
        except Exception as exc:QMessageBox.critical(self,"Requeue Dead Letters",str(exc))

    def current(self):return selected_row(self.table,self.rows)

    def add(self):
        d=UserDialog(self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.create_user(d.username.text(),d.name.text(),d.password.text(),d.role.currentText());self.refresh()
            except Exception as exc:QMessageBox.critical(self,"User",str(exc))

    def role(self):
        row=self.current()
        if not row:return
        val,ok=QInputDialog.getItem(self,"Role","Role",list(ROLE_PERMISSIONS),list(ROLE_PERMISSIONS).index(row.role) if row.role in ROLE_PERMISSIONS else 0,False)
        if ok:self.db.update_user(row.username,role=val);self.refresh()

    def toggle(self):
        row=self.current()
        if row:self.db.update_user(row.username,active=not row.active);self.refresh()

    def reset(self):
        row=self.current()
        if not row:return
        pw,ok=QInputDialog.getText(self,"Password","New password",QLineEdit.EchoMode.Password)
        if ok:
            try:self.db.update_user(row.username,password=pw);QMessageBox.information(self,"Password","Password updated and login lockout cleared.");self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Password",str(exc))

    def unlock(self):
        row=self.current()
        if not row:return
        try:
            self.db.unlock_user(row.username,self.user["username"],WORKSTATION)
            QMessageBox.information(self,"Login","Login lockout cleared.")
            self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Login",str(exc))

    def override(self):
        row=self.current()
        if not row:return
        perm,ok=QInputDialog.getItem(self,"Permission Override","Permission",PERMISSIONS,0,False)
        if not ok:return
        choice,ok=QInputDialog.getItem(self,"Permission Override",f"{row.username}: {perm}",["Allow","Deny","Use Role Default"],0,False)
        if ok:self.db.set_permission_override(row.username,perm,{"Allow":True,"Deny":False,"Use Role Default":None}[choice]);self.refresh()

    def manage_integration(self):
        row=selected_row(self.integration_table,self.integration_endpoints)
        d=IntegrationEndpointDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_integration_endpoint(d.data(),row.version if row else None);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Integration Endpoint",str(exc))

    def manage_certification(self):
        row=self.current()
        if not row:return
        code,ok=QInputDialog.getText(self,"Certification","Certification code")
        if not ok or not code.strip():return
        existing=next((x for x in self.db.list_technician_certifications(row.username) if x.cert_code==code.strip()),None)
        issuer,ok=QInputDialog.getText(self,"Certification","Issuer",text=existing.issuer if existing else "")
        if not ok:return
        days,ok=QInputDialog.getInt(self,"Certification","Validity days from today (0 = no expiry)",365,0,3650)
        if not ok:return
        note,ok=QInputDialog.getText(self,"Certification","Note",text=existing.note if existing else "")
        if not ok:return
        try:
            now=datetime.now()
            self.db.save_technician_certification({
                "username":row.username,"cert_code":code.strip(),"issuer":issuer.strip(),
                "issued_at":now,"expires_at":(now+timedelta(days=days)) if days else None,
                "active":True,"note":note.strip(),
            },existing.version if existing else None)
            self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Certification",str(exc))

    def manage_scope(self):
        row=self.current()
        if not row:return
        current=self.db.user_access_policy(row.username)
        current_mode=current.scope_mode if current else "UNRESTRICTED"
        mode,ok=QInputDialog.getItem(self,"Access Scope","Scope mode",["UNRESTRICTED","RESTRICTED"],0 if current_mode=="UNRESTRICTED" else 1,False)
        if not ok:return
        try:self.db.set_user_access_policy(row.username,mode)
        except Exception as exc:QMessageBox.critical(self,"Access Scope",str(exc));return
        if mode=="UNRESTRICTED":self.refresh();return
        scope_type,ok=QInputDialog.getItem(self,"Access Scope","Grant scope by",["NODE","EQUIPMENT"],0,False)
        if not ok:self.refresh();return
        if scope_type=="NODE":
            items=[f"{n.node_code} — {n.node_type}: {n.name}" for n in self.db.list_factory_nodes()]
            if not items:QMessageBox.warning(self,"Access Scope","No factory hierarchy nodes exist.");return
            choice,ok=QInputDialog.getItem(self,"Factory Scope","Node",items,0,False)
            if not ok:return
            key=choice.split(" — ",1)[0]
        else:
            items=[e.equipment_id for e in self.db.list_equipment()]
            choice,ok=QInputDialog.getItem(self,"Equipment Scope","Equipment",items,0,False)
            if not ok:return
            key=choice
        perms=["*"]+PERMISSIONS
        perm,ok=QInputDialog.getItem(self,"Access Scope","Permission within scope",perms,0,False)
        if not ok:return
        try:
            self.db.add_user_scope(row.username,scope_type,key,perm)
            self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Access Scope",str(exc))

    def clear_scopes(self):
        row=self.current()
        if not row:return
        if QMessageBox.question(self,"Clear Scopes",f"Clear all explicit scopes for {row.username}?")!=QMessageBox.StandardButton.Yes:return
        self.db.clear_user_scopes(row.username);self.refresh()

    def create_backup(self):
        postgres=self.db.url.startswith("postgresql")
        filt="PostgreSQL Backup (*.dump)" if postgres else "SQLite Backup (*.db)"
        default=str(Path.cwd()/("equipment_backup.dump" if postgres else "equipment_backup.db"))
        path,_=QFileDialog.getSaveFileName(self,"Create Database Backup",default,filt)
        if not path:return
        try:
            result=create_backup(self.db.url,path)
            self.db.audit(self.user["username"],"DATABASE_BACKUP","SYSTEM",result["path"],detail=result["verification"],workstation=WORKSTATION)
            QMessageBox.information(self,"Backup",f"Verified backup created.\n{result['path']}\n{result['size_bytes']} bytes\n{result['verification']}")
        except Exception as exc:QMessageBox.critical(self,"Backup",str(exc))

    def verify_backup(self):
        filt="PostgreSQL Backup (*.dump)" if self.db.url.startswith("postgresql") else "SQLite Backup (*.db)"
        path,_=QFileDialog.getOpenFileName(self,"Verify Database Backup","",filt)
        if not path:return
        ok,detail=verify_backup(self.db.url,path)
        if ok:QMessageBox.information(self,"Backup Verification","PASS — "+detail)
        else:QMessageBox.critical(self,"Backup Verification","FAIL — "+detail)


class AlarmPage(QWidget):
    open_incident=Signal(str,str)
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.rows=[];self.pareto=[];self.bursts=[]
        policy=db.alarm_burst_policy()
        self.burst_window=QSpinBox();self.burst_window.setRange(1,86400);self.burst_window.setValue(int(policy["window_seconds"]));self.burst_window.setSuffix(" s");self.burst_window.valueChanged.connect(self.refresh)
        self.burst_count=QSpinBox();self.burst_count.setRange(2,1000);self.burst_count.setValue(int(policy["threshold_count"]))
        self.burst_severity=QComboBox();self.burst_severity.addItems(["INFO","LOW","WARNING","MEDIUM","HIGH","CRITICAL"]);self.burst_severity.setCurrentText(str(policy["min_severity"]).upper())
        self.burst_auto=QCheckBox("Auto workflow");self.burst_auto.setChecked(bool(policy["auto_trigger"]))
        self.save_burst=QPushButton("Save Burst Policy");self.save_burst.clicked.connect(self.save_burst_policy)
        self.save_burst.setEnabled(db.has_permission(user,"workflow.override") or db.has_permission(user,"user.admin") or user.get("role")=="Administrator")
        v=QVBoxLayout(self);h=QHBoxLayout();title=QLabel("Equipment Alarms / Events");title.setStyleSheet("font-size:18pt;font-weight:700")
        self.eq=QLineEdit();self.eq.setPlaceholderText("Equipment filter");active=QCheckBox("Active only");active.setChecked(True);self.active_only=active
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh);ack=QPushButton("Acknowledge");ack.clicked.connect(self.acknowledge)
        create_inc=QPushButton("Create Incident");create_inc.clicked.connect(self.create_incident)
        link_inc=QPushButton("Link Existing");link_inc.clicked.connect(self.link_incident)
        open_inc=QPushButton("Open Incident");open_inc.clicked.connect(self.open_related_incident)
        burst_inc=QPushButton("Create Burst Incident");burst_inc.clicked.connect(self.create_burst_incident)
        manual=QPushButton("Record Manual Alarm");manual.clicked.connect(self.manual_alarm)
        can_ticket=db.has_permission(user,"ticket.edit");manual.setEnabled(can_ticket);create_inc.setEnabled(can_ticket);link_inc.setEnabled(can_ticket);burst_inc.setEnabled(can_ticket)
        h.addWidget(title);h.addStretch(1);h.addWidget(QLabel("Burst"));h.addWidget(self.burst_window);h.addWidget(QLabel("Count"));h.addWidget(self.burst_count);h.addWidget(QLabel("Min sev"));h.addWidget(self.burst_severity);h.addWidget(self.burst_auto);h.addWidget(self.save_burst);h.addWidget(self.eq);h.addWidget(active);h.addWidget(refresh);h.addWidget(ack);h.addWidget(create_inc);h.addWidget(link_inc);h.addWidget(open_inc);h.addWidget(burst_inc);h.addWidget(manual);v.addLayout(h)
        self.burst_policy_status=QLabel();self.burst_policy_status.setStyleSheet("color:#647581");v.addWidget(self.burst_policy_status)
        tabs=QTabWidget()
        wa=QWidget();va=QVBoxLayout(wa);self.table=make_table(["Event","Equipment","Alarm Code","Severity","Message","Source","State","Occurred","Ack By","Ack At","Cleared","Ticket"]);self.table.itemSelectionChanged.connect(self.load_attachment);va.addWidget(self.table);tabs.addTab(wa,"Alarm History")
        wp=QWidget();vp=QVBoxLayout(wp);self.pareto_table=make_table(["Alarm Code","Message","Count"]);vp.addWidget(self.pareto_table);tabs.addTab(wp,"30-Day Pareto")
        wb=QWidget();vb=QVBoxLayout(wb);self.burst_table=make_table(["Burst","Equipment","Alarm Code","Severity","Count","First Seen","Last Seen","Duration s","Source Events"]);vb.addWidget(self.burst_table);tabs.addTab(wb,"Correlated Bursts")
        self.attachments=AttachmentPanel(db,user);tabs.addTab(self.attachments,"Evidence / Attachments")
        v.addWidget(tabs);self.eq.textChanged.connect(self.refresh);self.active_only.stateChanged.connect(self.refresh);self.refresh()

    def refresh(self):
        equipment=self.eq.text().strip()
        self.rows=self.db.list_alarms(equipment,active_only=self.active_only.isChecked())
        fill_table(self.table,self.rows,["event_key","equipment_id","alarm_code","severity","message","source","state","occurred_at","acknowledged_by","acknowledged_at","cleared_at","related_ticket"])
        self.pareto=self.db.alarm_pareto(30,equipment)
        self.bursts=correlate_alarm_bursts([{"id":row.event_key,"equipment_id":row.equipment_id,"alarm_code":row.alarm_code,"severity":row.severity,"occurred_at":row.occurred_at} for row in self.rows],window_seconds=self.burst_window.value())
        self.burst_table.setRowCount(len(self.bursts))
        for r,burst in enumerate(self.bursts):
            values=[burst.burst_key,burst.equipment_id,burst.alarm_code,burst.severity,burst.count,burst.first_seen,burst.last_seen,f"{burst.duration_seconds:.0f}",", ".join(burst.alarm_ids)]
            for col,value in enumerate(values):self.burst_table.setItem(r,col,ti(value))
        self.pareto_table.setRowCount(len(self.pareto))
        for r,row in enumerate(self.pareto):
            for col,key in enumerate(["alarm_code","message","count"]):self.pareto_table.setItem(r,col,ti(row.get(key,"")))
        qualifying=sum(1 for b in self.bursts if b.count>=self.burst_count.value() and self.db._alarm_severity_rank(b.severity)>=self.db._alarm_severity_rank(self.burst_severity.currentText()))
        self.burst_policy_status.setText(f"Plant burst policy: {self.burst_count.value()} alarms within {self.burst_window.value()} s · min {self.burst_severity.currentText()} · auto workflow {'ON' if self.burst_auto.isChecked() else 'OFF'} · {qualifying} displayed burst(s) meet threshold")
        self.load_attachment()

    def save_burst_policy(self):
        try:
            self.db.save_alarm_burst_policy(
                self.burst_window.value(),self.burst_count.value(),
                self.burst_severity.currentText(),self.burst_auto.isChecked(),
            )
            QMessageBox.information(self,"Alarm burst policy","Plant alarm burst policy saved.")
            self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Alarm burst policy",str(exc))

    def load_attachment(self):
        row=selected_row(self.table,self.rows)
        self.attachments.set_entity("ALARM",row.event_key,row.equipment_id) if row else self.attachments.set_entity("","")

    def acknowledge(self):
        row=selected_row(self.table,self.rows)
        if not row:return
        try:self.db.acknowledge_alarm(row.event_key,self.user["username"]);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Alarm",str(exc))

    def create_incident(self):
        row=selected_row(self.table,self.rows)
        if not row:return
        if row.related_ticket:
            self.open_incident.emit(row.related_ticket,row.equipment_id);return
        if QMessageBox.question(self,"Create Incident",f"Create a governed incident from alarm {row.alarm_code} on {row.equipment_id}?")!=QMessageBox.StandardButton.Yes:return
        try:
            ticket=self.db.create_incident_from_alarm(row.event_key,self.user["username"],owner=self.user["username"],workstation=WORKSTATION)
            self.refresh();self.open_incident.emit(ticket.ticket_no,ticket.equipment_id)
        except Exception as exc:QMessageBox.critical(self,"Create Incident",str(exc))

    def create_burst_incident(self):
        burst=selected_row(self.burst_table,self.bursts)
        if not burst:return
        if QMessageBox.question(self,"Create Burst Incident",f"Create one incident for {burst.count} {burst.alarm_code} alarms on {burst.equipment_id}?")!=QMessageBox.StandardButton.Yes:return
        try:
            ticket=self.db.create_incident_from_alarm_burst(list(burst.alarm_ids),self.user["username"],owner=self.user["username"],workstation=WORKSTATION)
            self.refresh();self.open_incident.emit(ticket.ticket_no,ticket.equipment_id)
        except Exception as exc:QMessageBox.critical(self,"Create Burst Incident",str(exc))

    def link_incident(self):
        row=selected_row(self.table,self.rows)
        if not row:return
        candidates=[t for t in self.db.list_tickets() if t.equipment_id==row.equipment_id and t.status not in {"Closed","Cancelled"}]
        if not candidates:
            QMessageBox.information(self,"Link Incident","No open incidents exist for this equipment.");return
        labels=[f"{t.ticket_no} — {t.priority} — {t.title}" for t in candidates]
        choice,ok=QInputDialog.getItem(self,"Link Incident",f"Open incident for {row.equipment_id}",labels,0,False)
        if not ok:return
        ticket=candidates[labels.index(choice)]
        try:self.db.link_alarm_to_ticket(row.event_key,ticket.ticket_no,self.user["username"],WORKSTATION);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Link Incident",str(exc))

    def open_related_incident(self):
        row=selected_row(self.table,self.rows)
        if not row:return
        if not row.related_ticket:
            QMessageBox.information(self,"Open Incident","This alarm is not linked to an incident.");return
        self.open_incident.emit(row.related_ticket,row.equipment_id)

    def manual_alarm(self):
        equipment,ok=QInputDialog.getText(self,"Manual Alarm","Equipment ID")
        if not ok or not equipment.strip():return
        code,ok=QInputDialog.getText(self,"Manual Alarm","Alarm code")
        if not ok or not code.strip():return
        message,ok=QInputDialog.getText(self,"Manual Alarm","Message")
        if not ok:return
        severity,ok=QInputDialog.getItem(self,"Manual Alarm","Severity",["Info","Warning","Critical"],1,False)
        if not ok:return
        try:self.db.ingest_alarm(equipment.strip(),code.strip(),severity=severity,message=message.strip(),source="Manual");self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Alarm",str(exc))


class ReliabilityPage(QWidget):
    def __init__(self,db):
        super().__init__(); self.db=db; self.rows=[]
        v=QVBoxLayout(self); h=QHBoxLayout()
        title=QLabel("Equipment Reliability"); title.setStyleSheet("font-size:18pt;font-weight:700")
        self.days=QSpinBox(); self.days.setRange(1,3650); self.days.setValue(30); self.days.setSuffix(" days")
        refresh=QPushButton("Refresh"); refresh.clicked.connect(self.refresh)
        h.addWidget(title); h.addStretch(1); h.addWidget(QLabel("Period")); h.addWidget(self.days); h.addWidget(refresh); v.addLayout(h)
        note=QLabel("Metrics are derived from governed equipment state events. Unplanned downtime is counted when the state class is UNPLANNED_DOWNTIME.")
        note.setWordWrap(True); note.setStyleSheet("color:#5a6670"); v.addWidget(note)
        self.table=make_table(["Equipment","Availability %","Failures","Unplanned h","Planned h","Total Down h","MTTR h","MTBF h","Current State"])
        v.addWidget(self.table); self.refresh()

    def refresh(self):
        try:self.rows=self.db.reliability_report(self.days.value())
        except Exception as exc:QMessageBox.critical(self,"Reliability",str(exc));return
        self.table.setRowCount(len(self.rows))
        fields=["equipment_id","availability_pct","failure_count","unplanned_downtime_hours","planned_downtime_hours","downtime_hours","mttr_hours","mtbf_hours","current_state"]
        for r,row in enumerate(self.rows):
            for col,field in enumerate(fields):
                value=row.get(field,"")
                if isinstance(value,float): value=f"{value:.2f}"
                self.table.setItem(r,col,ti(value))


class MainWindow(QMainWindow):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;configure_productivity_context(db,user["username"]);self.setWindowTitle(APP_TITLE);self.resize(1450,850);root=QWidget();self.setCentralWidget(root);h=QHBoxLayout(root);self.nav=QListWidget();self.nav.setFixedWidth(210);self.stack=QStackedWidget();h.addWidget(self.nav);h.addWidget(self.stack,1)
        self.pages=[]
        def add(name,page):self.nav.addItem(name);self.stack.addWidget(page);self.pages.append(page)
        self.dashboard=DashboardPage(db);add("Dashboard",self.dashboard);add("Equipment",EquipmentPage(db,user));self.layout=LayoutPage(db,user);add("Layout / Map",self.layout);add("PM",PMPage(db,user));add("Issue Tickets",TicketPage(db,user));add("Alarms / Events",AlarmPage(db,user));add("Qualification",QualificationPage(db,user));add("Reliability",ReliabilityPage(db));add("Disposition / Release",ControlPage(db,user));add("Work / Labor",WorkLogPage(db,user));add("Endorsements",EndorsementPage(db,user));self.inventory=InventoryPage(db,user);add("Inventory",self.inventory);add("Documents",DocumentPage(db,user));add("Administration",AdminPage(db,user))
        self.inventory.show_map_part.connect(self.show_part_map);self.nav.currentRowChanged.connect(self.stack.setCurrentIndex);self.nav.setCurrentRow(0)
        self.statusBar().showMessage(f"{user['display_name']} — {user['role']} — {WORKSTATION}")
        refresh=QAction("Refresh",self);refresh.setShortcut(QKeySequence("F5"));refresh.triggered.connect(self.refresh_current);self.addAction(refresh);self.timer=QTimer(self);self.timer.timeout.connect(self.dashboard.refresh);self.timer.start(30000)
    def show_part_map(self,part):self.layout.highlight_inventory(part);self.nav.setCurrentRow(2)
    def refresh_current(self):
        p=self.stack.currentWidget()
        if hasattr(p,"refresh"):p.refresh()


def main():
    configure_logging("ems-main");install_exception_hook("ems-main")
    app=QApplication(sys.argv);app.setStyleSheet(STYLE);db=Database()
    if not db.has_users():
        first=FirstAdminDialog(db)
        if first.exec()!=QDialog.DialogCode.Accepted:return 1
    login=LoginDialog(db)
    if login.exec()!=QDialog.DialogCode.Accepted:return 0
    w=MainWindow(db,login.user);w.show();return app.exec()


if __name__=="__main__":raise SystemExit(main())
