from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,QComboBox,QFileDialog,QFrame,QGridLayout,QHBoxLayout,QHeaderView,QLabel,
    QLineEdit,QMessageBox,QPushButton,QSpinBox,QTableWidget,QTableWidgetItem,QTabWidget,QVBoxLayout,QWidget
)

from table_productivity import install_table_productivity
from reporting import export_weekly_review_pptx, export_weekly_review_xlsx
from pdf_reporting import export_weekly_review_pdf


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


class LineChart(QWidget):
    def __init__(self,title="",parent=None):
        super().__init__(parent);self.title=title;self.rows=[];self.setMinimumHeight(280)

    def set_data(self,rows,title: str | None=None):
        self.rows=list(rows)
        if title is not None:self.title=title
        self.update()

    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=self.rect();painter.fillRect(rect,QColor("#ffffff"))
        painter.setPen(QColor("#1b2733"));font=QFont();font.setBold(True);font.setPointSize(10);painter.setFont(font)
        painter.drawText(QRectF(12,8,rect.width()-24,28),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,self.title)
        if not self.rows:
            painter.setPen(QColor("#647581"));painter.drawText(rect,Qt.AlignmentFlag.AlignCenter,"No data");return
        left=62;top=45;right=24;bottom=42
        w=max(60,rect.width()-left-right);h=max(60,rect.height()-top-bottom)
        vals=[float(x[1] or 0) for x in self.rows];low=min(vals);high=max(vals)
        if high==low:high=low+1.0
        painter.setPen(QPen(QColor("#d7dfe5"),1));painter.drawLine(left,top,left,top+h);painter.drawLine(left,top+h,left+w,top+h)
        painter.setPen(QColor("#647581"))
        painter.drawText(QRectF(4,top-8,left-10,20),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,f"{high:.2f}")
        painter.drawText(QRectF(4,top+h-8,left-10,20),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,f"{low:.2f}")
        points=[]
        count=max(1,len(self.rows)-1)
        for i,row in enumerate(self.rows):
            x=left+(w*i/count if len(self.rows)>1 else w/2)
            y=top+h-((float(row[1] or 0)-low)/(high-low))*h
            points.append(QPointF(x,y))
        pen=QPen(QColor("#397fa6"),2);painter.setPen(pen)
        for a,b in zip(points,points[1:]):painter.drawLine(a,b)
        painter.setBrush(QColor("#397fa6"))
        for point in points:painter.drawEllipse(point,3,3)
        painter.setPen(QColor("#647581"))
        if self.rows:
            first=str(self.rows[0][0]);last=str(self.rows[-1][0])
            painter.drawText(QRectF(left,top+h+8,w/2,24),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,first[:16])
            painter.drawText(QRectF(left+w/2,top+h+8,w/2,24),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,last[:16])


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
        weekly_pdf=QPushButton("Weekly Review PDF");weekly_pdf.clicked.connect(self.export_weekly_pdf)
        head.addWidget(title);head.addStretch(1);head.addWidget(QLabel("Period"));head.addWidget(self.days);head.addWidget(weekly_ppt);head.addWidget(weekly_xlsx);head.addWidget(weekly_pdf);head.addWidget(refresh);root.addLayout(head)
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

        trend=QWidget();tv=QVBoxLayout(trend);th=QHBoxLayout()
        self.trend_metric=QComboBox();self.trend_metric.addItems(["Fleet availability %","Unplanned downtime h","Failure count"])
        self.bucket_days=QSpinBox();self.bucket_days.setRange(1,90);self.bucket_days.setValue(7);self.bucket_days.setSuffix(" d/bucket")
        rebuild=QPushButton("Rebuild trend");rebuild.clicked.connect(self.refresh_trend)
        th.addWidget(QLabel("Metric"));th.addWidget(self.trend_metric);th.addWidget(QLabel("Bucket"));th.addWidget(self.bucket_days);th.addWidget(rebuild);th.addStretch(1);tv.addLayout(th)
        self.trend_chart=LineChart("Fleet reliability trend");tv.addWidget(self.trend_chart,2)
        self.trend_table=_table(["Start","End","Availability %","Unplanned h","Planned h","Failures","Tools"]);tv.addWidget(self.trend_table,1);tabs.addTab(trend,"Fleet Trend")

        compare=QWidget();cv=QVBoxLayout(compare);ch=QHBoxLayout()
        self.compare_input=QLineEdit();self.compare_input.setPlaceholderText("Equipment IDs separated by commas, e.g. ETCH-01, ETCH-02")
        compareb=QPushButton("Compare");compareb.clicked.connect(self.refresh_compare)
        ch.addWidget(self.compare_input,1);ch.addWidget(compareb);cv.addLayout(ch)
        self.compare_table=_table(["Equipment","Name","Type","Area","State","Availability %","Failures","Unplanned h","MTTR h","MTBF h","Incidents","Active Alarms","Overdue PM"]);self.compare_table.doubleClicked.connect(self.open_compare_selected);cv.addWidget(self.compare_table);tabs.addTab(compare,"Tool Comparison")

        meter=QWidget();mv=QVBoxLayout(meter);mh=QHBoxLayout()
        self.meter_equipment=QComboBox();self.meter_equipment.currentTextChanged.connect(self.refresh_meter_choices)
        self.meter_code=QComboBox();self.meter_code.currentTextChanged.connect(self.refresh_meter_trend)
        meterb=QPushButton("Refresh meter");meterb.clicked.connect(self.refresh_meter_trend)
        mh.addWidget(QLabel("Equipment"));mh.addWidget(self.meter_equipment);mh.addWidget(QLabel("Meter"));mh.addWidget(self.meter_code);mh.addWidget(meterb);mh.addStretch(1);mv.addLayout(mh)
        self.meter_chart=LineChart("Meter / condition trend");mv.addWidget(self.meter_chart,2)
        self.meter_table=_table(["Time","Value","Type","Recorded By","Note"]);mv.addWidget(self.meter_table,1);tabs.addTab(meter,"Meter / Condition Trend")
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
        equipment_ids=[x["equipment_id"] for x in self.tool_rows]
        current=self.meter_equipment.currentText()
        self.meter_equipment.blockSignals(True);self.meter_equipment.clear();self.meter_equipment.addItems(equipment_ids)
        if current in equipment_ids:self.meter_equipment.setCurrentText(current)
        self.meter_equipment.blockSignals(False)
        if not self.compare_input.text().strip() and len(equipment_ids)>=2:self.compare_input.setText(", ".join(equipment_ids[:2]))
        self.refresh_trend();self.refresh_compare();self.refresh_meter_choices()

    def refresh_trend(self):
        rows=self.db.fleet_reliability_trend(self.days.value(),self.bucket_days.value())
        _fill(self.trend_table,rows,["start","end","availability_pct","unplanned_downtime_hours","planned_downtime_hours","failure_count","equipment_count"])
        metric=self.trend_metric.currentText()
        if metric=="Unplanned downtime h":key="unplanned_downtime_hours";title="Fleet unplanned downtime trend (hours)"
        elif metric=="Failure count":key="failure_count";title="Fleet failure-count trend"
        else:key="availability_pct";title="Fleet availability trend (%)"
        self.trend_chart.set_data([(row["end"].strftime("%Y-%m-%d"),row[key]) for row in rows],title)

    def refresh_compare(self):
        ids=[x.strip() for x in self.compare_input.text().split(",") if x.strip()]
        self.compare_rows=self.db.compare_equipment(ids,self.days.value()) if ids else []
        _fill(self.compare_table,self.compare_rows,["equipment_id","name","equipment_type","area","current_state","availability_pct","failure_count","unplanned_downtime_hours","mttr_hours","mtbf_hours","incidents","active_alarms","overdue_pm"])

    def open_compare_selected(self):
        row=self.compare_table.currentRow()
        rows=getattr(self,"compare_rows",[])
        if 0<=row<len(rows):self.open_equipment(rows[row]["equipment_id"])

    def refresh_meter_choices(self):
        equipment_id=self.meter_equipment.currentText().strip()
        current=self.meter_code.currentText()
        meters=self.db.list_meters(equipment_id) if equipment_id else []
        codes=[x.meter_code for x in meters if x.active]
        self.meter_code.blockSignals(True);self.meter_code.clear();self.meter_code.addItems(codes)
        if current in codes:self.meter_code.setCurrentText(current)
        self.meter_code.blockSignals(False)
        self.refresh_meter_trend()

    def refresh_meter_trend(self):
        equipment_id=self.meter_equipment.currentText().strip();meter_code=self.meter_code.currentText().strip()
        rows=self.db.meter_trend(equipment_id,meter_code,self.days.value()) if equipment_id and meter_code else []
        _fill(self.meter_table,rows,["recorded_at","value","reading_type","recorded_by","note"])
        self.meter_chart.set_data([(x["recorded_at"].strftime("%Y-%m-%d %H:%M"),x["value"]) for x in rows],f"{equipment_id} · {meter_code}")

    def export_weekly_pptx(self):
        path,_=QFileDialog.getSaveFileName(self,"Export Weekly Engineering Review","Equipment_Engineering_Weekly_Review.pptx","PowerPoint (*.pptx)")
        if not path:return
        if not path.lower().endswith(".pptx"):path+=".pptx"
        template=self.db.resolve_report_template("WEEKLY_ENGINEERING")
        try:
            export_weekly_review_pptx(self.db,path,self.days.value(),template)
            QMessageBox.information(self,"Weekly Review",f"Editable PowerPoint review pack created.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"Weekly Review",str(exc))

    def export_weekly_pdf(self):
        path,_=QFileDialog.getSaveFileName(self,"Export Weekly Engineering Review","Equipment_Engineering_Weekly_Review.pdf","PDF (*.pdf)")
        if not path:return
        if not path.lower().endswith(".pdf"):path+=".pdf"
        try:
            export_weekly_review_pdf(self.db,path,self.days.value())
            QMessageBox.information(self,"Weekly Review",f"Controlled weekly review PDF created.\n{path}")
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
