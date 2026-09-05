from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import Database
from demo_data import STATUS_COLORS, active_tickets, state_key
from main import WORKSTATION


def make_cad_background(width: int = 1550, height: int = 900) -> QPixmap:
    pix = QPixmap(width, height)
    pix.fill(QColor("#0b1117"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    painter.setPen(QPen(QColor("#152a36"), 1))
    for x in range(0, width, 25):
        painter.drawLine(x, 0, x, height)
    for y in range(0, height, 25):
        painter.drawLine(0, y, width, y)

    painter.setPen(QPen(QColor("#486472"), 2))
    painter.drawRect(45, 55, width - 90, height - 110)
    painter.setPen(QPen(QColor("#29434f"), 1))
    for y in [125, 230, 335, 440, 545, 650, 755]:
        painter.drawLine(85, y, width - 85, y)
    for x in [90, 440, 790, 1140, 1490]:
        painter.drawLine(x, 105, x, height - 100)

    painter.setPen(QPen(QColor("#7d98a5"), 1))
    painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
    for idx, y in enumerate([145, 250, 355, 460, 565, 670, 775], 1):
        painter.drawText(55, y + 25, f"BAY {idx:02d}")

    zones = [
        (105, 75, 305, 30, "PROCESS CORRIDOR A"),
        (455, 75, 305, 30, "PROCESS CORRIDOR B"),
        (805, 75, 305, 30, "PROCESS CORRIDOR C"),
        (1155, 75, 305, 30, "PROCESS CORRIDOR D"),
    ]
    painter.setPen(QPen(QColor("#6cb4d6"), 1))
    painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
    for x, y, w, h, label in zones:
        painter.drawRect(x, y, w, h)
        painter.drawText(x + 8, y + 20, label)

    painter.setPen(QPen(QColor("#315361"), 1, Qt.PenStyle.DashLine))
    painter.drawRect(90, 810, 520, 45)
    painter.drawRect(635, 810, 360, 45)
    painter.drawRect(1020, 810, 440, 45)
    painter.setPen(QPen(QColor("#64818f"), 1))
    painter.drawText(105, 838, "SUB-FAB / VACUUM / GAS DISTRIBUTION")
    painter.drawText(650, 838, "SERVICE CHASE")
    painter.drawText(1035, 838, "FACILITIES / UTILITY INTERFACE")
    painter.end()
    return pix


def make_tool_icon(tool_type: str, color: QColor) -> QPixmap:
    pix = QPixmap(38, 38)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(color, 2))
    painter.setBrush(QBrush(QColor("#12212b")))
    painter.drawRoundedRect(2, 2, 34, 34, 5, 5)
    tool = (tool_type or "").lower()
    if "etch" in tool or "cvd" in tool or "pvd" in tool:
        painter.drawEllipse(10, 9, 18, 18)
        painter.drawLine(10, 29, 28, 29)
    elif "stepper" in tool or "lith" in tool:
        painter.drawRect(9, 10, 20, 15)
        painter.drawLine(13, 29, 25, 29)
        painter.drawEllipse(16, 14, 6, 6)
    elif "cmp" in tool:
        painter.drawEllipse(8, 17, 22, 10)
        painter.drawEllipse(13, 8, 12, 12)
    elif "furn" in tool:
        painter.drawRect(10, 8, 18, 22)
        for y in [12, 17, 22]:
            painter.drawLine(14, y, 24, y)
    elif "wet" in tool:
        painter.drawRect(8, 12, 22, 16)
        painter.drawLine(12, 17, 26, 17)
        painter.drawLine(12, 22, 26, 22)
    else:
        painter.drawRect(9, 9, 20, 20)
        painter.drawLine(13, 13, 25, 25)
        painter.drawLine(25, 13, 13, 25)
    painter.end()
    return pix


class FabMapView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#071016"))
        self.setFrameShape(QFrame.Shape.NoFrame)

    def wheelEvent(self, event):
        factor = 1.18 if event.angleDelta().y() > 0 else 1 / 1.18
        self.scale(factor, factor)


class ToolNode(QGraphicsRectItem):
    WIDTH = 118
    HEIGHT = 70

    def __init__(self, equipment, tickets, selected_cb: Callable, movable: bool):
        super().__init__(0, 0, self.WIDTH, self.HEIGHT)
        self.equipment = equipment
        self.tickets = tickets
        self.selected_cb = selected_cb
        self.state = state_key(equipment, tickets)
        self.base_color = STATUS_COLORS[self.state]
        self.has_issue = bool(tickets)
        self.pulse_on = False
        self.setPos(equipment.map_x, equipment.map_y)
        self.setZValue(10)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, movable)
        self.setAcceptHoverEvents(True)
        self.setToolTip(f"{equipment.equipment_id}\n{equipment.name}\n{equipment.status}")

        icon = QGraphicsPixmapItem(make_tool_icon(equipment.equipment_type, self.base_color), self)
        icon.setPos(7, 8)
        id_text = QGraphicsSimpleTextItem(equipment.equipment_id.replace("FAB-", ""), self)
        id_text.setBrush(QBrush(QColor("#e8f1f5")))
        id_text.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        id_text.setPos(49, 8)
        status_text = QGraphicsSimpleTextItem(equipment.status, self)
        status_text.setBrush(QBrush(self.base_color))
        status_text.setFont(QFont("Segoe UI", 7))
        status_text.setPos(49, 28)
        issue_text = QGraphicsSimpleTextItem(
            f"{len(tickets)} ISSUE" if len(tickets) == 1 else f"{len(tickets)} ISSUES", self
        )
        issue_text.setBrush(QBrush(QColor("#ffd4d4" if self.state == "critical" else "#ffdca8")))
        issue_text.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
        issue_text.setPos(49, 47)
        issue_text.setVisible(self.has_issue)
        self.apply_visual(False)

    def apply_visual(self, pulse: bool):
        self.pulse_on = pulse
        edge = QColor(self.base_color)
        if self.has_issue and pulse:
            edge = edge.lighter(150)
            self.setScale(1.035)
            self.setOpacity(0.98)
        else:
            self.setScale(1.0)
            self.setOpacity(1.0)
        self.setPen(QPen(edge, 3 if self.has_issue else 1.5))
        fill = QColor("#15232d")
        fill.setAlpha(245 if self.has_issue else 225)
        self.setBrush(QBrush(fill))

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.selected_cb(self.equipment, self.tickets)

    def hoverEnterEvent(self, event):
        self.setPen(QPen(self.base_color.lighter(145), 3))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.apply_visual(self.pulse_on)
        super().hoverLeaveEvent(event)


class StorageNode(QGraphicsRectItem):
    def __init__(self, storage, highlighted: bool, movable: bool):
        super().__init__(0, 0, 88, 42)
        self.key = storage.location_code
        self.version = storage.version
        self.setPos(storage.map_x, storage.map_y)
        self.setZValue(8)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, movable)
        self.setBrush(QBrush(QColor("#5b4729" if not highlighted else "#9c5d16")))
        self.setPen(QPen(QColor("#d3a14e" if not highlighted else "#ffb13b"), 1.5))
        label = QGraphicsSimpleTextItem(storage.location_code, self)
        label.setBrush(QBrush(QColor("#f5e7c9")))
        label.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        label.setPos(7, 10)


class SmartLayoutPage(QWidget):
    def __init__(self, db: Database, user):
        super().__init__()
        self.db = db
        self.user = user
        self.nodes: list[ToolNode] = []
        self.storage_nodes: list[StorageNode] = []
        self.highlight_part = ""
        self.can_edit = db.has_permission(user, "layout.edit") or db.has_permission(user, "equipment.edit")
        self._pulse = False

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("FAB Live Equipment Map")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("Operational status overlay · click a tool for issue details · mouse wheel zooms")
        subtitle.setObjectName("Muted")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        title_row.addLayout(title_box)
        title_row.addStretch(1)
        self.health = QLabel()
        title_row.addWidget(self.health)
        root.addLayout(title_row)

        controls = QHBoxLayout()
        self.building = QComboBox()
        self.floor = QComboBox()
        all_equipment = db.list_equipment()
        buildings = sorted({e.building for e in all_equipment if e.building}) or ["FAB-A"]
        floors = sorted({e.floor for e in all_equipment if e.floor}) or ["1F"]
        self.building.addItems(buildings)
        self.floor.addItems(floors)
        if "FAB-A" in buildings:
            self.building.setCurrentText("FAB-A")
        if "1F" in floors:
            self.floor.setCurrentText("1F")
        self.building.currentTextChanged.connect(self.refresh)
        self.floor.currentTextChanged.connect(self.refresh)
        self.issue_only = QCheckBox("Issues only")
        self.issue_only.toggled.connect(self.refresh)
        self.edit_mode = QCheckBox("Layout edit")
        self.edit_mode.setEnabled(self.can_edit)
        self.edit_mode.toggled.connect(self.refresh)
        fit_btn = QPushButton("Fit FAB")
        fit_btn.clicked.connect(self.fit_map)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        save_btn = QPushButton("Save positions")
        save_btn.setEnabled(self.can_edit)
        save_btn.clicked.connect(self.save_positions)
        for widget in [
            QLabel("Building"), self.building, QLabel("Floor"), self.floor,
            self.issue_only, self.edit_mode, fit_btn, refresh_btn, save_btn,
        ]:
            controls.addWidget(widget)
        controls.addStretch(1)
        root.addLayout(controls)

        legend = QHBoxLayout()
        for key, text in [
            ("good", "Running / good"), ("attention", "Attention"),
            ("critical", "Down / critical"), ("planned", "PM / engineering"),
            ("offline", "Offline"),
        ]:
            dot = QLabel(f"● {text}")
            dot.setStyleSheet(f"color:{STATUS_COLORS[key].name()};font-weight:600;")
            legend.addWidget(dot)
        pulse = QLabel("Pulsing border = active issue")
        pulse.setObjectName("Muted")
        legend.addSpacing(15)
        legend.addWidget(pulse)
        legend.addStretch(1)
        root.addLayout(legend)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.scene = QGraphicsScene(self)
        self.view = FabMapView(self.scene)
        splitter.addWidget(self.view)

        inspector = QFrame()
        inspector.setObjectName("Inspector")
        inspector_layout = QVBoxLayout(inspector)
        self.detail_title = QLabel("Select an equipment icon")
        self.detail_title.setObjectName("SectionTitle")
        self.detail_title.setWordWrap(True)
        self.detail_status = QLabel("No tool selected")
        self.detail_status.setObjectName("Muted")
        self.detail_body = QLabel("Click a colored equipment square on the FAB image to inspect status, ownership and active issues.")
        self.detail_body.setWordWrap(True)
        self.detail_body.setTextFormat(Qt.TextFormat.RichText)
        self.issue_table = QTableWidget(0, 5)
        self.issue_table.setHorizontalHeaderLabels(["Ticket", "Pri", "Sev", "Status", "Owner"])
        self.issue_table.horizontalHeader().setStretchLastSection(True)
        self.issue_table.setMinimumHeight(180)
        self.issue_description = QLabel("")
        self.issue_description.setWordWrap(True)
        self.issue_description.setStyleSheet("background:white;border:1px solid #d8e0e6;border-radius:5px;padding:8px;")
        self.issue_table.currentCellChanged.connect(self.show_selected_issue)
        inspector_layout.addWidget(self.detail_title)
        inspector_layout.addWidget(self.detail_status)
        inspector_layout.addWidget(self.detail_body)
        issue_head = QLabel("Active Issues")
        issue_head.setStyleSheet("font-weight:700;margin-top:8px;")
        inspector_layout.addWidget(issue_head)
        inspector_layout.addWidget(self.issue_table)
        inspector_layout.addWidget(self.issue_description)
        inspector_layout.addStretch(1)
        splitter.addWidget(inspector)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([1100, 330])
        root.addWidget(splitter, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_issues)
        self.timer.start(650)
        self.refresh()
        QTimer.singleShot(50, self.fit_map)

    def scope_key(self):
        return f"{self.building.currentText()}|{self.floor.currentText()}"

    def tickets_by_equipment(self):
        grouped = {}
        for ticket in active_tickets(self.db):
            grouped.setdefault(ticket.equipment_id, []).append(ticket)
        return grouped

    def refresh(self):
        self.scene.clear()
        self.nodes = []
        self.storage_nodes = []
        background_path = self.db.get_layout_background(self.scope_key())
        pix = QPixmap(background_path) if background_path and Path(background_path).exists() else make_cad_background()
        if pix.isNull():
            pix = make_cad_background()
        background = QGraphicsPixmapItem(pix)
        background.setZValue(-20)
        self.scene.addItem(background)

        grouped = self.tickets_by_equipment()
        building = self.building.currentText()
        floor = self.floor.currentText()
        equipment = [
            e for e in self.db.list_equipment()
            if (not building or e.building == building) and (not floor or e.floor == floor)
        ]
        if self.issue_only.isChecked():
            equipment = [e for e in equipment if grouped.get(e.equipment_id)]

        for equipment_row in equipment:
            node = ToolNode(
                equipment_row,
                grouped.get(equipment_row.equipment_id, []),
                self.select_tool,
                self.edit_mode.isChecked(),
            )
            self.scene.addItem(node)
            self.nodes.append(node)

        matching_locations = set()
        if self.highlight_part:
            matching_locations = {
                item.location_code for item in self.db.list_inventory(self.highlight_part)
                if self.highlight_part.lower() in (item.part_number or "").lower()
            }
        for storage in self.db.list_storage_locations():
            if building and storage.building != building:
                continue
            if floor and storage.floor != floor:
                continue
            node = StorageNode(storage, storage.location_code in matching_locations, self.edit_mode.isChecked())
            self.scene.addItem(node)
            self.storage_nodes.append(node)

        issue_count = sum(1 for equipment_row in equipment if grouped.get(equipment_row.equipment_id))
        critical_count = sum(
            1 for equipment_row in equipment
            if state_key(equipment_row, grouped.get(equipment_row.equipment_id, [])) == "critical"
        )
        if critical_count:
            self.health.setText(f"FAB ATTENTION · {critical_count} critical · {issue_count} with issues")
            self.health.setStyleSheet("font-weight:700;padding:6px 10px;border-radius:5px;background:#ffe4e4;color:#9d2929;")
        elif issue_count:
            self.health.setText(f"FAB STABLE · {issue_count} tools need attention")
            self.health.setStyleSheet("font-weight:700;padding:6px 10px;border-radius:5px;background:#fff0d7;color:#8a5812;")
        else:
            self.health.setText(f"ALL GREEN · {len(equipment)} tools normal")
            self.health.setStyleSheet("font-weight:700;padding:6px 10px;border-radius:5px;background:#dff4e8;color:#176b43;")
        self.scene.setSceneRect(QRectF(0, 0, pix.width(), pix.height()))

    def fit_map(self):
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def animate_issues(self):
        self._pulse = not self._pulse
        for node in self.nodes:
            if node.has_issue:
                node.apply_visual(self._pulse)

    def select_tool(self, equipment, tickets):
        color = STATUS_COLORS[state_key(equipment, tickets)].name()
        self.detail_title.setText(f"{equipment.equipment_id} · {equipment.name}")
        self.detail_status.setText(f"{equipment.status} · {equipment.disposition}")
        self.detail_status.setStyleSheet(f"color:{color};font-weight:700;")
        updated = equipment.updated_at.strftime("%Y-%m-%d %H:%M") if equipment.updated_at else "-"
        self.detail_body.setText(
            f"<b>Type:</b> {equipment.equipment_type}<br>"
            f"<b>Maker / model:</b> {equipment.manufacturer} · {equipment.model}<br>"
            f"<b>Location:</b> {equipment.building} / {equipment.floor} / {equipment.area} / {equipment.line_cell}<br>"
            f"<b>Owner:</b> {equipment.owner}<br>"
            f"<b>Criticality:</b> {equipment.criticality}<br>"
            f"<b>Last record update:</b> {updated}"
        )
        self.issue_table.setRowCount(len(tickets))
        self._selected_tickets = tickets
        for row, ticket in enumerate(tickets):
            for column, value in enumerate([ticket.ticket_no, ticket.priority, ticket.severity, ticket.status, ticket.owner]):
                self.issue_table.setItem(row, column, QTableWidgetItem(str(value or "")))
        if tickets:
            self.issue_table.selectRow(0)
            self.show_selected_issue(0, 0, -1, -1)
        else:
            self.issue_description.setText("No active issue. Equipment is operating without an open ticket.")

    def show_selected_issue(self, row, _column, _previous_row, _previous_column):
        tickets = getattr(self, "_selected_tickets", [])
        if 0 <= row < len(tickets):
            ticket = tickets[row]
            self.issue_description.setText(
                f"<b>{ticket.title}</b><br><br>{ticket.description or 'No description entered.'}"
            )

    def save_positions(self):
        if not self.can_edit:
            return
        try:
            for node in self.nodes:
                equipment = node.equipment
                self.db.update_map_position(
                    "equipment", equipment.equipment_id,
                    node.pos().x(), node.pos().y(), equipment.version,
                )
            for node in self.storage_nodes:
                self.db.update_map_position("storage", node.key, node.pos().x(), node.pos().y(), node.version)
            self.db.audit(self.user["username"], "UPDATE", "LAYOUT", self.scope_key(), workstation=WORKSTATION)
            QMessageBox.information(self, "FAB Layout", "Map positions saved.")
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "FAB Layout", str(exc))
            self.refresh()

    def highlight_inventory(self, part: str):
        self.highlight_part = (part or "").strip()
        self.refresh()
