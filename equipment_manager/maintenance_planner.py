from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCalendarWidget, QDateTimeEdit, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QSplitter, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget, QInputDialog,
)

from table_productivity import install_table_productivity


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
        assign=QPushButton("Assign selected");assign.clicked.connect(self.assign_selected)
        schedule=QPushButton("Reschedule selected");schedule.clicked.connect(self.reschedule_selected)
        openpm=QPushButton("Open selected PM");openpm.clicked.connect(self.open_selected)
        for w in [self.search,QLabel("Horizon"),self.horizon,QLabel("Target"),self.plan_dt,assign,schedule,openpm]:controls.addWidget(w)
        controls.addStretch(1);root.addLayout(controls)

        tabs=QTabWidget();root.addWidget(tabs,1)

        board=QWidget();bv=QVBoxLayout(board)
        self.board=_table(["Task","Equipment","PM","Name","Original Due","Planned","Window","Status","Assigned","Hours","Priority","Ver"])
        self.board.doubleClicked.connect(self.open_selected);bv.addWidget(self.board);tabs.addTab(board,"Schedule board")

        calendar=QWidget();cv=QHBoxLayout(calendar);split=QSplitter()
        self.calendar=QCalendarWidget();self.calendar.selectionChanged.connect(self.calendar_changed);split.addWidget(self.calendar)
        right=QWidget();rv=QVBoxLayout(right);self.day_label=QLabel();self.day_label.setStyleSheet("font-weight:700;font-size:12pt")
        self.day_table=_table(["Task","Equipment","PM","Name","Status","Assigned","Hours","Window"])
        self.day_table.doubleClicked.connect(self.open_day_selected);rv.addWidget(self.day_label);rv.addWidget(self.day_table)
        split.addWidget(right);split.setStretchFactor(1,2);cv.addWidget(split);tabs.addTab(calendar,"Calendar / day plan")

        workload=QWidget();wv=QVBoxLayout(workload)
        self.workload_table=_table(["Date","Tasks","Hours","Capacity h","Load %","Overdue tasks"])
        self.team_table=_table(["Assigned to","Tasks","Planned hours","Overdue","Unassigned"])
        wv.addWidget(QLabel("Daily workload"));wv.addWidget(self.workload_table,1);wv.addWidget(QLabel("Technician / owner load"));wv.addWidget(self.team_table,1);tabs.addTab(workload,"Workload / capacity")

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
        fields=["id","equipment_id","pm_id","pm_name","original_due_date","scheduled_date","window","status","assigned_to","estimated_hours","priority","version"]
        for r,row in enumerate(self.filtered):
            for col,field in enumerate(fields):self.board.setItem(r,col,_item(row.get(field)))
        open_count=len(self.filtered);overdue=sum(1 for x in self.filtered if x["window"]=="OVERDUE");hours=sum(float(x.get("estimated_hours") or 0) for x in self.filtered)
        self.summary.setText(f"{open_count} open tasks · {hours:.1f} planned h · {overdue} overdue")
        self.rebuild_views()

    def rebuild_views(self):
        by_day=defaultdict(list);by_owner=defaultdict(list)
        for row in self.filtered:
            date=row.get("scheduled_date") or row.get("original_due_date")
            if date:by_day[date.date()].append(row)
            by_owner[(row.get("assigned_to") or "UNASSIGNED").strip() or "UNASSIGNED"].append(row)
        dates=sorted(by_day)
        self.workload_table.setRowCount(len(dates))
        cap=float(self.capacity.value())
        for i,day in enumerate(dates):
            tasks=by_day[day];hours=sum(float(x.get("estimated_hours") or 0) for x in tasks);overdue=sum(1 for x in tasks if x["window"]=="OVERDUE")
            vals=[day.isoformat(),len(tasks),f"{hours:.1f}",f"{cap:.1f}",f"{(hours/cap*100 if cap else 0):.0f}%",overdue]
            for col,val in enumerate(vals):self.workload_table.setItem(i,col,_item(val))
        owners=sorted(by_owner)
        self.team_table.setRowCount(len(owners))
        for i,owner in enumerate(owners):
            tasks=by_owner[owner];hours=sum(float(x.get("estimated_hours") or 0) for x in tasks);overdue=sum(1 for x in tasks if x["window"]=="OVERDUE")
            vals=[owner,len(tasks),f"{hours:.1f}",overdue,len(tasks) if owner=="UNASSIGNED" else 0]
            for col,val in enumerate(vals):self.team_table.setItem(i,col,_item(val))
        self.calendar_changed()

    def calendar_changed(self):
        qd=self.calendar.selectedDate();day=qd.toPython()
        self.plan_dt.setDate(qd)
        rows=[r for r in self.filtered if (r.get("scheduled_date") or r.get("original_due_date")) and (r.get("scheduled_date") or r.get("original_due_date")).date()==day]
        self._day_rows=rows;self.day_label.setText(f"{day.isoformat()} · {len(rows)} task(s) · {sum(float(x.get('estimated_hours') or 0) for x in rows):.1f} h")
        self.day_table.setRowCount(len(rows));fields=["id","equipment_id","pm_id","pm_name","status","assigned_to","estimated_hours","window"]
        for r,row in enumerate(rows):
            for col,field in enumerate(fields):self.day_table.setItem(r,col,_item(row.get(field)))

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
            try:self.db.plan_pm_task(row["id"],self.user["username"],assigned_to=owner,expected_version=row["version"]);done+=1
            except Exception as exc:failures.append(f"{row['id']}: {exc}")
        self.refresh();self._result("Assignment",done,len(rows),failures)

    def reschedule_selected(self):
        rows=self._selected_board_rows()
        if not rows:QMessageBox.information(self,"Reschedule PM","Select one or more PM tasks.");return
        when=self.plan_dt.dateTime().toPython()
        if QMessageBox.question(self,"Reschedule PM",f"Schedule {len(rows)} PM task(s) for {when:%Y-%m-%d %H:%M}?\nControlled early/grace/deferral rules will be enforced.")!=QMessageBox.StandardButton.Yes:return
        failures=[];done=0
        for row in rows:
            try:self.db.plan_pm_task(row["id"],self.user["username"],scheduled_date=when,expected_version=row["version"]);done+=1
            except Exception as exc:failures.append(f"{row['equipment_id']} / {row['pm_id']}: {exc}")
        self.refresh();self._result("Reschedule",done,len(rows),failures)

    def _result(self,title,done,total,failures):
        text=f"Updated {done}/{total} task(s)."
        if failures:text+="\n\n"+"\n".join(failures[:15])
        QMessageBox.information(self,title,text)

    def open_selected(self):
        rows=self._selected_board_rows()
        if rows:
            row=rows[0];self.open_entity.emit("PM_EXECUTION",str(row["id"]),row["equipment_id"])

    def open_day_selected(self):
        i=self.day_table.currentRow()
        rows=getattr(self,"_day_rows",[])
        if 0<=i<len(rows):
            row=rows[i];self.open_entity.emit("PM_TASK",str(row["id"]),row["equipment_id"])

    def select_task(self,task_id: int):
        self.refresh()
        for i,row in enumerate(self.filtered):
            if row["id"]==task_id:
                self.board.selectRow(i)
                item=self.board.item(i,0)
                if item:self.board.scrollToItem(item)
                break
