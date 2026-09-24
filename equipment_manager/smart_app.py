from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Callable

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import Database
from logging_config import configure_logging, install_exception_hook
from incident_workspace import IncidentWorkspace
from maintenance_planner import MaintenancePlanningWorkspace
from pm_execution_workspace import PMExecutionWorkspace
from workflow_automation import WorkflowAutomationStudio
from configuration_studio import ConfigurationStudio
from work_order_workspace import WorkOrderWorkspace
from shift_handover_workspace import ShiftHandoverWorkspace
from analytics_workspace import EngineeringAnalyticsWorkspace
from inventory_logistics_workspace import InventoryLogisticsWorkspace
from version import __version__
from demo_data import active_tickets, seed_demo_data
from main import (
    APP_TITLE,
    WORKSTATION,
    AdminPage,
    AlarmPage,
    ControlPage,
    DocumentPage,
    EndorsementPage,
    EquipmentPage,
    FirstAdminDialog,
    InventoryPage,
    LoginDialog,
    PMPage,
    QualificationPage,
    ReliabilityPage,
    TicketPage,
    WorkLogPage,
)
from smart_map import SmartLayoutPage
from workspaces import EquipmentWorkspaceTabs, MyWorkWorkspace, SearchWorkspace
from table_productivity import configure_productivity_context

DEMO_MODE=os.getenv("EMS_DEMO_MODE","0").strip().lower() in {"1","true","yes","on"}

SMART_STYLE = """
QWidget { font-family: "Segoe UI"; font-size: 10.5pt; color: #1b2733; }
QMainWindow, QDialog { background: #eef2f5; }
QFrame#TopBar { background: #0c1721; border: 0; }
QLabel#AppTitle { color: white; font-size: 18pt; font-weight: 700; }
QLabel#AppSubTitle { color: #93a8b8; font-size: 9pt; }
QListWidget { background: #101d28; color: #cbd7df; border: 0; padding: 8px; outline: 0; }
QListWidget::item { padding: 12px 13px; margin: 2px 0; border-radius: 5px; }
QListWidget::item:selected { background: #1e6f9f; color: white; font-weight: 600; }
QListWidget::item:hover { background: #182c3b; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit {
    background: white; border: 1px solid #c9d2da; border-radius: 5px; padding: 6px;
}
QPushButton { background: #176b96; color: white; border: 0; border-radius: 5px; padding: 7px 12px; font-weight: 600; }
QPushButton:hover { background: #0e7caf; }
QPushButton:disabled { background: #aeb9c1; color: #eef2f5; }
QTableWidget { background: white; border: 1px solid #d7dfe5; border-radius: 5px; gridline-color: #e8edf0; alternate-background-color: #f7f9fa; }
QHeaderView::section { background: #e8edf1; padding: 7px; border: 0; border-right: 1px solid #d5dde3; font-weight: 700; }
QFrame#Card { background: white; border: 1px solid #d8e0e6; border-radius: 8px; }
QFrame#Inspector { background: #f8fafb; border: 1px solid #cfd9e0; border-radius: 7px; }
QLabel#Muted { color: #647581; }
QLabel#SectionTitle { color: #10293a; font-size: 13pt; font-weight: 700; }
"""


class MetricCard(QFrame):
    def __init__(self, label: str, accent: str):
        super().__init__()
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        self.value = QLabel("0")
        self.value.setStyleSheet(f"font-size:24pt;font-weight:800;color:{accent};")
        caption = QLabel(label)
        caption.setObjectName("Muted")
        layout.addWidget(self.value)
        layout.addWidget(caption)


class SmartDashboardPage(QWidget):
    def __init__(self, db: Database, open_map: Callable):
        super().__init__()
        self.db=db;self.attention=[]
        layout=QVBoxLayout(self);layout.setContentsMargins(18,18,18,18)
        head=QHBoxLayout();title_box=QVBoxLayout()
        title=QLabel("FAB Operations Command Center");title.setObjectName("SectionTitle")
        subtitle=QLabel("Exceptions first: down tools, active alarms, overdue maintenance, escalated incidents, pending qualification/release and shift handovers")
        subtitle.setObjectName("Muted");title_box.addWidget(title);title_box.addWidget(subtitle);head.addLayout(title_box);head.addStretch(1)
        map_button=QPushButton("Open live FAB map");map_button.clicked.connect(open_map);head.addWidget(map_button);layout.addLayout(head)

        grid=QGridLayout()
        self.cards={
            "equipment_down":MetricCard("Tools down","#d74444"),
            "equipment_hold":MetricCard("On hold","#e1952c"),
            "alarms_active":MetricCard("Active alarms","#d74444"),
            "pm_overdue":MetricCard("PM overdue","#e1952c"),
            "tickets_critical":MetricCard("P1 / P2 incidents","#d74444"),
            "release_pending":MetricCard("Release pending","#4e6f87"),
            "endorsements_open":MetricCard("Shift handovers","#4e6f87"),
            "inventory_low":MetricCard("Low stock","#a86229"),
        }
        for index,card in enumerate(self.cards.values()):grid.addWidget(card,index//4,index%4)
        layout.addLayout(grid)

        frame=QFrame();frame.setObjectName("Card");box=QVBoxLayout(frame)
        issue_title=QLabel("WHAT REQUIRES ATTENTION");issue_title.setStyleSheet("font-weight:700;font-size:12pt;");box.addWidget(issue_title)
        self.table=QTableWidget(0,7);self.table.setHorizontalHeaderLabels(["Severity","Type","Equipment","Key","Action / Condition","Owner","Age (h)"])
        self.table.horizontalHeader().setStretchLastSection(True);box.addWidget(self.table);layout.addWidget(frame,1)
        self.updated=QLabel();self.updated.setObjectName("Muted");layout.addWidget(self.updated);self.refresh()

    def refresh(self):
        counts=self.db.dashboard_counts()
        for key,card in self.cards.items():card.value.setText(str(counts.get(key,0)))
        self.attention=self.db.operations_attention_queue(100)
        self.table.setRowCount(len(self.attention))
        fields=["severity","kind","equipment_id","key","summary","owner","age_hours"]
        for row,item in enumerate(self.attention):
            for column,field in enumerate(fields):
                value=item.get(field,"")
                if field=="age_hours":value=f"{float(value or 0):.1f}"
                self.table.setItem(row,column,QTableWidgetItem(str(value or "")))
        self.updated.setText("Updated "+datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class SmartMainWindow(QMainWindow):
    def __init__(self, db: Database, user):
        super().__init__()
        self.db = db
        self.user = user
        configure_productivity_context(db,user["username"])
        self.nav_history=[]
        self.nav_history_index=-1
        self._history_suspended=False
        self.setWindowTitle(APP_TITLE + (" · Demo" if DEMO_MODE else " · Operations Control"))
        self.resize(1600, 930)

        container = QWidget()
        self.setCentralWidget(container)
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        top = QFrame()
        top.setObjectName("TopBar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(18, 10, 18, 10)
        brand = QVBoxLayout()
        app_title = QLabel(f"EQUIPMENT OPERATIONS CONTROL  {__version__}")
        app_title.setObjectName("AppTitle")
        app_subtitle = QLabel("DEMO semiconductor FAB" if DEMO_MODE else "Production equipment engineering operations")
        app_subtitle.setObjectName("AppSubTitle")
        brand.addWidget(app_title)
        brand.addWidget(app_subtitle)
        top_layout.addLayout(brand)
        top_layout.addStretch(1)
        self.back_button=QPushButton("←")
        self.back_button.setToolTip("Back (Alt+Left)")
        self.back_button.setFixedWidth(34)
        self.back_button.clicked.connect(self.go_back)
        self.forward_button=QPushButton("→")
        self.forward_button.setToolTip("Forward (Alt+Right)")
        self.forward_button.setFixedWidth(34)
        self.forward_button.clicked.connect(self.go_forward)
        top_layout.addWidget(self.back_button)
        top_layout.addWidget(self.forward_button)
        self.global_search=QLineEdit()
        self.global_search.setPlaceholderText("Search equipment, tickets, PM, alarms, parts…")
        self.global_search.setMinimumWidth(360)
        self.global_search.returnPressed.connect(self.run_global_search)
        top_layout.addWidget(self.global_search)
        user_label = QLabel(f"{user['display_name']}  |  {user['role']}  |  {WORKSTATION}")
        user_label.setStyleSheet("color:#c8d6df;")
        top_layout.addWidget(user_label)
        outer.addWidget(top)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        self.nav = QListWidget()
        self.nav.setFixedWidth(225)
        self.stack = QStackedWidget()
        body_layout.addWidget(self.nav)
        body_layout.addWidget(self.stack, 1)
        outer.addWidget(body, 1)

        self.page_index={}
        def add(name, page):
            self.nav.addItem(name)
            self.stack.addWidget(page)
            self.page_index[name]=self.stack.count()-1
            return page

        self.search_workspace=add("Global Search",SearchWorkspace(db,user))
        self.my_work=add("My Work",MyWorkWorkspace(db,user))
        self.dashboard=add("Operations Overview",SmartDashboardPage(db,lambda:self.open_page("Live FAB Map")))
        self.equipment360=add("Equipment Workspaces",EquipmentWorkspaceTabs(db,user))
        self.equipment_page=add("Equipment Registry",EquipmentPage(db,user))
        self.layout_page=add("Live FAB Map",SmartLayoutPage(db,user))
        self.maintenance_planner=add("Maintenance Planner",MaintenancePlanningWorkspace(db,user))
        self.pm_execution=add("Technician PM Runner",PMExecutionWorkspace(db,user))
        self.work_order_workspace=add("Work Orders",WorkOrderWorkspace(db,user))
        self.pm_page=add("PM Configuration",PMPage(db,user))
        self.incident_workspace=add("Incident / RCA Workspace",IncidentWorkspace(db,user))
        self.ticket_page=add("Ticket Lifecycle / Troubleshooting",TicketPage(db,user))
        self.alarm_page=add("Alarms / Events",AlarmPage(db,user))
        self.qualification_page=add("Qualification",QualificationPage(db,user))
        self.analytics_workspace=add("Engineering Analytics",EngineeringAnalyticsWorkspace(db,user))
        self.reliability_page=add("Reliability / MTBF (Legacy)",ReliabilityPage(db))
        self.control_page=add("Disposition / Release",ControlPage(db,user))
        self.work_page=add("Work / Labor",WorkLogPage(db,user))
        self.shift_workspace=add("Shift Operations / Handover",ShiftHandoverWorkspace(db,user))
        self.endorsement_page=add("Handover Records",EndorsementPage(db,user))
        self.inventory_logistics=add("Parts / Inventory Logistics",InventoryLogisticsWorkspace(db,user))
        self.inventory=add("Parts / Inventory (Legacy)",InventoryPage(db,user))
        self.document_page=add("SOPs / Documents",DocumentPage(db,user))
        self.automation_studio=add("Workflow Automation",WorkflowAutomationStudio(db,user))
        self.configuration_studio=add("Configuration Studio",ConfigurationStudio(db,user))
        self.admin_page=add("Users / Administration",AdminPage(db,user))

        self.search_workspace.open_entity.connect(self.open_entity)
        self.my_work.open_entity.connect(self.open_entity)
        self.equipment360.open_entity.connect(self.open_entity)
        self.maintenance_planner.open_entity.connect(self.open_entity)
        self.pm_execution.open_entity.connect(self.open_entity)
        self.work_order_workspace.open_entity.connect(self.open_entity)
        self.shift_workspace.open_entity.connect(self.open_entity)
        self.analytics_workspace.open_entity.connect(self.open_entity)
        self.inventory_logistics.open_entity.connect(self.open_entity)
        self.incident_workspace.open_entity.connect(self.open_entity)
        self.alarm_page.open_incident.connect(lambda ticket,equipment:self.open_entity("TICKET",ticket,equipment))
        self.inventory.show_map_part.connect(self.show_part_map)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.currentRowChanged.connect(self._on_nav_changed)
        self.nav.setCurrentRow(self.page_index["Operations Overview"])

        refresh = QAction("Refresh", self)
        refresh.setShortcut(QKeySequence("F5"))
        refresh.triggered.connect(self.refresh_current)
        self.addAction(refresh)
        find_action=QAction("Global Search",self);find_action.setShortcut(QKeySequence("Ctrl+K"));find_action.triggered.connect(self.focus_global_search);self.addAction(find_action)
        back_action=QAction("Back",self);back_action.setShortcut(QKeySequence("Alt+Left"));back_action.triggered.connect(self.go_back);self.addAction(back_action)
        forward_action=QAction("Forward",self);forward_action.setShortcut(QKeySequence("Alt+Right"));forward_action.triggered.connect(self.go_forward);self.addAction(forward_action)
        self._update_history_buttons()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.dashboard.refresh)
        self.timer.start(30000)

    def _on_nav_changed(self,index: int):
        self.refresh_current()
        if index<0:return
        if not self._history_suspended:
            name=self.nav.item(index).text()
            if self.nav_history_index<0 or self.nav_history[self.nav_history_index]!=name:
                self.nav_history=self.nav_history[:self.nav_history_index+1]
                self.nav_history.append(name)
                self.nav_history_index=len(self.nav_history)-1
        self._update_history_buttons()

    def _update_history_buttons(self):
        self.back_button.setEnabled(self.nav_history_index>0)
        self.forward_button.setEnabled(0<=self.nav_history_index<len(self.nav_history)-1)

    def go_back(self):
        if self.nav_history_index<=0:return
        self.nav_history_index-=1;name=self.nav_history[self.nav_history_index]
        self._history_suspended=True
        try:self.nav.setCurrentRow(self.page_index[name])
        finally:self._history_suspended=False
        self._update_history_buttons()

    def go_forward(self):
        if self.nav_history_index<0 or self.nav_history_index>=len(self.nav_history)-1:return
        self.nav_history_index+=1;name=self.nav_history[self.nav_history_index]
        self._history_suspended=True
        try:self.nav.setCurrentRow(self.page_index[name])
        finally:self._history_suspended=False
        self._update_history_buttons()

    def focus_global_search(self):
        self.global_search.setFocus()
        self.global_search.selectAll()

    def open_page(self,name: str):
        index=self.page_index.get(name)
        if index is not None:self.nav.setCurrentRow(index)

    def run_global_search(self):
        query=self.global_search.text().strip()
        self.search_workspace.set_query(query)
        self.open_page("Global Search")

    def open_entity(self,entity_type: str,entity_key: str,equipment_id: str=""):
        entity_type=(entity_type or "").upper()
        if entity_type and entity_key:
            self.db.record_recent_item(self.user["username"],entity_type,str(entity_key),f"{entity_type}: {entity_key}",equipment_id)
        if entity_type=="REGISTRY":
            target=equipment_id or entity_key
            if hasattr(self.equipment_page,"select_equipment"):self.equipment_page.select_equipment(target)
            self.open_page("Equipment Registry")
            return
        if entity_type=="MAP":
            target=equipment_id or entity_key
            self.layout_page.highlight_equipment(target)
            self.open_page("Live FAB Map")
            return
        if entity_type=="EQUIPMENT" or (equipment_id and entity_type in {"ALARM","QUALIFICATION","DOCUMENT","RELEASE"}):
            target=entity_key if entity_type=="EQUIPMENT" else equipment_id
            self.equipment360.set_equipment(target)
            self.open_page("Equipment Workspaces")
            return
        if entity_type=="TICKET":
            self.incident_workspace.set_ticket(entity_key)
            self.open_page("Incident / RCA Workspace")
            return
        if entity_type=="WORK_ORDER":
            self.work_order_workspace.set_work_order(entity_key)
            self.open_page("Work Orders")
            return
        if entity_type=="TICKET_LEGACY":
            if hasattr(self.ticket_page,"select_ticket"):self.ticket_page.select_ticket(entity_key)
            self.open_page("Ticket Lifecycle / Troubleshooting")
            return
        if entity_type in {"PM_TASK","PM_EXECUTION"}:
            try:key=int(entity_key)
            except Exception:key=0
            self.pm_execution.set_task(key)
            self.open_page("Technician PM Runner")
            return
        if entity_type=="PM_LEGACY":
            try:key=int(entity_key)
            except Exception:key=0
            if hasattr(self.pm_page,"select_task"):self.pm_page.select_task(key)
            self.open_page("PM Configuration")
            return
        if entity_type=="PART":
            part=entity_key.split("@",1)[0]
            self.inventory_logistics.set_part(part)
            self.open_page("Parts / Inventory Logistics")
            return
        if entity_type=="DOCUMENT":
            if hasattr(self.document_page,"select_document"):self.document_page.select_document(entity_key)
            self.open_page("SOPs / Documents")
            return
        if entity_type=="ENDORSEMENT":
            self.shift_workspace.set_endorsement(entity_key)
            self.open_page("Shift Operations / Handover")
            return
        if equipment_id:
            self.equipment360.set_equipment(equipment_id);self.open_page("Equipment Workspaces")
            return
        self.open_page("Global Search")

    def show_part_map(self, part):
        self.layout_page.highlight_inventory(part)
        self.open_page("Live FAB Map")

    def refresh_current(self):
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()


def main():
    if "--version" in sys.argv:
        print(__version__)
        return 0
    if "--preflight" in sys.argv:
        from preflight import run_preflight
        result=run_preflight()
        for check in result["checks"]:
            print(f"{check['status']:<4} {check['name']}: {check['detail']}")
        return 0 if result["ok"] else 2
    configure_logging("ems-smart");install_exception_hook("ems-smart")
    app = QApplication(sys.argv)
    app.setStyleSheet(SMART_STYLE)
    db = Database()
    if not db.has_users():
        first = FirstAdminDialog(db)
        if first.exec() != QDialog.DialogCode.Accepted:
            return 1
    login = LoginDialog(db)
    if login.exec() != QDialog.DialogCode.Accepted:
        return 0
    seeded = seed_demo_data(db) if DEMO_MODE else False
    window = SmartMainWindow(db, login.user)
    if seeded:
        window.statusBar().showMessage("Demo FAB data created: 28 tools + 5 active issue scenarios")
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
