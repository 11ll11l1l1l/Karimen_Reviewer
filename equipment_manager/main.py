from __future__ import annotations

import os
import socket
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QBrush, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem, QGraphicsView,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QMainWindow,
    QMessageBox, QPushButton, QDoubleSpinBox, QSplitter, QStackedWidget, QTableWidget,
    QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout, QWidget, QInputDialog, QCheckBox,
)

from database import Database
from services import auto_mapping, dataframe_to_pm_backlog, dataframe_to_pm_specs, read_table, readonly_open_copy, workbook_sheets

APP_TITLE = "Equipment Management System"
WORKSTATION = socket.gethostname()

STYLE = """
QWidget { font-size: 10.5pt; }
QMainWindow, QDialog { background: #f4f6f8; }
QLineEdit, QComboBox, QDoubleSpinBox, QTextEdit { background: white; border: 1px solid #c8ced6; border-radius: 4px; padding: 6px; }
QPushButton { background: #1f5f8b; color: white; border: 0; border-radius: 4px; padding: 7px 12px; }
QPushButton:hover { background: #184b6d; }
QPushButton:disabled { background: #aeb7bf; }
QTableWidget { background: white; border: 1px solid #d9dee3; gridline-color: #e7eaed; }
QHeaderView::section { background: #e9edf1; padding: 6px; border: 0; border-right: 1px solid #d0d6dc; font-weight: 600; }
QListWidget { background: #172431; color: white; border: 0; padding: 8px; }
QListWidget::item { padding: 11px; border-radius: 4px; }
QListWidget::item:selected { background: #2a6f9e; }
"""


def table_item(value: Any) -> QTableWidgetItem:
    if isinstance(value, datetime):
        return QTableWidgetItem(value.strftime("%Y-%m-%d %H:%M"))
    return QTableWidgetItem("" if value is None else str(value))


class FirstAdminDialog(QDialog):
    def __init__(self, db: Database):
        super().__init__(); self.db = db; self.setWindowTitle("Create first administrator")
        form = QFormLayout(self); self.username = QLineEdit("admin"); self.name = QLineEdit(); self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.Password); self.confirm = QLineEdit(); self.confirm.setEchoMode(QLineEdit.Password)
        form.addRow("Username", self.username); form.addRow("Display name", self.name); form.addRow("Password", self.password); form.addRow("Confirm", self.confirm)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); buttons.accepted.connect(self.create); buttons.rejected.connect(self.reject); form.addRow(buttons)
    def create(self):
        if len(self.password.text()) < 10: QMessageBox.warning(self, "Password", "Use at least 10 characters."); return
        if self.password.text() != self.confirm.text(): QMessageBox.warning(self, "Password", "Passwords do not match."); return
        try: self.db.create_user(self.username.text(), self.name.text(), self.password.text()); self.accept()
        except Exception as exc: QMessageBox.critical(self, "Create administrator", str(exc))


class LoginDialog(QDialog):
    def __init__(self, db: Database):
        super().__init__(); self.db = db; self.user = None; self.setWindowTitle(APP_TITLE + " - Login"); self.setMinimumWidth(420)
        layout = QVBoxLayout(self); title = QLabel("EQUIPMENT MANAGEMENT"); title.setStyleSheet("font-size:20pt;font-weight:700;color:#16354b"); layout.addWidget(title)
        ok, status = db.health(); health = QLabel(f"Database: {'Connected' if ok else 'Offline'} — {status}"); health.setStyleSheet("color:#26734d" if ok else "color:#a62b2b"); layout.addWidget(health)
        form = QFormLayout(); self.username = QLineEdit(); self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.Password); self.remember = QCheckBox("Remember username on this PC"); form.addRow("Username", self.username); form.addRow("Password", self.password); form.addRow("", self.remember); layout.addLayout(form)
        btn = QPushButton("Login"); btn.clicked.connect(self.login); layout.addWidget(btn); self.password.returnPressed.connect(self.login)
    def login(self):
        user = self.db.authenticate(self.username.text(), self.password.text())
        if not user: QMessageBox.warning(self, "Login", "Invalid username/password or inactive account."); return
        self.user = user; self.db.audit(user["username"], "LOGIN", "SESSION", WORKSTATION, workstation=WORKSTATION); self.accept()


class MetricCard(QWidget):
    clicked = Signal()
    def __init__(self, title: str):
        super().__init__(); self.setStyleSheet("background:white;border:1px solid #d9dee3;border-radius:6px;")
        l = QVBoxLayout(self); self.value = QLabel("0"); self.value.setStyleSheet("font-size:24pt;font-weight:700;color:#16354b;border:0"); t = QLabel(title); t.setStyleSheet("color:#5a6670;border:0"); l.addWidget(self.value); l.addWidget(t)
    def mousePressEvent(self, e): self.clicked.emit(); super().mousePressEvent(e)


class DashboardPage(QWidget):
    def __init__(self, db):
        super().__init__(); self.db = db; outer = QVBoxLayout(self); title = QLabel("Operational Dashboard"); title.setStyleSheet("font-size:18pt;font-weight:700"); outer.addWidget(title); grid = QGridLayout(); outer.addLayout(grid)
        names = [("equipment_total","Equipment"),("equipment_down","Down"),("equipment_hold","On Hold"),("pm_open","Open PM"),("pm_overdue","PM Overdue"),("tickets_open","Open Tickets"),("tickets_critical","P1 / P2 Tickets"),("inventory_low","Low Stock Locations")]
        self.cards = {}
        for i,(key,label) in enumerate(names): card=MetricCard(label); self.cards[key]=card; grid.addWidget(card,i//4,i%4)
        outer.addWidget(QLabel("Dashboard refreshes every 30 seconds. F5 refreshes the current module.")); outer.addStretch(1); self.refresh()
    def refresh(self):
        for k,v in self.db.dashboard_counts().items():
            if k in self.cards: self.cards[k].value.setText(str(v))


class EquipmentDialog(QDialog):
    def __init__(self, parent=None, row=None):
        super().__init__(parent); self.row=row; self.setWindowTitle("Equipment"); form=QFormLayout(self); self.fields={}
        specs=[("equipment_id","Equipment ID"),("name","Name"),("equipment_type","Type"),("manufacturer","Manufacturer"),("model","Model"),("serial_number","Serial Number"),("asset_number","Asset Number"),("site","Site"),("building","Building"),("floor","Floor"),("area","Area"),("line_cell","Line / Bay / Cell"),("owner","Owner")]
        for key,label in specs: w=QLineEdit(); self.fields[key]=w; form.addRow(label,w)
        self.status=QComboBox(); self.status.addItems(["Available","Production","Down","PM","Engineering","Standby","Waiting Parts","Waiting Vendor","Qualification","Hold","Restricted","Offline","Decommissioned"])
        self.disposition=QComboBox(); self.disposition.addItems(["Released","Released With Conditions","Restricted Use","Engineering Use","Monitoring","Hold","PM Hold","Quality Hold","Safety Hold","Waiting Parts","Waiting Vendor","Qualification","Decommission","Scrap"])
        self.criticality=QComboBox(); self.criticality.addItems(["Low","Normal","High","Critical"]); self.map_x=QDoubleSpinBox(); self.map_x.setRange(-100000,100000); self.map_y=QDoubleSpinBox(); self.map_y.setRange(-100000,100000)
        form.addRow("Status",self.status); form.addRow("Disposition",self.disposition); form.addRow("Criticality",self.criticality); form.addRow("Map X",self.map_x); form.addRow("Map Y",self.map_y)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)
        if row:
            for k,w in self.fields.items(): w.setText(str(getattr(row,k,"") or ""))
            self.status.setCurrentText(row.status); self.disposition.setCurrentText(row.disposition); self.criticality.setCurrentText(row.criticality); self.map_x.setValue(row.map_x); self.map_y.setValue(row.map_y); self.fields["equipment_id"].setReadOnly(True)
    def data(self):
        d={k:w.text().strip() for k,w in self.fields.items()}; d.update(status=self.status.currentText(),disposition=self.disposition.currentText(),criticality=self.criticality.currentText(),map_x=self.map_x.value(),map_y=self.map_y.value()); return d


class EquipmentPage(QWidget):
    def __init__(self, db, user):
        super().__init__(); self.db=db; self.user=user; self.rows=[]; l=QVBoxLayout(self); top=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Search equipment ID, name, area or status..."); self.search.textChanged.connect(self.refresh); add=QPushButton("Add Equipment"); add.clicked.connect(self.add); edit=QPushButton("Edit Selected"); edit.clicked.connect(self.edit); top.addWidget(self.search,1); top.addWidget(add); top.addWidget(edit); l.addLayout(top)
        self.table=QTableWidget(); self.table.setColumnCount(10); self.table.setHorizontalHeaderLabels(["ID","Name","Type","Area","Line/Cell","Status","Disposition","Owner","Criticality","Version"]); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.doubleClicked.connect(self.edit); l.addWidget(self.table); self.refresh()
    def refresh(self):
        self.rows=self.db.list_equipment(self.search.text().strip()); self.table.setRowCount(len(self.rows))
        for r,e in enumerate(self.rows):
            for c,v in enumerate([e.equipment_id,e.name,e.equipment_type,e.area,e.line_cell,e.status,e.disposition,e.owner,e.criticality,e.version]): self.table.setItem(r,c,table_item(v))
    def selected(self): r=self.table.currentRow(); return self.rows[r] if 0<=r<len(self.rows) else None
    def add(self):
        d=EquipmentDialog(self)
        if d.exec()==QDialog.Accepted:
            data=d.data()
            if not data["equipment_id"]: QMessageBox.warning(self,"Equipment","Equipment ID is required."); return
            try: self.db.save_equipment(data); self.db.audit(self.user["username"],"CREATE","EQUIPMENT",data["equipment_id"],workstation=WORKSTATION); self.refresh()
            except Exception as exc: QMessageBox.critical(self,"Save",str(exc))
    def edit(self):
        row=self.selected()
        if not row: return
        d=EquipmentDialog(self,row)
        if d.exec()==QDialog.Accepted:
            try: self.db.save_equipment(d.data(),expected_version=row.version); self.db.audit(self.user["username"],"UPDATE","EQUIPMENT",row.equipment_id,workstation=WORKSTATION); self.refresh()
            except Exception as exc: QMessageBox.critical(self,"Concurrent update",str(exc))


class PMPage(QWidget):
    def __init__(self, db, user):
        super().__init__(); self.db=db; self.user=user; l=QVBoxLayout(self); top=QHBoxLayout(); b1=QPushButton("Import PM Backlog Excel"); b1.clicked.connect(self.import_backlog); b2=QPushButton("Import PM Steps / Specs Excel"); b2.clicked.connect(self.import_specs); top.addWidget(b1); top.addWidget(b2); top.addStretch(1); l.addLayout(top); self.tabs=QTabWidget(); l.addWidget(self.tabs)
        self.backlog=QTableWidget(); self.backlog.setColumnCount(10); self.backlog.setHorizontalHeaderLabels(["Equipment","PM ID","PM Name","Original Due","Scheduled","Status","Assigned","Hours","Priority","Version"]); self.backlog.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.specs=QTableWidget(); self.specs.setColumnCount(12); self.specs.setHorizontalHeaderLabels(["PM ID","Step","Activity","Method","Type","Unit","Target","Control Low","Control High","Spec Low","Spec High","Revision"]); self.specs.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.tabs.addTab(self.backlog,"Backlog / Schedule"); self.tabs.addTab(self.specs,"Checklist / Control Specs"); self.refresh()
    def refresh(self):
        rows=self.db.list_pm_tasks(); self.backlog.setRowCount(len(rows))
        for r,x in enumerate(rows):
            for c,v in enumerate([x.equipment_id,x.pm_id,x.pm_name,x.original_due_date,x.scheduled_date,x.status,x.assigned_to,x.estimated_hours,x.priority,x.version]): self.backlog.setItem(r,c,table_item(v))
        specs=self.db.list_pm_specs(); self.specs.setRowCount(len(specs))
        for r,x in enumerate(specs):
            for c,v in enumerate([x.pm_id,x.step_no,x.activity,x.method,x.input_type,x.unit,x.target,x.control_low,x.control_high,x.spec_low,x.spec_high,x.revision]): self.specs.setItem(r,c,table_item(v))
    def choose_sheet(self,path):
        sheets=workbook_sheets(path)
        if len(sheets)==1:return 0
        choice,ok=QInputDialog.getItem(self,"Worksheet","Choose worksheet",sheets,0,False); return choice if ok else None
    def import_backlog(self):
        path,_=QFileDialog.getOpenFileName(self,"Import PM backlog","","Excel/CSV (*.xlsx *.xlsm *.csv)")
        if not path:return
        sheet=self.choose_sheet(path)
        if sheet is None:return
        try:
            df=read_table(path,sheet); mapping=auto_mapping(list(df.columns)); rows,errors=dataframe_to_pm_backlog(df,mapping)
            if not rows: QMessageBox.warning(self,"Import","No valid rows found.\n"+"\n".join(errors[:10])); return
            if QMessageBox.question(self,"PM Backlog Import",f"Ready to import {len(rows)} backlog rows.\nDetected mapping: {mapping}\nWarnings/errors: {len(errors)}")!=QMessageBox.Yes:return
            for row in rows:self.db.upsert_pm_task(row)
            self.db.audit(self.user["username"],"IMPORT","PM_BACKLOG",Path(path).name,f"Rows={len(rows)} Errors={len(errors)}",WORKSTATION); self.refresh(); QMessageBox.information(self,"Import",f"Imported {len(rows)} rows.\n{len(errors)} rows required attention/skipped.")
        except Exception as exc: QMessageBox.critical(self,"Import",str(exc))
    def import_specs(self):
        path,_=QFileDialog.getOpenFileName(self,"Import PM steps/specifications","","Excel/CSV (*.xlsx *.xlsm *.csv)")
        if not path:return
        sheet=self.choose_sheet(path)
        if sheet is None:return
        try:
            df=read_table(path,sheet); mapping=auto_mapping(list(df.columns)); default_pm=""
            if "pm_id" not in mapping:
                default_pm,ok=QInputDialog.getText(self,"PM ID","No PM ID column detected. Enter PM ID for this sheet:")
                if not ok or not default_pm.strip():return
            rows,warnings=dataframe_to_pm_specs(df,mapping,default_pm.strip())
            if not rows: QMessageBox.warning(self,"Import","No valid PM steps found.\n"+"\n".join(warnings[:12])); return
            if QMessageBox.question(self,"PM Specification Import",f"Ready to import {len(rows)} PM steps/specifications.\nWarnings: {len(warnings)}\nExisting steps will be updated in place for this first build.")!=QMessageBox.Yes:return
            for row in rows:self.db.upsert_pm_spec(row)
            self.db.audit(self.user["username"],"IMPORT","PM_SPEC",Path(path).name,f"Rows={len(rows)} Warnings={len(warnings)}",WORKSTATION); self.refresh(); detail="\n".join(warnings[:15]); QMessageBox.information(self,"Import",f"Imported {len(rows)} steps.\nWarnings: {len(warnings)}"+("\n\n"+detail if detail else ""))
        except Exception as exc: QMessageBox.critical(self,"Import",str(exc))


class InventoryDialog(QDialog):
    def __init__(self,parent=None,row=None):
        super().__init__(parent); self.row=row; self.setWindowTitle("Inventory item"); form=QFormLayout(self); self.part=QLineEdit(); self.desc=QLineEdit(); self.location=QLineEdit(); self.qty=QDoubleSpinBox(); self.qty.setRange(0,1e9); self.minq=QDoubleSpinBox(); self.minq.setRange(0,1e9); self.unit=QLineEdit("pcs"); self.condition=QComboBox(); self.condition.addItems(["Available","Reserved","Installed","In Use","Repair","Quarantine","Inspection Required","Expired","Obsolete","Scrap","Vendor"]); self.image=QLineEdit(); browse=QPushButton("Browse..."); browse.clicked.connect(self.browse_image); imgrow=QHBoxLayout(); imgrow.addWidget(self.image); imgrow.addWidget(browse)
        form.addRow("Part Number",self.part); form.addRow("Description",self.desc); form.addRow("Location Code",self.location); form.addRow("Quantity",self.qty); form.addRow("Minimum",self.minq); form.addRow("Unit",self.unit); form.addRow("Condition",self.condition); form.addRow("Image",imgrow); buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)
        if row: self.part.setText(row.part_number); self.part.setReadOnly(True); self.desc.setText(row.description); self.location.setText(row.location_code); self.location.setReadOnly(True); self.qty.setValue(row.quantity); self.minq.setValue(row.min_quantity); self.unit.setText(row.unit); self.condition.setCurrentText(row.condition); self.image.setText(row.image_path)
    def browse_image(self):
        p,_=QFileDialog.getOpenFileName(self,"Choose image","","Images (*.png *.jpg *.jpeg *.bmp)")
        if p:self.image.setText(p)
    def data(self):return {"part_number":self.part.text().strip(),"description":self.desc.text().strip(),"location_code":self.location.text().strip(),"quantity":self.qty.value(),"min_quantity":self.minq.value(),"unit":self.unit.text().strip() or "pcs","condition":self.condition.currentText(),"image_path":self.image.text().strip()}


class StorageDialog(QDialog):
    def __init__(self,parent=None,row=None):
        super().__init__(parent); self.row=row; self.setWindowTitle("Storage location"); form=QFormLayout(self); self.code=QLineEdit(); self.name=QLineEdit(); self.site=QLineEdit(); self.building=QLineEdit(); self.floor=QLineEdit(); self.area=QLineEdit(); self.cabinet=QLineEdit(); self.shelf=QLineEdit(); self.bin=QLineEdit(); self.x=QDoubleSpinBox(); self.x.setRange(-100000,100000); self.y=QDoubleSpinBox(); self.y.setRange(-100000,100000); self.image=QLineEdit(); browse=QPushButton("Browse..."); browse.clicked.connect(self.browse); ir=QHBoxLayout(); ir.addWidget(self.image); ir.addWidget(browse)
        for lab,w in [("Location Code",self.code),("Name",self.name),("Site",self.site),("Building",self.building),("Floor",self.floor),("Area",self.area),("Cabinet",self.cabinet),("Shelf",self.shelf),("Drawer/Bin",self.bin),("Map X",self.x),("Map Y",self.y)]:form.addRow(lab,w)
        form.addRow("Location image",ir); b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); form.addRow(b)
    def browse(self):
        p,_=QFileDialog.getOpenFileName(self,"Location image","","Images (*.png *.jpg *.jpeg *.bmp)")
        if p:self.image.setText(p)
    def data(self):return {"location_code":self.code.text().strip(),"name":self.name.text().strip(),"site":self.site.text().strip(),"building":self.building.text().strip(),"floor":self.floor.text().strip(),"area":self.area.text().strip(),"cabinet":self.cabinet.text().strip(),"shelf":self.shelf.text().strip(),"drawer_bin":self.bin.text().strip(),"map_x":self.x.value(),"map_y":self.y.value(),"image_path":self.image.text().strip()}


class InventoryPage(QWidget):
    def __init__(self,db,user):
        super().__init__(); self.db=db; self.user=user; self.rows=[]; l=QVBoxLayout(self); top=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Search part number, description or location..."); self.search.textChanged.connect(self.refresh); a=QPushButton("Add Item"); a.clicked.connect(self.add); s=QPushButton("Add Storage Location"); s.clicked.connect(self.add_storage); e=QPushButton("Edit Selected"); e.clicked.connect(self.edit); c=QPushButton("Use / Consume"); c.clicked.connect(self.consume); top.addWidget(self.search,1); top.addWidget(a); top.addWidget(s); top.addWidget(e); top.addWidget(c); l.addLayout(top)
        split=QSplitter(); self.table=QTableWidget(); self.table.setColumnCount(8); self.table.setHorizontalHeaderLabels(["Part","Description","Qty","Min","Unit","Condition","Location","Version"]); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.itemSelectionChanged.connect(self.show_image)
        right=QWidget(); rl=QVBoxLayout(right); self.image=QLabel("Select an item to preview image"); self.image.setAlignment(Qt.AlignCenter); self.image.setMinimumSize(260,180); self.image.setStyleSheet("background:white;border:1px solid #d9dee3"); self.location_detail=QLabel(); self.location_detail.setWordWrap(True); rl.addWidget(self.image); rl.addWidget(self.location_detail); rl.addStretch(1); split.addWidget(self.table); split.addWidget(right); split.setStretchFactor(0,3); split.setStretchFactor(1,1); l.addWidget(split); self.refresh()
    def refresh(self):
        self.rows=self.db.list_inventory(self.search.text().strip()); self.table.setRowCount(len(self.rows))
        for r,x in enumerate(self.rows):
            for c,v in enumerate([x.part_number,x.description,x.quantity,x.min_quantity,x.unit,x.condition,x.location_code,x.version]):self.table.setItem(r,c,table_item(v))
    def selected(self): r=self.table.currentRow(); return self.rows[r] if 0<=r<len(self.rows) else None
    def add(self):
        d=InventoryDialog(self)
        if d.exec()==QDialog.Accepted:
            data=d.data()
            if not data["part_number"] or not data["location_code"]: QMessageBox.warning(self,"Inventory","Part number and location are required.");return
            try:self.db.save_inventory_item(data);self.db.audit(self.user["username"],"CREATE","INVENTORY",data["part_number"],workstation=WORKSTATION);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Save",str(exc))
    def edit(self):
        row=self.selected()
        if not row:return
        d=InventoryDialog(self,row)
        if d.exec()==QDialog.Accepted:
            try:self.db.save_inventory_item(d.data(),row.version);self.db.audit(self.user["username"],"UPDATE","INVENTORY",row.part_number,workstation=WORKSTATION);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Concurrent update",str(exc))
    def add_storage(self):
        d=StorageDialog(self)
        if d.exec()==QDialog.Accepted:
            data=d.data()
            if not data["location_code"]:return
            try:self.db.save_storage_location(data);self.db.audit(self.user["username"],"CREATE","STORAGE",data["location_code"],workstation=WORKSTATION)
            except Exception as exc:QMessageBox.critical(self,"Storage",str(exc))
    def consume(self):
        row=self.selected()
        if not row:return
        qty,ok=QInputDialog.getDouble(self,"Consume inventory",f"Use quantity from {row.part_number} at {row.location_code}",1,0.0001,1e9,2)
        if not ok:return
        try:
            success,remaining=self.db.consume_inventory(row.part_number,row.location_code,qty)
            if not success:QMessageBox.warning(self,"Inventory changed",f"Not enough stock. Current quantity: {remaining}")
            else:self.db.audit(self.user["username"],"CONSUME","INVENTORY",row.part_number,f"Qty={qty} Location={row.location_code}",WORKSTATION);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Inventory",str(exc))
    def show_image(self):
        row=self.selected()
        if not row:return
        if row.image_path and Path(row.image_path).exists(): self.image.setPixmap(QPixmap(row.image_path).scaled(self.image.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
        else:self.image.setText("No image registered")
        locs={x.location_code:x for x in self.db.list_storage_locations()}; loc=locs.get(row.location_code)
        if loc:self.location_detail.setText(f"{loc.location_code} — {loc.name}\n{loc.building} / {loc.floor} / {loc.area}\n{loc.cabinet} / {loc.shelf} / {loc.drawer_bin}")
        else:self.location_detail.setText(f"Location: {row.location_code} (not yet registered on map)")


class LayoutPage(QWidget):
    def __init__(self,db):
        super().__init__(); self.db=db; l=QVBoxLayout(self); top=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Highlight inventory part number or location..."); b=QPushButton("Refresh / Highlight"); b.clicked.connect(self.refresh); top.addWidget(self.search,1); top.addWidget(b); l.addLayout(top); self.scene=QGraphicsScene(); self.view=QGraphicsView(self.scene); l.addWidget(self.view); l.addWidget(QLabel("Rectangles = equipment. Circles = distributed storage. Search a part number to highlight every location holding it.")); self.refresh()
    def refresh(self):
        self.scene.clear(); search=self.search.text().strip(); highlighted=set()
        if search:
            for item in self.db.list_inventory(search): highlighted.add(item.location_code)
        for e in self.db.list_equipment():
            x,y=e.map_x,e.map_y; color=QColor("#d9534f") if e.status=="Down" else QColor("#f0ad4e") if "Hold" in e.disposition else QColor("#5cb85c"); rect=QGraphicsRectItem(x,y,100,48); rect.setBrush(QBrush(color)); rect.setPen(QPen(Qt.black)); self.scene.addItem(rect); text=QGraphicsTextItem(f"{e.equipment_id}\n{e.status}"); text.setPos(x+4,y+3); self.scene.addItem(text)
        for loc in self.db.list_storage_locations():
            x,y=loc.map_x,loc.map_y; is_hi=loc.location_code in highlighted; ell=QGraphicsEllipseItem(x,y,34,34); ell.setBrush(QBrush(QColor("#ffd54f") if is_hi else QColor("#5dade2"))); ell.setPen(QPen(QColor("#c62828") if is_hi else Qt.black,4 if is_hi else 1)); self.scene.addItem(ell); t=QGraphicsTextItem(loc.location_code); t.setPos(x+38,y+5); self.scene.addItem(t)
        if self.scene.items(): self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-80,-80,80,80)); self.view.fitInView(self.scene.sceneRect(),Qt.KeepAspectRatio)


class TicketDialog(QDialog):
    def __init__(self,parent=None,row=None,user=""):
        super().__init__(parent); self.row=row; self.user=user; self.setWindowTitle("Issue Ticket"); f=QFormLayout(self); self.no=QLineEdit(row.ticket_no if row else datetime.now().strftime("EQI-%Y%m%d-%H%M%S")); self.eq=QLineEdit(); self.title=QLineEdit(); self.desc=QTextEdit(); self.sev=QComboBox(); self.sev.addItems(["S1","S2","S3","S4"]); self.pri=QComboBox(); self.pri.addItems(["P1","P2","P3","P4"]); self.status=QComboBox(); self.status.addItems(["Open","Assigned","Investigation","Waiting Parts","Waiting Vendor","Waiting Production","Monitoring","Resolved","Verification","Closed","Cancelled"]); self.owner=QLineEdit(); self.disp=QLineEdit(); self.root=QTextEdit(); self.action=QTextEdit(); self.verify=QTextEdit()
        for lab,w in [("Ticket No",self.no),("Equipment ID",self.eq),("Title",self.title),("Description",self.desc),("Severity",self.sev),("Priority",self.pri),("Status",self.status),("Owner",self.owner),("Disposition",self.disp),("Root Cause",self.root),("Corrective Action",self.action),("Verification",self.verify)]:f.addRow(lab,w)
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b)
        if row:
            self.no.setReadOnly(True); self.eq.setText(row.equipment_id); self.title.setText(row.title); self.desc.setPlainText(row.description); self.sev.setCurrentText(row.severity); self.pri.setCurrentText(row.priority); self.status.setCurrentText(row.status); self.owner.setText(row.owner); self.disp.setText(row.disposition); self.root.setPlainText(row.root_cause); self.action.setPlainText(row.corrective_action); self.verify.setPlainText(row.verification)
    def data(self):return {"ticket_no":self.no.text().strip(),"equipment_id":self.eq.text().strip(),"title":self.title.text().strip(),"description":self.desc.toPlainText(),"severity":self.sev.currentText(),"priority":self.pri.currentText(),"status":self.status.currentText(),"owner":self.owner.text().strip(),"disposition":self.disp.text().strip(),"root_cause":self.root.toPlainText(),"corrective_action":self.action.toPlainText(),"verification":self.verify.toPlainText(),"created_by":self.row.created_by if self.row else self.user}


class TicketsPage(QWidget):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.rows=[];l=QVBoxLayout(self);top=QHBoxLayout();a=QPushButton("New Ticket");a.clicked.connect(self.add);e=QPushButton("Edit Selected");e.clicked.connect(self.edit);top.addWidget(a);top.addWidget(e);top.addStretch(1);l.addLayout(top);self.table=QTableWidget();self.table.setColumnCount(9);self.table.setHorizontalHeaderLabels(["Ticket","Equipment","Title","Severity","Priority","Status","Owner","Disposition","Version"]);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.doubleClicked.connect(self.edit);l.addWidget(self.table);self.refresh()
    def refresh(self):
        self.rows=self.db.list_tickets();self.table.setRowCount(len(self.rows))
        for r,x in enumerate(self.rows):
            for c,v in enumerate([x.ticket_no,x.equipment_id,x.title,x.severity,x.priority,x.status,x.owner,x.disposition,x.version]):self.table.setItem(r,c,table_item(v))
    def selected(self):r=self.table.currentRow();return self.rows[r] if 0<=r<len(self.rows) else None
    def add(self):
        d=TicketDialog(self,user=self.user["username"])
        if d.exec()==QDialog.Accepted:
            try:self.db.save_ticket(d.data());self.db.audit(self.user["username"],"CREATE","TICKET",d.data()["ticket_no"],workstation=WORKSTATION);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Ticket",str(exc))
    def edit(self):
        row=self.selected()
        if not row:return
        d=TicketDialog(self,row,self.user["username"])
        if d.exec()==QDialog.Accepted:
            try:self.db.save_ticket(d.data(),row.version);self.db.audit(self.user["username"],"UPDATE","TICKET",row.ticket_no,workstation=WORKSTATION);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Concurrent update",str(exc))


class DocumentsPage(QWidget):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.rows=[];l=QVBoxLayout(self);top=QHBoxLayout();a=QPushButton("Link Existing File");a.clicked.connect(self.add);o=QPushButton("Open Selected Read-Only");o.clicked.connect(self.open);top.addWidget(a);top.addWidget(o);top.addStretch(1);l.addLayout(top);self.table=QTableWidget();self.table.setColumnCount(7);self.table.setHorizontalHeaderLabels(["Entity Type","Entity Key","Type","Title","Revision","Status","Path"]);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.doubleClicked.connect(self.open);l.addWidget(self.table);self.refresh()
    def refresh(self):
        self.rows=self.db.list_documents();self.table.setRowCount(len(self.rows))
        for r,x in enumerate(self.rows):
            for c,v in enumerate([x.entity_type,x.entity_key,x.document_type,x.title,x.revision,x.status,x.path]):self.table.setItem(r,c,table_item(v))
    def add(self):
        path,_=QFileDialog.getOpenFileName(self,"Link existing file")
        if not path:return
        et,ok=QInputDialog.getItem(self,"Entity type","Link to",["Equipment","PM","Ticket","Inventory","General"],0,False)
        if not ok:return
        key,ok=QInputDialog.getText(self,"Entity key","Equipment ID / PM ID / Ticket No / Part No (optional)")
        if not ok:return
        self.db.add_document({"entity_type":et,"entity_key":key.strip(),"document_type":"Document","title":Path(path).name,"path":path,"added_by":self.user["username"]});self.db.audit(self.user["username"],"LINK","DOCUMENT",key.strip(),path,WORKSTATION);self.refresh()
    def open(self):
        r=self.table.currentRow()
        if not 0<=r<len(self.rows):return
        try:readonly_open_copy(self.rows[r].path);self.db.audit(self.user["username"],"OPEN_READONLY","DOCUMENT",self.rows[r].entity_key,self.rows[r].path,WORKSTATION)
        except Exception as exc:QMessageBox.critical(self,"Open read-only",str(exc))


class MainWindow(QMainWindow):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.setWindowTitle(f"{APP_TITLE} — {user['display_name']}");self.resize(1500,900);central=QWidget();self.setCentralWidget(central);outer=QHBoxLayout(central);outer.setContentsMargins(0,0,0,0);self.nav=QListWidget();self.nav.setFixedWidth(220);self.stack=QStackedWidget();outer.addWidget(self.nav);outer.addWidget(self.stack,1)
        self.pages=[("Dashboard",DashboardPage(db)),("Equipment",EquipmentPage(db,user)),("PM Control",PMPage(db,user)),("Inventory",InventoryPage(db,user)),("Equipment Layout",LayoutPage(db)),("Issue Tickets",TicketsPage(db,user)),("Documents",DocumentsPage(db,user))]
        for name,page in self.pages:self.nav.addItem(name);self.stack.addWidget(page)
        self.nav.currentRowChanged.connect(self.switch);self.nav.setCurrentRow(0);self.statusBar().showMessage(f"Logged in: {user['display_name']} ({user['role']}) | Workstation: {WORKSTATION}"); refresh=QAction("Refresh",self);refresh.setShortcut("F5");refresh.triggered.connect(self.refresh_current);self.addAction(refresh);self.timer=QTimer(self);self.timer.setInterval(30000);self.timer.timeout.connect(self.background_refresh);self.timer.start()
    def switch(self,index):self.stack.setCurrentIndex(index);self.refresh_current()
    def refresh_current(self):
        page=self.stack.currentWidget()
        if hasattr(page,"refresh"):
            try:page.refresh()
            except Exception as exc:self.statusBar().showMessage(f"Refresh error: {exc}")
    def background_refresh(self):
        if isinstance(self.stack.currentWidget(),DashboardPage):self.refresh_current()
    def closeEvent(self,event):
        try:self.db.audit(self.user["username"],"LOGOUT","SESSION",WORKSTATION,workstation=WORKSTATION)
        finally:super().closeEvent(event)


def main():
    app=QApplication(sys.argv);app.setApplicationName(APP_TITLE);app.setStyleSheet(STYLE);db=Database();ok,msg=db.health()
    if not ok:QMessageBox.critical(None,"Database unavailable",f"Cannot connect to database.\n\n{msg}");return 2
    if not db.has_users():
        first=FirstAdminDialog(db)
        if first.exec()!=QDialog.Accepted:return 0
    login=LoginDialog(db)
    if login.exec()!=QDialog.Accepted:return 0
    w=MainWindow(db,login.user);w.show();return app.exec()


if __name__=="__main__":raise SystemExit(main())
