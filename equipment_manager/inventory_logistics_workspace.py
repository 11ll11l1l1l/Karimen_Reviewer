from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,QCheckBox,QDoubleSpinBox,QHBoxLayout,QHeaderView,QInputDialog,QLabel,
    QLineEdit,QMessageBox,QPushButton,QSpinBox,QTableWidget,QTableWidgetItem,QTabWidget,
    QTextEdit,QVBoxLayout,QWidget
)

from table_productivity import install_table_productivity


def _item(value):
    if isinstance(value,float):value=f"{value:g}"
    if isinstance(value,bool):value="Yes" if value else "No"
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers,multi=False):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection if multi else QAbstractItemView.SelectionMode.SingleSelection)
    t.setAlternatingRowColors(True);t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    install_table_productivity(t,headers[0] if headers else "Inventory Logistics")
    return t


def _fill(table,rows,fields):
    table.setRowCount(len(rows))
    for r,row in enumerate(rows):
        for c,field in enumerate(fields):
            value=row.get(field,"") if isinstance(row,dict) else getattr(row,field,"")
            table.setItem(r,c,_item(value))


def _selected(table,rows):
    i=table.currentRow()
    return rows[i] if 0<=i<len(rows) else None


class InventoryLogisticsWorkspace(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.stock=[];self.catalog=[];self.reorder=[];self.alternates=[];self.kit=None
        root=QVBoxLayout(self);head=QHBoxLayout()
        title=QLabel("Parts / Inventory Logistics");title.setStyleSheet("font-size:20pt;font-weight:800")
        self.scan=QLineEdit();self.scan.setPlaceholderText("Scan barcode / supplier PN / part number and press Enter");self.scan.setMinimumWidth(380);self.scan.returnPressed.connect(self.resolve_scan)
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh)
        head.addWidget(title);head.addStretch(1);head.addWidget(self.scan);head.addWidget(refresh);root.addLayout(head)
        self.scan_status=QLabel("Scanner input is treated like normal keyboard input; no dedicated scanner driver is required.");self.scan_status.setStyleSheet("color:#647581");root.addWidget(self.scan_status)

        tabs=QTabWidget();root.addWidget(tabs,1)

        stock=QWidget();sv=QVBoxLayout(stock);sh=QHBoxLayout()
        self.search=QLineEdit();self.search.setPlaceholderText("Filter part / description / location");self.search.textChanged.connect(self.load_stock)
        receive=QPushButton("Receive");receive.clicked.connect(self.receive)
        transfer=QPushButton("Transfer");transfer.clicked.connect(self.transfer)
        count=QPushButton("Cycle Count");count.clicked.connect(self.cycle_count)
        show_eq=QPushButton("Open compatible equipment");show_eq.clicked.connect(self.open_compatible_equipment)
        for w in [self.search,receive,transfer,count,show_eq]:sh.addWidget(w)
        sv.addLayout(sh);self.stock_table=_table(["Part","Description","Qty","Min","Unit","Condition","Location","Compatible Equipment","Ver"]);sv.addWidget(self.stock_table);tabs.addTab(stock,"Stock / Transactions")

        reorder=QWidget();rv=QVBoxLayout(reorder);self.reorder_summary=QLabel();rv.addWidget(self.reorder_summary)
        self.reorder_table=_table(["Part","Description","Location","On Hand","Reserved","Available","Minimum","Short to Min","Suggested Order","Supplier","Supplier PN","Lead Days"]);rv.addWidget(self.reorder_table);tabs.addTab(reorder,"Reorder Queue")

        cat=QWidget();cv=QVBoxLayout(cat);ch=QHBoxLayout()
        addcat=QPushButton("Add / Edit Part Catalog");addcat.clicked.connect(self.edit_catalog)
        alternate=QPushButton("Add Approved Substitute");alternate.clicked.connect(self.add_alternate)
        ch.addWidget(addcat);ch.addWidget(alternate);ch.addStretch(1);cv.addLayout(ch)
        self.catalog_table=_table(["Part","Description","Category","Manufacturer","Supplier","Supplier PN","Barcode","Lead Days","Reorder Qty","Active","Ver"]);self.catalog_table.itemSelectionChanged.connect(self.load_alternates);cv.addWidget(self.catalog_table,2)
        self.alt_table=_table(["Primary","Alternate","Approved","Note","Created By","Created"]);cv.addWidget(QLabel("Approved substitutes / alternates"));cv.addWidget(self.alt_table,1);tabs.addTab(cat,"Part Catalog / Substitutes")

        kit=QWidget();kv=QVBoxLayout(kit);kh=QHBoxLayout();self.task=QSpinBox();self.task.setRange(0,100000000);self.task.setPrefix("PM Task ")
        loadkit=QPushButton("Load Kit");loadkit.clicked.connect(self.load_kit)
        reserve=QPushButton("Reserve Required Parts");reserve.clicked.connect(self.reserve_kit);reserve.setEnabled(db.has_permission(user,"inventory.reserve"))
        kh.addWidget(self.task);kh.addWidget(loadkit);kh.addWidget(reserve);kh.addStretch(1);kv.addLayout(kh)
        self.kit_summary=QLabel("Enter a PM task ID to see kit readiness and approved substitutes.");self.kit_summary.setWordWrap(True);kv.addWidget(self.kit_summary)
        self.kit_table=_table(["Part","Required","Reserved","Available Unreserved","Shortage","Ready","Approved Alternates"]);kv.addWidget(self.kit_table,2)
        self.res_table=_table(["Reservation","Part","Location","Qty","Status","Reserved By"]);kv.addWidget(QLabel("Reservations"));kv.addWidget(self.res_table,1);tabs.addTab(kit,"PM Kits")

        self.refresh()

    def refresh(self):
        self.load_stock();self.load_reorder();self.load_catalog()
        if self.task.value():self.load_kit()

    def resolve_scan(self):
        code=self.scan.text().strip()
        if not code:return
        part=self.db.resolve_part_scan(code)
        if not part:
            self.scan_status.setText(f"No part found for scan: {code}");return
        self.search.setText(part);self.scan_status.setText(f"Resolved {code} → {part}")
        self.load_stock()

    def set_part(self,part_number: str):
        self.search.setText(part_number);self.scan.setText(part_number);self.load_stock()

    def load_stock(self):
        self.stock=self.db.list_inventory(self.search.text().strip())
        _fill(self.stock_table,self.stock,["part_number","description","quantity","min_quantity","unit","condition","location_code","compatible_equipment","version"])

    def _locations(self):
        return [x.location_code for x in self.db.list_storage_locations()]

    def receive(self):
        row=_selected(self.stock_table,self.stock);part=row.part_number if row else (self.db.resolve_part_scan(self.scan.text()) or self.search.text().strip())
        if not part:
            part,ok=QInputDialog.getText(self,"Receive inventory","Part number")
            if not ok or not part.strip():return
            part=part.strip()
        locations=self._locations()
        if row:default=row.location_code
        else:default=locations[0] if locations else ""
        if locations:
            location,ok=QInputDialog.getItem(self,"Receive inventory","Location",locations,locations.index(default) if default in locations else 0,False)
        else:
            location,ok=QInputDialog.getText(self,"Receive inventory","Location code",text=default)
        if not ok or not location.strip():return
        qty,ok=QInputDialog.getDouble(self,"Receive inventory","Quantity",1,0.0001,1e9,3)
        if not ok:return
        ref,ok=QInputDialog.getText(self,"Receive inventory","PO / receipt / reference")
        if not ok:return
        note,ok=QInputDialog.getText(self,"Receive inventory","Note")
        if not ok:return
        try:self.db.receive_inventory(part,location.strip(),qty,self.user["username"],ref,note);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Receive inventory",str(exc))

    def transfer(self):
        row=_selected(self.stock_table,self.stock)
        if not row:return
        locations=[x for x in self._locations() if x!=row.location_code]
        if not locations:QMessageBox.information(self,"Transfer","No other storage location is configured.");return
        dest,ok=QInputDialog.getItem(self,"Transfer",f"Destination for {row.part_number}",locations,0,False)
        if not ok:return
        qty,ok=QInputDialog.getDouble(self,"Transfer",f"Quantity from {row.location_code}",1,0.0001,float(row.quantity or 0),3)
        if not ok:return
        note,ok=QInputDialog.getText(self,"Transfer","Note")
        if not ok:return
        try:self.db.transfer_inventory(row.part_number,row.location_code,dest,qty,self.user["username"],note);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Transfer",str(exc))

    def cycle_count(self):
        row=_selected(self.stock_table,self.stock)
        if not row:return
        counted,ok=QInputDialog.getDouble(self,"Cycle Count",f"Counted quantity for {row.part_number} @ {row.location_code}",float(row.quantity or 0),0,1e9,3)
        if not ok:return
        reason,ok=QInputDialog.getText(self,"Cycle Count","Reason / count reference")
        if not ok:return
        try:self.db.cycle_count_inventory(row.part_number,row.location_code,counted,self.user["username"],reason);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Cycle Count",str(exc))

    def open_compatible_equipment(self):
        row=_selected(self.stock_table,self.stock)
        if not row:return
        raw=(row.compatible_equipment or "").strip()
        if not raw:QMessageBox.information(self,"Equipment","No compatible equipment is recorded.");return
        eq=raw.split(",")[0].strip()
        if eq:self.open_entity.emit("EQUIPMENT",eq,eq)

    def load_reorder(self):
        self.reorder=self.db.inventory_reorder_queue()
        _fill(self.reorder_table,self.reorder,["part_number","description","location_code","on_hand","reserved","available","min_quantity","shortage_to_min","suggested_order_qty","supplier","supplier_part_number","lead_time_days"])
        self.reorder_summary.setText(f"{len(self.reorder)} stock location(s) at/below reorder threshold.")

    def load_catalog(self):
        self.catalog=self.db.list_part_catalog()
        _fill(self.catalog_table,self.catalog,["part_number","description","category","manufacturer","supplier","supplier_part_number","barcode","lead_time_days","reorder_qty","active","version"])
        self.load_alternates()

    def load_alternates(self):
        row=_selected(self.catalog_table,self.catalog)
        self.alternates=self.db.list_part_alternates(row.part_number) if row else self.db.list_part_alternates()
        _fill(self.alt_table,self.alternates,["part_number","alternate_part_number","approved","note","created_by","created_at"])

    def edit_catalog(self):
        current=_selected(self.catalog_table,self.catalog)
        part,ok=QInputDialog.getText(self,"Part Catalog","Part number",text=current.part_number if current else "")
        if not ok or not part.strip():return
        description,ok=QInputDialog.getText(self,"Part Catalog","Description",text=current.description if current else "")
        if not ok:return
        supplier,ok=QInputDialog.getText(self,"Part Catalog","Supplier",text=current.supplier if current else "")
        if not ok:return
        supplier_pn,ok=QInputDialog.getText(self,"Part Catalog","Supplier part number",text=current.supplier_part_number if current else "")
        if not ok:return
        barcode,ok=QInputDialog.getText(self,"Part Catalog","Barcode / scan code",text=current.barcode if current else "")
        if not ok:return
        lead,ok=QInputDialog.getInt(self,"Part Catalog","Lead time days",current.lead_time_days if current else 0,0,3650)
        if not ok:return
        reorder,ok=QInputDialog.getDouble(self,"Part Catalog","Suggested reorder quantity",float(current.reorder_qty if current else 0),0,1e9,3)
        if not ok:return
        data={
            "part_number":part.strip(),"description":description.strip(),
            "category":current.category if current else "","manufacturer":current.manufacturer if current else "",
            "supplier":supplier.strip(),"supplier_part_number":supplier_pn.strip(),"barcode":barcode.strip(),
            "lead_time_days":lead,"reorder_qty":reorder,"notes":current.notes if current else "","active":True,
        }
        try:self.db.save_part_catalog(data,current.version if current and current.part_number==part.strip() else None);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Part Catalog",str(exc))

    def add_alternate(self):
        row=_selected(self.catalog_table,self.catalog)
        primary=row.part_number if row else ""
        if not primary:
            primary,ok=QInputDialog.getText(self,"Approved Substitute","Primary part")
            if not ok or not primary.strip():return
            primary=primary.strip()
        alternate,ok=QInputDialog.getText(self,"Approved Substitute","Alternate part number")
        if not ok or not alternate.strip():return
        note,ok=QInputDialog.getText(self,"Approved Substitute","Approval note / restriction")
        if not ok:return
        try:self.db.save_part_alternate(primary,alternate.strip(),self.user["username"],True,note);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Approved Substitute",str(exc))

    def load_kit(self):
        if not self.task.value():return
        try:self.kit=self.db.pm_kit_status(self.task.value())
        except Exception as exc:self.kit=None;self.kit_summary.setText(str(exc));self.kit_table.setRowCount(0);self.res_table.setRowCount(0);return
        self.kit_table.setRowCount(len(self.kit["parts"]))
        for r,row in enumerate(self.kit["parts"]):
            vals=[row["part_number"],row["required"],row["reserved"],row["available_unreserved"],row["shortage"],row["ready"],", ".join(row.get("alternates",[]))]
            for c,val in enumerate(vals):self.kit_table.setItem(r,c,_item(val))
        reservations=self.kit["reservations"];self.res_table.setRowCount(len(reservations))
        for r,row in enumerate(reservations):
            for c,key in enumerate(["id","part_number","location_code","quantity","status","reserved_by"]):self.res_table.setItem(r,c,_item(row.get(key)))
        shortages=sum(1 for x in self.kit["parts"] if not x["ready"])
        self.kit_summary.setText(f"Equipment: {self.kit['equipment_id']} · Parts: {self.kit['parts_status']} · Certifications: {self.kit['certification_status']} · Short part lines: {shortages}")

    def reserve_kit(self):
        if not self.task.value():return
        try:
            rows=self.db.reserve_pm_required_parts(self.task.value(),self.user["username"],"INVENTORY-LOGISTICS")
            QMessageBox.information(self,"PM Kit",f"Created {len(rows)} reservation(s)." if rows else "Kit already reserved or no required parts.")
            self.refresh()
        except Exception as exc:QMessageBox.critical(self,"PM Kit",str(exc))
