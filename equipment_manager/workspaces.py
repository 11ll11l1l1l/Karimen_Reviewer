from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QSplitter,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from attachment_store import duplicate_attachment_file, store_attachment_file, store_clipboard_image
from services import readonly_open_copy
from reporting import export_equipment_pptx, export_equipment_xlsx
from pdf_reporting import export_equipment_pdf
from image_annotator import ImageAnnotationDialog
from table_productivity import install_table_productivity

FILE_ROOT=os.getenv("EMS_FILE_ROOT",str(Path.cwd()/"equipment_files"))


def _item(value: Any) -> QTableWidgetItem:
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers: list[str]) -> QTableWidget:
    table=QTableWidget(0,len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    install_table_productivity(table,headers[0] if headers else "EMS Export")
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
        self.setAcceptDrops(True)
        self.db=db;self.user=user;self.entity_type=entity_type;self.entity_key=str(entity_key);self.equipment_id=equipment_id
        self.rows=[]
        root=QVBoxLayout(self);buttons=QHBoxLayout()
        self.add_button=QPushButton("Add files")
        self.paste_button=QPushButton("Paste screenshot")
        self.open_button=QPushButton("Open")
        self.edit_button=QPushButton("Edit metadata")
        self.copy_button=QPushButton("Copy to record")
        self.annotate_button=QPushButton("Annotate image")
        self.remove_button=QPushButton("Remove link")
        self.add_button.clicked.connect(self.add_files)
        self.paste_button.clicked.connect(self.paste_screenshot)
        self.open_button.clicked.connect(self.open_selected)
        self.edit_button.clicked.connect(self.edit_selected)
        self.copy_button.clicked.connect(self.copy_selected)
        self.annotate_button.clicked.connect(self.annotate_selected)
        self.remove_button.clicked.connect(self.remove_selected)
        for b in [self.add_button,self.paste_button,self.open_button,self.edit_button,self.copy_button,self.annotate_button,self.remove_button]:buttons.addWidget(b)
        buttons.addStretch(1);root.addLayout(buttons)
        self.table=_table(["Name","Category","Caption","Tags","Type","Size","Added by","Added"])
        self.table.doubleClicked.connect(self.open_selected);self.table.itemSelectionChanged.connect(self.update_preview)
        split=QSplitter(Qt.Orientation.Horizontal);split.addWidget(self.table)
        self.preview=QLabel("Select an attachment to preview");self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter);self.preview.setWordWrap(True);self.preview.setMinimumWidth(300);self.preview.setStyleSheet("background:#f8fafb;border:1px solid #d7dfe5;padding:10px;")
        split.addWidget(self.preview);split.setStretchFactor(0,3);split.setStretchFactor(1,1)
        root.addWidget(split,1)
        self.empty=QLabel("Select a record to view or attach evidence.")
        self.empty.setStyleSheet("color:#647581;")
        root.addWidget(self.empty)
        self.paste_shortcut=QShortcut(QKeySequence.Paste,self)
        self.paste_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.paste_shortcut.activated.connect(self.paste_screenshot)
        self.refresh()

    def set_entity(self,entity_type: str,entity_key: str,equipment_id: str=""):
        self.entity_type=(entity_type or "").upper();self.entity_key=str(entity_key or "");self.equipment_id=equipment_id or ""
        self.refresh()

    def refresh(self):
        enabled=bool(self.entity_type and self.entity_key)
        for b in [self.add_button,self.paste_button,self.open_button,self.edit_button,self.copy_button,self.annotate_button,self.remove_button]:b.setEnabled(enabled)
        self.rows=self.db.list_attachments(self.entity_type,self.entity_key) if enabled else []
        _fill_objects(self.table,self.rows,["original_name","category","caption","tags","media_type","file_size","created_by","created_at"])
        self.empty.setVisible(not enabled or not self.rows)
        self.update_preview()

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

    def update_preview(self):
        row=_selected(self.table,self.rows)
        if not row:
            self.preview.setPixmap(QPixmap());self.preview.setText("Select an attachment to preview");return
        path=Path(row.stored_path)
        if (row.media_type or "").startswith("image/") and path.is_file():
            pix=QPixmap(str(path))
            if not pix.isNull():
                self.preview.setText("");self.preview.setPixmap(pix.scaled(420,300,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));return
        self.preview.setPixmap(QPixmap())
        self.preview.setText(f"{row.original_name}\n\n{row.caption or 'No caption'}\n\n{row.media_type or 'Unknown type'}\n{row.file_size:,} bytes")

    def dragEnterEvent(self,event):
        if self.entity_key and event.mimeData().hasUrls():event.acceptProposedAction()
        else:event.ignore()

    def dropEvent(self,event):
        if not self.entity_key:return
        paths=[url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if not paths:return
        failures=[]
        for path in paths:
            try:self._register(store_attachment_file(path,FILE_ROOT,self.entity_type,self.entity_key),category="Evidence")
            except Exception as exc:failures.append(f"{Path(path).name}: {exc}")
        if failures:QMessageBox.warning(self,"Attachments","Some dropped files could not be attached:\n"+"\n".join(failures[:12]))
        event.acceptProposedAction()

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

    def annotate_selected(self):
        row=_selected(self.table,self.rows)
        if not row:return
        if not (row.media_type or "").startswith("image/"):
            QMessageBox.information(self,"Annotation","Select an image attachment to annotate.");return
        try:
            dialog=ImageAnnotationDialog(row.stored_path,self)
            if dialog.exec()!=QDialog.DialogCode.Accepted or not dialog.output_path:return
            stored=store_attachment_file(dialog.output_path,FILE_ROOT,self.entity_type,self.entity_key)
            self.db.add_attachment(
                self.entity_type,self.entity_key,stored["stored_path"],
                original_name=stored["original_name"],media_type="image/png",
                category="Annotated Evidence",caption=(row.caption+" [annotated]").strip(),
                tags=row.tags,equipment_id=self.equipment_id,created_by=self.user["username"],
                copied_from_id=row.id,
            )
            self.refresh();self.changed.emit()
        except Exception as exc:QMessageBox.critical(self,"Annotation",str(exc))

    def copy_selected(self):
        row=_selected(self.table,self.rows)
        if not row:return
        target_type,ok=QInputDialog.getItem(self,"Copy attachment","Target record type",["EQUIPMENT","TICKET","PM_EXECUTION","QUALIFICATION","ALARM","RELEASE","ENDORSEMENT","WORK_LOG"],0,False)
        if not ok:return
        target_key,ok=QInputDialog.getText(self,"Copy attachment","Target record key / ID")
        if not ok or not target_key.strip():return
        equipment_id=self.equipment_id
        if target_type=="EQUIPMENT":equipment_id=target_key.strip()
        try:
            stored=duplicate_attachment_file(row.stored_path,FILE_ROOT,target_type,target_key.strip())
            self.db.add_attachment(
                target_type,target_key.strip(),stored["stored_path"],
                original_name=row.original_name,media_type=row.media_type,category=row.category,
                caption=row.caption,tags=row.tags,equipment_id=equipment_id,
                created_by=self.user["username"],copied_from_id=row.id,
            )
            QMessageBox.information(self,"Attachment",f"Copied to {target_type}:{target_key.strip()} with provenance retained.")
        except Exception as exc:QMessageBox.critical(self,"Attachment copy",str(exc))

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
        super().__init__(parent);self.db=db;self.user=user;self.rows=[];self.filtered=[];self.watched=[]
        root=QVBoxLayout(self);head=QHBoxLayout()
        title=QLabel("My Work / Action Center");title.setStyleSheet("font-size:18pt;font-weight:700")
        self.filter=QComboBox();self.filter.addItems(["All","Critical / High","Approvals / Verification","Mentions","Work Orders","PM","Incidents / Equipment"])
        self.filter.currentTextChanged.connect(self.apply_filter)
        ack=QPushButton("Acknowledge mention");ack.clicked.connect(self.acknowledge_selected_mention)
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh)
        head.addWidget(title);head.addStretch(1);head.addWidget(QLabel("Filter"));head.addWidget(self.filter);head.addWidget(ack);head.addWidget(refresh);root.addLayout(head)
        note=QLabel("Assigned work, approvals, verification, mentions and watched-record activity in one queue.")
        note.setStyleSheet("color:#647581;");root.addWidget(note)
        tabs=QTabWidget();root.addWidget(tabs,1)
        queue=QWidget();qv=QVBoxLayout(queue)
        self.table=_table(["Severity","Type","Equipment","Key","Work item","Owner","Age (h)"])
        self.table.doubleClicked.connect(self.open_selected);qv.addWidget(self.table);tabs.addTab(queue,"Action Queue")
        watch=QWidget();wv=QVBoxLayout(watch)
        self.watch_table=_table(["Type","Key","Equipment","Last activity","By","Latest comment"])
        self.watch_table.doubleClicked.connect(self.open_watched);wv.addWidget(self.watch_table);tabs.addTab(watch,"Watchlist")
        self.summary=QLabel();self.summary.setStyleSheet("color:#647581");root.addWidget(self.summary)
        self.refresh()

    @staticmethod
    def _entity_for(row: dict) -> str:
        kind=row.get("kind","")
        if kind=="MENTION":return str(row.get("entity_type") or "")
        return {"INCIDENT":"TICKET","PM":"PM_EXECUTION","EQUIPMENT":"EQUIPMENT","QUALIFICATION":"QUALIFICATION","VERIFY":"QUALIFICATION","APPROVAL":"EQUIPMENT","RELEASE":"EQUIPMENT","HANDOVER":"ENDORSEMENT","WORK_ORDER":"WORK_ORDER"}.get(kind,kind)

    def refresh(self):
        self.rows=self.db.my_work(self.user["username"],500)
        self.watched=self.db.list_watched_records(self.user["username"],300)
        _fill_objects(self.watch_table,self.watched,["entity_type","entity_key","equipment_id","last_activity","last_by","last_comment"])
        self.apply_filter()

    def apply_filter(self):
        mode=self.filter.currentText()
        def keep(row):
            kind=row.get("kind","")
            if mode=="Critical / High":return row.get("severity") in {"CRITICAL","HIGH"}
            if mode=="Approvals / Verification":return kind in {"APPROVAL","VERIFY","QUALIFICATION","RELEASE"}
            if mode=="Mentions":return kind=="MENTION"
            if mode=="Work Orders":return kind=="WORK_ORDER"
            if mode=="PM":return kind=="PM"
            if mode=="Incidents / Equipment":return kind in {"INCIDENT","EQUIPMENT"}
            return True
        self.filtered=[x for x in self.rows if keep(x)]
        _fill_objects(self.table,self.filtered,["severity","kind","equipment_id","key","summary","owner","age_hours"])
        mentions=sum(1 for x in self.rows if x.get("kind")=="MENTION")
        critical=sum(1 for x in self.rows if x.get("severity") in {"CRITICAL","HIGH"})
        approvals=sum(1 for x in self.rows if x.get("kind") in {"APPROVAL","VERIFY"})
        self.summary.setText(f"{len(self.rows)} active item(s) · {critical} high/critical · {approvals} approval/verification · {mentions} unacknowledged mention(s) · {len(self.watched)} watched record(s)")

    def acknowledge_selected_mention(self):
        row=_selected(self.table,self.filtered)
        if not row or row.get("kind")!="MENTION":
            QMessageBox.information(self,"Mention","Select a mention in the action queue.");return
        try:self.db.acknowledge_mention(int(row.get("key") or 0),self.user["username"]);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Mention",str(exc))

    def open_selected(self):
        row=_selected(self.table,self.filtered)
        if not row:return
        entity=self._entity_for(row)
        if row.get("kind")=="MENTION":
            key=str(row.get("entity_key") or "")
            try:self.db.acknowledge_mention(int(row.get("key") or 0),self.user["username"])
            except Exception:pass
        else:key=str(row.get("key",""))
        equipment=row.get("equipment_id","")
        self.open_entity.emit(entity,key,equipment)
        if row.get("kind")=="MENTION":self.refresh()

    def open_watched(self):
        row=_selected(self.watch_table,self.watched)
        if not row:return
        self.open_entity.emit(str(row.get("entity_type") or ""),str(row.get("entity_key") or ""),str(row.get("equipment_id") or ""))


class Equipment360Workspace(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.equipment_id="";self.eq=None
        root=QVBoxLayout(self)
        head=QHBoxLayout()
        self.title=QLabel("Equipment 360");self.title.setStyleSheet("font-size:20pt;font-weight:800")
        self.state=QLabel();self.state.setStyleSheet("font-size:12pt;font-weight:700")
        self.favorite=QPushButton("☆ Favorite");self.favorite.clicked.connect(self.toggle_favorite)
        self.incident_button=QPushButton("Open active incident");self.incident_button.clicked.connect(self.open_active_incident)
        self.pm_button=QPushButton("Open current PM");self.pm_button.clicked.connect(self.open_current_pm)
        registry_button=QPushButton("Registry / state");registry_button.clicked.connect(self.open_registry)
        map_button=QPushButton("Show on FAB map");map_button.clicked.connect(self.open_map)
        ppt=QPushButton("Review PPTX");ppt.clicked.connect(self.export_pptx)
        xlsx=QPushButton("Review Excel");xlsx.clicked.connect(self.export_xlsx)
        pdf=QPushButton("Review PDF");pdf.clicked.connect(self.export_pdf)
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh)
        head.addWidget(self.title);head.addWidget(self.state);head.addStretch(1)
        for button in [self.incident_button,self.pm_button,registry_button,map_button,ppt,xlsx,pdf,self.favorite,refresh]:head.addWidget(button)
        root.addLayout(head)
        self.summary=QLabel("Select equipment from Global Search or another workspace.")
        self.summary.setWordWrap(True);self.summary.setStyleSheet("color:#647581;font-size:11pt;");root.addWidget(self.summary)
        self.tabs=QTabWidget();root.addWidget(self.tabs,1)

        overview=QWidget();ov=QVBoxLayout(overview)
        self.metrics=QGridLayout();ov.addLayout(self.metrics);self.metric_labels={}
        for i,key in enumerate(["Active alarms","Open incidents","Open PM","Open work orders","Qualification","Release","Availability 30d","MTBF 30d","MTTR 30d"]):
            card=QFrame();card.setFrameShape(QFrame.Shape.StyledPanel);box=QVBoxLayout(card);value=QLabel("—");value.setStyleSheet("font-size:18pt;font-weight:700");box.addWidget(value);box.addWidget(QLabel(key));self.metric_labels[key]=value;self.metrics.addWidget(card,i//4,i%4)
        ov.addStretch(1);self.tabs.addTab(overview,"Overview")

        timeline=QWidget();tl=QVBoxLayout(timeline);self.timeline_table=_table(["Time","Type","Key","Activity","Status","User","Source"]);tl.addWidget(self.timeline_table);self.tabs.addTab(timeline,"Unified timeline")

        issues=QWidget();iv=QVBoxLayout(issues)
        self.ticket_table=_table(["Ticket","Title","Priority","Status","Owner","Updated"]);self.ticket_table.doubleClicked.connect(self.open_ticket)
        self.alarm_table=_table(["Alarm","Severity","Message","State","Occurred","Ticket"]);iv.addWidget(QLabel("Incidents"));iv.addWidget(self.ticket_table,1);iv.addWidget(QLabel("Alarms"));iv.addWidget(self.alarm_table,1);self.tabs.addTab(issues,"Incidents / Alarms")

        maintenance=QWidget();mv=QVBoxLayout(maintenance)
        self.pm_table=_table(["Task","PM","Name","Scheduled","Status","Assigned","Priority"]);self.pm_table.doubleClicked.connect(self.open_pm)
        self.work_table=_table(["ID","Type","Reference","User","Start","End","Minutes","Note"]);mv.addWidget(QLabel("Maintenance / PM"));mv.addWidget(self.pm_table,1);mv.addWidget(QLabel("Labor / work logs"));mv.addWidget(self.work_table,1);self.tabs.addTab(maintenance,"Maintenance / Work")

        qr=QWidget();qv=QVBoxLayout(qr)
        self.qual_table=_table(["Run","Protocol","Revision","Status","Started","Verified","Approved","Expires"]);self.release_table=_table(["ID","Status","Requested By","Verified By","Approved By","Requested","Approved"]);qv.addWidget(QLabel("Qualification"));qv.addWidget(self.qual_table,1);qv.addWidget(QLabel("Release"));qv.addWidget(self.release_table,1);self.tabs.addTab(qr,"Qualification / Release")

        cp=QWidget();cv=QVBoxLayout(cp)
        self.component_table=_table(["Component","Parent","Name","Type","Part","Serial","Status","Usage"]);self.meter_table=_table(["Meter","Name","Unit","Current","Last reading","Active"]);self.inventory_table=_table(["Part","Location","Type","Qty","Ticket","User","Time"]);cv.addWidget(QLabel("Installed components"));cv.addWidget(self.component_table,1);cv.addWidget(QLabel("Meters / counters"));cv.addWidget(self.meter_table,1);cv.addWidget(QLabel("Part transactions"));cv.addWidget(self.inventory_table,1);self.tabs.addTab(cp,"Components / Usage / Parts")

        docs=QWidget();dv=QVBoxLayout(docs);self.document_table=_table(["Document","Type","Title","Owner","Status","Revision"]);dv.addWidget(self.document_table);self.tabs.addTab(docs,"Documents")

        ops=QWidget();opv=QVBoxLayout(ops);self.handover_table=_table(["No","Condition","Pending","Restrictions","Next owner","Status","Created"]);self.disposition_table=_table(["State","Reason","Restrictions","Release criteria","Ticket","Created by","Approved by","Effective"]);opv.addWidget(QLabel("Shift handovers"));opv.addWidget(self.handover_table,1);opv.addWidget(QLabel("Disposition history"));opv.addWidget(self.disposition_table,1);self.tabs.addTab(ops,"Handover / Disposition")
        related=QWidget();rv=QVBoxLayout(related);self.relationships=[];self.related_table=_table(["Type","Key","Title / Context","Status"]);self.related_table.doubleClicked.connect(self.open_related);rv.addWidget(self.related_table);self.tabs.addTab(related,"Related Records")
        self.attachments=AttachmentPanel(db,user);self.tabs.addTab(self.attachments,"Evidence / Attachments")
        self.collaboration=CollaborationPanel(db,user);self.tabs.addTab(self.collaboration,"Comments / Watchers")
        self.custom_fields=CustomFieldsPanel(db,user);self.tabs.addTab(self.custom_fields,"Custom Fields")

        self.active_tickets=[];self.current_pm=[]
        self._clear()

    def _clear(self):
        for table in [self.timeline_table,self.ticket_table,self.alarm_table,self.pm_table,self.work_table,self.qual_table,self.release_table,self.component_table,self.meter_table,self.inventory_table,self.document_table,self.handover_table,self.disposition_table,self.related_table]:table.setRowCount(0)
        self.relationships=[]
        for value in self.metric_labels.values():value.setText("—")

    def set_equipment(self,equipment_id: str):
        self.equipment_id=(equipment_id or "").strip()
        self.refresh()

    def export_pptx(self):
        if not self.eq:return
        default=f"{self.eq.equipment_id}_Equipment_Review.pptx"
        path,_=QFileDialog.getSaveFileName(self,"Export Equipment Review PowerPoint",default,"PowerPoint (*.pptx)")
        if not path:return
        if not path.lower().endswith(".pptx"):path+=".pptx"
        try:
            template=self.db.resolve_report_template("EQUIPMENT",self.eq.equipment_id)
            export_equipment_pptx(self.db,self.eq.equipment_id,path,template);QMessageBox.information(self,"PowerPoint",f"Editable equipment review deck created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"PowerPoint",str(exc))

    def export_pdf(self):
        if not self.eq:return
        default=f"{self.eq.equipment_id}_Equipment_Review.pdf"
        path,_=QFileDialog.getSaveFileName(self,"Export Equipment Review PDF",default,"PDF (*.pdf)")
        if not path:return
        if not path.lower().endswith(".pdf"):path+=".pdf"
        try:export_equipment_pdf(self.db,self.eq.equipment_id,path);QMessageBox.information(self,"PDF",f"Controlled equipment review PDF created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"PDF",str(exc))

    def export_xlsx(self):
        if not self.eq:return
        default=f"{self.eq.equipment_id}_Equipment_Review.xlsx"
        path,_=QFileDialog.getSaveFileName(self,"Export Equipment Review Excel",default,"Excel Workbook (*.xlsx)")
        if not path:return
        if not path.lower().endswith(".xlsx"):path+=".xlsx"
        try:export_equipment_xlsx(self.db,self.eq.equipment_id,path);QMessageBox.information(self,"Excel",f"Equipment review workbook created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"Excel",str(exc))

    def open_registry(self):
        if self.eq:self.open_entity.emit("REGISTRY",self.eq.equipment_id,self.eq.equipment_id)

    def open_active_incident(self):
        if self.active_tickets:
            row=self.active_tickets[0];self.open_entity.emit("TICKET",row.ticket_no,row.equipment_id)

    def open_current_pm(self):
        if self.current_pm:
            row=self.current_pm[0];self.open_entity.emit("PM_EXECUTION",str(row.id),row.equipment_id)

    def open_map(self):
        if self.eq:self.open_entity.emit("MAP",self.eq.equipment_id,self.eq.equipment_id)

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
            self.eq=None;self._clear();self.attachments.set_entity("","");self.collaboration.set_entity("","");self.custom_fields.set_entity("","");return
        self.eq=self.db.get_equipment(self.equipment_id)
        if not self.eq:
            self.title.setText("Equipment not found");self._clear();return
        eq=self.eq
        self.db.record_recent_item(self.user["username"],"EQUIPMENT",eq.equipment_id,f"{eq.equipment_id} — {eq.name}",eq.equipment_id)
        self.title.setText(f"{eq.equipment_id}  ·  {eq.name}")
        self.state.setText(f"{eq.status}  |  {eq.disposition}")
        self.summary.setText(f"{eq.site} / {eq.building} / {eq.floor} / {eq.area} / {eq.line_cell}    Owner: {eq.owner or '—'}    Criticality: {eq.criticality}    Model: {eq.model or '—'}    Serial: {eq.serial_number or '—'}")
        self._update_favorite()

        activity=self.db.equipment_activity_timeline(eq.equipment_id,700)
        tickets=[x for x in self.db.list_tickets() if x.equipment_id==eq.equipment_id]
        alarms=self.db.list_alarms(eq.equipment_id,False,500)
        pm=[x for x in self.db.list_pm_tasks() if x.equipment_id==eq.equipment_id]
        work_orders=self.db.list_work_orders(eq.equipment_id)
        work=self.db.list_work_logs(eq.equipment_id,False,500)
        qual=self.db.list_qualification_runs(eq.equipment_id)
        releases=[x for x in self.db.list_release_requests() if x.equipment_id==eq.equipment_id]
        comps=self.db.list_components(eq.equipment_id,False)
        meters=self.db.list_meters(eq.equipment_id)
        inv=[x for x in self.db.list_inventory_transactions(1000) if x.equipment_id==eq.equipment_id]
        docs=self.db.list_controlled_documents("Equipment",eq.equipment_id)
        handovers=[x for x in self.db.list_endorsements() if x.equipment_id==eq.equipment_id]
        dispositions=[x for x in self.db.list_dispositions() if x.equipment_id==eq.equipment_id]
        rel=self.db.reliability_summary(eq.equipment_id)

        _fill_objects(self.timeline_table,activity,["occurred_at","kind","key","summary","status","user","source"])
        _fill_objects(self.ticket_table,tickets,["ticket_no","title","priority","status","owner","updated_at"])
        _fill_objects(self.alarm_table,alarms,["alarm_code","severity","message","state","occurred_at","related_ticket"])
        _fill_objects(self.pm_table,pm,["id","pm_id","pm_name","scheduled_date","status","assigned_to","priority"])
        _fill_objects(self.work_table,work,["id","work_type","entity_key","username","started_at","ended_at","duration_minutes","note"])
        _fill_objects(self.qual_table,qual,["run_no","protocol_id","protocol_revision","status","started_at","verified_at","approved_at","expires_at"])
        _fill_objects(self.release_table,releases,["id","status","requested_by","verified_by","approved_by","requested_at","approved_at"])
        _fill_objects(self.component_table,comps,["component_id","parent_component_id","name","component_type","part_number","serial_number","status","usage_value"])
        _fill_objects(self.meter_table,meters,["meter_code","name","unit","current_value","last_reading_at","active"])
        _fill_objects(self.inventory_table,inv,["part_number","location_code","transaction_type","quantity","related_ticket","user","created_at"])
        _fill_objects(self.document_table,docs,["document_id","document_type","title","owner","status","current_revision"])
        _fill_objects(self.handover_table,handovers,["endorsement_no","current_condition","pending_work","restrictions","next_owner","status","created_at"])
        _fill_objects(self.disposition_table,dispositions,["state","reason","restrictions","release_criteria","related_ticket","created_by","approved_by","effective_at"])
        self.relationships=[]
        for x in tickets:self.relationships.append({"entity_type":"TICKET","entity_key":x.ticket_no,"title":x.title,"status":x.status})
        for x in pm:self.relationships.append({"entity_type":"PM_TASK","entity_key":x.id,"title":f"{x.pm_id} — {x.pm_name}","status":x.status})
        for x in work_orders:self.relationships.append({"entity_type":"WORK_ORDER","entity_key":x.work_order_no,"title":x.title,"status":x.status})
        for x in alarms:self.relationships.append({"entity_type":"ALARM","entity_key":x.event_key,"title":f"{x.alarm_code} — {x.message}","status":x.state})
        for x in qual:self.relationships.append({"entity_type":"QUALIFICATION","entity_key":x.run_no,"title":x.protocol_name,"status":x.status})
        for x in releases:self.relationships.append({"entity_type":"RELEASE","entity_key":x.id,"title":"Equipment release","status":x.status})
        for x in comps:self.relationships.append({"entity_type":"COMPONENT","entity_key":x.component_id,"title":f"{x.name} · {x.part_number}","status":x.status})
        for x in docs:self.relationships.append({"entity_type":"DOCUMENT","entity_key":x.document_id,"title":x.title,"status":x.status})
        for x in handovers:self.relationships.append({"entity_type":"ENDORSEMENT","entity_key":x.endorsement_no,"title":x.pending_work or x.current_condition,"status":x.status})
        _fill_objects(self.related_table,self.relationships,["entity_type","entity_key","title","status"])
        self.attachments.set_entity("EQUIPMENT",eq.equipment_id,eq.equipment_id)
        self.collaboration.set_entity("EQUIPMENT",eq.equipment_id,eq.equipment_id)
        self.custom_fields.set_entity("EQUIPMENT",eq.equipment_id,eq.equipment_type)

        self.active_tickets=sorted([x for x in tickets if x.status not in {"Closed","Cancelled"}],key=lambda x:(0 if x.priority=="P1" else 1 if x.priority=="P2" else 2,x.updated_at or x.created_at),reverse=False)
        self.current_pm=sorted([x for x in pm if x.status not in {"Completed","Cancelled"}],key=lambda x:(0 if x.status=="Overdue" else 1,x.scheduled_date or x.original_due_date))
        self.incident_button.setEnabled(bool(self.active_tickets));self.pm_button.setEnabled(bool(self.current_pm))
        self.metric_labels["Active alarms"].setText(str(sum(1 for x in alarms if x.state=="ACTIVE")))
        self.metric_labels["Open incidents"].setText(str(sum(1 for x in tickets if x.status not in {"Closed","Cancelled"})))
        self.metric_labels["Open PM"].setText(str(sum(1 for x in pm if x.status not in {"Completed","Cancelled"})))
        self.metric_labels["Open work orders"].setText(str(sum(1 for x in work_orders if x.status not in {"Completed","Cancelled"})))
        self.metric_labels["Qualification"].setText(qual[0].status if qual else "None")
        pending=[x for x in releases if x.status!="Approved / Released"]
        self.metric_labels["Release"].setText(pending[0].status if pending else eq.disposition)
        self.metric_labels["Availability 30d"].setText(f"{rel['availability_pct']:.1f}%")
        self.metric_labels["MTBF 30d"].setText(f"{rel['mtbf_hours']:.1f} h")
        self.metric_labels["MTTR 30d"].setText(f"{rel['mttr_hours']:.1f} h")

    def open_related(self):
        row=_selected(self.related_table,self.relationships)
        if not row:return
        self.open_entity.emit(row["entity_type"],str(row["entity_key"]),self.equipment_id)

    def open_ticket(self):
        row=_selected(self.ticket_table,[x for x in self.db.list_tickets() if x.equipment_id==self.equipment_id])
        if row:self.open_entity.emit("TICKET",row.ticket_no,self.equipment_id)

    def open_pm(self):
        rows=[x for x in self.db.list_pm_tasks() if x.equipment_id==self.equipment_id]
        row=_selected(self.pm_table,rows)
        if row:self.open_entity.emit("PM_TASK",str(row.id),self.equipment_id)


class EquipmentWorkspaceTabs(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.by_equipment={}
        root=QVBoxLayout(self);head=QHBoxLayout()
        title=QLabel("Equipment Workspaces");title.setStyleSheet("font-size:18pt;font-weight:700")
        hint=QLabel("Keep multiple tools open side-by-side as persistent tabs.")
        hint.setStyleSheet("color:#647581;")
        head.addWidget(title);head.addWidget(hint);head.addStretch(1);root.addLayout(head)
        self.tabs=QTabWidget();self.tabs.setTabsClosable(True);self.tabs.setMovable(True);self.tabs.tabCloseRequested.connect(self.close_tab);root.addWidget(self.tabs,1)
        saved=self.db.get_user_preference(self.user["username"],"workspace.open_equipment_tabs",[])
        if isinstance(saved,list):
            for equipment_id in saved[:12]:
                if self.db.get_equipment(str(equipment_id)):self.open_equipment(str(equipment_id),persist=False)

    def _persist(self):
        ids=[]
        for i in range(self.tabs.count()):
            page=self.tabs.widget(i)
            equipment_id=getattr(page,"equipment_id","")
            if equipment_id:ids.append(equipment_id)
        self.db.set_user_preference(self.user["username"],"workspace.open_equipment_tabs",ids)

    def open_equipment(self,equipment_id: str,persist: bool=True):
        equipment_id=(equipment_id or "").strip()
        if not equipment_id:return
        page=self.by_equipment.get(equipment_id)
        if page is not None:
            self.tabs.setCurrentWidget(page);page.refresh();return
        eq=self.db.get_equipment(equipment_id)
        if not eq:return
        page=Equipment360Workspace(self.db,self.user)
        page.open_entity.connect(self.open_entity)
        page.set_equipment(equipment_id)
        self.by_equipment[equipment_id]=page
        self.tabs.addTab(page,equipment_id)
        self.tabs.setTabToolTip(self.tabs.indexOf(page),f"{equipment_id} — {eq.name}")
        self.tabs.setCurrentWidget(page)
        if persist:self._persist()

    def set_equipment(self,equipment_id: str):
        self.open_equipment(equipment_id)

    def close_tab(self,index: int):
        page=self.tabs.widget(index)
        if page is None:return
        equipment_id=getattr(page,"equipment_id","")
        self.tabs.removeTab(index)
        if equipment_id:self.by_equipment.pop(equipment_id,None)
        page.deleteLater();self._persist()

    def refresh(self):
        page=self.tabs.currentWidget()
        if page and hasattr(page,"refresh"):page.refresh()
