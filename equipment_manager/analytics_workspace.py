from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,QFileDialog,QFrame,QGridLayout,QHBoxLayout,QHeaderView,QLabel,
    QMessageBox,QPushButton,QSpinBox,QTableWidget,QTableWidgetItem,QTabWidget,QVBoxLayout,QWidget
)

from table_productivity import install_table_productivity
from reporting import export_weekly_review_pptx, export_weekly_review_xlsx


def _item(value):
    if isinstance(value,float):value=f"{value:.2f}"
    if isinstance(value,datetime):value=value.strftime("%Y-%m-%d %H:%M")
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setAlternatingRowColors(True);t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    install_table_productivity(t,headers[0] if headers else "Engineering Analytics")
    return t


def _fill(table,rows,fields):
    table.setRowCount(len(rows))
    for r,row in enumerate(rows):
        for c,field in enumerate(fields):
            value=row.get(field,"") if isinstance(row,dict) else getattr(row,field,"")
            table.setItem(r,c,_item(value))


class MetricCard(QFrame):
    def __init__(self,label):
        super().__init__();self.setFrameShape(QFrame.Shape.StyledPanel)
        v=QVBoxLayout(self);self.value=QLabel("—");self.value.setStyleSheet("font-size:22pt;font-weight:800")
        caption=QLabel(label);caption.setStyleSheet("color:#647581")
        v.addWidget(self.value);v.addWidget(caption)


class BarChart(QWidget):
    itemActivated=Signal(str)

    def __init__(self,title="",parent=None):
        super().__init__(parent);self.title=title;self.rows=[];self.setMinimumHeight(270)
        self.setMouseTracking(True)

    def set_data(self,rows):
        self.rows=list(rows)[:15];self.update()

    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=self.rect();painter.fillRect(rect,QColor("#ffffff"))
        painter.setPen(QColor("#1b2733"));font=QFont();font.setBold(True);font.setPointSize(10);painter.setFont(font)
        painter.drawText(QRectF(12,8,rect.width()-24,28),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,self.title)
        if not self.rows:
            painter.setPen(QColor("#647581"));painter.drawText(rect,Qt.AlignmentFlag.AlignCenter,"No data");return
        left=165;top=44;bottom=20;right=48
        chart_w=max(40,rect.width()-left-right);chart_h=max(40,rect.height()-top-bottom)
        max_val=max(float(r[1] or 0) for r in self.rows) or 1.0
        row_h=chart_h/max(len(self.rows),1)
        for i,(label,value,key) in enumerate(self.rows):
            y=top+i*row_h
            painter.setPen(QColor("#334e5c"));painter.drawText(QRectF(6,y,left-16,row_h),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,str(label)[:24])
            width=chart_w*(float(value or 0)/max_val)
            bar=QRectF(left,y+row_h*.18,max(2,width),row_h*.64)
            painter.fillRect(bar,QColor("#397fa6"))
            painter.setPen(QColor("#1b2733"));painter.drawText(QRectF(left+width+6,y,45,row_h),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,f"{float(value or 0):.1f}")

    def mouseDoubleClickEvent(self,event):
        if not self.rows:return
        left=165;top=44;bottom=20
        chart_h=max(40,self.height()-top-bottom);row_h=chart_h/max(len(self.rows),1)
        idx=int((event.position().y()-top)/row_h)
        if 0<=idx<len(self.rows):self.itemActivated.emit(str(self.rows[idx][2]))


class EngineeringAnalyticsWorkspace(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.data={};self.tool_rows=[];self.alarm_rows=[];self.incident_rows=[]
        root=QVBoxLayout(self);head=QHBoxLayout()
        title=QLabel("Engineering Analytics");title.setStyleSheet("font-size:20pt;font-weight:800")
        self.days=QSpinBox();self.days.setRange(7,3650);self.days.setValue(30);self.days.setSuffix(" days")
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh)
        weekly_ppt=QPushButton("Weekly Review PPTX");weekly_ppt.clicked.connect(self.export_weekly_pptx)
        weekly_xlsx=QPushButton("Weekly Review Excel");weekly_xlsx.clicked.connect(self.export_weekly_xlsx)
        head.addWidget(title);head.addStretch(1);head.addWidget(QLabel("Period"));head.addWidget(self.days);head.addWidget(weekly_ppt);head.addWidget(weekly_xlsx);head.addWidget(refresh);root.addLayout(head)
        self.period=QLabel();self.period.setStyleSheet("color:#647581");root.addWidget(self.period)

        cards=QGridLayout();root.addLayout(cards);self.cards={}
        for i,label in enumerate(["Fleet availability","Unplanned downtime","Failures","Open P1/P2","Active alarms","PM compliance","PM overdue","Tools analyzed"]):
            card=MetricCard(label);self.cards[label]=card;cards.addWidget(card,i//4,i%4)

        tabs=QTabWidget();root.addWidget(tabs,1)
        fleet=QWidget();fv=QVBoxLayout(fleet)
        self.downtime_chart=BarChart("Unplanned downtime Pareto by equipment (hours)");self.downtime_chart.itemActivated.connect(self.open_equipment)
        fv.addWidget(self.downtime_chart,1)
        self.tool_table=_table(["Equipment","Availability %","Failures","Unplanned h","Planned h","MTTR h","MTBF h","Incidents","Open","P1/P2 Open","Active Alarms","State"])
        self.tool_table.doubleClicked.connect(self.open_selected_tool);fv.addWidget(self.tool_table,2);tabs.addTab(fleet,"Fleet Reliability / Chronic Tools")

        alarm=QWidget();av=QVBoxLayout(alarm)
        self.alarm_chart=BarChart("Alarm Pareto");av.addWidget(self.alarm_chart,1)
        self.alarm_table=_table(["Alarm Code","Message","Count"]);av.addWidget(self.alarm_table,1);tabs.addTab(alarm,"Alarm Pareto")

        incident=QWidget();iv=QVBoxLayout(incident)
        self.incident_chart=BarChart("Incident Pareto by equipment");self.incident_chart.itemActivated.connect(self.open_equipment);iv.addWidget(self.incident_chart,1)
        self.incident_table=_table(["Equipment","Incidents"]);self.incident_table.doubleClicked.connect(self.open_selected_incident_tool);iv.addWidget(self.incident_table,1);tabs.addTab(incident,"Incident Pareto")

        pm=QWidget();pv=QVBoxLayout(pm);self.pm_summary=QLabel();self.pm_summary.setStyleSheet("font-size:16pt;font-weight:700");pv.addWidget(self.pm_summary)
        self.pm_bar=BarChart("PM completion / overdue / deferred");pv.addWidget(self.pm_bar);pv.addStretch(1);tabs.addTab(pm,"PM Compliance")
        self.refresh()

    def refresh(self):
        self.data=self.db.engineering_analytics(self.days.value())
        start=self.data["start"].strftime("%Y-%m-%d");end=self.data["end"].strftime("%Y-%m-%d")
        self.period.setText(f"Governed operational data: {start} to {end}. Double-click equipment rows/bars to drill into Equipment 360.")
        self.tool_rows=self.data["tool_matrix"];self.alarm_rows=self.data["alarm_pareto"];self.incident_rows=self.data["incident_pareto"]
        _fill(self.tool_table,self.tool_rows,["equipment_id","availability_pct","failure_count","unplanned_downtime_hours","planned_downtime_hours","mttr_hours","mtbf_hours","incidents_period","open_incidents","critical_open","active_alarms","current_state"])
        _fill(self.alarm_table,self.alarm_rows,["alarm_code","message","count"])
        _fill(self.incident_table,self.incident_rows,["equipment_id","count"])
        self.downtime_chart.set_data([(x["equipment_id"],x["unplanned_downtime_hours"],x["equipment_id"]) for x in self.tool_rows if x["unplanned_downtime_hours"]>0][:15])
        self.alarm_chart.set_data([(x["alarm_code"],x["count"],x["alarm_code"]) for x in self.alarm_rows[:15]])
        self.incident_chart.set_data([(x["equipment_id"],x["count"],x["equipment_id"]) for x in self.incident_rows[:15]])
        pm=self.data["pm"];self.pm_summary.setText(f"PM compliance: {pm['compliance_pct']:.1f}%   Due: {pm['due']}   Completed: {pm['completed']}   Overdue: {pm['overdue']}   Deferred: {pm['deferred']}")
        self.pm_bar.set_data([("Completed",pm["completed"],"completed"),("Overdue",pm["overdue"],"overdue"),("Deferred",pm["deferred"],"deferred")])
        if self.tool_rows:
            total_period=sum(float(x["unplanned_downtime_hours"]) for x in self.tool_rows)
            failures=sum(int(x["failure_count"]) for x in self.tool_rows)
            critical=sum(int(x["critical_open"]) for x in self.tool_rows)
            alarms=sum(int(x["active_alarms"]) for x in self.tool_rows)
            fleet=sum(float(x["availability_pct"]) for x in self.tool_rows)/len(self.tool_rows)
        else:total_period=0;failures=critical=alarms=0;fleet=100
        vals={
            "Fleet availability":f"{fleet:.1f}%",
            "Unplanned downtime":f"{total_period:.1f} h",
            "Failures":str(failures),"Open P1/P2":str(critical),"Active alarms":str(alarms),
            "PM compliance":f"{pm['compliance_pct']:.1f}%","PM overdue":str(pm["overdue"]),"Tools analyzed":str(len(self.tool_rows)),
        }
        for key,val in vals.items():self.cards[key].value.setText(val)

    def export_weekly_pptx(self):
        path,_=QFileDialog.getSaveFileName(self,"Export Weekly Engineering Review","Equipment_Engineering_Weekly_Review.pptx","PowerPoint (*.pptx)")
        if not path:return
        if not path.lower().endswith(".pptx"):path+=".pptx"
        template=""
        if QMessageBox.question(self,"PowerPoint template","Use a site PowerPoint template?")==QMessageBox.StandardButton.Yes:
            template,_=QFileDialog.getOpenFileName(self,"Select PowerPoint Template","","PowerPoint (*.pptx *.potx)")
            if not template:return
        try:
            export_weekly_review_pptx(self.db,path,self.days.value(),template)
            QMessageBox.information(self,"Weekly Review",f"Editable PowerPoint review pack created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"Weekly Review",str(exc))

    def export_weekly_xlsx(self):
        path,_=QFileDialog.getSaveFileName(self,"Export Weekly Engineering Review","Equipment_Engineering_Weekly_Review.xlsx","Excel Workbook (*.xlsx)")
        if not path:return
        if not path.lower().endswith(".xlsx"):path+=".xlsx"
        try:
            export_weekly_review_xlsx(self.db,path,self.days.value())
            QMessageBox.information(self,"Weekly Review",f"Engineering review workbook created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"Weekly Review",str(exc))

    def open_equipment(self,equipment_id: str):
        if equipment_id:self.open_entity.emit("EQUIPMENT",equipment_id,equipment_id)

    def open_selected_tool(self):
        row=self.tool_table.currentRow()
        if 0<=row<len(self.tool_rows):self.open_equipment(self.tool_rows[row]["equipment_id"])

    def open_selected_incident_tool(self):
        row=self.incident_table.currentRow()
        if 0<=row<len(self.incident_rows):self.open_equipment(self.incident_rows[row]["equipment_id"])
