from __future__ import annotations

from feedback import notify

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,QCheckBox,QComboBox,QDateTimeEdit,QDialog,QDialogButtonBox,QDoubleSpinBox,
    QFormLayout,QHBoxLayout,QHeaderView,QInputDialog,QLabel,QLineEdit,QMessageBox,QPushButton,
    QSpinBox,QTableWidget,QTableWidgetItem,QTabWidget,QTextEdit,QVBoxLayout,QWidget
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


class SupplierOrderDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Supplier Order")
        form=QFormLayout(self)
        self.order_no=QLineEdit(row.order_no if row else "")
        self.supplier=QLineEdit(row.supplier if row else "")
        self.expected=QDateTimeEdit();self.expected.setCalendarPopup(True);self.expected.setDateTime(row.expected_at if row and row.expected_at else __import__("datetime").datetime.now())
        self.reference=QLineEdit(row.external_reference if row else "")
        self.notes=QTextEdit(row.notes if row else "");self.notes.setMaximumHeight(100)
        form.addRow("Order / PO no.",self.order_no);form.addRow("Supplier",self.supplier);form.addRow("Expected",self.expected);form.addRow("External reference",self.reference);form.addRow("Notes",self.notes)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);form.addRow(buttons)
    def data(self):
        return {"order_no":self.order_no.text().strip(),"supplier":self.supplier.text().strip(),"expected_at":self.expected.dateTime().toPython(),"external_reference":self.reference.text().strip(),"notes":self.notes.toPlainText().strip()}


class SupplierOrderLineDialog(QDialog):
    def __init__(self,locations,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Supplier Order Line")
        form=QFormLayout(self)
        self.part=QLineEdit(row.part_number if row else "")
        self.supplier_part=QLineEdit(row.supplier_part_number if row else "")
        self.qty=QDoubleSpinBox();self.qty.setRange(0.0001,1e9);self.qty.setDecimals(3);self.qty.setValue(float(row.ordered_qty if row else 1))
        self.unit_cost=QDoubleSpinBox();self.unit_cost.setRange(0,1e12);self.unit_cost.setDecimals(2);self.unit_cost.setValue(float(row.unit_cost if row else 0))
        self.currency=QComboBox();self.currency.addItems(["JPY","USD","EUR","PHP","CNY","KRW"]);self.currency.setCurrentText(row.currency if row else "JPY")
        self.location=QComboBox();self.location.setEditable(True);self.location.addItems(locations);self.location.setCurrentText(row.destination_location if row else (locations[0] if locations else ""))
        self.note=QLineEdit(row.note if row else "")
        form.addRow("Part number",self.part);form.addRow("Supplier part no.",self.supplier_part);form.addRow("Ordered qty",self.qty);form.addRow("Unit cost",self.unit_cost);form.addRow("Currency",self.currency);form.addRow("Destination",self.location);form.addRow("Note",self.note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);form.addRow(buttons)
    def data(self):
        return {"part_number":self.part.text().strip(),"supplier_part_number":self.supplier_part.text().strip(),"ordered_qty":self.qty.value(),"unit_cost":self.unit_cost.value(),"currency":self.currency.currentText(),"destination_location":self.location.currentText().strip(),"note":self.note.text().strip()}


class RotableDialog(QDialog):
    def __init__(self,locations,row=None,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle("Register / Edit Rotable")
        form=QFormLayout(self)
        self.asset=QLineEdit(row.asset_id if row else "");self.part=QLineEdit(row.part_number if row else "");self.serial=QLineEdit(row.serial_number if row else "")
        self.description=QLineEdit(row.description if row else "")
        self.location=QComboBox();self.location.setEditable(True);self.location.addItems(locations);self.location.setCurrentText(row.current_location if row else (locations[0] if locations else ""))
        self.notes=QTextEdit(row.notes if row else "");self.notes.setMaximumHeight(90)
        form.addRow("Asset ID",self.asset);form.addRow("Part number",self.part);form.addRow("Serial number",self.serial);form.addRow("Description",self.description);form.addRow("Stock location",self.location);form.addRow("Notes",self.notes)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);form.addRow(buttons)
    def data(self):
        return {"asset_id":self.asset.text().strip(),"part_number":self.part.text().strip(),"serial_number":self.serial.text().strip(),"description":self.description.text().strip(),"current_location":self.location.currentText().strip(),"notes":self.notes.toPlainText().strip()}


class RotableTransitionDialog(QDialog):
    def __init__(self,row,locations,equipment,parent=None):
        super().__init__(parent);self.row=row;self.setWindowTitle(f"Rotable Transition — {row.asset_id}")
        form=QFormLayout(self)
        self.status=QComboBox();self.status.addItems(["Stock","Installed","In Repair","Quarantine","Scrapped"])
        self.location=QComboBox();self.location.setEditable(True);self.location.addItems(locations);self.location.setCurrentText(row.current_location or (locations[0] if locations else ""))
        self.equipment=QComboBox();self.equipment.setEditable(True);self.equipment.addItems(equipment);self.equipment.setCurrentText(row.equipment_id or "")
        self.component=QLineEdit(row.component_id or "");self.vendor=QLineEdit(row.vendor or "");self.reference=QLineEdit(row.repair_reference or "");self.note=QTextEdit();self.note.setMaximumHeight(90)
        form.addRow("New status",self.status);form.addRow("Location",self.location);form.addRow("Equipment",self.equipment);form.addRow("Component ID",self.component);form.addRow("Repair vendor",self.vendor);form.addRow("Reference / RMA",self.reference);form.addRow("Note",self.note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);form.addRow(buttons)
    def data(self):
        return {"target_status":self.status.currentText(),"location_code":self.location.currentText().strip(),"equipment_id":self.equipment.currentText().strip(),"component_id":self.component.text().strip(),"vendor":self.vendor.text().strip(),"reference":self.reference.text().strip(),"note":self.note.toPlainText().strip()}


class InventoryLogisticsWorkspace(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.stock=[];self.catalog=[];self.reorder=[];self.alternates=[];self.kit=None;self.orders=[];self.order_lines=[];self.rotables=[];self.rotable_events=[]
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
        self.res_table=_table(["Reservation","Part","Location","Qty","Status","Reserved By"]);kv.addWidget(QLabel("Reservations"));kv.addWidget(self.res_table,1)
        stagebar=QHBoxLayout();stage=QPushButton("Mark Kit Staged");issue=QPushButton("Issue Kit");complete=QPushButton("Complete Kit");stage.clicked.connect(lambda:self.set_kit_stage("Staged"));issue.clicked.connect(lambda:self.set_kit_stage("Issued"));complete.clicked.connect(lambda:self.set_kit_stage("Completed"));stagebar.addWidget(stage);stagebar.addWidget(issue);stagebar.addWidget(complete);stagebar.addStretch(1);kv.addLayout(stagebar)
        self.stage_label=QLabel();self.stage_label.setStyleSheet("color:#647581");kv.addWidget(self.stage_label);tabs.addTab(kit,"PM Kits")

        po=QWidget();pov=QVBoxLayout(po);poh=QHBoxLayout();newpo=QPushButton("New / Edit PO");addline=QPushButton("Add / Edit Line");submit=QPushButton("Submit PO");receivepo=QPushButton("Receive Selected Line");cancelpo=QPushButton("Cancel PO")
        newpo.clicked.connect(self.edit_order);addline.clicked.connect(self.edit_order_line);submit.clicked.connect(self.submit_order);receivepo.clicked.connect(self.receive_order_line);cancelpo.clicked.connect(self.cancel_order)
        for b in [newpo,addline,submit,receivepo,cancelpo]:poh.addWidget(b)
        poh.addStretch(1);pov.addLayout(poh)
        self.order_table=_table(["PO","Supplier","Status","Order Date","Expected","Reference","Created By","Submitted By","Version"]);self.order_table.itemSelectionChanged.connect(self.load_order_lines);pov.addWidget(self.order_table,1)
        self.order_line_table=_table(["Line","Part","Supplier PN","Ordered","Received","Unit Cost","Currency","Destination","Status","Note","Version"]);pov.addWidget(QLabel("Order lines"));pov.addWidget(self.order_line_table,1);tabs.addTab(po,"Supplier Orders")

        rot=QWidget();rotv=QVBoxLayout(rot);roth=QHBoxLayout();self.rotable_search=QLineEdit();self.rotable_search.setPlaceholderText("Search asset / part / serial / equipment / vendor");self.rotable_search.textChanged.connect(self.load_rotables);register=QPushButton("Register / Edit");transition=QPushButton("Lifecycle Transition");register.clicked.connect(self.edit_rotable);transition.clicked.connect(self.transition_rotable);roth.addWidget(self.rotable_search,1);roth.addWidget(register);roth.addWidget(transition);rotv.addLayout(roth)
        self.rotable_table=_table(["Asset","Part","Serial","Description","Status","Condition","Location","Equipment","Component","Vendor","Repair Ref","Repairs","Version"]);self.rotable_table.itemSelectionChanged.connect(self.load_rotable_events);rotv.addWidget(self.rotable_table,2)
        self.rotable_event_table=_table(["Time","Event","From","To","Location","Equipment","Reference","User","Note"]);rotv.addWidget(QLabel("Rotable lifecycle history"));rotv.addWidget(self.rotable_event_table,1);tabs.addTab(rot,"Rotables / Repairables")

        self.refresh()

    def refresh(self):
        self.load_stock();self.load_reorder();self.load_catalog();self.load_orders();self.load_rotables()
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
        stage=self.db.pm_kit_stage(self.task.value())
        self.stage_label.setText(f"Kit stage: {stage.status} · {stage.staging_location or 'no staging location'} · staged by {stage.staged_by or '—'}" if stage else "Kit stage: not staged")

    def reserve_kit(self):
        if not self.task.value():return
        try:
            rows=self.db.reserve_pm_required_parts(self.task.value(),self.user["username"],"INVENTORY-LOGISTICS")
            notify(f"Created {len(rows)} reservation(s)." if rows else "Kit already reserved or no required parts.")
            self.refresh()
        except Exception as exc:QMessageBox.critical(self,"PM Kit",str(exc))

    def set_kit_stage(self,status: str):
        if not self.task.value():return
        stage=self.db.pm_kit_stage(self.task.value())
        location=stage.staging_location if stage else ""
        if status=="Staged":
            locations=self._locations()
            location,ok=QInputDialog.getItem(self,"PM Kit Staging","Staging location",locations,0,True) if locations else QInputDialog.getText(self,"PM Kit Staging","Staging location")
            if not ok:return
        note,ok=QInputDialog.getText(self,"PM Kit",f"{status} note")
        if not ok:return
        try:self.db.set_pm_kit_stage(self.task.value(),status,self.user["username"],location,note,stage.version if stage else None);self.load_kit()
        except Exception as exc:QMessageBox.critical(self,"PM Kit",str(exc))

    def load_orders(self):
        current=_selected(self.order_table,self.orders) if hasattr(self,"order_table") else None;key=current.order_no if current else ""
        self.orders=self.db.list_supplier_orders()
        if hasattr(self,"order_table"):_fill(self.order_table,self.orders,["order_no","supplier","status","order_date","expected_at","external_reference","created_by","submitted_by","version"])
        if key:
            for i,row in enumerate(self.orders):
                if row.order_no==key:self.order_table.selectRow(i);break
        self.load_order_lines()

    def load_order_lines(self):
        row=_selected(self.order_table,self.orders) if hasattr(self,"order_table") else None
        self.order_lines=self.db.list_supplier_order_lines(row.order_no) if row else []
        if hasattr(self,"order_line_table"):_fill(self.order_line_table,self.order_lines,["line_no","part_number","supplier_part_number","ordered_qty","received_qty","unit_cost","currency","destination_location","status","note","version"])

    def edit_order(self):
        current=_selected(self.order_table,self.orders)
        d=SupplierOrderDialog(current,self)
        if d.exec()!=QDialog.DialogCode.Accepted:return
        try:self.db.save_supplier_order(d.data(),self.user["username"],current.version if current else None);self.load_orders()
        except Exception as exc:QMessageBox.critical(self,"Supplier Order",str(exc))

    def edit_order_line(self):
        order=_selected(self.order_table,self.orders)
        if not order:QMessageBox.information(self,"Supplier Order","Select a supplier order first.");return
        current=_selected(self.order_line_table,self.order_lines)
        d=SupplierOrderLineDialog(self._locations(),current,self)
        if d.exec()!=QDialog.DialogCode.Accepted:return
        data=d.data()
        if current:data["line_no"]=current.line_no
        try:self.db.add_supplier_order_line(order.order_no,data,self.user["username"],current.version if current else None);self.load_orders()
        except Exception as exc:QMessageBox.critical(self,"Supplier Order Line",str(exc))

    def submit_order(self):
        order=_selected(self.order_table,self.orders)
        if not order:return
        try:self.db.submit_supplier_order(order.order_no,self.user["username"],order.version);self.load_orders()
        except Exception as exc:QMessageBox.critical(self,"Submit Supplier Order",str(exc))

    def receive_order_line(self):
        line=_selected(self.order_line_table,self.order_lines)
        if not line:return
        remaining=max(0.0,float(line.ordered_qty or 0)-float(line.received_qty or 0))
        if remaining<=0:QMessageBox.information(self,"Receipt","Selected line is already fully received.");return
        qty,ok=QInputDialog.getDouble(self,"Receive PO Line",f"Quantity to receive (remaining {remaining:g})",remaining,0.0001,remaining,3)
        if not ok:return
        ref,ok=QInputDialog.getText(self,"Receive PO Line","Receipt / delivery reference")
        if not ok:return
        try:self.db.receive_supplier_order_line(line.id,qty,self.user["username"],ref);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Receive PO Line",str(exc))

    def cancel_order(self):
        order=_selected(self.order_table,self.orders)
        if not order:return
        reason,ok=QInputDialog.getText(self,"Cancel Supplier Order","Reason")
        if not ok:return
        try:self.db.cancel_supplier_order(order.order_no,self.user["username"],reason);self.load_orders()
        except Exception as exc:QMessageBox.critical(self,"Cancel Supplier Order",str(exc))

    def load_rotables(self):
        q=self.rotable_search.text().strip() if hasattr(self,"rotable_search") else ""
        self.rotables=self.db.list_rotables(q)
        if hasattr(self,"rotable_table"):_fill(self.rotable_table,self.rotables,["asset_id","part_number","serial_number","description","status","condition","current_location","equipment_id","component_id","vendor","repair_reference","repair_count","version"])
        self.load_rotable_events()

    def load_rotable_events(self):
        row=_selected(self.rotable_table,self.rotables) if hasattr(self,"rotable_table") else None
        self.rotable_events=self.db.list_rotable_events(row.asset_id) if row else []
        if hasattr(self,"rotable_event_table"):_fill(self.rotable_event_table,self.rotable_events,["occurred_at","event_type","from_status","to_status","location_code","equipment_id","reference","user","note"])

    def edit_rotable(self):
        current=_selected(self.rotable_table,self.rotables)
        d=RotableDialog(self._locations(),current,self)
        if d.exec()!=QDialog.DialogCode.Accepted:return
        try:self.db.register_rotable(d.data(),self.user["username"],current.version if current else None);self.load_rotables()
        except Exception as exc:QMessageBox.critical(self,"Rotable",str(exc))

    def transition_rotable(self):
        current=_selected(self.rotable_table,self.rotables)
        if not current:return
        equipment=[x.equipment_id for x in self.db.list_equipment()]
        d=RotableTransitionDialog(current,self._locations(),equipment,self)
        if d.exec()!=QDialog.DialogCode.Accepted:return
        try:self.db.transition_rotable(current.asset_id,user=self.user["username"],expected_version=current.version,**d.data());self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Rotable Transition",str(exc))
