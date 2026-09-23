from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QSplitter,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from attachment_store import store_attachment_file, store_clipboard_image
from services import readonly_open_copy

FILE_ROOT=os.getenv("EMS_FILE_ROOT",str(Path.cwd()/"equipment_files"))


def _item(value: Any) -> QTableWidgetItem:
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers: list[str]) -> QTableWidget:
    table=QTableWidget(0,len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    return table


def _fill_objects(table: QTableWidget, rows: list[Any], fields: list[str]):
    table.setRowCount(len(rows))
    for r,row in enumerate(rows):
        for c,field in enumerate(fields):
            value=row.get(field,"") if isinstance(row,dict) else getattr(row,field,"")
            table.setItem(r,c,_item(value))


def _selected(table: QTableWidget, rows: list[Any]):
    i=table.currentRow()
    return rows[i] if 0<=i<len(rows) else None


class AttachmentPanel(QWidget):
    changed=Signal()

    def __init__(self,db,user,entity_type: str="",entity_key: str="",equipment_id: str="",parent=None):
        super().__init__(parent)
        self.db=db;self.user=user;self.entity_type=entity_type;self.entity_key=str(entity_key);self.equipment_id=equipment_id
        self.rows=[]
        root=QVBoxLayout(self);buttons=QHBoxLayout()
        self.add_button=QPushButton("Add files")
        self.paste_button=QPushButton("Paste screenshot")
        self.open_button=QPushButton("Open")
        self.edit_button=QPushButton("Edit metadata")
        self.remove_button=QPushButton("Remove link")
        self.add_button.clicked.connect(self.add_files)
        self.paste_button.clicked.connect(self.paste_screenshot)
        self.open_button.clicked.connect(self.open_selected)
        self.edit_button.clicked.connect(self.edit_selected)
        self.remove_button.clicked.connect(self.remove_selected)
        for b in [self.add_button,self.paste_button,self.open_button,self.edit_button,self.remove_button]:buttons.addWidget(b)
        buttons.addStretch(1);root.addLayout(buttons)
        self.table=_table(["Name","Category","Caption","Tags","Type","Size","Added by","Added"])
        self.table.doubleClicked.connect(self.open_selected)
        root.addWidget(self.table,1)
        self.empty=QLabel("Select a record to view or attach evidence.")
        self.empty.setStyleSheet("color:#647581;")
        root.addWidget(self.empty)
        self.refresh()

    def set_entity(self,entity_type: str,entity_key: str,equipment_id: str=""):
        self.entity_type=(entity_type or "").upper();self.entity_key=str(entity_key or "");self.equipment_id=equipment_id or ""
        self.refresh()

    def refresh(self):
        enabled=bool(self.entity_type and self.entity_key)
        for b in [self.add_button,self.paste_button,self.open_button,self.edit_button,self.remove_button]:b.setEnabled(enabled)
        self.rows=self.db.list_attachments(self.entity_type,self.entity_key) if enabled else []
        _fill_objects(self.table,self.rows,["original_name","category","caption","tags","media_type","file_size","created_by","created_at"])
        self.empty.setVisible(not enabled or not self.rows)

    def _register(self,stored: dict,caption: str="",category: str="Evidence"):
        row=self.db.add_attachment(
            self.entity_type,self.entity_key,stored["stored_path"],
            original_name=stored.get("original_name",""),
            media_type=stored.get("media_type",""),
            category=category,caption=caption,equipment_id=self.equipment_id,
            created_by=self.user["username"],
        )
        self.refresh();self.changed.emit();return row

    def add_files(self):
        if not self.entity_key:return
        paths,_=QFileDialog.getOpenFileNames(self,"Attach evidence / file")
        if not paths:return
        category,ok=QInputDialog.getItem(self,"Attachment category","Category",["Evidence","Screenshot","Photo","Log","Spreadsheet","Report","Reference","Other"],0,False)
        if not ok:return
        failures=[]
        for path in paths:
            try:self._register(store_attachment_file(path,FILE_ROOT,self.entity_type,self.entity_key),category=category)
            except Exception as exc:failures.append(f"{Path(path).name}: {exc}")
        if failures:QMessageBox.warning(self,"Attachments","Some files could not be attached:\n"+"\n".join(failures[:12]))

    def paste_screenshot(self):
        if not self.entity_key:return
        image=QApplication.clipboard().image()
        if image.isNull():
            QMessageBox.warning(self,"Clipboard","Clipboard does not contain an image.")
            return
        caption,ok=QInputDialog.getText(self,"Screenshot","Caption (optional)")
        if not ok:return
        try:self._register(store_clipboard_image(image,FILE_ROOT,self.entity_type,self.entity_key),caption=caption,category="Screenshot")
        except Exception as exc:QMessageBox.critical(self,"Screenshot",str(exc))

    def open_selected(self):
        row=_selected(self.table,self.rows)
        if not row:return
        try:readonly_open_copy(row.stored_path)
        except Exception as exc:QMessageBox.critical(self,"Attachment",str(exc))

    def edit_selected(self):
        row=_selected(self.table,self.rows)
        if not row:return
        category,ok=QInputDialog.getText(self,"Attachment","Category",text=row.category)
        if not ok:return
        caption,ok=QInputDialog.getText(self,"Attachment","Caption",text=row.caption)
        if not ok:return
        tags,ok=QInputDialog.getText(self,"Attachment","Tags",text=row.tags)
        if not ok:return
        try:self.db.update_attachment_metadata(row.id,caption,tags,category,self.user["username"]);self.refresh();self.changed.emit()
        except Exception as exc:QMessageBox.critical(self,"Attachment",str(exc))

    def remove_selected(self):
        row=_selected(self.table,self.rows)
        if not row:return
        if QMessageBox.question(self,"Remove attachment",f"Remove this EMS attachment link?\n{row.original_name}")!=QMessageBox.StandardButton.Yes:return
        try:self.db.remove_attachment(row.id,self.user["username"]);self.refresh();self.changed.emit()
        except Exception as exc:QMessageBox.critical(self,"Attachment",str(exc))


class SearchWorkspace(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.results=[];self.recents=[];self.favorites=[]
        root=QVBoxLayout(self)
        title=QLabel("Global Search");title.setStyleSheet("font-size:18pt;font-weight:700");root.addWidget(title)
        self.query=QLineEdit();self.query.setPlaceholderText("Search equipment, ticket, PM, alarm, part, document…");self.query.returnPressed.connect(self.search)
        root.addWidget(self.query)
        tabs=QTabWidget();root.addWidget(tabs,1)
        self.result_table=_table(["Type","Key","Title","Context","Equipment"]);self.result_table.doubleClicked.connect(lambda *_:self._open(self.result_table,self.results))
        wr=QWidget();vr=QVBoxLayout(wr);vr.addWidget(self.result_table);tabs.addTab(wr,"Results")
        self.recent_table=_table(["Type","Key","Title","Equipment","Last opened"]);self.recent_table.doubleClicked.connect(lambda *_:self._open_recent())
        wrecent=QWidget();vrecent=QVBoxLayout(wrecent);vrecent.addWidget(self.recent_table);tabs.addTab(wrecent,"Recent")
        self.favorite_table=_table(["Type","Key","Title","Equipment"]);self.favorite_table.doubleClicked.connect(lambda *_:self._open_favorite())
        wf=QWidget();vf=QVBoxLayout(wf);vf.addWidget(self.favorite_table);tabs.addTab(wf,"Favorites")
        self.refresh()

    def set_query(self,text: str):
        self.query.setText(text);self.search()

    def search(self):
        self.results=self.db.global_search(self.query.text(),100)
        _fill_objects(self.result_table,self.results,["entity_type","entity_key","title","subtitle","equipment_id"])

    def refresh(self):
        self.recents=self.db.list_recent_items(self.user["username"],40)
        self.favorites=self.db.list_favorites(self.user["username"])
        _fill_objects(self.recent_table,self.recents,["entity_type","entity_key","title","equipment_id","opened_at"])
        _fill_objects(self.favorite_table,self.favorites,["entity_type","entity_key","title","equipment_id"])
        if self.query.text().strip():self.search()

    def _open(self,table,rows):
        row=_selected(table,rows)
        if not row:return
        self.db.record_recent_item(self.user["username"],row["entity_type"],row["entity_key"],row["title"],row.get("equipment_id",""))
        self.open_entity.emit(row["entity_type"],row["entity_key"],row.get("equipment_id",""))
        self.refresh()

    def _open_recent(self):
        row=_selected(self.recent_table,self.recents)
        if row:self.open_entity.emit(row.entity_type,row.entity_key,row.equipment_id or "")

    def _open_favorite(self):
        row=_selected(self.favorite_table,self.favorites)
        if row:self.open_entity.emit(row.entity_type,row.entity_key,row.equipment_id or "")


class MyWorkWorkspace(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.rows=[]
        root=QVBoxLayout(self);head=QHBoxLayout()
        title=QLabel("My Work");title.setStyleSheet("font-size:18pt;font-weight:700")
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh)
        head.addWidget(title);head.addStretch(1);head.addWidget(refresh);root.addLayout(head)
        note=QLabel("Assigned operational exceptions plus verification and approval work that requires your role.")
        note.setStyleSheet("color:#647581;");root.addWidget(note)
        self.table=_table(["Severity","Type","Equipment","Key","Work item","Owner","Age (h)"])
        self.table.doubleClicked.connect(self.open_selected);root.addWidget(self.table,1)
        self.refresh()

    @staticmethod
    def _entity_for(row: dict) -> str:
        kind=row.get("kind","")
        return {"INCIDENT":"TICKET","PM":"PM_TASK","EQUIPMENT":"EQUIPMENT","QUALIFICATION":"QUALIFICATION","VERIFY":"QUALIFICATION","APPROVAL":"EQUIPMENT","RELEASE":"EQUIPMENT","HANDOVER":"ENDORSEMENT"}.get(kind,kind)

    def refresh(self):
        self.rows=self.db.my_work(self.user["username"],250)
        _fill_objects(self.table,self.rows,["severity","kind","equipment_id","key","summary","owner","age_hours"])

    def open_selected(self):
        row=_selected(self.table,self.rows)
        if not row:return
        entity=self._entity_for(row);key=str(row.get("key",""));equipment=row.get("equipment_id","")
        self.open_entity.emit(entity,key,equipment)


class Equipment360Workspace(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.equipment_id="";self.eq=None
        root=QVBoxLayout(self)
        head=QHBoxLayout()
        self.title=QLabel("Equipment 360");self.title.setStyleSheet("font-size:20pt;font-weight:800")
        self.state=QLabel();self.state.setStyleSheet("font-size:12pt;font-weight:700")
        self.favorite=QPushButton("☆ Favorite");self.favorite.clicked.connect(self.toggle_favorite)
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh)
        head.addWidget(self.title);head.addWidget(self.state);head.addStretch(1);head.addWidget(self.favorite);head.addWidget(refresh);root.addLayout(head)
        self.summary=QLabel("Select equipment from Global Search or another workspace.")
        self.summary.setWordWrap(True);self.summary.setStyleSheet("color:#647581;font-size:11pt;");root.addWidget(self.summary)
        self.tabs=QTabWidget();root.addWidget(self.tabs,1)

        overview=QWidget();ov=QVBoxLayout(overview)
        self.metrics=QGridLayout();ov.addLayout(self.metrics);self.metric_labels={}
        for i,key in enumerate(["Active alarms","Open incidents","Open PM","Qualification","Release","Availability 30d","MTBF 30d","MTTR 30d"]):
            card=QFrame();card.setFrameShape(QFrame.Shape.StyledPanel);box=QVBoxLayout(card);value=QLabel("—");value.setStyleSheet("font-size:18pt;font-weight:700");box.addWidget(value);box.addWidget(QLabel(key));self.metric_labels[key]=value;self.metrics.addWidget(card,i//4,i%4)
        ov.addStretch(1);self.tabs.addTab(overview,"Overview")

        timeline=QWidget();tl=QVBoxLayout(timeline);self.timeline_table=_table(["From","To","Class","Reason","Detail","Ticket","PM","Owner","By","Time"]);tl.addWidget(self.timeline_table);self.tabs.addTab(timeline,"Unified timeline")

        issues=QWidget();iv=QVBoxLayout(issues)
        self.ticket_table=_table(["Ticket","Title","Priority","Status","Owner","Updated"]);self.ticket_table.doubleClicked.connect(self.open_ticket)
        self.alarm_table=_table(["Alarm","Severity","Message","State","Occurred","Ticket"]);iv.addWidget(QLabel("Incidents"));iv.addWidget(self.ticket_table,1);iv.addWidget(QLabel("Alarms"));iv.addWidget(self.alarm_table,1);self.tabs.addTab(issues,"Incidents / Alarms")

        maintenance=QWidget();mv=QVBoxLayout(maintenance)
        self.pm_table=_table(["Task","PM","Name","Scheduled","Status","Assigned","Priority"]);self.pm_table.doubleClicked.connect(self.open_pm)
        self.work_table=_table(["ID","Type","Reference","User","Start","End","Minutes","Note"]);mv.addWidget(QLabel("Maintenance / PM"));mv.addWidget(self.pm_table,1);mv.addWidget(QLabel("Labor / work logs"));mv.addWidget(self.work_table,1);self.tabs.addTab(maintenance,"Maintenance / Work")

        qr=QWidget();qv=QVBoxLayout(qr)
        self.qual_table=_table(["Run","Protocol","Revision","Status","Started","Verified","Approved","Expires"]);self.release_table=_table(["ID","Status","Requested By","Verified By","Approved By","Requested","Approved"]);qv.addWidget(QLabel("Qualification"));qv.addWidget(self.qual_table,1);qv.addWidget(QLabel("Release"));qv.addWidget(self.release_table,1);self.tabs.addTab(qr,"Qualification / Release")

        cp=QWidget();cv=QVBoxLayout(cp)
        self.component_table=_table(["Component","Parent","Name","Type","Part","Serial","Status","Usage"]);self.inventory_table=_table(["Part","Location","Type","Qty","Ticket","User","Time"]);cv.addWidget(QLabel("Installed components"));cv.addWidget(self.component_table,1);cv.addWidget(QLabel("Part transactions"));cv.addWidget(self.inventory_table,1);self.tabs.addTab(cp,"Components / Parts")

        docs=QWidget();dv=QVBoxLayout(docs);self.document_table=_table(["Document","Type","Title","Owner","Status","Revision"]);dv.addWidget(self.document_table);self.tabs.addTab(docs,"Documents")

        self.attachments=AttachmentPanel(db,user);self.tabs.addTab(self.attachments,"Evidence / Attachments")

        self._clear()

    def _clear(self):
        for table in [self.timeline_table,self.ticket_table,self.alarm_table,self.pm_table,self.work_table,self.qual_table,self.release_table,self.component_table,self.inventory_table,self.document_table]:table.setRowCount(0)
        for value in self.metric_labels.values():value.setText("—")

    def set_equipment(self,equipment_id: str):
        self.equipment_id=(equipment_id or "").strip()
        self.refresh()

    def toggle_favorite(self):
        if not self.eq:return
        current=self.db.is_favorite(self.user["username"],"EQUIPMENT",self.eq.equipment_id)
        self.db.set_favorite(self.user["username"],"EQUIPMENT",self.eq.equipment_id,not current,f"{self.eq.equipment_id} — {self.eq.name}",self.eq.equipment_id)
        self._update_favorite()

    def _update_favorite(self):
        fav=bool(self.eq and self.db.is_favorite(self.user["username"],"EQUIPMENT",self.eq.equipment_id))
        self.favorite.setText("★ Favorited" if fav else "☆ Favorite")

    def refresh(self):
        if not self.equipment_id:
            self.eq=None;self._clear();self.attachments.set_entity("","");return
        self.eq=self.db.get_equipment(self.equipment_id)
        if not self.eq:
            self.title.setText("Equipment not found");self._clear();return
        eq=self.eq
        self.db.record_recent_item(self.user["username"],"EQUIPMENT",eq.equipment_id,f"{eq.equipment_id} — {eq.name}",eq.equipment_id)
        self.title.setText(f"{eq.equipment_id}  ·  {eq.name}")
        self.state.setText(f"{eq.status}  |  {eq.disposition}")
        self.summary.setText(f"{eq.site} / {eq.building} / {eq.floor} / {eq.area} / {eq.line_cell}    Owner: {eq.owner or '—'}    Criticality: {eq.criticality}    Model: {eq.model or '—'}    Serial: {eq.serial_number or '—'}")
        self._update_favorite()

        state_events=self.db.list_equipment_state_events(eq.equipment_id,500)
        tickets=[x for x in self.db.list_tickets() if x.equipment_id==eq.equipment_id]
        alarms=self.db.list_alarms(eq.equipment_id,False,500)
        pm=[x for x in self.db.list_pm_tasks() if x.equipment_id==eq.equipment_id]
        work=self.db.list_work_logs(eq.equipment_id,False,500)
        qual=self.db.list_qualification_runs(eq.equipment_id)
        releases=[x for x in self.db.list_release_requests() if x.equipment_id==eq.equipment_id]
        comps=self.db.list_components(eq.equipment_id,False)
        inv=[x for x in self.db.list_inventory_transactions(1000) if x.equipment_id==eq.equipment_id]
        docs=self.db.list_controlled_documents("Equipment",eq.equipment_id)
        rel=self.db.reliability_summary(eq.equipment_id)

        _fill_objects(self.timeline_table,state_events,["from_state","to_state","state_class","reason_code","reason_text","related_ticket","related_pm_task_id","owner","changed_by","changed_at"])
        _fill_objects(self.ticket_table,tickets,["ticket_no","title","priority","status","owner","updated_at"])
        _fill_objects(self.alarm_table,alarms,["alarm_code","severity","message","state","occurred_at","related_ticket"])
        _fill_objects(self.pm_table,pm,["id","pm_id","pm_name","scheduled_date","status","assigned_to","priority"])
        _fill_objects(self.work_table,work,["id","work_type","reference_key","username","started_at","ended_at","minutes","note"])
        _fill_objects(self.qual_table,qual,["run_no","protocol_id","protocol_revision","status","started_at","verified_at","approved_at","expires_at"])
        _fill_objects(self.release_table,releases,["id","status","requested_by","verified_by","approved_by","requested_at","approved_at"])
        _fill_objects(self.component_table,comps,["component_id","parent_component_id","name","component_type","part_number","serial_number","status","usage_value"])
        _fill_objects(self.inventory_table,inv,["part_number","location_code","transaction_type","quantity","related_ticket","user","occurred_at"])
        _fill_objects(self.document_table,docs,["document_id","document_type","title","owner","status","current_revision"])
        self.attachments.set_entity("EQUIPMENT",eq.equipment_id,eq.equipment_id)

        self.metric_labels["Active alarms"].setText(str(sum(1 for x in alarms if x.state=="ACTIVE")))
        self.metric_labels["Open incidents"].setText(str(sum(1 for x in tickets if x.status not in {"Closed","Cancelled"})))
        self.metric_labels["Open PM"].setText(str(sum(1 for x in pm if x.status not in {"Completed","Cancelled"})))
        self.metric_labels["Qualification"].setText(qual[0].status if qual else "None")
        pending=[x for x in releases if x.status!="Approved / Released"]
        self.metric_labels["Release"].setText(pending[0].status if pending else eq.disposition)
        self.metric_labels["Availability 30d"].setText(f"{rel['availability_pct']:.1f}%")
        self.metric_labels["MTBF 30d"].setText(f"{rel['mtbf_hours']:.1f} h")
        self.metric_labels["MTTR 30d"].setText(f"{rel['mttr_hours']:.1f} h")

    def open_ticket(self):
        row=_selected(self.ticket_table,[x for x in self.db.list_tickets() if x.equipment_id==self.equipment_id])
        if row:self.open_entity.emit("TICKET",row.ticket_no,self.equipment_id)

    def open_pm(self):
        rows=[x for x in self.db.list_pm_tasks() if x.equipment_id==self.equipment_id]
        row=_selected(self.pm_table,rows)
        if row:self.open_entity.emit("PM_TASK",str(row.id),self.equipment_id)
