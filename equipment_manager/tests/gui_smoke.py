from __future__ import annotations

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

from PySide6.QtWidgets import QApplication, QTableView

from database import Database
from main import MainWindow
from smart_app import SmartMainWindow


def run() -> None:
    app=QApplication.instance() or QApplication([])
    db=Database("sqlite:///:memory:")
    db.create_user("admin","CI Administrator","ci-password-12345","Administrator")
    user=db.authenticate("admin","ci-password-12345",workstation="WINDOWS-CI")
    assert user is not None

    main=MainWindow(db,user)
    assert main.nav.count()>=10
    assert main.stack.count()==main.nav.count()
    main.refresh_current()
    app.processEvents()
    main.close()

    started=time.perf_counter()
    smart=SmartMainWindow(db,user)
    startup=time.perf_counter()-started
    assert startup<8.0,f"Smart shell startup took {startup:.3f}s"
    assert smart.nav.count()>=10
    assert smart.stack.count()==smart.nav.count()
    assert isinstance(smart.dashboard.table,QTableView)
    assert smart.dashboard.table.accessibleName()
    assert smart.global_search.accessibleName()
    assert smart.nav.accessibleName()
    smart.refresh_current()
    app.processEvents()
    smart.close()


if __name__=="__main__":
    run()
    print("EMS Windows/PySide6 GUI smoke PASS")
