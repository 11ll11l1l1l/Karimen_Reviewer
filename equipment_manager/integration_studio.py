from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,QCheckBox,QComboBox,QDialog,QDialogButtonBox,QFileDialog,QFormLayout,
    QHBoxLayout,QHeaderView,QInputDialog,QLabel,QLineEdit,QMessageBox,QPushButton,
    QTableWidget,QTableWidgetItem,QTabWidget,QVBoxLayout,QWidget
)

from inbound_integrations import preview_inbound_file,process_inbound_endpoint,process_inbound_file
from integrations import dispatch_pending
from table_productivity import install_table_productivity


TARGET_FIELDS={
    "ALARM":[
        ("equipment_id","Equipment ID",True),("alarm_code","Alarm code",True),("state","State",False),
        ("severity","Severity",False),("message","Message",False),("source","Source",False),
        ("event_key","Event key",False),("occurred_at","Occurred at",False),("related_ticket","Related ticket",False),
    ],
    "METER":[
        ("equipment_id","Equipment ID",True),("meter_code","Meter code",True),("value","Value",True),
        ("note","Note",False),("reset","Reset flag",False),
    ],
}


def _item(value):
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers,multi=False):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection if multi else QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);t.setAlternatingRowColors(True)
    install_table_productivity(t,headers[0] if headers else "Integration Studio")
    return t


def _fill(table,rows,fields):
    table.setRowCount(len(rows))
    for r,row in enumerate(rows):
        for c,field in enumerate(fields):
            value=row.get(field,"") if isinstance(row,dict) else getattr(row,field,"")
            table.setItem(r,c,_item(value))


def _selected(table,rows):
    i=table.currentRow();return rows[i] if 0<=i<len(rows) else None


class InboundMappingDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent);self.row=row;self.mapping_widgets={};self.default_widgets={}
        self.setWindowTitle("Inbound Mapping");self.resize(900,720)
        root=QVBoxLayout(self);form=QFormLayout()
        self.endpoint=QLineEdit(row.endpoint_id if row else "");self.name=QLineEdit(row.name if row else "")
        self.adapter=QComboBox();self.adapter.addItems(["FILE_JSON","FILE_CSV"]);self.adapter.setCurrentText(row.adapter_type if row else "FILE_JSON")
        self.entity=QComboBox();self.entity.addItems(["ALARM","METER"]);self.entity.setCurrentText(row.entity_type if row else "ALARM")
        self.source=QLineEdit(row.source_path if row else "");source_b=QPushButton("Browse");source_b.clicked.connect(self.choose_source);source_h=QHBoxLayout();source_h.addWidget(self.source,1);source_h.addWidget(source_b)
        self.pattern=QLineEdit(row.file_pattern if row else "*.json")
        self.archive=QLineEdit(row.archive_path if row else "");self.quarantine=QLineEdit(row.quarantine_path if row else "")
        self.enabled=QCheckBox("Enabled");self.enabled.setChecked(row.enabled if row else True)
        if row:self.endpoint.setReadOnly(True)
        form.addRow("Endpoint ID",self.endpoint);form.addRow("Name",self.name);form.addRow("Adapter",self.adapter);form.addRow("Target",self.entity);form.addRow("Source folder",source_h);form.addRow("File pattern",self.pattern);form.addRow("Archive folder",self.archive);form.addRow("Quarantine folder",self.quarantine);form.addRow("",self.enabled)
        root.addLayout(form)
        note=QLabel("Map each EMS target field to a source column/key. Dotted JSON paths such as equipment.id are supported. Defaults apply only when the mapped source value is blank.")
        note.setWordWrap(True);note.setStyleSheet("color:#647581");root.addWidget(note)
        self.map_table=QTableWidget();self.map_table.setColumnCount(4);self.map_table.setHorizontalHeaderLabels(["EMS Target","Required","Source column / JSON path","Default"]);self.map_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);root.addWidget(self.map_table,1)
        self.entity.currentTextChanged.connect(self.rebuild_mapping)
        self.adapter.currentTextChanged.connect(self.adapter_changed)
        self._existing_mapping=json.loads(row.mapping_json or "{}") if row else {}
        self._existing_defaults=json.loads(row.defaults_json or "{}") if row else {}
        self.rebuild_mapping()
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.validate_accept);buttons.rejected.connect(self.reject);root.addWidget(buttons)

    def choose_source(self):
        path=QFileDialog.getExistingDirectory(self,"Inbound source folder",self.source.text().strip() or str(Path.cwd()))
        if path:self.source.setText(path)

    def adapter_changed(self):
        if not self.pattern.text().strip() or self.pattern.text() in {"*.json","*.csv"}:
            self.pattern.setText("*.csv" if self.adapter.currentText()=="FILE_CSV" else "*.json")

    def rebuild_mapping(self):
        old_sources={};old_defaults={}
        for key,w in self.mapping_widgets.items():old_sources[key]=w.text()
        for key,w in self.default_widgets.items():old_defaults[key]=w.text()
        self.mapping_widgets={};self.default_widgets={}
        fields=TARGET_FIELDS[self.entity.currentText()];self.map_table.setRowCount(len(fields))
        for r,(key,label,required) in enumerate(fields):
            self.map_table.setItem(r,0,_item(f"{label} ({key})"));self.map_table.setItem(r,1,_item("Yes" if required else "No"))
            source=QLineEdit(old_sources.get(key,self._existing_mapping.get(key,"")));default=QLineEdit(old_defaults.get(key,str(self._existing_defaults.get(key,"") if key in self._existing_defaults else "")))
            source.setPlaceholderText("source field / dotted.path")
            self.mapping_widgets[key]=source;self.default_widgets[key]=default;self.map_table.setCellWidget(r,2,source);self.map_table.setCellWidget(r,3,default)

    def mapping(self):
        return {k:w.text().strip() for k,w in self.mapping_widgets.items() if w.text().strip()}

    def defaults(self):
        return {k:w.text().strip() for k,w in self.default_widgets.items() if w.text().strip()}

    def validate_accept(self):
        if not self.endpoint.text().strip() or not self.source.text().strip():
            QMessageBox.warning(self,"Inbound Mapping","Endpoint ID and source folder are required.");return
        missing=[label for key,label,required in TARGET_FIELDS[self.entity.currentText()] if required and not self.mapping().get(key) and key not in self.defaults()]
        if missing:
            QMessageBox.warning(self,"Inbound Mapping","Required fields need a source mapping or default: "+", ".join(missing));return
        self.accept()

    def data(self):
        return {
            "endpoint_id":self.endpoint.text().strip(),"name":self.name.text().strip(),
            "adapter_type":self.adapter.currentText(),"entity_type":self.entity.currentText(),
            "source_path":self.source.text().strip(),"file_pattern":self.pattern.text().strip(),
            "mapping_json":json.dumps(self.mapping(),sort_keys=True),"defaults_json":json.dumps(self.defaults(),sort_keys=True),
            "archive_path":self.archive.text().strip(),"quarantine_path":self.quarantine.text().strip(),
            "enabled":self.enabled.isChecked(),
        }


class IntegrationStudio(QWidget):
    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.inbound=[];self.receipts=[];self.records=[];self.outbound=[];self.deliveries=[]
        can_admin=db.has_permission(user,"user.admin") or user.get("role")=="Administrator"
        root=QVBoxLayout(self);head=QHBoxLayout();title=QLabel("Integration Studio");title.setStyleSheet("font-size:20pt;font-weight:800");note=QLabel("Map, preview, operate and troubleshoot plant data exchange without editing JSON by hand.");note.setStyleSheet("color:#647581");refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh);head.addWidget(title);head.addWidget(note);head.addStretch(1);head.addWidget(refresh);root.addLayout(head)
        tabs=QTabWidget();root.addWidget(tabs,1)

        inbound=QWidget();iv=QVBoxLayout(inbound);ih=QHBoxLayout()
        add=QPushButton("New Mapping");edit=QPushButton("Edit Mapping");preview=QPushButton("Preview Sample File");process=QPushButton("Process Feed");replay=QPushButton("Replay Receipt")
        add.clicked.connect(self.add_inbound);edit.clicked.connect(self.edit_inbound);preview.clicked.connect(self.preview_sample);process.clicked.connect(self.process_feed);replay.clicked.connect(self.replay_receipt)
        for b in [add,edit,process,replay]:b.setEnabled(can_admin)
        for b in [add,edit,preview,process,replay]:ih.addWidget(b)
        ih.addStretch(1);iv.addLayout(ih)
        self.inbound_table=_table(["Endpoint","Name","Adapter","Target","Source","Pattern","Enabled","Version"]);self.inbound_table.itemSelectionChanged.connect(self.load_receipts);iv.addWidget(self.inbound_table,1)
        self.receipt_table=_table(["ID","Source","Status","Total","Applied","Rejected","Error","Processed"]);self.receipt_table.itemSelectionChanged.connect(self.load_records);iv.addWidget(QLabel("Receipts"));iv.addWidget(self.receipt_table,1)
        self.record_table=_table(["Row","Target","Status","Entity Key","Error","Processed"]);iv.addWidget(QLabel("Record results"));iv.addWidget(self.record_table,1);tabs.addTab(inbound,"Inbound Mapping / Replay")

        outbound=QWidget();ov=QVBoxLayout(outbound);oh=QHBoxLayout();dispatch=QPushButton("Dispatch Pending Now");requeue=QPushButton("Requeue Selected");dead=QPushButton("Dead-letter Selected");all_dead=QPushButton("Requeue All Dead Letters")
        dispatch.clicked.connect(self.dispatch_now);requeue.clicked.connect(self.requeue_selected);dead.clicked.connect(self.dead_letter_selected);all_dead.clicked.connect(self.requeue_all_dead)
        for b in [dispatch,requeue,dead,all_dead]:b.setEnabled(can_admin);oh.addWidget(b)
        oh.addStretch(1);ov.addLayout(oh)
        self.outbound_table=_table(["Endpoint","Name","Adapter","Target","Topics","Enabled","Version"]);ov.addWidget(self.outbound_table,1)
        self.delivery_table=_table(["ID","Topic","Entity","Key","Endpoint","Status","Attempts","Next Attempt","Last Error","Sent"]);ov.addWidget(QLabel("Delivery operations"));ov.addWidget(self.delivery_table,2);tabs.addTab(outbound,"Outbound / Delivery Operations")
        self.refresh()

    def refresh(self):
        self.inbound=self.db.list_inbound_endpoints();_fill(self.inbound_table,self.inbound,["endpoint_id","name","adapter_type","entity_type","source_path","file_pattern","enabled","version"])
        self.outbound=self.db.list_integration_endpoints();_fill(self.outbound_table,self.outbound,["endpoint_id","name","adapter_type","target","topics","enabled","version"])
        self.deliveries=self.db.integration_delivery_rows(1500);_fill(self.delivery_table,self.deliveries,["id","topic","entity_type","entity_key","endpoint_id","status","attempts","next_attempt_at","last_error","sent_at"])
        self.load_receipts()

    def current_inbound(self):return _selected(self.inbound_table,self.inbound)

    def add_inbound(self):
        d=InboundMappingDialog(parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_inbound_endpoint(d.data());self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Integration Studio",str(exc))

    def edit_inbound(self):
        row=self.current_inbound()
        if not row:return
        d=InboundMappingDialog(row,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.db.save_inbound_endpoint(d.data(),row.version);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"Integration Studio",str(exc))

    def preview_sample(self):
        row=self.current_inbound()
        if not row:return
        pattern="CSV (*.csv)" if row.adapter_type=="FILE_CSV" else "JSON (*.json)"
        path,_=QFileDialog.getOpenFileName(self,"Preview inbound sample",row.source_path,pattern+";;All Files (*)")
        if not path:return
        try:result=preview_inbound_file(self.db,row.endpoint_id,path,100)
        except Exception as exc:QMessageBox.critical(self,"Inbound Preview",str(exc));return
        dialog=QDialog(self);dialog.setWindowTitle(f"Preview — {row.endpoint_id}");dialog.resize(1100,650);layout=QVBoxLayout(dialog)
        summary=QLabel(f"{result['records_total']} total record(s) · previewed {result['previewed']} · valid {result['valid']} · invalid {result['invalid']}");layout.addWidget(summary)
        table=_table(["Row","Valid","Error","Mapped Output"])
        table.setRowCount(len(result["rows"]))
        for r,item in enumerate(result["rows"]):
            vals=[item["row"],"Yes" if item["valid"] else "No",item["error"],json.dumps(item["mapped"],default=str,ensure_ascii=False,sort_keys=True)]
            for col,val in enumerate(vals):table.setItem(r,col,_item(val))
        layout.addWidget(table,1);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.reject);buttons.clicked.connect(dialog.accept);layout.addWidget(buttons);dialog.exec()

    def process_feed(self):
        row=self.current_inbound()
        if not row:return
        try:
            stats=process_inbound_endpoint(self.db,row.endpoint_id,500)
            QMessageBox.information(self,"Inbound Feed",f"Files {stats['files']} · processed {stats['processed']} · quarantined/partial {stats['quarantined']} · duplicates {stats['duplicates']} · applied {stats['applied']} · rejected {stats['rejected']}")
            self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Inbound Feed",str(exc))

    def load_receipts(self):
        row=self.current_inbound()
        self.receipts=self.db.list_inbound_receipts(row.endpoint_id if row else "",1000)
        _fill(self.receipt_table,self.receipts,["id","source_name","status","records_total","records_applied","records_rejected","error","processed_at"])
        self.load_records()

    def load_records(self):
        receipt=_selected(self.receipt_table,self.receipts)
        self.records=self.db.list_inbound_records(receipt_id=receipt.id if receipt else None,limit=3000) if receipt else []
        _fill(self.record_table,self.records,["row_index","target_entity","status","entity_key","error","processed_at"])

    def replay_receipt(self):
        receipt=_selected(self.receipt_table,self.receipts)
        if not receipt:return
        try:detail=json.loads(receipt.detail_json or "{}")
        except Exception:detail={}
        path=str(detail.get("final_path") or "")
        if not path or not Path(path).is_file():
            QMessageBox.warning(self,"Replay","The archived/quarantined source file is no longer available.");return
        if QMessageBox.question(self,"Replay",f"Replay receipt {receipt.id}?\n{path}")!=QMessageBox.StandardButton.Yes:return
        try:
            result=process_inbound_file(self.db,receipt.endpoint_id,path,replay=True);self.refresh()
            QMessageBox.information(self,"Replay",f"{result['status']} · applied {result['applied']} · rejected {result['rejected']} · skipped {result['skipped']}")
        except Exception as exc:QMessageBox.critical(self,"Replay",str(exc))

    def dispatch_now(self):
        try:
            result=dispatch_pending(self.db,1000);self.refresh();QMessageBox.information(self,"Outbound Dispatch",f"Pending {result['pending']} · sent {result['sent']} · failed {result['failed']}")
        except Exception as exc:QMessageBox.critical(self,"Outbound Dispatch",str(exc))

    def _selected_delivery_ids(self):
        rows=sorted({idx.row() for idx in self.delivery_table.selectedIndexes()})
        return [int(self.deliveries[i]["id"]) for i in rows if 0<=i<len(self.deliveries)]

    def requeue_selected(self):
        ids=self._selected_delivery_ids()
        for value in ids:self.db.requeue_integration_delivery(value,False)
        if ids:self.refresh()

    def dead_letter_selected(self):
        ids=self._selected_delivery_ids()
        if not ids:return
        reason,ok=QInputDialog.getText(self,"Dead Letter","Reason")
        if not ok:return
        failures=[]
        for value in ids:
            try:self.db.dead_letter_integration_delivery(value,reason)
            except Exception as exc:failures.append(f"{value}: {exc}")
        self.refresh()
        if failures:QMessageBox.warning(self,"Dead Letter","\n".join(failures[:20]))

    def requeue_all_dead(self):
        try:
            count=self.db.requeue_dead_letters();self.refresh();QMessageBox.information(self,"Dead Letters",f"Requeued {count} delivery record(s).")
        except Exception as exc:QMessageBox.critical(self,"Dead Letters",str(exc))
