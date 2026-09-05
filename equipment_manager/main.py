from __future__ import annotations

import json
import os
import socket
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene,
    QGraphicsTextItem, QGraphicsView, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMessageBox, QPushButton, QSpinBox, QStackedWidget, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QInputDialog,
)

from database import Database, PERMISSIONS, ROLE_PERMISSIONS
from services import (
    auto_mapping, calculate_next_due, copy_clipboard_image, dataframe_to_pm_backlog,
    dataframe_to_pm_specs, evaluate_measurement, pm_parts_readiness, read_clipboard_table,
    read_table, readonly_open_copy, workbook_sheets, workload_by_day,
)

APP_TITLE = "Equipment Management System"
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


def make_table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(); t.setColumnCount(len(headers)); t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setAlternatingRowColors(True)
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
        user = self.db.authenticate(self.username.text(), self.password.text())
        if not user: QMessageBox.warning(self, "Login", "Invalid username/password or inactive account."); return
        self.user = user; self.db.audit(user["username"], "LOGIN", "SESSION", WORKSTATION, workstation=WORKSTATION); self.accept()


class MetricCard(QWidget):
    def __init__(self, label: str):
        super().__init__(); self.setStyleSheet("background:white;border:1px solid #d9dee3;border-radius:6px;")
        v = QVBoxLayout(self); self.value = QLabel("0"); self.value.setStyleSheet("font-size:24pt;font-weight:700;color:#16354b;border:0"); t = QLabel(label); t.setStyleSheet("color:#5a6670;border:0"); v.addWidget(self.value); v.addWidget(t)


class DashboardPage(QWidget):
    def __init__(self, db: Database):
        super().__init__(); self.db = db; v = QVBoxLayout(self); title = QLabel("Operational Dashboard"); title.setStyleSheet("font-size:18pt;font-weight:700"); v.addWidget(title); g = QGridLayout(); v.addLayout(g)
        defs = [("equipment_total","Equipment"),("equipment_down","Down"),("equipment_hold","On Hold"),("pm_open","Open PM"),("pm_overdue","PM Overdue"),("tickets_open","Open Tickets"),("tickets_critical","P1/P2 Tickets"),("inventory_low","Low Stock"),("release_pending","Release Pending"),("reservations_active","Part Reservations"),("endorsements_open","Endorsements"),("dispositions_active","Active Dispositions")]
        self.cards = {}
        for i, (key, label) in enumerate(defs): self.cards[key] = MetricCard(label); g.addWidget(self.cards[key], i//4, i%4)
        self.updated = QLabel(); v.addWidget(self.updated); v.addStretch(1); self.refresh()
    def refresh(self):
        for k, val in self.db.dashboard_counts().items():
            if k in self.cards: self.cards[k].value.setText(str(val))
        self.updated.setText("Updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class EquipmentDialog(QDialog):
    def __init__(self, row=None, parent=None):
        super().__init__(parent); self.row = row; self.setWindowTitle("Equipment"); f = QFormLayout(self); self.fields = {}
        for k, label in [("equipment_id","Equipment ID"),("name","Name"),("equipment_type","Type"),("manufacturer","Manufacturer"),("model","Model"),("serial_number","Serial"),("asset_number","Asset Number"),("site","Site"),("building","Building"),("floor","Floor"),("area","Area"),("line_cell","Line / Bay / Cell"),("owner","Owner")]:
            w = QLineEdit(); self.fields[k] = w; f.addRow(label, w)
        self.status = QComboBox(); self.status.addItems(["Available","Production","Down","PM","Engineering","Standby","Waiting Parts","Waiting Vendor","Qualification","Hold","Restricted","Offline","Decommissioned"])
        self.disposition = QComboBox(); self.disposition.addItems(["Released","Released With Conditions","Restricted Use","Engineering Use","Monitoring","Hold","PM Hold","Quality Hold","Safety Hold","Waiting Parts","Waiting Vendor","Qualification","Decommission","Scrap"])
        self.criticality = QComboBox(); self.criticality.addItems(["Low","Normal","High","Critical"]); self.x = QDoubleSpinBox(); self.y = QDoubleSpinBox(); self.x.setRange(-100000,100000); self.y.setRange(-100000,100000)
        f.addRow("Status", self.status); f.addRow("Disposition", self.disposition); f.addRow("Criticality", self.criticality); f.addRow("Map X", self.x); f.addRow("Map Y", self.y)
        b = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b)
        if row:
            for k, w in self.fields.items(): w.setText(str(getattr(row,k,"") or ""))
            self.fields["equipment_id"].setReadOnly(True); self.status.setCurrentText(row.status); self.disposition.setCurrentText(row.disposition); self.criticality.setCurrentText(row.criticality); self.x.setValue(row.map_x); self.y.setValue(row.map_y)
    def data(self):
        d = {k:w.text().strip() for k,w in self.fields.items()}; d.update(status=self.status.currentText(), disposition=self.disposition.currentText(), criticality=self.criticality.currentText(), map_x=self.x.value(), map_y=self.y.value()); return d


class EquipmentPage(QWidget):
    def __init__(self, db, user):
        super().__init__(); self.db=db; self.user=user; self.rows=[]; v=QVBoxLayout(self); h=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Search equipment..."); self.search.textChanged.connect(self.refresh); add=QPushButton("Add"); edit=QPushButton("Edit"); add.clicked.connect(self.add); edit.clicked.connect(self.edit); add.setEnabled(db.has_permission(user,"equipment.edit")); edit.setEnabled(db.has_permission(user,"equipment.edit")); h.addWidget(self.search,1); h.addWidget(add); h.addWidget(edit); v.addLayout(h)
        self.table=make_table(["ID","Name","Type","Area","Line/Cell","Status","Disposition","Owner","Criticality","Ver"]); self.table.doubleClicked.connect(self.edit); v.addWidget(self.table); self.refresh()
    def refresh(self):
        self.rows=self.db.list_equipment(self.search.text().strip()); fill_table(self.table,self.rows,["equipment_id","name","equipment_type","area","line_cell","status","disposition","owner","criticality","version"])
    def add(self):
        d=EquipmentDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try: row=self.db.save_equipment(d.data()); self.db.audit(self.user["username"],"CREATE","EQUIPMENT",row.equipment_id,workstation=WORKSTATION); self.refresh()
            except Exception as exc: QMessageBox.critical(self,"Equipment",str(exc))
    def edit(self):
        row=selected_row(self.table,self.rows)
        if not row:return
        d=EquipmentDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_equipment(d.data(),row.version); self.db.audit(self.user["username"],"UPDATE","EQUIPMENT",row.equipment_id,workstation=WORKSTATION); self.refresh()
            except Exception as exc: QMessageBox.critical(self,"Equipment",str(exc))


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


class PMExecutionDialog(QDialog):
    def __init__(self,db,user,task,parent=None):
        super().__init__(parent); self.db=db; self.user=user; self.task=task; self.execrow=db.start_pm_execution(task.id,user["username"]); self.specs=db.list_pm_specs(task.pm_id); self.results={r.step_no:r for r in db.list_pm_results(self.execrow.id)}; self.setWindowTitle(f"Execute PM — {task.equipment_id} / {task.pm_id}"); self.resize(1050,650); v=QVBoxLayout(self); self.table=make_table(["Step","Activity","Type","Target","Low","High","Value","Result","Evidence"]); self.table.doubleClicked.connect(self.enter_result); v.addWidget(self.table); h=QHBoxLayout(); enter=QPushButton("Enter Selected Result"); enter.clicked.connect(self.enter_result); paste=QPushButton("Paste Image Evidence"); paste.clicked.connect(self.paste_evidence); complete=QPushButton("Complete PM"); complete.clicked.connect(self.complete); h.addWidget(enter); h.addWidget(paste); h.addStretch(1); h.addWidget(complete); v.addLayout(h); self.refresh()
    def refresh(self):
        self.results={r.step_no:r for r in self.db.list_pm_results(self.execrow.id)}; self.table.setRowCount(len(self.specs))
        for r,s in enumerate(self.specs):
            res=self.results.get(s.step_no); vals=[s.step_no,s.activity,s.input_type,s.target,s.spec_low,s.spec_high,res.value_text if res else "",res.result if res else "",Path(res.evidence_path).name if res and res.evidence_path else ""]
            for c,val in enumerate(vals):self.table.setItem(r,c,ti(val))
    def selected_spec(self):
        r=self.table.currentRow(); return self.specs[r] if 0<=r<len(self.specs) else None
    def enter_result(self):
        spec=self.selected_spec()
        if not spec:return
        current=self.results.get(spec.step_no); prompt="Numeric value" if spec.input_type=="Numeric" else "Result / text"
        val,ok=QInputDialog.getText(self,"PM Result",prompt,text=current.value_text if current else "")
        if not ok:return
        num=None
        if spec.input_type=="Numeric":
            try:num=float(val)
            except Exception: QMessageBox.warning(self,"PM","Numeric value required."); return
        result=evaluate_measurement(spec,val,num)
        try:self.db.save_pm_result(self.execrow.id,spec.step_no,{"value_text":val,"value_numeric":num,"result":result,"entered_by":self.user["username"],"evidence_path":current.evidence_path if current else ""},current.version if current else None); self.refresh()
        except Exception as exc: QMessageBox.critical(self,"PM",str(exc))
    def paste_evidence(self):
        spec=self.selected_spec()
        if not spec:return
        img=QApplication.clipboard().image()
        if img.isNull(): QMessageBox.warning(self,"Clipboard","Clipboard does not contain an image."); return
        try:
            path=copy_clipboard_image(img,FILE_ROOT,"PM",f"{self.task.id}_step_{spec.step_no}"); current=self.results.get(spec.step_no); data={"value_text":current.value_text if current else "Evidence attached","value_numeric":current.value_numeric if current else None,"result":current.result if current else "RECORDED","entered_by":self.user["username"],"evidence_path":path}; self.db.save_pm_result(self.execrow.id,spec.step_no,data,current.version if current else None); self.refresh()
        except Exception as exc: QMessageBox.critical(self,"Evidence",str(exc))
    def complete(self):
        try:self.db.complete_pm_execution(self.execrow.id,self.user["username"]); self.accept()
        except Exception as exc: QMessageBox.critical(self,"Complete PM",str(exc))


class PMPage(QWidget):
    def __init__(self,db,user):
        super().__init__(); self.db=db; self.user=user; self.defs=[]; self.tasks=[]; self.specrows=[]; v=QVBoxLayout(self); self.tabs=QTabWidget(); v.addWidget(self.tabs)
        wd=QWidget(); vd=QVBoxLayout(wd); hd=QHBoxLayout(); add=QPushButton("Add Definition"); edit=QPushButton("Edit Definition"); gen=QPushButton("Generate Next PM"); ready=QPushButton("Parts Readiness"); add.clicked.connect(self.add_def); edit.clicked.connect(self.edit_def); gen.clicked.connect(self.generate_next); ready.clicked.connect(self.parts_ready); canedit=db.has_permission(user,"pm.edit"); add.setEnabled(canedit); edit.setEnabled(canedit); gen.setEnabled(canedit); hd.addWidget(add);hd.addWidget(edit);hd.addWidget(gen);hd.addWidget(ready);hd.addStretch(1);vd.addLayout(hd);self.def_table=make_table(["PM ID","Name","Equipment","Type","Frequency","Unit","Anchor","Early","Grace","Hours","Parts","Ver"]);vd.addWidget(self.def_table);self.tabs.addTab(wd,"Definitions")
        wb=QWidget(); vb=QVBoxLayout(wb); hb=QHBoxLayout(); imp=QPushButton("Import Excel/CSV"); paste=QPushButton("Paste from Excel"); execute=QPushButton("Execute Selected"); forecast=QPushButton("Workload Forecast"); imp.clicked.connect(self.import_backlog); paste.clicked.connect(self.paste_backlog); execute.clicked.connect(self.execute); forecast.clicked.connect(self.forecast); imp.setEnabled(canedit); paste.setEnabled(canedit); execute.setEnabled(db.has_permission(user,"pm.execute")); [hb.addWidget(x) for x in [imp,paste,execute,forecast]];hb.addStretch(1);vb.addLayout(hb);self.task_table=make_table(["Equipment","PM ID","PM Name","Original Due","Scheduled","Status","Assigned","Hours","Priority","Ver"]);vb.addWidget(self.task_table);self.tabs.addTab(wb,"Backlog / Schedule")
        ws=QWidget(); vs=QVBoxLayout(ws); hs=QHBoxLayout(); ispec=QPushButton("Import Steps / Specs"); pspec=QPushButton("Paste Steps / Specs"); ispec.clicked.connect(self.import_specs); pspec.clicked.connect(self.paste_specs); ispec.setEnabled(canedit); pspec.setEnabled(canedit); hs.addWidget(ispec);hs.addWidget(pspec);hs.addStretch(1);vs.addLayout(hs);self.spec_table=make_table(["PM ID","Step","Activity","Method","Type","Unit","Target","CL","CH","LSL","USL","Rev"]);vs.addWidget(self.spec_table);self.tabs.addTab(ws,"Checklist / Specs")
        self.refresh()
    def refresh(self):
        self.defs=self.db.list_pm_definitions(); fill_table(self.def_table,self.defs,["pm_id","name","equipment_id","schedule_type","frequency_value","frequency_unit","anchor_mode","early_window_days","grace_days","estimated_hours","required_parts","version"])
        self.tasks=self.db.list_pm_tasks(); fill_table(self.task_table,self.tasks,["equipment_id","pm_id","pm_name","original_due_date","scheduled_date","status","assigned_to","estimated_hours","priority","version"])
        self.specrows=self.db.list_pm_specs(); fill_table(self.spec_table,self.specrows,["pm_id","step_no","activity","method","input_type","unit","target","control_low","control_high","spec_low","spec_high","revision"])
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
        mapping=auto_mapping(list(df.columns)); rows,errors=dataframe_to_pm_backlog(df,mapping)
        if not rows:QMessageBox.warning(self,"Import","No valid rows.\n"+"\n".join(errors[:10]));return
        if QMessageBox.question(self,"Import",f"Import {len(rows)} rows? Errors/warnings: {len(errors)}")!=QMessageBox.StandardButton.Yes:return
        for row in rows:self.db.upsert_pm_task(row)
        self.refresh();QMessageBox.information(self,"Import",f"Imported {len(rows)} rows; {len(errors)} skipped/warned.")
    def import_backlog(self):
        path,_=QFileDialog.getOpenFileName(self,"Import PM Backlog","","Excel/CSV (*.xlsx *.xlsm *.csv)")
        if not path:return
        try:s=self.choose_sheet(path); self._import_backlog_df(read_table(path,s)) if s is not None else None
        except Exception as exc:QMessageBox.critical(self,"Import",str(exc))
    def paste_backlog(self):
        try:self._import_backlog_df(read_clipboard_table(QApplication.clipboard().text()))
        except Exception as exc:QMessageBox.critical(self,"Paste",str(exc))
    def _import_specs_df(self,df):
        mapping=auto_mapping(list(df.columns)); default=""
        if "pm_id" not in mapping:
            default,ok=QInputDialog.getText(self,"PM ID","Enter PM ID for pasted/imported steps:")
            if not ok:return
        rows,warns=dataframe_to_pm_specs(df,mapping,default.strip())
        if not rows:QMessageBox.warning(self,"Import","No valid steps.\n"+"\n".join(warns[:10]));return
        revise=QMessageBox.question(self,"Revision","Create controlled revisions for existing steps?")==QMessageBox.StandardButton.Yes
        for row in rows:self.db.upsert_pm_spec(row,revise)
        self.refresh();QMessageBox.information(self,"Import",f"Imported {len(rows)} steps; warnings {len(warns)}")
    def import_specs(self):
        path,_=QFileDialog.getOpenFileName(self,"Import PM Specs","","Excel/CSV (*.xlsx *.xlsm *.csv)")
        if not path:return
        try:s=self.choose_sheet(path); self._import_specs_df(read_table(path,s)) if s is not None else None
        except Exception as exc:QMessageBox.critical(self,"Import",str(exc))
    def paste_specs(self):
        try:self._import_specs_df(read_clipboard_table(QApplication.clipboard().text()))
        except Exception as exc:QMessageBox.critical(self,"Paste",str(exc))
    def execute(self):
        row=selected_row(self.task_table,self.tasks)
        if not row:return
        d=PMExecutionDialog(self.db,self.user,row,self)
        if d.exec()==QDialog.DialogCode.Accepted:self.refresh()
    def forecast(self):
        data=workload_by_day([t for t in self.tasks if t.status not in {"Completed","Cancelled"}]); text="\n".join(f"{d}: {h:.1f} hr" for d,h in sorted(data.items())[:60]) or "No scheduled workload"; QMessageBox.information(self,"PM Workload Forecast",text)


class TicketDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Issue Ticket");f=QFormLayout(self);self.no=QLineEdit();self.eq=QLineEdit();self.title=QLineEdit();self.desc=QTextEdit();self.sev=QComboBox();self.sev.addItems(["S1","S2","S3","S4"]);self.prio=QComboBox();self.prio.addItems(["P1","P2","P3","P4"]);self.status=QComboBox();self.status.addItems(["Open","Assigned","Investigation","Waiting Parts","Waiting Vendor","Waiting Production","Monitoring","Resolved","Verification","Closed","Cancelled"]);self.owner=QLineEdit();self.root=QTextEdit();self.action=QTextEdit();self.verify=QTextEdit()
        for label,w in [("Ticket No",self.no),("Equipment ID",self.eq),("Title",self.title),("Description",self.desc),("Severity",self.sev),("Priority",self.prio),("Status",self.status),("Owner",self.owner),("Root Cause",self.root),("Corrective Action",self.action),("Verification",self.verify)]:f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:self.no.setText(row.ticket_no);self.no.setReadOnly(True);self.eq.setText(row.equipment_id);self.title.setText(row.title);self.desc.setPlainText(row.description);self.sev.setCurrentText(row.severity);self.prio.setCurrentText(row.priority);self.status.setCurrentText(row.status);self.owner.setText(row.owner);self.root.setPlainText(row.root_cause);self.action.setPlainText(row.corrective_action);self.verify.setPlainText(row.verification)
    def data(self,user):return {"ticket_no":self.no.text().strip(),"equipment_id":self.eq.text().strip(),"title":self.title.text().strip(),"description":self.desc.toPlainText().strip(),"severity":self.sev.currentText(),"priority":self.prio.currentText(),"status":self.status.currentText(),"owner":self.owner.text().strip(),"root_cause":self.root.toPlainText().strip(),"corrective_action":self.action.toPlainText().strip(),"verification":self.verify.toPlainText().strip(),"created_by":getattr(self.row,"created_by","") or user}


class InvestigationDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle("Investigation Step");f=QFormLayout(self);self.obs=QTextEdit();self.check=QTextEdit();self.result=QTextEdit();self.concl=QTextEdit();self.action=QTextEdit();self.evidence=QLineEdit();browse=QPushButton("Browse Evidence");browse.clicked.connect(self.browse);f.addRow("Observation",self.obs);f.addRow("Check Performed",self.check);f.addRow("Result",self.result);f.addRow("Conclusion",self.concl);f.addRow("Action",self.action);f.addRow("Evidence Path",self.evidence);f.addRow("",browse);b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
    def browse(self):
        p,_=QFileDialog.getOpenFileName(self,"Evidence");
        if p:self.evidence.setText(p)
    def data(self,user):return {"observation":self.obs.toPlainText().strip(),"check_performed":self.check.toPlainText().strip(),"result":self.result.toPlainText().strip(),"conclusion":self.concl.toPlainText().strip(),"action":self.action.toPlainText().strip(),"evidence_path":self.evidence.text().strip(),"entered_by":user}


class TicketPage(QWidget):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.rows=[];self.inv=[];v=QVBoxLayout(self);h=QHBoxLayout();add=QPushButton("New Ticket");edit=QPushButton("Edit Ticket");invest=QPushButton("Add Investigation Step");add.clicked.connect(self.add);edit.clicked.connect(self.edit);invest.clicked.connect(self.add_investigation);allowed=db.has_permission(user,"ticket.edit");add.setEnabled(allowed);edit.setEnabled(allowed);invest.setEnabled(allowed);h.addWidget(add);h.addWidget(edit);h.addWidget(invest);h.addStretch(1);v.addLayout(h);self.table=make_table(["Ticket","Equipment","Title","Severity","Priority","Status","Owner","Updated","Ver"]);self.table.itemSelectionChanged.connect(self.load_inv);v.addWidget(self.table,2);v.addWidget(QLabel("Investigation / troubleshooting history"));self.invtable=make_table(["#","Observation","Check","Result","Conclusion","Action","By","Time"]);v.addWidget(self.invtable,1);self.refresh()
    def refresh(self):self.rows=self.db.list_tickets();fill_table(self.table,self.rows,["ticket_no","equipment_id","title","severity","priority","status","owner","updated_at","version"]);self.load_inv()
    def add(self):
        d=TicketDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_ticket(d.data(self.user["username"]));self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Ticket",str(exc))
    def edit(self):
        row=selected_row(self.table,self.rows)
        if not row:return
        d=TicketDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_ticket(d.data(self.user["username"]),row.version);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Ticket",str(exc))
    def load_inv(self):
        row=selected_row(self.table,self.rows);self.inv=self.db.list_ticket_investigations(row.ticket_no) if row else [];fill_table(self.invtable,self.inv,["sequence","observation","check_performed","result","conclusion","action","entered_by","entered_at"])
    def add_investigation(self):
        row=selected_row(self.table,self.rows)
        if not row:return
        d=InvestigationDialog(self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.add_ticket_investigation(row.ticket_no,d.data(self.user["username"]));self.load_inv()
            except Exception as exc:QMessageBox.critical(self,"Investigation",str(exc))


class DispositionDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle("Equipment Disposition");f=QFormLayout(self);self.eq=QLineEdit();self.state=QComboBox();self.state.addItems(["Released With Conditions","Restricted Use","Engineering Use","Monitoring","Hold","PM Hold","Quality Hold","Safety Hold","Waiting Parts","Waiting Vendor","Qualification","Decommission","Scrap"]);self.reason=QTextEdit();self.rest=QTextEdit();self.criteria=QTextEdit();self.ticket=QLineEdit();f.addRow("Equipment",self.eq);f.addRow("State",self.state);f.addRow("Reason",self.reason);f.addRow("Restrictions",self.rest);f.addRow("Release Criteria",self.criteria);f.addRow("Related Ticket",self.ticket);b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
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
        p=self.db.release_precheck(self.eq.text().strip());self.checks["critical_tickets_cleared"].setChecked(p["critical_tickets_open"]==0);QMessageBox.information(self,"Precheck",f"Open P1/P2 tickets: {p['critical_tickets_open']}\nOverdue PM: {p['overdue_pm']}")
    def check_data(self):return {k:c.isChecked() for k,c in self.checks.items()}


class ControlPage(QWidget):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.disp=[];self.rel=[];v=QVBoxLayout(self);tabs=QTabWidget();v.addWidget(tabs)
        wd=QWidget();vd=QVBoxLayout(wd);bd=QPushButton("New Disposition");bd.clicked.connect(self.new_disp);bd.setEnabled(db.has_permission(user,"disposition.edit"));vd.addWidget(bd);self.dtable=make_table(["Equipment","State","Reason","Restrictions","Criteria","Ticket","Created By","Approved By","Effective"]);vd.addWidget(self.dtable);tabs.addTab(wd,"Disposition")
        wr=QWidget();vr=QVBoxLayout(wr);hr=QHBoxLayout();new=QPushButton("New Release Request");verify=QPushButton("Verify Selected");approve=QPushButton("Approve / Release");new.clicked.connect(self.new_release);verify.clicked.connect(self.verify_release);approve.clicked.connect(self.approve_release);new.setEnabled(db.has_permission(user,"release.verify") or db.has_permission(user,"disposition.edit"));verify.setEnabled(db.has_permission(user,"release.verify"));approve.setEnabled(db.has_permission(user,"release.approve"));hr.addWidget(new);hr.addWidget(verify);hr.addWidget(approve);hr.addStretch(1);vr.addLayout(hr);self.rtable=make_table(["ID","Equipment","Ticket","Status","Requested By","Verified By","Approved By","Requested","Ver"]);vr.addWidget(self.rtable);tabs.addTab(wr,"Release Verification");self.refresh()
    def refresh(self):self.disp=self.db.list_dispositions();fill_table(self.dtable,self.disp,["equipment_id","state","reason","restrictions","release_criteria","related_ticket","created_by","approved_by","effective_at"]);self.rel=self.db.list_release_requests();fill_table(self.rtable,self.rel,["id","equipment_id","related_ticket","status","requested_by","verified_by","approved_by","requested_at","version"])
    def new_disp(self):
        d=DispositionDialog(self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.set_disposition(d.data(self.user["username"]));self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Disposition",str(exc))
    def new_release(self):
        d=ReleaseDialog(self.db,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.create_release_request(d.eq.text().strip(),d.ticket.text().strip(),d.check_data(),d.notes.toPlainText().strip(),self.user["username"]);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Release",str(exc))
    def verify_release(self):
        row=selected_row(self.rtable,self.rel)
        if not row:return
        d=ReleaseDialog(self.db,self,row);d.eq.setReadOnly(True)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.verify_release(row.id,d.check_data(),self.user["username"],row.version);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Release",str(exc))
    def approve_release(self):
        row=selected_row(self.rtable,self.rel)
        if not row:return
        if QMessageBox.question(self,"Approve Release",f"Release {row.equipment_id} to service?")!=QMessageBox.StandardButton.Yes:return
        try:self.db.approve_release(row.id,self.user["username"],row.version);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Release",str(exc))


class EndorsementDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle("Endorsement / Handover");f=QFormLayout(self);self.no=QLineEdit("END-"+datetime.now().strftime("%Y%m%d-%H%M%S"));self.eq=QLineEdit();self.condition=QTextEdit();self.done=QTextEdit();self.pending=QTextEdit();self.rest=QTextEdit();self.next=QTextEdit();self.owner=QLineEdit();
        for label,w in [("Endorsement No",self.no),("Equipment",self.eq),("Current Condition",self.condition),("Work Completed",self.done),("Pending Work",self.pending),("Restrictions",self.rest),("Next Action",self.next),("Next Owner",self.owner)]:f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
    def data(self,user):return {"endorsement_no":self.no.text().strip(),"equipment_id":self.eq.text().strip(),"current_condition":self.condition.toPlainText().strip(),"work_completed":self.done.toPlainText().strip(),"pending_work":self.pending.toPlainText().strip(),"restrictions":self.rest.toPlainText().strip(),"next_action":self.next.toPlainText().strip(),"next_owner":self.owner.text().strip(),"created_by":user}


class EndorsementPage(QWidget):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.rows=[];v=QVBoxLayout(self);h=QHBoxLayout();add=QPushButton("New Endorsement");ack=QPushButton("Acknowledge Selected");add.clicked.connect(self.add);ack.clicked.connect(self.ack);allowed=db.has_permission(user,"endorsement.edit");add.setEnabled(allowed);ack.setEnabled(allowed);h.addWidget(add);h.addWidget(ack);h.addStretch(1);v.addLayout(h);self.table=make_table(["No","Equipment","Condition","Pending","Restrictions","Next Owner","Status","Created By","Ack By","Time"]);v.addWidget(self.table);self.refresh()
    def refresh(self):self.rows=self.db.list_endorsements();fill_table(self.table,self.rows,["endorsement_no","equipment_id","current_condition","pending_work","restrictions","next_owner","status","created_by","acknowledged_by","created_at"])
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
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Inventory Item");f=QFormLayout(self);self.part=QLineEdit();self.desc=QLineEdit();self.cat=QLineEdit();self.mfg=QLineEdit();self.model=QLineEdit();self.compat=QLineEdit();self.qty=QDoubleSpinBox();self.qty.setRange(0,1e9);self.minq=QDoubleSpinBox();self.minq.setRange(0,1e9);self.unit=QLineEdit("pcs");self.cond=QComboBox();self.cond.addItems(["Available","Reserved","Installed","In Use","Repair","Quarantine","Inspection Required","Expired","Obsolete","Scrap","Vendor"]);self.loc=QLineEdit();self.image=QLineEdit();self.notes=QTextEdit()
        for label,w in [("Part Number",self.part),("Description",self.desc),("Category",self.cat),("Manufacturer",self.mfg),("Model",self.model),("Compatible Equipment",self.compat),("Quantity",self.qty),("Minimum",self.minq),("Unit",self.unit),("Condition",self.cond),("Location Code",self.loc),("Image Path",self.image),("Notes",self.notes)]:f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        if row:self.part.setText(row.part_number);self.part.setReadOnly(True);self.desc.setText(row.description);self.cat.setText(row.category);self.mfg.setText(row.manufacturer);self.model.setText(row.model);self.compat.setText(row.compatible_equipment);self.qty.setValue(row.quantity);self.minq.setValue(row.min_quantity);self.unit.setText(row.unit);self.cond.setCurrentText(row.condition);self.loc.setText(row.location_code);self.loc.setReadOnly(True);self.image.setText(row.image_path);self.notes.setPlainText(row.notes)
    def data(self):return {"part_number":self.part.text().strip(),"description":self.desc.text().strip(),"category":self.cat.text().strip(),"manufacturer":self.mfg.text().strip(),"model":self.model.text().strip(),"compatible_equipment":self.compat.text().strip(),"quantity":self.qty.value(),"min_quantity":self.minq.value(),"unit":self.unit.text().strip() or "pcs","condition":self.cond.currentText(),"location_code":self.loc.text().strip(),"image_path":self.image.text().strip(),"notes":self.notes.toPlainText().strip()}


class InventoryPage(QWidget):
    show_map_part=Signal(str)
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.items=[];self.locs=[];self.res=[];v=QVBoxLayout(self);tabs=QTabWidget();v.addWidget(tabs)
        wi=QWidget();vi=QVBoxLayout(wi);hi=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText("Search part / description / location");self.search.textChanged.connect(self.refresh);add=QPushButton("Add Item");edit=QPushButton("Edit");consume=QPushButton("Consume");reserve=QPushButton("Reserve");show=QPushButton("Show on Map");add.clicked.connect(self.add_item);edit.clicked.connect(self.edit_item);consume.clicked.connect(self.consume);reserve.clicked.connect(self.reserve);show.clicked.connect(self.map_item);add.setEnabled(db.has_permission(user,"inventory.edit"));edit.setEnabled(db.has_permission(user,"inventory.edit"));consume.setEnabled(db.has_permission(user,"inventory.consume") or db.has_permission(user,"inventory.edit"));reserve.setEnabled(db.has_permission(user,"inventory.reserve"));hi.addWidget(self.search,1);[hi.addWidget(x) for x in [add,edit,consume,reserve,show]];vi.addLayout(hi);self.itable=make_table(["Part","Description","Qty","Min","Unit","Condition","Location","Image","Ver"]);vi.addWidget(self.itable);tabs.addTab(wi,"Inventory")
        wl=QWidget();vl=QVBoxLayout(wl);addl=QPushButton("Add Storage Location");addl.clicked.connect(self.add_loc);addl.setEnabled(db.has_permission(user,"inventory.edit"));vl.addWidget(addl);self.ltable=make_table(["Code","Name","Building","Floor","Area","Cabinet","Shelf","Bin","Image","Ver"]);vl.addWidget(self.ltable);tabs.addTab(wl,"Storage Locations")
        wr=QWidget();vr=QVBoxLayout(wr);rel=QPushButton("Release Selected Reservation");rel.clicked.connect(self.release_res);rel.setEnabled(db.has_permission(user,"inventory.reserve"));vr.addWidget(rel);self.rtable=make_table(["ID","Part","Location","Qty","PM Task","Equipment","Status","Reserved By","Time","Ver"]);vr.addWidget(self.rtable);tabs.addTab(wr,"Reservations");self.refresh()
    def refresh(self):self.items=self.db.list_inventory(self.search.text().strip());fill_table(self.itable,self.items,["part_number","description","quantity","min_quantity","unit","condition","location_code","image_path","version"]);self.locs=self.db.list_storage_locations();fill_table(self.ltable,self.locs,["location_code","name","building","floor","area","cabinet","shelf","drawer_bin","image_path","version"]);self.res=self.db.list_reservations();fill_table(self.rtable,self.res,["id","part_number","location_code","quantity","pm_task_id","equipment_id","status","reserved_by","reserved_at","version"])
    def add_item(self):
        d=InventoryDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_inventory_item(d.data());self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Inventory",str(exc))
    def edit_item(self):
        row=selected_row(self.itable,self.items)
        if not row:return
        d=InventoryDialog(row,self)
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
        super().__init__();self.db=db;self.user=user;self.rows=[];v=QVBoxLayout(self);h=QHBoxLayout();self.type=QLineEdit();self.type.setPlaceholderText("Entity type e.g. Equipment");self.key=QLineEdit();self.key.setPlaceholderText("Entity key");find=QPushButton("Filter");add=QPushButton("Link File");openb=QPushButton("Open Read-Only");find.clicked.connect(self.refresh);add.clicked.connect(self.add);openb.clicked.connect(self.open);add.setEnabled(db.has_permission(user,"document.link"));h.addWidget(self.type);h.addWidget(self.key);h.addWidget(find);h.addWidget(add);h.addWidget(openb);v.addLayout(h);self.table=make_table(["Entity","Key","Type","Title","Revision","Status","Path","Added By","Time"]);v.addWidget(self.table);self.refresh()
    def refresh(self):self.rows=self.db.list_documents(self.type.text().strip(),self.key.text().strip());fill_table(self.table,self.rows,["entity_type","entity_key","document_type","title","revision","status","path","added_by","added_at"])
    def add(self):
        p,_=QFileDialog.getOpenFileName(self,"Link Existing File")
        if not p:return
        title,ok=QInputDialog.getText(self,"Title","Document title",text=Path(p).name)
        if not ok:return
        dtype,ok=QInputDialog.getItem(self,"Type","Document type",["SOP","Manual","Drawing","Report","Engineering Analysis","Vendor Report","Calibration Certificate","Image","Log","Spreadsheet","Other"],0,False)
        if not ok:return
        self.db.add_document({"entity_type":self.type.text().strip() or "General","entity_key":self.key.text().strip(),"document_type":dtype,"title":title,"path":p,"status":"Active","added_by":self.user["username"]});self.refresh()
    def open(self):
        row=selected_row(self.table,self.rows)
        if row:
            try:readonly_open_copy(row.path)
            except Exception as exc:QMessageBox.critical(self,"Open",str(exc))


class UserDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle("New User");f=QFormLayout(self);self.username=QLineEdit();self.name=QLineEdit();self.password=QLineEdit();self.password.setEchoMode(QLineEdit.EchoMode.Password);self.role=QComboBox();self.role.addItems(list(ROLE_PERMISSIONS));f.addRow("Username",self.username);f.addRow("Display Name",self.name);f.addRow("Password",self.password);f.addRow("Role",self.role);b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)


class AdminPage(QWidget):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.rows=[];v=QVBoxLayout(self);h=QHBoxLayout();add=QPushButton("Add User");role=QPushButton("Change Role");toggle=QPushButton("Enable / Disable");reset=QPushButton("Reset Password");override=QPushButton("Permission Override");add.clicked.connect(self.add);role.clicked.connect(self.role);toggle.clicked.connect(self.toggle);reset.clicked.connect(self.reset);override.clicked.connect(self.override);allowed=db.has_permission(user,"user.admin") or user.get("role")=="Administrator";[x.setEnabled(allowed) for x in [add,role,toggle,reset,override]];[h.addWidget(x) for x in [add,role,toggle,reset,override]];h.addStretch(1);v.addLayout(h);self.table=make_table(["Username","Display Name","Role","Active","Last Login","Created"]);v.addWidget(self.table);self.refresh()
    def refresh(self):self.rows=self.db.list_users();fill_table(self.table,self.rows,["username","display_name","role","active","last_login","created_at"])
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
            try:self.db.update_user(row.username,password=pw);QMessageBox.information(self,"Password","Password updated.")
            except Exception as exc:QMessageBox.critical(self,"Password",str(exc))
    def override(self):
        row=self.current()
        if not row:return
        perm,ok=QInputDialog.getItem(self,"Permission Override","Permission",PERMISSIONS,0,False)
        if not ok:return
        choice,ok=QInputDialog.getItem(self,"Permission Override",f"{row.username}: {perm}",["Allow","Deny","Use Role Default"],0,False)
        if ok:self.db.set_permission_override(row.username,perm,{"Allow":True,"Deny":False,"Use Role Default":None}[choice])


class MainWindow(QMainWindow):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.setWindowTitle(APP_TITLE);self.resize(1450,850);root=QWidget();self.setCentralWidget(root);h=QHBoxLayout(root);self.nav=QListWidget();self.nav.setFixedWidth(210);self.stack=QStackedWidget();h.addWidget(self.nav);h.addWidget(self.stack,1)
        self.pages=[]
        def add(name,page):self.nav.addItem(name);self.stack.addWidget(page);self.pages.append(page)
        self.dashboard=DashboardPage(db);add("Dashboard",self.dashboard);add("Equipment",EquipmentPage(db,user));self.layout=LayoutPage(db,user);add("Layout / Map",self.layout);add("PM",PMPage(db,user));add("Issue Tickets",TicketPage(db,user));add("Disposition / Release",ControlPage(db,user));add("Endorsements",EndorsementPage(db,user));self.inventory=InventoryPage(db,user);add("Inventory",self.inventory);add("Documents",DocumentPage(db,user));add("Administration",AdminPage(db,user))
        self.inventory.show_map_part.connect(self.show_part_map);self.nav.currentRowChanged.connect(self.stack.setCurrentIndex);self.nav.setCurrentRow(0)
        self.statusBar().showMessage(f"{user['display_name']} — {user['role']} — {WORKSTATION}")
        refresh=QAction("Refresh",self);refresh.setShortcut(QKeySequence("F5"));refresh.triggered.connect(self.refresh_current);self.addAction(refresh);self.timer=QTimer(self);self.timer.timeout.connect(self.dashboard.refresh);self.timer.start(30000)
    def show_part_map(self,part):self.layout.highlight_inventory(part);self.nav.setCurrentRow(2)
    def refresh_current(self):
        p=self.stack.currentWidget()
        if hasattr(p,"refresh"):p.refresh()


def main():
    app=QApplication(sys.argv);app.setStyleSheet(STYLE);db=Database()
    if not db.has_users():
        first=FirstAdminDialog(db)
        if first.exec()!=QDialog.DialogCode.Accepted:return 1
    login=LoginDialog(db)
    if login.exec()!=QDialog.DialogCode.Accepted:return 0
    w=MainWindow(db,login.user);w.show();return app.exec()


if __name__=="__main__":raise SystemExit(main())
