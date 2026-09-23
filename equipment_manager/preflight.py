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
            require_pitr=os.getenv("EMS_REQUIRE_PITR","0").strip().lower() in {"1","true","yes","on"}
            require_ha=os.getenv("EMS_REQUIRE_HA","0").strip().lower() in {"1","true","yes","on"}
            strict_auth=os.getenv("EMS_STRICT_AUTHZ","0").strip().lower() in {"1","true","yes","on"}
            add("strict_backend_authorization","PASS" if strict_auth else "WARN","EMS_STRICT_AUTHZ is enabled." if strict_auth else "Set EMS_STRICT_AUTHZ=1 for production backend permission enforcement.")
            try:
                with db.engine.connect() as conn:
                    version=conn.execute(text("SHOW server_version")).scalar_one()
                    encoding=conn.execute(text("SHOW server_encoding")).scalar_one()
                    wal_level=conn.execute(text("SHOW wal_level")).scalar_one()
                    archive_mode=conn.execute(text("SHOW archive_mode")).scalar_one()
                    max_wal_senders=int(conn.execute(text("SHOW max_wal_senders")).scalar_one())
                    hot_standby=conn.execute(text("SHOW hot_standby")).scalar_one()
                    try:replicas=int(conn.execute(text("SELECT count(*) FROM pg_stat_replication")).scalar_one())
                    except Exception:replicas=-1
                add("postgresql_server","PASS",f"PostgreSQL {version}; encoding {encoding}")
                wal_ok=str(wal_level).lower() in {"replica","logical"}
                add("postgresql_wal_level","PASS" if wal_ok else ("FAIL" if require_ha else "WARN"),f"wal_level={wal_level}")
                archive_ok=str(archive_mode).lower() in {"on","always"}
                add("postgresql_archive_mode","PASS" if archive_ok else ("FAIL" if require_pitr else "WARN"),f"archive_mode={archive_mode}; enable WAL archiving for PITR")
                senders_ok=max_wal_senders>0
                add("postgresql_replication_capacity","PASS" if senders_ok else ("FAIL" if require_ha else "WARN"),f"max_wal_senders={max_wal_senders}; hot_standby={hot_standby}")
                if replicas>=0:
                    add("postgresql_active_standby","PASS" if replicas>0 else ("FAIL" if require_ha else "WARN"),f"active streaming replicas={replicas}")
                else:
                    add("postgresql_active_standby","WARN","Unable to read pg_stat_replication with this database account.")
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
    if ok:
        try:
            free=shutil.disk_usage(Path(file_root)).free/(1024**3)
            minimum=float(os.getenv("EMS_MIN_FREE_GB","5"))
            add("file_root_free_space","PASS" if free>=minimum else "WARN",f"{free:.1f} GiB free; threshold {minimum:.1f} GiB")
        except Exception as exc:add("file_root_free_space","WARN",str(exc))
    attachments=Path(file_root)/"Attachments"
    ok,detail=_writable_directory(attachments)
    add("attachments_write","PASS" if ok else "FAIL",detail)

    ok,detail=_writable_directory(Path(backup_root))
    add("backup_root_write","PASS" if ok else "FAIL",detail)
    if ok:
        try:
            free=shutil.disk_usage(Path(backup_root)).free/(1024**3)
            minimum=float(os.getenv("EMS_MIN_BACKUP_FREE_GB","10"))
            add("backup_root_free_space","PASS" if free>=minimum else "WARN",f"{free:.1f} GiB free; threshold {minimum:.1f} GiB")
        except Exception as exc:add("backup_root_free_space","WARN",str(exc))
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
