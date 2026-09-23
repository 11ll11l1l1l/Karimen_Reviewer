from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,QComboBox,QHBoxLayout,QHeaderView,QInputDialog,QLabel,QLineEdit,
    QMessageBox,QPushButton,QTableWidget,QTableWidgetItem,QTabWidget,QTextEdit,QVBoxLayout,QWidget
)

from table_productivity import install_table_productivity
from workspaces import AttachmentPanel


def _item(value):
    if isinstance(value,datetime):value=value.strftime("%Y-%m-%d %H:%M")
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setAlternatingRowColors(True);t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    install_table_productivity(t,headers[0] if headers else "Work Order")
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


class WorkOrderWorkspace(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.rows=[];self.work_order_no="";self.work_order=None;self.links=[];self.events=[];self.logs=[]
        root=QVBoxLayout(self)
        head=QHBoxLayout()
        self.title=QLabel("Work Orders");self.title.setStyleSheet("font-size:20pt;font-weight:800")
        self.search=QLineEdit();self.search.setPlaceholderText("Filter work orders / equipment / owner / status…");self.search.textChanged.connect(self.refresh)
        new=QPushButton("New engineering WO");new.clicked.connect(self.new_engineering)
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh)
        head.addWidget(self.title);head.addStretch(1);head.addWidget(self.search);head.addWidget(new);head.addWidget(refresh);root.addLayout(head)

        self.list_table=_table(["Work Order","Equipment","Source","Title","Priority","Status","Owner","Team","Created","Updated"])
        self.list_table.itemSelectionChanged.connect(self.load_selected);self.list_table.doubleClicked.connect(self.load_selected);root.addWidget(self.list_table,2)

        actions=QHBoxLayout()
        self.owner=QLineEdit();self.owner.setPlaceholderText("Owner")
        assign=QPushButton("Assign");assign.clicked.connect(lambda:self.transition("Assigned"))
        start=QPushButton("Start / Resume");start.clicked.connect(lambda:self.transition("In Progress"))
        wait_parts=QPushButton("Waiting Parts");wait_parts.clicked.connect(lambda:self.transition("Waiting Parts",True))
        wait_prod=QPushButton("Waiting Production");wait_prod.clicked.connect(lambda:self.transition("Waiting Production",True))
        ready=QPushButton("Ready for Qualification");ready.clicked.connect(lambda:self.transition("Ready for Qualification"))
        complete=QPushButton("Complete");complete.clicked.connect(lambda:self.transition("Completed"))
        cancel=QPushButton("Cancel");cancel.clicked.connect(lambda:self.transition("Cancelled",True))
        for w in [self.owner,assign,start,wait_parts,wait_prod,ready,complete,cancel]:actions.addWidget(w)
        actions.addStretch(1);root.addLayout(actions)

        self.context=QLabel("Select or create a work order.");self.context.setWordWrap(True);self.context.setStyleSheet("color:#647581;");root.addWidget(self.context)

        tabs=QTabWidget();root.addWidget(tabs,3)
        overview=QWidget();ov=QVBoxLayout(overview);self.description=QTextEdit();self.description.setReadOnly(True);ov.addWidget(QLabel("Work scope / description"));ov.addWidget(self.description);tabs.addTab(overview,"Overview")

        events=QWidget();ev=QVBoxLayout(events);self.event_table=_table(["From","To","Reason","Owner","Changed by","Time"]);ev.addWidget(self.event_table);tabs.addTab(events,"Lifecycle")

        links=QWidget();lv=QVBoxLayout(links);lh=QHBoxLayout();add_link=QPushButton("Link record");add_link.clicked.connect(self.add_link);open_link=QPushButton("Open selected");open_link.clicked.connect(self.open_selected_link);lh.addWidget(add_link);lh.addWidget(open_link);lh.addStretch(1);lv.addLayout(lh)
        self.link_table=_table(["Type","Key","Relation","Created By","Created"]);self.link_table.doubleClicked.connect(self.open_selected_link);lv.addWidget(self.link_table);tabs.addTab(links,"Related Records")

        labor=QWidget();labv=QVBoxLayout(labor);labh=QHBoxLayout();start_log=QPushButton("Start my work timer");start_log.clicked.connect(self.start_labor);stop_log=QPushButton("Stop selected active timer");stop_log.clicked.connect(self.stop_labor);labh.addWidget(start_log);labh.addWidget(stop_log);labh.addStretch(1);labv.addLayout(labh)
        self.labor_table=_table(["ID","User","Type","Started","Ended","Minutes","Status","Note"]);labv.addWidget(self.labor_table);tabs.addTab(labor,"Labor")

        closeout=QWidget();cov=QVBoxLayout(closeout);coh=QHBoxLayout()
        start_qual=QPushButton("Start / Open Qualification");start_qual.clicked.connect(self.start_qualification)
        request_release=QPushButton("Create / Open Release Request");request_release.clicked.connect(self.request_release)
        coh.addWidget(start_qual);coh.addWidget(request_release);coh.addStretch(1);cov.addLayout(coh)
        self.closeout_summary=QLabel("Select a work order.");self.closeout_summary.setWordWrap(True);self.closeout_summary.setStyleSheet("background:#f8fafb;border:1px solid #d7dfe5;padding:10px;")
        cov.addWidget(self.closeout_summary);cov.addStretch(1);tabs.addTab(closeout,"Qualification / Release Closeout")
        self.attachments=AttachmentPanel(db,user);tabs.addTab(self.attachments,"Evidence / Attachments")
        self.refresh()

    def refresh(self):
        query=self.search.text().strip().lower()
        rows=self.db.list_work_orders()
        if query:
            rows=[r for r in rows if query in " ".join(str(x or "") for x in [r.work_order_no,r.equipment_id,r.source_type,r.source_key,r.title,r.status,r.owner,r.team]).lower()]
        current=self.work_order_no
        self.rows=rows;_fill(self.list_table,rows,["work_order_no","equipment_id","source_type","title","priority","status","owner","team","created_at","updated_at"])
        if current:
            for i,row in enumerate(rows):
                if row.work_order_no==current:self.list_table.selectRow(i);break
        self.load_selected()

    def set_work_order(self,work_order_no: str):
        self.work_order_no=(work_order_no or "").strip();self.refresh()

    def load_selected(self):
        row=_selected(self.list_table,self.rows)
        if row:self.work_order_no=row.work_order_no
        self.work_order=self.db.get_work_order(self.work_order_no) if self.work_order_no else None
        if not self.work_order:
            self.context.setText("Select or create a work order.");self.description.clear();self.owner.clear();self.closeout_summary.setText("Select a work order.");self.attachments.set_entity("","");return
        wo=self.work_order
        self.title.setText(f"{wo.work_order_no} · {wo.title}")
        self.context.setText(f"{wo.equipment_id}    {wo.priority}    {wo.status}    Source: {wo.source_type}:{wo.source_key or '—'}    Qualification required: {'Yes' if wo.qualification_required else 'No'}    Release required: {'Yes' if wo.release_required else 'No'}")
        self.owner.setText(wo.owner or "");self.description.setPlainText(wo.description or "")
        self.events=self.db.list_work_order_events(wo.work_order_no);_fill(self.event_table,self.events,["from_state","to_state","reason","owner","changed_by","occurred_at"])
        self.links=self.db.list_work_order_links(wo.work_order_no);_fill(self.link_table,self.links,["entity_type","entity_key","relation","created_by","created_at"])
        self.logs=[x for x in self.db.list_work_logs(wo.equipment_id,False,1000) if x.entity_type=="WORK_ORDER" and x.entity_key==wo.work_order_no]
        _fill(self.labor_table,self.logs,["id","username","work_type","started_at","ended_at","duration_minutes","status","note"])
        self.attachments.set_entity("WORK_ORDER",wo.work_order_no,wo.equipment_id)
        try:
            close=self.db.work_order_closeout_status(wo.work_order_no)
            blockers="\n".join(f"• {x}" for x in close["blockers"]) or "• No current closeout blockers detected."
            self.closeout_summary.setText(
                f"Work order: {close['status']}\n"
                f"Labor entries: {close['labor_entries']}  |  Active labor: {close['active_labor']}\n"
                f"Evidence attachments: {close['attachment_count']}\n"
                f"Part reservations: {close['part_reservations']}  |  Active reservations: {close['active_part_reservations']}\n"
                f"Open P1/P2 incidents: {close['critical_tickets_open']}  |  Overdue PM: {close['overdue_pm']}\n"
                f"Qualification required: {'Yes' if close['qualification_required'] else 'No'}  |  "
                f"Valid qualification: {close['valid_qualification_run'] or 'None'}  |  "
                f"Open qualification: {close['open_qualification_run'] or 'None'}\n"
                f"Release required: {'Yes' if close['release_required'] else 'No'}  |  "
                f"Active release: {close['active_release_status'] or 'None'}\n\n"
                f"Blockers / next controls:\n{blockers}"
            )
        except Exception as exc:self.closeout_summary.setText(f"Closeout status unavailable: {exc}")

    def start_qualification(self):
        if not self.work_order:return
        try:
            close=self.db.work_order_closeout_status(self.work_order.work_order_no)
            existing=close["open_qualification_run"] or close["valid_qualification_run"]
            if existing:
                self.open_entity.emit("QUALIFICATION",existing,self.work_order.equipment_id);return
            protocols=self.db.applicable_qualification_protocols(self.work_order.equipment_id)
            protocol_id=""
            if len(protocols)>1:
                labels=[f"{x.protocol_id} R{x.revision} — {x.name}" for x in protocols]
                choice,ok=QInputDialog.getItem(self,"Work-order qualification","Applicable protocol",labels,0,False)
                if not ok:return
                protocol_id=protocols[labels.index(choice)].protocol_id
            elif len(protocols)==1:protocol_id=protocols[0].protocol_id
            run=self.db.start_work_order_qualification(self.work_order.work_order_no,self.user["username"],protocol_id,"WORK-ORDER-WORKSPACE")
            self.load_selected();self.open_entity.emit("QUALIFICATION",run.run_no,self.work_order.equipment_id)
        except Exception as exc:QMessageBox.critical(self,"Qualification closeout",str(exc))

    def request_release(self):
        if not self.work_order:return
        try:
            close=self.db.work_order_closeout_status(self.work_order.work_order_no)
            if close["active_release_id"]:
                self.open_entity.emit("RELEASE",str(close["active_release_id"]),self.work_order.equipment_id);return
            release=self.db.create_work_order_release_request(self.work_order.work_order_no,self.user["username"],"WORK-ORDER-WORKSPACE")
            self.load_selected();self.open_entity.emit("RELEASE",str(release.id),self.work_order.equipment_id)
        except Exception as exc:QMessageBox.critical(self,"Release closeout",str(exc))

    def new_engineering(self):
        equipment,ok=QInputDialog.getText(self,"New work order","Equipment ID")
        if not ok or not equipment.strip():return
        title,ok=QInputDialog.getText(self,"New work order","Work title")
        if not ok or not title.strip():return
        desc,ok=QInputDialog.getMultiLineText(self,"New work order","Work scope / description")
        if not ok:return
        try:
            row=self.db.create_work_order({"equipment_id":equipment.strip(),"source_type":"ENGINEERING","title":title.strip(),"description":desc,"owner":self.user["username"]},self.user["username"],"WORK-ORDER-WORKSPACE")
            self.set_work_order(row.work_order_no)
        except Exception as exc:QMessageBox.critical(self,"Work order",str(exc))

    def transition(self,target: str,require_reason: bool=False):
        if not self.work_order:return
        reason=""
        if require_reason:
            reason,ok=QInputDialog.getMultiLineText(self,"Work order",f"Reason for {target}")
            if not ok:return
        try:
            row=self.db.transition_work_order(self.work_order.work_order_no,target,self.user["username"],reason,self.owner.text().strip(),self.work_order.version,"WORK-ORDER-WORKSPACE")
            self.work_order_no=row.work_order_no;self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Work order",str(exc))

    def add_link(self):
        if not self.work_order:return
        entity_type,ok=QInputDialog.getItem(self,"Link record","Record type",["TICKET","PM_TASK","PM_EXECUTION","ALARM","COMPONENT","QUALIFICATION","RELEASE","INVENTORY_RESERVATION","DOCUMENT"],0,False)
        if not ok:return
        key,ok=QInputDialog.getText(self,"Link record","Record key / ID")
        if not ok or not key.strip():return
        relation,ok=QInputDialog.getText(self,"Link record","Relationship",text="RELATED")
        if not ok:return
        try:self.db.add_work_order_link(self.work_order.work_order_no,entity_type,key.strip(),relation,self.user["username"]);self.load_selected()
        except Exception as exc:QMessageBox.critical(self,"Work order link",str(exc))

    def open_selected_link(self):
        link=_selected(self.link_table,self.links)
        if not link:return
        self.open_entity.emit(link.entity_type,link.entity_key,self.work_order.equipment_id if self.work_order else "")

    def start_labor(self):
        if not self.work_order:return
        work_type,ok=QInputDialog.getItem(self,"Start work","Work type",["Engineering","Maintenance","Troubleshooting","Repair","Qualification","Vendor Support"],0,True)
        if not ok:return
        note,ok=QInputDialog.getText(self,"Start work","Note / activity")
        if not ok:return
        try:
            self.db.start_work_log("WORK_ORDER",self.work_order.work_order_no,self.work_order.equipment_id,self.user["username"],work_type,note)
            if self.work_order.status in {"Open","Assigned"}:
                try:self.db.transition_work_order(self.work_order.work_order_no,"In Progress",self.user["username"],"",self.owner.text().strip(),self.work_order.version,"WORK-ORDER-WORKSPACE")
                except Exception:pass
            self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Work log",str(exc))

    def stop_labor(self):
        row=_selected(self.labor_table,self.logs)
        if not row:return
        if row.status!="Active":QMessageBox.information(self,"Work log","Selected work log is already closed.");return
        note,ok=QInputDialog.getText(self,"Stop work","Completion note")
        if not ok:return
        try:self.db.stop_work_log(row.id,self.user["username"],note);self.load_selected()
        except Exception as exc:QMessageBox.critical(self,"Work log",str(exc))
