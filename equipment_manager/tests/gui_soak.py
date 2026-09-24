from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

from PySide6.QtWidgets import QApplication

from database import Database
from smart_app import SmartMainWindow


def run() -> None:
    app=QApplication.instance() or QApplication([])
    db=Database("sqlite:///:memory:")
    db.create_user("admin","Soak Administrator","ci-password-12345","Administrator")
    user=db.authenticate("admin","ci-password-12345",workstation="WINDOWS-SOAK")
    assert user is not None
    window=SmartMainWindow(db,user)

    window.resize(1100,760);app.processEvents()
    assert window.nav.width()==185
    window.resize(1600,930);app.processEvents()
    assert window.nav.width()==225

    baseline=len(app.allWidgets())
    for _ in range(3):
        for row in range(window.nav.count()):
            window.nav.setCurrentRow(row)
            window.refresh_current()
            app.processEvents()
    final=len(app.allWidgets())
    # Persistent workspace widgets are expected; repeated navigation must not
    # continuously create a new copy of them.
    assert final <= baseline + 20,(baseline,final)
    window.close()
    app.processEvents()


if __name__=="__main__":
    run()
    print("EMS Windows GUI navigation/resize soak PASS")
