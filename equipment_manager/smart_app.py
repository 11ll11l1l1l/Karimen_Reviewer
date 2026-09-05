from __future__ import annotations

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
from demo_data import active_tickets, seed_demo_data
from main import (
    APP_TITLE,
    WORKSTATION,
    AdminPage,
    ControlPage,
    DocumentPage,
    EndorsementPage,
    EquipmentPage,
    FirstAdminDialog,
    InventoryPage,
    LoginDialog,
    PMPage,
    TicketPage,
)
from smart_map import SmartLayoutPage

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
        self.db = db
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)

        head = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("FAB Operations Overview")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("Current equipment health, maintenance exposure and active issues")
        subtitle.setObjectName("Muted")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        head.addLayout(title_box)
        head.addStretch(1)
        map_button = QPushButton("Open live FAB map")
        map_button.clicked.connect(open_map)
        head.addWidget(map_button)
        layout.addLayout(head)

        grid = QGridLayout()
        self.cards = {
            "equipment_total": MetricCard("Registered equipment", "#176b96"),
            "equipment_down": MetricCard("Down", "#d74444"),
            "equipment_hold": MetricCard("On hold", "#e1952c"),
            "tickets_open": MetricCard("Open tickets", "#8b4fc6"),
            "tickets_critical": MetricCard("P1 / P2 tickets", "#d74444"),
            "pm_overdue": MetricCard("PM overdue", "#e1952c"),
            "inventory_low": MetricCard("Low stock", "#a86229"),
            "release_pending": MetricCard("Release pending", "#4e6f87"),
        }
        for index, card in enumerate(self.cards.values()):
            grid.addWidget(card, index // 4, index % 4)
        layout.addLayout(grid)

        issue_frame = QFrame()
        issue_frame.setObjectName("Card")
        issue_layout = QVBoxLayout(issue_frame)
        issue_title = QLabel("Highest-priority active equipment issues")
        issue_title.setStyleSheet("font-weight:700;font-size:11pt;")
        issue_layout.addWidget(issue_title)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Equipment", "Ticket", "Priority", "Severity", "Status", "Issue"])
        self.table.horizontalHeader().setStretchLastSection(True)
        issue_layout.addWidget(self.table)
        layout.addWidget(issue_frame, 1)
        self.updated = QLabel()
        self.updated.setObjectName("Muted")
        layout.addWidget(self.updated)
        self.refresh()

    def refresh(self):
        counts = self.db.dashboard_counts()
        for key, card in self.cards.items():
            card.value.setText(str(counts.get(key, 0)))
        rank = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
        tickets = sorted(
            active_tickets(self.db),
            key=lambda ticket: (
                rank.get((ticket.priority or "").upper(), 9),
                ticket.created_at or datetime.min,
            ),
        )[:12]
        self.table.setRowCount(len(tickets))
        for row, ticket in enumerate(tickets):
            values = [ticket.equipment_id, ticket.ticket_no, ticket.priority, ticket.severity, ticket.status, ticket.title]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value or "")))
        self.updated.setText("Updated " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class SmartMainWindow(QMainWindow):
    def __init__(self, db: Database, user):
        super().__init__()
        self.db = db
        self.user = user
        self.setWindowTitle(APP_TITLE + " · Smart FAB Demo")
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
        app_title = QLabel("EQUIPMENT OPERATIONS CONTROL")
        app_title.setObjectName("AppTitle")
        app_subtitle = QLabel("Demo semiconductor FAB · shared database · read-only document workflow")
        app_subtitle.setObjectName("AppSubTitle")
        brand.addWidget(app_title)
        brand.addWidget(app_subtitle)
        top_layout.addLayout(brand)
        top_layout.addStretch(1)
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

        def add(name, page):
            self.nav.addItem(name)
            self.stack.addWidget(page)

        self.layout_page = SmartLayoutPage(db, user)
        self.dashboard = SmartDashboardPage(db, lambda: self.nav.setCurrentRow(2))
        add("Operations Overview", self.dashboard)
        add("Equipment Registry", EquipmentPage(db, user))
        add("Live FAB Map", self.layout_page)
        add("PM Planning / Execution", PMPage(db, user))
        add("Issue / Repair Tickets", TicketPage(db, user))
        add("Disposition / Release", ControlPage(db, user))
        add("Shift Endorsements", EndorsementPage(db, user))
        self.inventory = InventoryPage(db, user)
        add("Parts / Inventory", self.inventory)
        add("SOPs / Documents", DocumentPage(db, user))
        add("Users / Administration", AdminPage(db, user))

        self.inventory.show_map_part.connect(self.show_part_map)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.currentRowChanged.connect(lambda _index: self.refresh_current())
        self.nav.setCurrentRow(0)

        refresh = QAction("Refresh", self)
        refresh.setShortcut(QKeySequence("F5"))
        refresh.triggered.connect(self.refresh_current)
        self.addAction(refresh)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.dashboard.refresh)
        self.timer.start(30000)

    def show_part_map(self, part):
        self.layout_page.highlight_inventory(part)
        self.nav.setCurrentRow(2)

    def refresh_current(self):
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()


def main():
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
    seeded = seed_demo_data(db)
    window = SmartMainWindow(db, login.user)
    if seeded:
        window.statusBar().showMessage("Demo FAB data created: 28 tools + 5 active issue scenarios")
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
