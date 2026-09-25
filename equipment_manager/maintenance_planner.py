from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from PySide6.QtCore import QDate, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QCalendarWidget, QDateTimeEdit, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QSplitter, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget, QInputDialog,
)

from table_productivity import install_table_productivity
from feedback import notify


def _item(value):
    if isinstance(value,datetime):value=value.strftime("%Y-%m-%d %H:%M")
    return QTableWidgetItem("" if value is None else str(value))


def _table(headers):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    t.setAlternatingRowColors(True);t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    install_table_productivity(t,headers[0] if headers else "PM Planning")
    return t


class PlanningTimeline(QWidget):
    rescheduleRequested=Signal(int,object)

    def __init__(self,parent=None):
        super().__init__(parent);self.rows=[];self.start=None;self.end=None;self.drag_row=-1
        self.setMinimumHeight(330);self.setMouseTracking(True)

    def set_rows(self,rows,start,end):
        self.rows=list(rows)[:36];self.start=start;self.end=end;self.update()

    def _geometry(self):
        left=210;top=46;right=24;bottom=24
        width=max(80,self.width()-left-right);height=max(80,self.height()-top-bottom)
        row_h=height/max(1,len(self.rows))
        return left,top,width,height,row_h

    def _x_for(self,when):
        left,top,width,height,row_h=self._geometry()
        if not self.start or not self.end or not when:return left
        span=max(1.0,(self.end-self.start).total_seconds())
        frac=max(0.0,min(1.0,(when-self.start).total_seconds()/span))
        return left+width*frac

    def _when_for_x(self,x,row):
        left,top,width,height,row_h=self._geometry()
        frac=max(0.0,min(1.0,(x-left)/max(1,width)))
        when=self.start+(self.end-self.start)*frac
        planned=row.get("scheduled_date") or row.get("original_due_date")
        if planned:return when.replace(hour=planned.hour,minute=planned.minute,second=0,microsecond=0)
        return when.replace(hour=8,minute=0,second=0,microsecond=0)

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.fillRect(self.rect(),QColor("#ffffff"))
        left,top,width,height,row_h=self._geometry()
        font=QFont();font.setBold(True);p.setFont(font);p.setPen(QColor("#1b2733"))
        p.drawText(QRectF(10,8,self.width()-20,28),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,"PM Planning Timeline — drag planned markers to reschedule")
        if not self.rows or not self.start or not self.end:
            p.setPen(QColor("#647581"));p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,"No PM tasks in this planning horizon");return
        total_days=max(1,(self.end.date()-self.start.date()).days)
        step=1 if total_days<=14 else 7 if total_days<=90 else 14
        d=self.start.replace(hour=0,minute=0,second=0,microsecond=0)
        while d<=self.end:
            day=(d.date()-self.start.date()).days
            if day>=0 and day%step==0:
                x=self._x_for(d);p.setPen(QPen(QColor("#e4e9ed"),1));p.drawLine(int(x),top,int(x),top+height)
                p.setPen(QColor("#647581"));p.drawText(QRectF(x-35,top-20,70,18),Qt.AlignmentFlag.AlignCenter,d.strftime("%m-%d"))
            d+=timedelta(days=1)
        for i,row in enumerate(self.rows):
            y=top+i*row_h
            p.setPen(QColor("#334e5c"))
            label=f"{row.get('equipment_id','')} · {row.get('pm_id','')}"
            p.drawText(QRectF(8,y,195,row_h),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,label[:30])
            p.setPen(QPen(QColor("#edf1f4"),1));p.drawLine(left,int(y+row_h),left+width,int(y+row_h))
            early=row.get("early_date") or row.get("original_due_date");latest=row.get("latest_date") or row.get("original_due_date")
            planned=row.get("scheduled_date") or row.get("original_due_date")
            if early and latest:
                x1=self._x_for(early);x2=self._x_for(latest)
                p.fillRect(QRectF(min(x1,x2),y+row_h*.32,max(3,abs(x2-x1)),row_h*.36),QColor("#d8e8f1"))
            if planned:
                x=self._x_for(planned)
                blocked=row.get("parts_status")=="SHORT" or row.get("certification_status") in {"MISSING","UNASSIGNED"}
                color=QColor("#b75a4a") if row.get("window")=="OVERDUE" else QColor("#d08b2e") if blocked else QColor("#2577a3")
                p.setBrush(color);p.setPen(QPen(color,1));p.drawEllipse(QRectF(x-5,y+row_h*.5-5,10,10))

    def mousePressEvent(self,event):
        if not self.rows:return
        left,top,width,height,row_h=self._geometry()
        idx=int((event.position().y()-top)/max(1,row_h))
        if 0<=idx<len(self.rows) and event.position().x()>=left:self.drag_row=idx
        else:self.drag_row=-1

    def mouseReleaseEvent(self,event):
        if self.drag_row<0 or self.drag_row>=len(self.rows):return
        row=self.rows[self.drag_row];when=self._when_for_x(event.position().x(),row);self.drag_row=-1
        self.rescheduleRequested.emit(int(row["id"]),when)


class WeekScheduleView(QWidget):
    moveRequested=Signal(str,str,object)
    resizeRequested=Signal(str,str,object)
    entityActivated=Signal(str,str,str)

    def __init__(self,parent=None):
        super().__init__(parent);self.rows=[];self.week_start=None;self.drag_row=None;self.drag_mode="move";self.rects=[]
        self.setMinimumHeight(520);self.setMouseTracking(True)

    def set_week(self,rows,anchor_date):
        if hasattr(anchor_date,"toPython"):anchor_date=anchor_date.toPython()
        start=anchor_date-timedelta(days=anchor_date.weekday())
        self.week_start=datetime.combine(start,datetime.min.time())
        end=self.week_start+timedelta(days=7)
        self.rows=[x for x in rows if x.get("start_at") and self.week_start<=x["start_at"]<end]
        self.update()

    def _geometry(self):
        left=72;top=44;right=12;bottom=18
        width=max(210,self.width()-left-right);height=max(360,self.height()-top-bottom)
        return left,top,width,height,width/7.0,height/24.0

    def _rect_for(self,row):
        left,top,width,height,day_w,hour_h=self._geometry()
        start=row.get("start_at")
        if not start or not self.week_start:return QRectF()
        end=row.get("end_at") or (start+timedelta(hours=1))
        day=max(0,min(6,(start.date()-self.week_start.date()).days))
        start_h=start.hour+start.minute/60.0
        end_h=(end.hour+end.minute/60.0) if end.date()==start.date() else 24.0
        duration=max(.35,end_h-start_h)
        x=left+day*day_w+3;y=top+start_h*hour_h+1
        return QRectF(x,y,max(18,day_w-6),max(18,duration*hour_h-2))

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.fillRect(self.rect(),QColor("#ffffff"))
        left,top,width,height,day_w,hour_h=self._geometry()
        if not self.week_start:
            p.setPen(QColor("#647581"));p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,"No week selected");return
        days=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        for d in range(7):
            x=left+d*day_w;date=self.week_start.date()+timedelta(days=d)
            p.setPen(QColor("#1b2733"));p.setFont(QFont("Segoe UI",8,QFont.Weight.Bold))
            p.drawText(QRectF(x,4,day_w,34),Qt.AlignmentFlag.AlignCenter,f"{days[d]}\n{date:%m-%d}")
            p.setPen(QPen(QColor("#dfe6ea"),1));p.drawLine(int(x),top,int(x),top+height)
        p.drawLine(int(left+width),top,int(left+width),top+height)
        for hour in range(25):
            y=top+hour*hour_h;p.setPen(QPen(QColor("#eef2f4"),1));p.drawLine(left,int(y),left+width,int(y))
            if hour<24:
                p.setPen(QColor("#647581"));p.setFont(QFont("Segoe UI",7))
                p.drawText(QRectF(5,y-8,left-10,16),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,f"{hour:02d}:00")
        self.rects=[]
        for row in self.rows:
            rect=self._rect_for(row);self.rects.append((rect,row))
            if row.get("kind")=="PM":
                color=QColor("#b75045") if row.get("window")=="OVERDUE" else QColor("#2577a3")
            else:
                priority=str(row.get("priority") or "").upper()
                color=QColor("#c46f2d") if priority in {"P1","CRITICAL","HIGH"} else QColor("#397f68")
            if row.get("status")=="In Progress":color=QColor("#386cb0")
            p.setBrush(QColor(color.red(),color.green(),color.blue(),215));p.setPen(QPen(color.darker(125),1.2));p.drawRoundedRect(rect,4,4)
            p.setPen(QColor("#ffffff"));p.setFont(QFont("Segoe UI",7,QFont.Weight.Bold))
            label=f"{row.get('equipment_id','')} · {row.get('kind','')} · {row.get('title','')}"
            p.drawText(rect.adjusted(5,2,-4,-2),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop,label[:42])
            p.setFont(QFont("Segoe UI",6));owner=row.get("owner") or "UNASSIGNED"
            p.drawText(rect.adjusted(5,18,-4,-2),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop,owner[:22])

    def _hit(self,pos):
        for rect,row in reversed(self.rects):
            if rect.contains(pos):return row
        return None

    def _hit_detail(self,pos):
        for rect,row in reversed(self.rects):
            if rect.contains(pos):
                resize_zone=pos.y()>=rect.bottom()-8
                return row,("resize" if resize_zone else "move")
        return None,"move"

    def mousePressEvent(self,event):
        self.drag_row,self.drag_mode=self._hit_detail(event.position())

    def mouseDoubleClickEvent(self,event):
        row=self._hit(event.position())
        if row:self.entityActivated.emit(row["entity_type"],str(row["entity_key"]),row["equipment_id"])

    def mouseReleaseEvent(self,event):
        row=self.drag_row;mode=self.drag_mode;self.drag_row=None;self.drag_mode="move"
        if not row or not self.week_start:return
        left,top,width,height,day_w,hour_h=self._geometry()
        x=max(left,min(left+width-1,event.position().x()));y=max(top,min(top+height-1,event.position().y()))
        raw_minutes=((y-top)/hour_h)*60.0;rounded=int(round(raw_minutes/15.0)*15);rounded=max(0,min(24*60,rounded))
        if mode=="resize":
            start=row["start_at"];target=datetime.combine(start.date(),datetime.min.time())+timedelta(minutes=rounded)
            if target<=start:target=start+timedelta(minutes=15)
            self.resizeRequested.emit(row["entity_type"],str(row["entity_key"]),target)
            return
        day=max(0,min(6,int((x-left)/day_w)));rounded=min(23*60+45,rounded)
        target=self.week_start+timedelta(days=day,hours=rounded//60,minutes=rounded%60)
        self.moveRequested.emit(row["entity_type"],str(row["entity_key"]),target)


class MaintenancePlanningWorkspace(QWidget):
    open_entity=Signal(str,str,str)

    def __init__(self,db,user,parent=None):
        super().__init__(parent);self.db=db;self.user=user;self.rows=[];self.filtered=[]
        root=QVBoxLayout(self)
        title_row=QHBoxLayout()
        title=QLabel("Maintenance Planning");title.setStyleSheet("font-size:20pt;font-weight:800")
        self.summary=QLabel();self.summary.setStyleSheet("color:#647581;")
        title_row.addWidget(title);title_row.addWidget(self.summary);title_row.addStretch(1)
        refresh=QPushButton("Refresh");refresh.clicked.connect(self.refresh);title_row.addWidget(refresh);root.addLayout(title_row)

        controls=QHBoxLayout()
        self.search=QLineEdit();self.search.setPlaceholderText("Filter equipment / PM / technician / status…");self.search.textChanged.connect(self.apply_filter)
        self.horizon=QSpinBox();self.horizon.setRange(7,365);self.horizon.setValue(60);self.horizon.setSuffix(" days");self.horizon.valueChanged.connect(self.refresh)
        self.capacity=QSpinBox();self.capacity.setRange(1,200);self.capacity.setValue(32);self.capacity.setSuffix(" team h/day");self.capacity.valueChanged.connect(self.rebuild_views)
        self.plan_dt=QDateTimeEdit();self.plan_dt.setCalendarPopup(True);self.plan_dt.setDateTime(datetime.now());self.plan_dt.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.plan_end_dt=QDateTimeEdit();self.plan_end_dt.setCalendarPopup(True);self.plan_end_dt.setDateTime(datetime.now()+timedelta(hours=1));self.plan_end_dt.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.reason=QLineEdit();self.reason.setPlaceholderText("Scheduling reason (required outside PM window)");self.reason.setMinimumWidth(260)
        assign=QPushButton("Assign selected");assign.clicked.connect(self.assign_selected)
        schedule=QPushButton("Move / Reschedule");schedule.clicked.connect(self.reschedule_selected)
        openpm=QPushButton("Open selected PM");openpm.clicked.connect(self.open_selected)
        for w in [self.search,QLabel("Horizon"),self.horizon,QLabel("Start"),self.plan_dt,QLabel("End"),self.plan_end_dt,self.reason,assign,schedule,openpm]:controls.addWidget(w)
        controls.addStretch(1);root.addLayout(controls)

        tabs=QTabWidget();root.addWidget(tabs,1)

        board=QWidget();bv=QVBoxLayout(board)
        self.board=_table(["Task","Equipment","PM","Name","Controlled Due","Slot Start","Slot End","Slot h","Window","Parts","Certs","Status","Assigned","Std h","Priority","Ver"])
        self.board.doubleClicked.connect(self.open_selected);self.board.itemSelectionChanged.connect(self.load_selected_slot);bv.addWidget(self.board);tabs.addTab(board,"Schedule board")

        calendar=QWidget();cv=QHBoxLayout(calendar);split=QSplitter()
        self.calendar=QCalendarWidget();self.calendar.selectionChanged.connect(self.calendar_changed);split.addWidget(self.calendar)
        right=QWidget();rv=QVBoxLayout(right);self.day_label=QLabel();self.day_label.setStyleSheet("font-weight:700;font-size:12pt")
        self.day_table=_table(["Type","ID","Equipment","Activity","Start","End","Hours","Status","Owner","Priority / Window"])
        self.day_table.doubleClicked.connect(self.open_day_selected);rv.addWidget(self.day_label);rv.addWidget(self.day_table)
        split.addWidget(right);split.setStretchFactor(1,2);cv.addWidget(split);tabs.addTab(calendar,"Month / Day")

        week=QWidget();weekv=QVBoxLayout(week);weekbar=QHBoxLayout()
        prev_week=QPushButton("‹ Previous week");prev_week.clicked.connect(lambda:self.shift_week(-7))
        today=QPushButton("Today");today.clicked.connect(self.go_today)
        next_week=QPushButton("Next week ›");next_week.clicked.connect(lambda:self.shift_week(7))
        self.week_label=QLabel();self.week_label.setStyleSheet("font-weight:700;font-size:12pt")
        weekbar.addWidget(prev_week);weekbar.addWidget(today);weekbar.addWidget(next_week);weekbar.addStretch(1);weekbar.addWidget(self.week_label);weekv.addLayout(weekbar)
        self.week_view=WeekScheduleView();self.week_view.moveRequested.connect(self.week_reschedule);self.week_view.resizeRequested.connect(self.week_resize);self.week_view.entityActivated.connect(self.open_calendar_entity);weekv.addWidget(self.week_view,3)
        backlog_bar=QHBoxLayout();self.unscheduled_label=QLabel("Unscheduled engineering work")
        schedule_wo=QPushButton("Schedule selected work order");schedule_wo.clicked.connect(self.schedule_unscheduled_work)
        open_wo=QPushButton("Open selected work order");open_wo.clicked.connect(self.open_unscheduled_work)
        backlog_bar.addWidget(self.unscheduled_label);backlog_bar.addStretch(1);backlog_bar.addWidget(schedule_wo);backlog_bar.addWidget(open_wo);weekv.addLayout(backlog_bar)
        self.unscheduled_table=_table(["WO","Equipment","Activity","Priority","Status","Owner"]);self.unscheduled_table.setMaximumHeight(180);self.unscheduled_table.doubleClicked.connect(self.open_unscheduled_work);weekv.addWidget(self.unscheduled_table,1)
        tabs.addTab(week,"Week Calendar")

        timeline=QWidget();tv=QVBoxLayout(timeline);self.timeline=PlanningTimeline();self.timeline.rescheduleRequested.connect(self.timeline_reschedule);tv.addWidget(self.timeline);tabs.addTab(timeline,"Timeline / Gantt")

        workload=QWidget();wv=QVBoxLayout(workload)
        self.workload_table=_table(["Date","Tasks","Hours","Capacity h","Load %","Overdue tasks"])
        self.team_table=_table(["Assigned to","Tasks","Planned hours","Overdue","Unassigned"])
        wv.addWidget(QLabel("Daily workload"));wv.addWidget(self.workload_table,1);wv.addWidget(QLabel("Technician / owner load"));wv.addWidget(self.team_table,1);tabs.addTab(workload,"Workload / capacity")

        history=QWidget();hv=QVBoxLayout(history);self.history_label=QLabel("Select a PM task to view scheduling history.")
        self.history_table=_table(["Changed","Old Start","Old End","New Start","New End","Old Assignee","New Assignee","Outside Window","Reason","Changed By"])
        hv.addWidget(self.history_label);hv.addWidget(self.history_table);tabs.addTab(history,"Schedule history")

        self.refresh()

    def refresh(self):
        try:self.rows=self.db.pm_planning_rows(self.horizon.value(),True)
        except Exception as exc:QMessageBox.critical(self,"Maintenance planning",str(exc));return
        self.apply_filter()

    def apply_filter(self):
        q=self.search.text().strip().lower()
        if q:
            self.filtered=[r for r in self.rows if q in " ".join(str(r.get(k,"") or "") for k in ["equipment_id","pm_id","pm_name","status","assigned_to","priority","window"]).lower()]
        else:self.filtered=list(self.rows)
        self.board.setRowCount(len(self.filtered))
        fields=["id","equipment_id","pm_id","pm_name","original_due_date","scheduled_start_at","scheduled_end_at","planned_hours","window","parts_status","certification_status","status","assigned_to","estimated_hours","priority","version"]
        for r,row in enumerate(self.filtered):
            for col,field in enumerate(fields):self.board.setItem(r,col,_item(row.get(field)))
        open_count=len(self.filtered);overdue=sum(1 for x in self.filtered if x["window"]=="OVERDUE");hours=sum(float(x.get("planned_hours") or x.get("estimated_hours") or 0) for x in self.filtered)
        parts_short=sum(1 for x in self.filtered if x.get("parts_status")=="SHORT")
        cert_block=sum(1 for x in self.filtered if x.get("certification_status") in {"MISSING","UNASSIGNED"})
        self.summary.setText(f"{open_count} open tasks · {hours:.1f} planned h · {overdue} overdue · {parts_short} parts-blocked · {cert_block} cert-blocked")
        self.rebuild_views()

    def rebuild_views(self):
        by_day=defaultdict(list);by_owner=defaultdict(list)
        for row in self.filtered:
            date=row.get("scheduled_start_at") or row.get("scheduled_date") or row.get("original_due_date")
            if date:by_day[date.date()].append(row)
            by_owner[(row.get("assigned_to") or "UNASSIGNED").strip() or "UNASSIGNED"].append(row)
        dates=sorted(by_day)
        self.workload_table.setRowCount(len(dates))
        cap=float(self.capacity.value())
        for i,day in enumerate(dates):
            tasks=by_day[day];hours=sum(float(x.get("planned_hours") or x.get("estimated_hours") or 0) for x in tasks);overdue=sum(1 for x in tasks if x["window"]=="OVERDUE")
            vals=[day.isoformat(),len(tasks),f"{hours:.1f}",f"{cap:.1f}",f"{(hours/cap*100 if cap else 0):.0f}%",overdue]
            for col,val in enumerate(vals):self.workload_table.setItem(i,col,_item(val))
        owners=sorted(by_owner)
        self.team_table.setRowCount(len(owners))
        for i,owner in enumerate(owners):
            tasks=by_owner[owner];hours=sum(float(x.get("planned_hours") or x.get("estimated_hours") or 0) for x in tasks);overdue=sum(1 for x in tasks if x["window"]=="OVERDUE")
            vals=[owner,len(tasks),f"{hours:.1f}",overdue,len(tasks) if owner=="UNASSIGNED" else 0]
            for col,val in enumerate(vals):self.team_table.setItem(i,col,_item(val))
        start=datetime.now();end=start+timedelta(days=self.horizon.value())
        self.timeline.set_rows(self.filtered,start,end)
        self.calendar_changed()
        self.rebuild_week()

    def go_today(self):
        self.calendar.setSelectedDate(QDate.currentDate());self.rebuild_week()

    def shift_week(self,days: int):
        self.calendar.setSelectedDate(self.calendar.selectedDate().addDays(days));self.rebuild_week()

    def _calendar_search_match(self,row):
        q=self.search.text().strip().lower()
        if not q:return True
        return q in " ".join(str(row.get(k,"") or "") for k in [
            "entity_type","entity_key","kind","equipment_id","title","owner","status","priority","window"
        ]).lower()

    def rebuild_week(self):
        day=self.calendar.selectedDate().toPython();monday=day-timedelta(days=day.weekday());sunday=monday+timedelta(days=6)
        start=datetime.combine(monday,datetime.min.time());end=start+timedelta(days=7)
        try:rows=self.db.operational_calendar_rows(start,end)
        except Exception as exc:
            self.week_label.setText(f"Calendar unavailable: {exc}");self._week_rows=[];self.week_view.set_week([],day);return
        self._week_rows=[x for x in rows if self._calendar_search_match(x)]
        self.week_label.setText(f"{monday:%Y-%m-%d} — {sunday:%Y-%m-%d} · {len(self._week_rows)} scheduled activity(s)")
        self.week_view.set_week(self._week_rows,day)
        work_orders=[x for x in self.db.list_work_orders(open_only=True) if x.planned_start is None]
        q=self.search.text().strip().lower()
        if q:
            work_orders=[x for x in work_orders if q in " ".join([
                x.work_order_no,x.equipment_id,x.title,x.priority,x.status,x.owner,x.team
            ]).lower()]
        self._unscheduled_work=work_orders
        self.unscheduled_label.setText(f"Unscheduled engineering work · {len(work_orders)}")
        self.unscheduled_table.setRowCount(len(work_orders))
        for r,row in enumerate(work_orders):
            for col,value in enumerate([row.work_order_no,row.equipment_id,row.title,row.priority,row.status,row.owner]):
                self.unscheduled_table.setItem(r,col,_item(value))

    def _selected_unscheduled_work(self):
        row=self.unscheduled_table.currentRow();items=getattr(self,"_unscheduled_work",[])
        return items[row] if 0<=row<len(items) else None

    def schedule_unscheduled_work(self):
        wo=self._selected_unscheduled_work()
        if not wo:
            QMessageBox.information(self,"Operational Calendar","Select an unscheduled work order.");return
        start=self.plan_dt.dateTime().toPython();end=self.plan_end_dt.dateTime().toPython()
        if end<=start:
            end=start+timedelta(hours=1)
        try:
            self.db.schedule_work_order(
                wo.work_order_no,self.user["username"],start_at=start,end_at=end,
                reason=self.reason.text().strip() or "Scheduled from operational calendar",
                expected_version=wo.version,workstation="OPERATIONAL-CALENDAR",
            )
            notify(f"{wo.work_order_no} scheduled for {start:%Y-%m-%d %H:%M}.")
            self.refresh();self.calendar.setSelectedDate(QDate(start.year,start.month,start.day))
        except Exception as exc:QMessageBox.critical(self,"Operational Calendar",str(exc))

    def open_unscheduled_work(self):
        wo=self._selected_unscheduled_work()
        if wo:self.open_entity.emit("WORK_ORDER",wo.work_order_no,wo.equipment_id)

    def week_resize(self,entity_type: str,entity_key: str,new_end):
        row=next((x for x in getattr(self,"_week_rows",[]) if x["entity_type"]==entity_type and str(x["entity_key"])==str(entity_key)),None)
        if not row:return
        start=row["start_at"]
        if new_end<=start:return
        try:
            if entity_type=="PM_TASK":
                pm_row=next((x for x in self.rows if str(x["id"])==str(entity_key)),None)
                self.db.schedule_pm_task(
                    int(entity_key),self.user["username"],start_at=start,end_at=new_end,
                    reason=self.reason.text().strip() or "Calendar duration change",
                    expected_task_version=pm_row.get("version") if pm_row else None,
                    workstation="OPERATIONAL-CALENDAR",
                )
            elif entity_type=="WORK_ORDER":
                self.db.schedule_work_order(
                    entity_key,self.user["username"],start_at=start,end_at=new_end,
                    reason=self.reason.text().strip() or "Calendar duration change",
                    expected_version=row.get("version"),workstation="OPERATIONAL-CALENDAR",
                )
            self.refresh()
        except Exception as exc:QMessageBox.critical(self,"Calendar duration",str(exc))

    def week_reschedule(self,entity_type: str,entity_key: str,when):
        row=next((x for x in getattr(self,"_week_rows",[]) if x["entity_type"]==entity_type and str(x["entity_key"])==str(entity_key)),None)
        if not row:return
        duration=max(.5,((row.get("end_at") or (row["start_at"]+timedelta(hours=1)))-row["start_at"]).total_seconds()/3600)
        end=when+timedelta(hours=duration)
        try:
            if entity_type=="PM_TASK":
                pm_row=next((x for x in self.rows if str(x["id"])==str(entity_key)),None)
                reason=self.reason.text().strip()
                if pm_row:
                    early=pm_row.get("early_date");latest=pm_row.get("latest_date")
                    outside=bool((early and when<early) or (latest and when>latest))
                    if outside and not reason:
                        reason,ok=QInputDialog.getText(self,"Move outside PM window","Reason for scheduling outside the recommended PM window:")
                        if not ok or not reason.strip():return
                    expected=pm_row.get("version")
                else:expected=None
                self.db.schedule_pm_task(
                    int(entity_key),self.user["username"],start_at=when,end_at=end,
                    reason=reason,expected_task_version=expected,workstation="OPERATIONAL-CALENDAR",
                )
            elif entity_type=="WORK_ORDER":
                self.db.schedule_work_order(
                    entity_key,self.user["username"],start_at=when,end_at=end,
                    reason=self.reason.text().strip() or "Calendar drag",
                    expected_version=row.get("version"),workstation="OPERATIONAL-CALENDAR",
                )
            self.refresh();self.calendar.setSelectedDate(QDate(when.year,when.month,when.day))
        except Exception as exc:QMessageBox.critical(self,"Calendar move",str(exc))

    def open_calendar_entity(self,entity_type: str,entity_key: str,equipment_id: str):
        self.open_entity.emit(entity_type,entity_key,equipment_id)

    def calendar_changed(self):
        qd=self.calendar.selectedDate();day=qd.toPython();self.plan_dt.setDate(qd)
        start=datetime.combine(day,datetime.min.time());end=start+timedelta(days=1)
        try:rows=[x for x in self.db.operational_calendar_rows(start,end) if self._calendar_search_match(x)]
        except Exception as exc:
            rows=[];self.day_label.setText(f"{day.isoformat()} · calendar unavailable: {exc}")
        else:
            hours=sum(max(.0,((x.get("end_at") or x["start_at"])-x["start_at"]).total_seconds()/3600) for x in rows)
            self.day_label.setText(f"{day.isoformat()} · {len(rows)} scheduled activity(s) · {hours:.1f} h")
        self._day_rows=rows;self.day_table.setRowCount(len(rows))
        fields=["kind","entity_key","equipment_id","title","start_at","end_at","hours","status","owner","priority_window"]
        for r,row in enumerate(rows):
            row=dict(row)
            row["hours"]=max(.0,((row.get("end_at") or row["start_at"])-row["start_at"]).total_seconds()/3600)
            row["priority_window"]=" · ".join(x for x in [str(row.get("priority") or ""),str(row.get("window") or "")] if x)
            for col,field in enumerate(fields):self.day_table.setItem(r,col,_item(row.get(field)))
        self.rebuild_week()

    def timeline_reschedule(self,task_id: int,when):
        row=next((x for x in self.filtered if x["id"]==task_id),None)
        if not row:return
        duration=float(row.get("planned_hours") or row.get("estimated_hours") or 1)
        end=when+timedelta(hours=max(duration,0.5))
        reason=""
        early=row.get("early_date");latest=row.get("latest_date")
        outside=bool((early and when<early) or (latest and when>latest))
        if outside:
            reason,ok=QInputDialog.getText(self,"Move outside PM window","Reason for scheduling outside the recommended PM window:")
            if not ok or not reason.strip():return
        try:
            self.db.schedule_pm_task(
                task_id,self.user["username"],start_at=when,end_at=end,reason=reason,
                expected_task_version=row["version"],workstation="MAINTENANCE-PLANNER",
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self,"Timeline reschedule",str(exc))

    def load_selected_slot(self):
        rows=self._selected_board_rows()
        if not rows:
            self.history_label.setText("Select a PM task to view scheduling history.")
            self.history_table.setRowCount(0);return
        row=rows[0]
        start=row.get("scheduled_start_at") or row.get("scheduled_date") or row.get("original_due_date")
        duration=float(row.get("planned_hours") or row.get("estimated_hours") or 1)
        end=row.get("scheduled_end_at") or (start+timedelta(hours=max(duration,0.5)) if start else None)
        if start:self.plan_dt.setDateTime(start)
        if end:self.plan_end_dt.setDateTime(end)
        events=self.db.list_pm_schedule_events(row["id"])
        self.history_label.setText(f"{row['equipment_id']} · {row['pm_id']} · controlled due {row.get('original_due_date') or '—'}")
        self.history_table.setRowCount(len(events))
        fields=["changed_at","old_start_at","old_end_at","new_start_at","new_end_at","old_assignee","new_assignee","outside_window","reason","changed_by"]
        for r,event in enumerate(events):
            for col,field in enumerate(fields):self.history_table.setItem(r,col,_item(getattr(event,field,"")))

    def _selected_board_rows(self):
        indexes=sorted({x.row() for x in self.board.selectedIndexes()})
        return [self.filtered[i] for i in indexes if 0<=i<len(self.filtered)]

    def assign_selected(self):
        rows=self._selected_board_rows()
        if not rows:QMessageBox.information(self,"Assign PM","Select one or more PM tasks.");return
        users=[u.username for u in self.db.list_users() if u.active]
        owner,ok=QInputDialog.getItem(self,"Assign PM",f"Assign {len(rows)} task(s) to",[""]+users,0,True)
        if not ok:return
        failures=[];done=0
        for row in rows:
            start=row.get("scheduled_start_at") or row.get("scheduled_date") or row.get("original_due_date") or datetime.now()
            duration=float(row.get("planned_hours") or row.get("estimated_hours") or 1)
            end=row.get("scheduled_end_at") or (start+timedelta(hours=max(duration,0.5)))
            try:
                self.db.schedule_pm_task(
                    row["id"],self.user["username"],start_at=start,end_at=end,assigned_to=owner,
                    reason="Assignment update",expected_task_version=row["version"],workstation="MAINTENANCE-PLANNER",
                );done+=1
            except Exception as exc:failures.append(f"{row['id']}: {exc}")
        self.refresh();self._result("Assignment",done,len(rows),failures)

    def reschedule_selected(self):
        rows=self._selected_board_rows()
        if not rows:QMessageBox.information(self,"Reschedule PM","Select one or more PM tasks.");return
        target_start=self.plan_dt.dateTime().toPython();target_end=self.plan_end_dt.dateTime().toPython()
        if target_end<=target_start:QMessageBox.warning(self,"Reschedule PM","End must be after start.");return
        reason=self.reason.text().strip()
        anchor=rows[0].get("scheduled_start_at") or rows[0].get("scheduled_date") or rows[0].get("original_due_date") or target_start
        delta=target_start-anchor
        failures=[];done=0
        for index,row in enumerate(rows):
            old_start=row.get("scheduled_start_at") or row.get("scheduled_date") or row.get("original_due_date") or target_start
            duration=float(row.get("planned_hours") or row.get("estimated_hours") or 1)
            if len(rows)==1:
                start=target_start;end=target_end
            else:
                start=old_start+delta;end=start+timedelta(hours=max(duration,0.5))
            try:
                self.db.schedule_pm_task(
                    row["id"],self.user["username"],start_at=start,end_at=end,reason=reason,
                    expected_task_version=row["version"],workstation="MAINTENANCE-PLANNER",
                );done+=1
            except Exception as exc:failures.append(f"{row['equipment_id']} / {row['pm_id']}: {exc}")
        self.refresh();self._result("Reschedule",done,len(rows),failures)

    def _result(self,title,done,total,failures):
        text=f"Updated {done}/{total} task(s)."
        if failures:
            text+="\n\n"+"\n".join(failures[:15]);QMessageBox.warning(self,title,text)
        else:notify(f"{title}: {text}")

    def open_selected(self):
        rows=self._selected_board_rows()
        if rows:
            row=rows[0];self.open_entity.emit("PM_EXECUTION",str(row["id"]),row["equipment_id"])

    def open_day_selected(self):
        i=self.day_table.currentRow();rows=getattr(self,"_day_rows",[])
        if 0<=i<len(rows):
            row=rows[i];self.open_entity.emit(row["entity_type"],str(row["entity_key"]),row["equipment_id"])

    def select_task(self,task_id: int):
        self.refresh()
        for i,row in enumerate(self.filtered):
            if row["id"]==task_id:
                self.board.selectRow(i)
                item=self.board.item(i,0)
                if item:self.board.scrollToItem(item)
                break
