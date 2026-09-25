from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from database import Database


def _pg_env(url):
    env=os.environ.copy()
    if url.password:env["PGPASSWORD"]=url.password
    return env


def _pg_base_args(url, command):
    args=[command]
    if url.host:args+=["-h",url.host]
    if url.port:args+=["-p",str(url.port)]
    if url.username:args+=["-U",url.username]
    return args


def sqlite_restore_drill(source_database_url: str, backup_path: str) -> tuple[bool,str]:
    path=Path(backup_path)
    if not path.is_file():return False,"Backup file not found"
    with tempfile.TemporaryDirectory() as root:
        restored=Path(root)/"restored.db"
        shutil.copy2(path,restored)
        try:
            db=Database(f"sqlite:///{restored}")
            ok,detail=db.schema_health()
            if not ok:return False,detail
            with db.engine.connect() as conn:
                tables=int(conn.execute(text("SELECT count(*) FROM sqlite_master WHERE type='table'")).scalar_one())
            return True,f"Scratch restore opened successfully; tables={tables}; {detail}"
        except Exception as exc:
            return False,str(exc)


def postgres_restore_drill(source_database_url: str, backup_path: str, admin_url: str | None = None) -> tuple[bool,str]:
    backup=Path(backup_path)
    if not backup.is_file():return False,"Backup file not found"
    pg_restore=shutil.which("pg_restore")
    if not pg_restore:return False,"pg_restore not found in PATH"

    source=make_url(source_database_url)
    admin=make_url(admin_url or os.getenv("EMS_RECOVERY_ADMIN_URL") or str(source.set(database="postgres")))
    scratch=f"ems_restore_{datetime.utcnow():%Y%m%d%H%M%S%f}".lower()
    safe_name="".join(ch for ch in scratch if ch.isalnum() or ch=="_")
    admin_engine=create_engine(admin,isolation_level="AUTOCOMMIT",future=True)
    created=False
    try:
        with admin_engine.connect() as conn:
            conn.exec_driver_sql(f'CREATE DATABASE "{safe_name}"')
            created=True

        restore_url=admin.set(database=safe_name)
        args=_pg_base_args(restore_url,pg_restore)+["--no-owner","--no-privileges","-d",safe_name,str(backup)]
        proc=subprocess.run(args,env=_pg_env(restore_url),capture_output=True,text=True)
        if proc.returncode!=0:
            return False,(proc.stderr or proc.stdout or "pg_restore failed").strip()

        restored=Database(str(restore_url))
        ok,detail=restored.schema_health()
        if not ok:return False,detail
        with restored.engine.connect() as conn:
            equipment=int(conn.execute(text("SELECT count(*) FROM equipment")).scalar_one())
            migrations=int(conn.execute(text("SELECT count(*) FROM schema_migrations")).scalar_one())
        return True,f"Scratch PostgreSQL restore validated; equipment={equipment}; migrations={migrations}; {detail}"
    except Exception as exc:
        return False,str(exc)
    finally:
        if created:
            try:
                with admin_engine.connect() as conn:
                    conn.exec_driver_sql(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
                        (safe_name,),
                    )
                    conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{safe_name}"')
            except Exception:
                pass
        admin_engine.dispose()


def run_restore_drill(
    database_url: str | None,
    backup_path: str,
    user: str = "",
    database: Database | None = None,
) -> tuple[bool,str]:
    db=database or (Database(database_url) if database_url else Database())
    effective_url=db.url
    if effective_url.startswith("sqlite"):
        ok,detail=sqlite_restore_drill(effective_url,backup_path)
        db_type="SQLite"
    elif effective_url.startswith("postgresql"):
        ok,detail=postgres_restore_drill(effective_url,backup_path)
        db_type="PostgreSQL"
    else:
        return False,"Unsupported database driver"
    db.record_recovery_drill(
        backup_path,db_type,ok,detail,user=user,
        workstation=socket.gethostname(),
    )
    return ok,detail


def main() -> int:
    import argparse
    parser=argparse.ArgumentParser(description="EMS backup restore drill")
    parser.add_argument("backup_path")
    parser.add_argument("--user",default=os.getenv("USERNAME") or os.getenv("USER") or "operator")
    args=parser.parse_args()
    db=Database()
    ok,detail=run_restore_drill(db.url,args.backup_path,args.user,database=db)
    print(("RESTORE DRILL PASS: " if ok else "RESTORE DRILL FAIL: ")+detail)
    return 0 if ok else 2


if __name__=="__main__":
    raise SystemExit(main())
