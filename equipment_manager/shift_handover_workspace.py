from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,QHBoxLayout,QHeaderView,QLabel,QMessageBox,QPushButton,
    QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget,QSplitter
)

from table_productivity import install_table_productivity
from workspaces import AttachmentPanel


def _item(value):
    if isinstance(value,datetime):value=value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value,bool):value="Yes" if value else "No"
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers,multi=False):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection if multi else QAbstractItemView.SelectionMode.SingleSelection)
    t.setAlternatingRowColors(True);t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    install_table_productivity(t,headers[0] if headers else "Shift Handover")
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


class ShiftHandoverWorkspace(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.candidates=[];self.rows=[]
        root=QVBoxLayout(self);head=QHBoxLayout()
        title=QLabel("Shift Operations / Handover");title.setStyleSheet("font-size:20pt;font-weight:800")
        self.summary=QLabel();self.summary.setStyleSheet("color:#647581;")
        refresh=QPushButton("Refresh live status");refresh.clicked.connect(self.refresh)
        publish=QPushButton("Publish selected candidates");publish.clicked.connect(self.publish_selected);publish.setEnabled(db.has_permission(user,"endorsement.edit"))
        head.addWidget(title);head.addWidget(self.summary);head.addStretch(1);head.addWidget(refresh);head.addWidget(publish);root.addLayout(head)
        note=QLabel("Candidates are assembled automatically from abnormal equipment states, incidents, alarms, PM, work orders, qualification/release and active restrictions.")
        note.setWordWrap(True);note.setStyleSheet("color:#647581;");root.addWidget(note)

        split=QSplitter();root.addWidget(split,1)
        left=QWidget();lv=QVBoxLayout(left);lv.addWidget(QLabel("LIVE HANDOVER CANDIDATES"))
        self.candidate_table=_table(["Severity","Equipment","Name","Condition","Incidents","Alarms","PM","Work Orders","Next Owner","Existing Handover"],True)
        self.candidate_table.doubleClicked.connect(self.open_candidate_equipment);lv.addWidget(self.candidate_table)
        self.detail=QLabel();self.detail.setWordWrap(True);self.detail.setStyleSheet("background:#f8fafb;border:1px solid #d7dfe5;padding:8px;")
        self.candidate_table.itemSelectionChanged.connect(self.show_candidate_detail);lv.addWidget(self.detail);split.addWidget(left)

        right=QWidget();rv=QVBoxLayout(right);rh=QHBoxLayout();rh.addWidget(QLabel("PUBLISHED / ACTIVE HANDOVERS"));rh.addStretch(1)
        ack=QPushButton("Acknowledge selected");ack.clicked.connect(self.acknowledge);ack.setEnabled(db.has_permission(user,"endorsement.edit"));rh.addWidget(ack)
        open_eq=QPushButton("Open Equipment");open_eq.clicked.connect(self.open_handover_equipment);rh.addWidget(open_eq);rv.addLayout(rh)
        self.handover_table=_table(["No","Equipment","Condition","Pending","Restrictions","Next Action","Next Owner","Status","Created By","Ack By","Created"])
        self.handover_table.itemSelectionChanged.connect(self.load_attachment);rv.addWidget(self.handover_table,2)
        self.attachments=AttachmentPanel(db,user);rv.addWidget(self.attachments,1);split.addWidget(right);split.setStretchFactor(0,1);split.setStretchFactor(1,1)
        self.refresh()

    def refresh(self):
        try:self.candidates=self.db.shift_handover_candidates()
        except Exception as exc:QMessageBox.critical(self,"Shift handover",str(exc));return
        _fill(self.candidate_table,self.candidates,["severity","equipment_id","equipment_name","current_condition","active_incidents","active_alarms","open_pm","open_work_orders","next_owner","existing_open_handover"])
        self.rows=self.db.list_endorsements()
        _fill(self.handover_table,self.rows,["endorsement_no","equipment_id","current_condition","pending_work","restrictions","next_action","next_owner","status","created_by","acknowledged_by","created_at"])
        critical=sum(1 for x in self.candidates if x["severity"]=="CRITICAL");high=sum(1 for x in self.candidates if x["severity"]=="HIGH")
        self.summary.setText(f"{len(self.candidates)} live candidates · {critical} critical · {high} high · {sum(1 for x in self.rows if x.status in {'Open','Acknowledged'})} active handovers")
        self.show_candidate_detail();self.load_attachment()

    def selected_candidate_rows(self):
        indexes=sorted({x.row() for x in self.candidate_table.selectedIndexes()})
        return [self.candidates[i] for i in indexes if 0<=i<len(self.candidates)]

    def show_candidate_detail(self):
        rows=self.selected_candidate_rows()
        if not rows:self.detail.setText("Select a candidate to review automatically assembled pending work and restrictions.");return
        row=rows[0]
        self.detail.setText(
            f"{row['equipment_id']} — {row['current_condition']}\n\n"
            f"Pending work:\n{row['pending_work'] or 'None'}\n\n"
            f"Restrictions:\n{row['restrictions'] or 'None'}\n\n"
            f"Next action: {row['next_action']}\nNext owner: {row['next_owner'] or 'Unassigned'}"
        )

    def publish_selected(self):
        rows=self.selected_candidate_rows()
        if not rows:QMessageBox.information(self,"Shift handover","Select one or more live candidates.");return
        if QMessageBox.question(self,"Publish handovers",f"Publish {len(rows)} selected handover record(s) from current live operations?")!=QMessageBox.StandardButton.Yes:return
        created=[];failures=[]
        for row in rows:
            try:created.append(self.db.publish_shift_handover(row["equipment_id"],self.user["username"],row["next_owner"],"SHIFT-WORKSPACE"))
            except Exception as exc:failures.append(f"{row['equipment_id']}: {exc}")
        self.refresh()
        text=f"Published {len(created)}/{len(rows)} handover(s)."
        if failures:text+="\n\n"+"\n".join(failures[:12])
        QMessageBox.information(self,"Shift handover",text)

    def acknowledge(self):
        row=_selected(self.handover_table,self.rows)
        if not row:return
        try:self.db.acknowledge_endorsement(row.endorsement_no,self.user["username"]);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Shift handover",str(exc))

    def load_attachment(self):
        row=_selected(self.handover_table,self.rows)
        self.attachments.set_entity("ENDORSEMENT",row.endorsement_no,row.equipment_id) if row else self.attachments.set_entity("","")

    def set_endorsement(self,key: str):
        self.refresh()
        for i,row in enumerate(self.rows):
            if row.endorsement_no==key:
                self.handover_table.selectRow(i);break

    def open_candidate_equipment(self):
        rows=self.selected_candidate_rows()
        if rows:self.open_entity.emit("EQUIPMENT",rows[0]["equipment_id"],rows[0]["equipment_id"])

    def open_handover_equipment(self):
        row=_selected(self.handover_table,self.rows)
        if row:self.open_entity.emit("EQUIPMENT",row.equipment_id,row.equipment_id)
