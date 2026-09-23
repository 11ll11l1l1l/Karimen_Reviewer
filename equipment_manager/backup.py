from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url


def _postgres_env(url):
    env=os.environ.copy()
    if url.password:
        env["PGPASSWORD"]=url.password
    return env


def _postgres_args(url, command: str) -> list[str]:
    args=[command]
    if url.host:args+=["-h",url.host]
    if url.port:args+=["-p",str(url.port)]
    if url.username:args+=["-U",url.username]
    return args


def verify_backup(database_url: str, backup_path: str) -> tuple[bool,str]:
    path=Path(backup_path)
    if not path.is_file():
        return False,"Backup file not found"
    url=make_url(database_url)
    if url.drivername.startswith("sqlite"):
        try:
            conn=sqlite3.connect(str(path))
            result=conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            ok=bool(result and result[0]=="ok")
            return ok,"SQLite integrity_check: "+(result[0] if result else "no result")
        except Exception as exc:
            return False,str(exc)
    if url.drivername.startswith("postgresql"):
        pg_restore=shutil.which("pg_restore")
        if not pg_restore:
            return False,"pg_restore not found in PATH"
        proc=subprocess.run(
            _postgres_args(url,pg_restore)+["--list",str(path)],
            env=_postgres_env(url),capture_output=True,text=True,
        )
        if proc.returncode!=0:
            return False,(proc.stderr or proc.stdout or "pg_restore --list failed").strip()
        entries=[line for line in proc.stdout.splitlines() if line and not line.startswith(";")]
        return bool(entries),f"PostgreSQL archive entries: {len(entries)}"
    return False,f"Unsupported database driver: {url.drivername}"


def create_backup(database_url: str, destination: str) -> dict:
    url=make_url(database_url)
    dest=Path(destination).expanduser().resolve()
    dest.parent.mkdir(parents=True,exist_ok=True)

    if url.drivername.startswith("sqlite"):
        source_name=url.database
        if not source_name or source_name==":memory:":
            raise ValueError("In-memory SQLite databases cannot be backed up to a persistent file.")
        src=Path(source_name).expanduser().resolve()
        if not src.is_file():
            raise FileNotFoundError(src)
        source=sqlite3.connect(str(src))
        target=sqlite3.connect(str(dest))
        try:
            source.backup(target)
        finally:
            target.close();source.close()
    elif url.drivername.startswith("postgresql"):
        pg_dump=shutil.which("pg_dump")
        if not pg_dump:
            raise RuntimeError("pg_dump not found in PATH. Install PostgreSQL client tools on this workstation.")
        args=_postgres_args(url,pg_dump)+["-Fc","-f",str(dest)]
        if url.database:args+=["-d",url.database]
        proc=subprocess.run(args,env=_postgres_env(url),capture_output=True,text=True)
        if proc.returncode!=0:
            try:dest.unlink()
            except OSError:pass
            raise RuntimeError((proc.stderr or proc.stdout or "pg_dump failed").strip())
    else:
        raise ValueError(f"Unsupported database driver: {url.drivername}")

    ok,detail=verify_backup(database_url,str(dest))
    if not ok:
        try:dest.unlink()
        except OSError:pass
        raise RuntimeError("Backup verification failed: "+detail)
    return {"path":str(dest),"size_bytes":dest.stat().st_size,"verified":True,"verification":detail}


def default_backup_path(database_url: str, root: str = "equipment_backups") -> str:
    url=make_url(database_url)
    suffix=".db" if url.drivername.startswith("sqlite") else ".dump"
    return str((Path(root)/f"EMS_{datetime.now():%Y%m%d_%H%M%S}{suffix}").resolve())


def main() -> int:
    parser=argparse.ArgumentParser(description="Equipment Management System database backup utility")
    parser.add_argument("action",choices=["backup","verify"])
    parser.add_argument("path",nargs="?")
    args=parser.parse_args()
    url=os.getenv("EMS_DATABASE_URL","sqlite:///equipment_manager.db")
    backup_root=os.getenv("EMS_BACKUP_ROOT","equipment_backups")
    path=args.path or default_backup_path(url,backup_root)
    if args.action=="backup":
        result=create_backup(url,path)
        print(f"BACKUP VERIFIED: {result['path']} ({result['size_bytes']} bytes) — {result['verification']}")
        return 0
    ok,detail=verify_backup(url,path)
    print(("VERIFY PASS: " if ok else "VERIFY FAIL: ")+detail)
    return 0 if ok else 2


if __name__=="__main__":
    raise SystemExit(main())
