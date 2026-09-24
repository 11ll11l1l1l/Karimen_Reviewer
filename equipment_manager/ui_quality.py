from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractButton, QAbstractItemView, QComboBox, QLineEdit, QListWidget,
    QSpinBox, QDoubleSpinBox, QTableView, QTableWidget, QTextEdit, QWidget,
)


def _display(value: Any) -> str:
    if value is None:
        return ""
    try:
        from datetime import datetime
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return str(value)


class ObjectTableModel(QAbstractTableModel):
    """Read-only model/view table that renders only visible cells."""

    def __init__(self, headers: list[str], fields: list[str], parent: QObject | None = None):
        super().__init__(parent)
        self.headers=list(headers)
        self.fields=list(fields)
        self.rows: list[Any]=[]

    def set_rows(self, rows: list[Any]) -> None:
        self.beginResetModel()
        self.rows=list(rows)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.fields)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.rows)):
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            row=self.rows[index.row()]
            field=self.fields[index.column()]
            value=row.get(field,"") if isinstance(row,dict) else getattr(row,field,"")
            if field=="age_hours":
                try:return f"{float(value or 0):.1f}"
                except Exception:return _display(value)
            return _display(value)
        if role == Qt.ItemDataRole.UserRole:
            return self.rows[index.row()]
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.headers):
            return self.headers[section]
        return section + 1

    def object_at(self, row: int):
        return self.rows[row] if 0 <= row < len(self.rows) else None


def make_model_table(headers: list[str], fields: list[str], accessible_name: str = "") -> tuple[QTableView,ObjectTableModel]:
    view=QTableView()
    model=ObjectTableModel(headers,fields,view)
    view.setModel(model)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    view.setAlternatingRowColors(True)
    view.setSortingEnabled(False)
    view.horizontalHeader().setStretchLastSection(True)
    if accessible_name:
        view.setAccessibleName(accessible_name)
    return view,model


@dataclass
class AccessibilityIssue:
    widget_class: str
    object_name: str
    reason: str


_INTERACTIVE=(QAbstractButton,QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox,QTextEdit,QListWidget,QTableView,QTableWidget)


def apply_accessibility_defaults(root: QWidget) -> list[AccessibilityIssue]:
    """Populate missing accessible names and return anything still unresolved."""
    issues: list[AccessibilityIssue]=[]
    for widget in [root,*root.findChildren(QWidget)]:
        if not isinstance(widget,_INTERACTIVE):
            continue
        if widget.accessibleName().strip():
            continue
        candidates=[]
        if isinstance(widget,QAbstractButton):
            candidates.append(widget.text())
        if isinstance(widget,QLineEdit):
            candidates.append(widget.placeholderText())
        parent=widget.parentWidget()
        layout=parent.layout() if parent is not None else None
        if layout is not None and hasattr(layout,"labelForField"):
            try:
                form_label=layout.labelForField(widget)
                if form_label is not None:candidates.append(form_label.text())
            except Exception:
                pass
        if isinstance(widget,(QTableView,QTableWidget)):
            try:
                model=widget.model()
                first=model.headerData(0,Qt.Orientation.Horizontal,Qt.ItemDataRole.DisplayRole) if model is not None else ""
                if first:candidates.append(f"{first} table")
            except Exception:
                pass
        if isinstance(widget,QListWidget) and widget.count():
            candidates.append(f"Navigation list starting with {widget.item(0).text()}")
        if isinstance(widget,QComboBox) and widget.currentText():
            candidates.append(f"{widget.currentText()} selection")
        candidates.extend([widget.toolTip(),widget.objectName()])
        label=next((str(x).strip() for x in candidates if str(x or "").strip()),"")
        if label:
            widget.setAccessibleName(label.replace("&",""))
        else:
            issues.append(AccessibilityIssue(widget.__class__.__name__,widget.objectName(),"missing accessible name"))
    return issues


class WorkerSignals(QObject):
    finished=Signal(object)
    failed=Signal(str)


class _Worker(QRunnable):
    def __init__(self, fn: Callable[[],Any]):
        super().__init__()
        self.fn=fn
        self.signals=WorkerSignals()

    @Slot()
    def run(self):
        try:self.signals.finished.emit(self.fn())
        except Exception as exc:self.signals.failed.emit(str(exc))


def run_background(fn: Callable[[],Any], on_done: Callable[[Any],None], on_error: Callable[[str],None] | None = None):
    """Run a read-heavy callable away from the GUI thread and marshal the result back."""
    worker=_Worker(fn)
    worker.signals.finished.connect(on_done)
    if on_error is not None:worker.signals.failed.connect(on_error)
    QThreadPool.globalInstance().start(worker)
    return worker
