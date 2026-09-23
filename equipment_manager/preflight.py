from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from sqlalchemy import text

from backup import default_backup_path
from database import Database


def _writable_directory(path: Path) -> tuple[bool,str]:
    try:
        path.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(prefix=".ems_write_",dir=str(path))
        os.close(fd)
        os.remove(name)
        return True,str(path)
    except Exception as exc:
        return False,f"{path}: {exc}"


def run_preflight(database_url: str | None = None, file_root: str | None = None, backup_root: str | None = None) -> dict:
    database_url=database_url or os.getenv("EMS_DATABASE_URL","sqlite:///equipment_manager.db")
    file_root=file_root or os.getenv("EMS_FILE_ROOT",str(Path.cwd()/"equipment_files"))
    backup_root=backup_root or os.getenv("EMS_BACKUP_ROOT",str(Path.cwd()/"equipment_backups"))
    checks=[]

    def add(name,status,detail):
        checks.append({"name":name,"status":status,"detail":detail})

    try:
        db=Database(database_url)
        ok,detail=db.health()
        add("database_connection","PASS" if ok else "FAIL",detail)
        ok,detail=db.schema_health()
        add("database_schema","PASS" if ok else "FAIL",detail)

        if database_url.startswith("postgresql"):
            try:
                with db.engine.connect() as conn:
                    version=conn.execute(text("SHOW server_version")).scalar_one()
                    encoding=conn.execute(text("SHOW server_encoding")).scalar_one()
                add("postgresql_server","PASS",f"PostgreSQL {version}; encoding {encoding}")
            except Exception as exc:
                add("postgresql_server","FAIL",str(exc))
            for tool in ["pg_dump","pg_restore"]:
                path=shutil.which(tool)
                add(tool,"PASS" if path else "FAIL",path or f"{tool} not found in PATH")
        else:
            add("production_database_mode","WARN","SQLite is supported for local/demo only; production multi-user deployment should use PostgreSQL.")
    except Exception as exc:
        add("database_initialization","FAIL",str(exc))

    ok,detail=_writable_directory(Path(file_root))
    add("file_root_write","PASS" if ok else "FAIL",detail)
    attachments=Path(file_root)/"Attachments"
    ok,detail=_writable_directory(attachments)
    add("attachments_write","PASS" if ok else "FAIL",detail)

    ok,detail=_writable_directory(Path(backup_root))
    add("backup_root_write","PASS" if ok else "FAIL",detail)
    try:
        example=default_backup_path(database_url,backup_root)
        add("backup_target","PASS",example)
    except Exception as exc:
        add("backup_target","FAIL",str(exc))

    failures=[x for x in checks if x["status"]=="FAIL"]
    warnings=[x for x in checks if x["status"]=="WARN"]
    return {
        "ok":not failures,
        "failure_count":len(failures),
        "warning_count":len(warnings),
        "database_url_safe":database_url.split("@")[-1] if "@" in database_url else database_url,
        "file_root":file_root,
        "backup_root":backup_root,
        "checks":checks,
    }


def main() -> int:
    result=run_preflight()
    for check in result["checks"]:
        print(f"{check['status']:<4} {check['name']}: {check['detail']}")
    print(json.dumps({k:v for k,v in result.items() if k!="checks"},indent=2,default=str))
    return 0 if result["ok"] else 2


if __name__=="__main__":
    raise SystemExit(main())
