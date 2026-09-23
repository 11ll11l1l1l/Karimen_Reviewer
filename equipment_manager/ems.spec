# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules("psycopg")
    + ["pandas", "openpyxl", "sqlalchemy.dialects.postgresql", "sqlalchemy.dialects.sqlite"]
)

gui_a = Analysis(
    ["smart_app.py"], pathex=["."], binaries=[], datas=[], hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
gui_pyz = PYZ(gui_a.pure)
gui = EXE(
    gui_pyz, gui_a.scripts, gui_a.binaries, gui_a.datas, [],
    name="EMS", debug=False, bootloader_ignore_signals=False, strip=False,
    upx=False, console=False, disable_windowed_traceback=False,
)

cli_a = Analysis(
    ["ems_cli.py"], pathex=["."], binaries=[], datas=[], hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
cli_pyz = PYZ(cli_a.pure)
cli = EXE(
    cli_pyz, cli_a.scripts, cli_a.binaries, cli_a.datas, [],
    name="EMSCLI", debug=False, bootloader_ignore_signals=False, strip=False,
    upx=False, console=True, disable_windowed_traceback=False,
)
