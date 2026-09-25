from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRectF, Signal, QMimeData
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,QCheckBox,QComboBox,QFileDialog,QFrame,QGraphicsItem,QGraphicsPixmapItem,QGraphicsRectItem,
    QGraphicsScene,QGraphicsSimpleTextItem,QGraphicsView,QHBoxLayout,QLabel,
    QMessageBox,QPushButton,QSplitter,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget,
)

from database import Database
from demo_data import STATUS_COLORS
from main import WORKSTATION
from feedback import notify
from shift_report import build_fab_status_report, export_fab_status_csv, export_fab_status_xlsx, export_fab_status_pdf


def make_cad_background(width: int = 1550, height: int = 900) -> QPixmap:
    pix=QPixmap(width,height);pix.fill(QColor("#0b1117"))
    painter=QPainter(pix);painter.setRenderHint(QPainter.RenderHint.Antialiasing,True)
    painter.setPen(QPen(QColor("#152a36"),1))
    for x in range(0,width,25):painter.drawLine(x,0,x,height)
    for y in range(0,height,25):painter.drawLine(0,y,width,y)
    painter.setPen(QPen(QColor("#486472"),2));painter.drawRect(45,55,width-90,height-110)
    painter.setPen(QPen(QColor("#29434f"),1))
    for y in [125,230,335,440,545,650,755]:painter.drawLine(85,y,width-85,y)
    for x in [90,440,790,1140,1490]:painter.drawLine(x,105,x,height-100)
    painter.setPen(QPen(QColor("#7d98a5"),1));painter.setFont(QFont("Consolas",10,QFont.Weight.Bold))
    for idx,y in enumerate([145,250,355,460,565,670,775],1):painter.drawText(55,y+25,f"BAY {idx:02d}")
    zones=[(105,75,305,30,"PROCESS CORRIDOR A"),(455,75,305,30,"PROCESS CORRIDOR B"),(805,75,305,30,"PROCESS CORRIDOR C"),(1155,75,305,30,"PROCESS CORRIDOR D")]
    painter.setPen(QPen(QColor("#6cb4d6"),1));painter.setFont(QFont("Segoe UI",8,QFont.Weight.DemiBold))
    for x,y,w,h,label in zones:painter.drawRect(x,y,w,h);painter.drawText(x+8,y+20,label)
    painter.setPen(QPen(QColor("#315361"),1,Qt.PenStyle.DashLine))
    painter.drawRect(90,810,520,45);painter.drawRect(635,810,360,45);painter.drawRect(1020,810,440,45)
    painter.setPen(QPen(QColor("#64818f"),1))
    painter.drawText(105,838,"SUB-FAB / VACUUM / GAS DISTRIBUTION");painter.drawText(650,838,"SERVICE CHASE");painter.drawText(1035,838,"FACILITIES / UTILITY INTERFACE")
    painter.end();return pix


def make_tool_icon(tool_type: str,color: QColor) -> QPixmap:
    pix=QPixmap(38,38);pix.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pix);painter.setRenderHint(QPainter.RenderHint.Antialiasing,True)
    painter.setPen(QPen(color,2));painter.setBrush(QBrush(QColor("#12212b")));painter.drawRoundedRect(2,2,34,34,5,5)
    tool=(tool_type or "").lower()
    if "etch" in tool or "cvd" in tool or "pvd" in tool:
        painter.drawEllipse(10,9,18,18);painter.drawLine(10,29,28,29)
    elif "stepper" in tool or "lith" in tool:
        painter.drawRect(9,10,20,15);painter.drawLine(13,29,25,29);painter.drawEllipse(16,14,6,6)
    elif "cmp" in tool:
        painter.drawEllipse(8,17,22,10);painter.drawEllipse(13,8,12,12)
    elif "furn" in tool:
        painter.drawRect(10,8,18,22)
        for y in [12,17,22]:painter.drawLine(14,y,24,y)
    elif "wet" in tool:
        painter.drawRect(8,12,22,16);painter.drawLine(12,17,26,17);painter.drawLine(12,22,26,22)
    else:
        painter.drawRect(9,9,20,20);painter.drawLine(13,13,25,25);painter.drawLine(25,13,13,25)
    painter.end();return pix


class FabMapView(QGraphicsView):
    def __init__(self,scene,parent=None):
        super().__init__(scene,parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#071016"));self.setFrameShape(QFrame.Shape.NoFrame)

    def wheelEvent(self,event):
        factor=1.18 if event.angleDelta().y()>0 else 1/1.18
        self.scale(factor,factor)


class ToolNode(QGraphicsRectItem):
    WIDTH=138;HEIGHT=78

    def __init__(self,snapshot: dict,selected_cb,movable: bool):
        super().__init__(0,0,self.WIDTH,self.HEIGHT)
        self.snapshot=snapshot;self.selected_cb=selected_cb
        self.base_color=STATUS_COLORS.get(snapshot.get("health","good"),STATUS_COLORS["good"])
        self.has_issue=snapshot.get("health") in {"critical","attention"} or snapshot.get("active_alarm_count",0)>0 or snapshot.get("open_ticket_count",0)>0
        self.pulse_on=False
        self.setPos(float(snapshot.get("map_x") or 0),float(snapshot.get("map_y") or 0));self.setZValue(10)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,True);self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,movable);self.setAcceptHoverEvents(True)
        lots=", ".join(snapshot.get("lots") or [])
        self.setToolTip(
            f"{snapshot.get('equipment_id','')}\n{snapshot.get('name','')}\n"
            f"{snapshot.get('equipment_status','')} · {snapshot.get('health','')}\n"
            f"{snapshot.get('current_issue_title','')}\nLots: {lots or '—'}"
        )
        icon=QGraphicsPixmapItem(make_tool_icon(snapshot.get("equipment_type",""),self.base_color),self);icon.setPos(7,8)
        id_text=QGraphicsSimpleTextItem(snapshot.get("equipment_id",""),self);id_text.setBrush(QBrush(QColor("#e8f1f5")));id_text.setFont(QFont("Segoe UI",7,QFont.Weight.Bold));id_text.setPos(49,6)
        status_text=QGraphicsSimpleTextItem(snapshot.get("equipment_status",""),self);status_text.setBrush(QBrush(self.base_color));status_text.setFont(QFont("Segoe UI",7));status_text.setPos(49,24)
        badges=[]
        if snapshot.get("active_alarm_count"):badges.append(f"A{snapshot['active_alarm_count']}")
        if snapshot.get("open_ticket_count"):badges.append(f"T{snapshot['open_ticket_count']}")
        if snapshot.get("active_pm_task_id"):badges.append("PM")
        if snapshot.get("open_work_order_count"):badges.append(f"WO{snapshot['open_work_order_count']}")
        badge_text=QGraphicsSimpleTextItem("  ".join(badges) or "OK",self);badge_text.setBrush(QBrush(QColor("#ffd4d4") if self.has_issue else QColor("#9fd9ba")));badge_text.setFont(QFont("Segoe UI",6,QFont.Weight.Bold));badge_text.setPos(49,43)
        if snapshot.get("next_pm_within_24h") and snapshot.get("next_pm_at"):
            next_text=QGraphicsSimpleTextItem("Next PM "+snapshot["next_pm_at"].strftime("%m-%d %H:%M"),self);next_text.setBrush(QBrush(QColor("#8fc7e9")));next_text.setFont(QFont("Segoe UI",5));next_text.setPos(7,62)
        self.apply_visual(False)

    def apply_visual(self,pulse: bool):
        self.pulse_on=pulse;edge=QColor(self.base_color)
        if self.has_issue and pulse:
            edge=edge.lighter(150);self.setScale(1.035);self.setOpacity(.98)
        else:self.setScale(1.0);self.setOpacity(1.0)
        self.setPen(QPen(edge,3 if self.has_issue else 1.5));fill=QColor("#15232d");fill.setAlpha(245 if self.has_issue else 225);self.setBrush(QBrush(fill))

    def mousePressEvent(self,event):
        super().mousePressEvent(event);self.selected_cb(self.snapshot)

    def hoverEnterEvent(self,event):
        self.setPen(QPen(self.base_color.lighter(145),3));super().hoverEnterEvent(event)

    def hoverLeaveEvent(self,event):
        self.apply_visual(self.pulse_on);super().hoverLeaveEvent(event)


class StorageNode(QGraphicsRectItem):
    def __init__(self,storage,highlighted: bool,movable: bool):
        super().__init__(0,0,88,42);self.key=storage.location_code;self.version=storage.version
        self.setPos(storage.map_x,storage.map_y);self.setZValue(8);self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,movable)
        self.setBrush(QBrush(QColor("#5b4729" if not highlighted else "#9c5d16")));self.setPen(QPen(QColor("#d3a14e" if not highlighted else "#ffb13b"),1.5))
        label=QGraphicsSimpleTextItem(storage.location_code,self);label.setBrush(QBrush(QColor("#f5e7c9")));label.setFont(QFont("Segoe UI",7,QFont.Weight.Bold));label.setPos(7,10)


class SmartLayoutPage(QWidget):
    open_entity=Signal(str,str,str)
    report_issue=Signal(str)

    def __init__(self,db: Database,user):
        super().__init__();self.db=db;self.user=user;self.nodes=[];self.storage_nodes=[];self.highlight_part="";self._pulse=False;self.health_filter="all"
        self.can_edit=db.has_permission(user,"layout.edit") or db.has_permission(user,"equipment.edit")
        root=QVBoxLayout(self);root.setContentsMargins(12,12,12,12);root.setSpacing(8)

        title_row=QHBoxLayout();title_box=QVBoxLayout();title=QLabel("FAB Live Equipment Map");title.setObjectName("SectionTitle")
        subtitle=QLabel("Management command center · manual tickets, alarms, PM and schedule status");subtitle.setObjectName("Muted")
        title_box.addWidget(title);title_box.addWidget(subtitle);title_row.addLayout(title_box);title_row.addStretch(1);self.health=QLabel();title_row.addWidget(self.health);root.addLayout(title_row)

        all_equipment=db.list_equipment()
        controls=QHBoxLayout();self.building=QComboBox();self.floor=QComboBox();self.area=QComboBox()
        buildings=sorted({e.building for e in all_equipment if e.building}) or ["FAB-A"];floors=sorted({e.floor for e in all_equipment if e.floor}) or ["1F"]
        self.building.addItems(buildings);self.floor.addItems(floors);self.area.addItem("All areas")
        if "FAB-A" in buildings:self.building.setCurrentText("FAB-A")
        if "1F" in floors:self.floor.setCurrentText("1F")
        self.building.currentTextChanged.connect(self._scope_changed);self.floor.currentTextChanged.connect(self._scope_changed);self.area.currentTextChanged.connect(self.refresh)
        self.issue_only=QCheckBox("Problems only");self.issue_only.toggled.connect(self.refresh)
        self.edit_mode=QCheckBox("Layout edit");self.edit_mode.setEnabled(self.can_edit);self.edit_mode.toggled.connect(self.refresh)
        fit_btn=QPushButton("Fit FAB");fit_btn.clicked.connect(self.fit_map);refresh_btn=QPushButton("Refresh");refresh_btn.clicked.connect(self.refresh);save_btn=QPushButton("Save positions");save_btn.setEnabled(self.can_edit);save_btn.clicked.connect(self.save_positions)
        copy_status=QPushButton("Copy FAB Status");copy_status.clicked.connect(self.copy_fab_status)
        copy_image=QPushButton("Copy Dashboard Image");copy_image.clicked.connect(self.copy_dashboard_image)
        export_report=QPushButton("Export Report");export_report.clicked.connect(self.export_fab_report)
        for widget in [QLabel("Building"),self.building,QLabel("Floor"),self.floor,QLabel("Area"),self.area,self.issue_only,self.edit_mode,fit_btn,refresh_btn,copy_status,copy_image,export_report,save_btn]:controls.addWidget(widget)
        controls.addStretch(1);root.addLayout(controls)

        self.kpi_row=QHBoxLayout();self.kpi_buttons={}
        for key,label in [("all","All"),("good","Running / good"),("critical","Critical / down"),("attention","Attention"),("planned","PM / engineering"),("offline","Offline")]:
            b=QPushButton(label);b.clicked.connect(lambda _=False,k=key:self.set_health_filter(k));self.kpi_buttons[key]=b;self.kpi_row.addWidget(b)
        self.kpi_row.addStretch(1);root.addLayout(self.kpi_row)

        legend=QHBoxLayout()
        for key,text in [("good","Running / good"),("attention","Attention"),("critical","Down / critical"),("planned","PM / engineering"),("offline","Offline")]:
            dot=QLabel(f"● {text}");dot.setStyleSheet(f"color:{STATUS_COLORS[key].name()};font-weight:600;");legend.addWidget(dot)
        pulse=QLabel("Pulsing border = active abnormal condition");pulse.setObjectName("Muted");legend.addSpacing(15);legend.addWidget(pulse);legend.addStretch(1);root.addLayout(legend)

        splitter=QSplitter(Qt.Orientation.Horizontal);self.scene=QGraphicsScene(self);self.view=FabMapView(self.scene);splitter.addWidget(self.view)
        inspector=QFrame();inspector.setObjectName("Inspector");iv=QVBoxLayout(inspector)
        self.detail_title=QLabel("Select an equipment icon");self.detail_title.setObjectName("SectionTitle");self.detail_title.setWordWrap(True)
        self.detail_status=QLabel("No tool selected");self.detail_status.setObjectName("Muted")
        self.detail_body=QLabel("Click a colored equipment tile to inspect current status, lots, active issues and planned PM.");self.detail_body.setWordWrap(True);self.detail_body.setTextFormat(Qt.TextFormat.RichText)
        action_row=QHBoxLayout();self.open_equipment_btn=QPushButton("Equipment 360");self.open_issue_btn=QPushButton("Open Issue");self.report_issue_btn=QPushButton("Report Issue");self.open_pm_btn=QPushButton("Open PM")
        self.open_equipment_btn.clicked.connect(self.open_selected_equipment);self.open_issue_btn.clicked.connect(self.open_selected_issue);self.report_issue_btn.clicked.connect(self.report_selected_issue);self.open_pm_btn.clicked.connect(self.open_selected_pm)
        for b in [self.open_equipment_btn,self.open_issue_btn,self.report_issue_btn,self.open_pm_btn]:action_row.addWidget(b)
        self.issue_table=QTableWidget(0,5);self.issue_table.setHorizontalHeaderLabels(["Ticket","Pri","Sev","Status","Owner"]);self.issue_table.horizontalHeader().setStretchLastSection(True);self.issue_table.setMinimumHeight(160)
        self.issue_description=QLabel("");self.issue_description.setWordWrap(True);self.issue_description.setStyleSheet("background:white;border:1px solid #d8e0e6;border-radius:5px;padding:8px;")
        self.issue_table.currentCellChanged.connect(self.show_selected_issue)
        iv.addWidget(self.detail_title);iv.addWidget(self.detail_status);iv.addWidget(self.detail_body);iv.addLayout(action_row);iv.addWidget(QLabel("Active Issues"));iv.addWidget(self.issue_table);iv.addWidget(self.issue_description);iv.addStretch(1)
        splitter.addWidget(inspector);splitter.setStretchFactor(0,4);splitter.setStretchFactor(1,1);splitter.setSizes([1100,360]);root.addWidget(splitter,1)

        self.timer=QTimer(self);self.timer.timeout.connect(self.animate_issues);self.timer.start(650)
        self.refresh_timer=QTimer(self);self.refresh_timer.timeout.connect(self.refresh);self.refresh_timer.start(20000)
        self.refresh();QTimer.singleShot(50,self.fit_map)

    def scope_key(self):return f"{self.building.currentText()}|{self.floor.currentText()}"

    def _scope_changed(self):
        building=self.building.currentText();floor=self.floor.currentText()
        areas=sorted({e.area for e in self.db.list_equipment() if (not building or e.building==building) and (not floor or e.floor==floor) and e.area})
        current=self.area.currentText();self.area.blockSignals(True);self.area.clear();self.area.addItem("All areas");self.area.addItems(areas)
        if current in areas:self.area.setCurrentText(current)
        self.area.blockSignals(False);self.refresh()

    def set_health_filter(self,key: str):
        self.health_filter=key;self.refresh()

    def refresh(self):
        self.scene.clear();self.nodes=[];self.storage_nodes=[]
        background_path=self.db.get_layout_background(self.scope_key());pix=QPixmap(background_path) if background_path and Path(background_path).exists() else make_cad_background()
        if pix.isNull():pix=make_cad_background()
        background=QGraphicsPixmapItem(pix);background.setZValue(-20);self.scene.addItem(background)
        area="" if self.area.currentText()=="All areas" else self.area.currentText()
        all_rows=self.db.fab_health_snapshot(self.building.currentText(),self.floor.currentText(),area)
        self._last_snapshot=all_rows
        counts={key:sum(1 for x in all_rows if x["health"]==key) for key in ["good","critical","attention","planned","offline"]};counts["all"]=len(all_rows)
        for key,button in self.kpi_buttons.items():button.setText(f"{button.text().split('  ·  ')[0]}  ·  {counts.get(key,0)}")
        rows=list(all_rows)
        if self.issue_only.isChecked():rows=[x for x in rows if x["health"] in {"critical","attention"} or x["active_alarm_count"] or x["open_ticket_count"]]
        if self.health_filter!="all":rows=[x for x in rows if x["health"]==self.health_filter]
        for snap in rows:
            node=ToolNode(snap,self.select_tool,self.edit_mode.isChecked());self.scene.addItem(node);self.nodes.append(node)
        for storage in self.db.list_storage_locations():
            if self.building.currentText() and storage.building!=self.building.currentText():continue
            if self.floor.currentText() and storage.floor!=self.floor.currentText():continue
            node=StorageNode(storage,False,self.edit_mode.isChecked());self.scene.addItem(node);self.storage_nodes.append(node)
        critical=counts["critical"];attention=counts["attention"]
        if critical:
            self.health.setText(f"FAB ATTENTION · {critical} critical · {attention} attention");self.health.setStyleSheet("font-weight:700;padding:6px 10px;border-radius:5px;background:#ffe4e4;color:#9d2929;")
        elif attention:
            self.health.setText(f"FAB STABLE · {attention} tools need attention");self.health.setStyleSheet("font-weight:700;padding:6px 10px;border-radius:5px;background:#fff0d7;color:#8a5812;")
        else:
            self.health.setText(f"ALL GREEN · {counts['good']} normal");self.health.setStyleSheet("font-weight:700;padding:6px 10px;border-radius:5px;background:#dff4e8;color:#176b43;")
        self.scene.setSceneRect(QRectF(0,0,pix.width(),pix.height()))

    def fit_map(self):self.view.fitInView(self.scene.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)

    def animate_issues(self):
        self._pulse=not self._pulse
        for node in self.nodes:
            if node.has_issue:node.apply_visual(self._pulse)

    def highlight_equipment(self,equipment_id: str):
        eq=self.db.get_equipment(equipment_id)
        if not eq:return False
        self.building.blockSignals(True);self.floor.blockSignals(True)
        try:
            if eq.building and self.building.findText(eq.building)>=0:self.building.setCurrentText(eq.building)
            if eq.floor and self.floor.findText(eq.floor)>=0:self.floor.setCurrentText(eq.floor)
        finally:self.building.blockSignals(False);self.floor.blockSignals(False)
        self.health_filter="all";self.issue_only.setChecked(False);self._scope_changed()
        for node in self.nodes:
            if node.snapshot["equipment_id"]==equipment_id:
                node.setSelected(True);self.view.centerOn(node);self.select_tool(node.snapshot);return True
        return False

    def select_tool(self,snapshot: dict):
        self._selected_snapshot=snapshot
        color=STATUS_COLORS.get(snapshot["health"],STATUS_COLORS["good"]).name()
        self.detail_title.setText(f"{snapshot['equipment_id']} · {snapshot['name']}")
        self.detail_status.setText(f"{snapshot['equipment_status']} · {snapshot['disposition']} · {snapshot['health'].upper()}")
        self.detail_status.setStyleSheet(f"color:{color};font-weight:700;")
        lots=", ".join(snapshot.get("lots") or []) or "—";alarms=", ".join(snapshot.get("alarm_codes") or []) or "—"
        next_pm=snapshot.get("next_pm_at")
        self.detail_body.setText(
            f"<b>Area:</b> {snapshot['area']} / {snapshot['line_cell']}<br>"
            f"<b>Owner:</b> {snapshot['owner'] or '—'}<br>"
            f"<b>Running / affected lots:</b> {lots}<br>"
            f"<b>Active alarms:</b> {snapshot['active_alarm_count']} ({alarms})<br>"
            f"<b>Open tickets:</b> {snapshot['open_ticket_count']} &nbsp; <b>Open WO:</b> {snapshot['open_work_order_count']}<br>"
            f"<b>Current issue:</b> {snapshot.get('current_issue_no') or '—'} {snapshot.get('current_issue_title') or ''}<br>"
            f"<b>Current / next action:</b> {snapshot.get('current_action') or '—'}<br>"
            f"<b>Active PM:</b> {snapshot.get('active_pm_id') or '—'}<br>"
            f"<b>Next scheduled PM:</b> {snapshot.get('next_pm_id') or '—'} {next_pm or ''}"
        )
        tickets=[x for x in self.db.list_tickets(snapshot["equipment_id"]) if x.status not in {"Closed","Cancelled"}]
        self._selected_tickets=tickets;self.issue_table.setRowCount(len(tickets))
        for row,ticket in enumerate(tickets):
            for col,value in enumerate([ticket.ticket_no,ticket.priority,ticket.severity,ticket.status,ticket.owner]):self.issue_table.setItem(row,col,QTableWidgetItem(str(value or "")))
        if tickets:self.issue_table.selectRow(0);self.show_selected_issue(0,0,-1,-1)
        else:self.issue_description.setText("No active ticket.")
        self.open_issue_btn.setEnabled(bool(snapshot.get("current_issue_no")));self.open_pm_btn.setEnabled(bool(snapshot.get("active_pm_task_id") or snapshot.get("next_pm_task_id")))

    def show_selected_issue(self,row,_column,_previous_row,_previous_column):
        tickets=getattr(self,"_selected_tickets",[])
        if 0<=row<len(tickets):
            ticket=tickets[row];lots=", ".join(x.lot_number for x in self.db.list_entity_lots("TICKET",ticket.ticket_no))
            self.issue_description.setText(f"<b>{ticket.title}</b><br>{ticket.description or 'No description entered.'}<br><b>Lots:</b> {lots or '—'}")

    def open_selected_equipment(self):
        snap=getattr(self,"_selected_snapshot",None)
        if snap:self.open_entity.emit("EQUIPMENT",snap["equipment_id"],snap["equipment_id"])

    def open_selected_issue(self):
        snap=getattr(self,"_selected_snapshot",None)
        if snap and snap.get("current_issue_no"):self.open_entity.emit("TICKET",snap["current_issue_no"],snap["equipment_id"])

    def report_selected_issue(self):
        snap=getattr(self,"_selected_snapshot",None)
        if snap:self.report_issue.emit(snap["equipment_id"])

    def open_selected_pm(self):
        snap=getattr(self,"_selected_snapshot",None)
        if not snap:return
        task_id=snap.get("active_pm_task_id") or snap.get("next_pm_task_id")
        if task_id:self.open_entity.emit("PM_TASK",str(task_id),snap["equipment_id"])

    def copy_fab_status(self):
        rows=getattr(self,"_last_snapshot",[])
        if not rows:notify("FAB status: no equipment in the current scope.");return
        title=f"FAB Status — {self.building.currentText()} / {self.floor.currentText()}"
        plain,html=build_fab_status_report(rows,title=title)
        mime=QMimeData();mime.setText(plain);mime.setHtml(html);QApplication.clipboard().setMimeData(mime)
        notify("FAB status copied. Paste directly into Outlook, Teams, or another message.")

    def copy_dashboard_image(self):
        pix=self.grab()
        if pix.isNull():notify("Dashboard image capture failed.");return
        QApplication.clipboard().setPixmap(pix)
        notify("FAB dashboard image copied to clipboard.")

    def export_fab_report(self):
        rows=getattr(self,"_last_snapshot",[])
        if not rows:notify("FAB report: no equipment in the current scope.");return
        default=f"FAB_Status_{self.building.currentText()}_{self.floor.currentText()}"
        path,selected=QFileDialog.getSaveFileName(
            self,"Export FAB Status",default+".xlsx",
            "Excel Workbook (*.xlsx);;CSV (*.csv);;PDF (*.pdf)",
        )
        if not path:return
        try:
            low=path.lower()
            if "CSV" in selected or low.endswith(".csv"):
                if not low.endswith(".csv"):path+=".csv"
                export_fab_status_csv(rows,path)
            elif "PDF" in selected or low.endswith(".pdf"):
                if not low.endswith(".pdf"):path+=".pdf"
                export_fab_status_pdf(rows,path,f"FAB Status — {self.building.currentText()} / {self.floor.currentText()}")
            else:
                if not low.endswith(".xlsx"):path+=".xlsx"
                export_fab_status_xlsx(rows,path)
            notify(f"FAB report exported: {path}")
        except Exception as exc:QMessageBox.critical(self,"FAB report",str(exc))

    def save_positions(self):
        if not self.can_edit:return
        try:
            for node in self.nodes:
                snap=node.snapshot
                self.db.update_map_position("equipment",snap["equipment_id"],node.pos().x(),node.pos().y(),snap["version"])
            for node in self.storage_nodes:self.db.update_map_position("storage",node.key,node.pos().x(),node.pos().y(),node.version)
            self.db.audit(self.user["username"],"UPDATE","LAYOUT",self.scope_key(),workstation=WORKSTATION);QMessageBox.information(self,"FAB Layout","Map positions saved.");self.refresh()
        except Exception as exc:QMessageBox.critical(self,"FAB Layout",str(exc));self.refresh()

    def highlight_inventory(self,part: str):
        self.highlight_part=(part or "").strip();self.refresh()
