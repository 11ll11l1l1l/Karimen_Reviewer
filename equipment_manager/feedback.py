from __future__ import annotations

from PySide6.QtWidgets import QApplication, QMainWindow, QStatusBar


def notify(message: str, timeout_ms: int = 5000):
    app=QApplication.instance()
    window=app.activeWindow() if app else None
    if isinstance(window,QMainWindow):
        window.statusBar().showMessage(str(message),timeout_ms)
        return
    # Walk top-level widgets because activeWindow can briefly be a child dialog.
    if app:
        for widget in app.topLevelWidgets():
            if isinstance(widget,QMainWindow) and widget.isVisible():
                widget.statusBar().showMessage(str(message),timeout_ms)
                return


def notify_persistent(message: str):
    notify(message,0)
