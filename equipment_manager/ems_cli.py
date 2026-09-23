from __future__ import annotations

import argparse
import json
import os

from backup import create_backup, default_backup_path, verify_backup
from integrations import dispatch_pending
from preflight import run_preflight
from recovery import run_restore_drill
from database import Database
from version import __version__


def main() -> int:
    parser=argparse.ArgumentParser(prog="EMSCLI",description="Equipment Management System operations CLI")
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("version")
    sub.add_parser("preflight")
    b=sub.add_parser("backup");b.add_argument("path",nargs="?")
    v=sub.add_parser("verify-backup");v.add_argument("path")
    r=sub.add_parser("restore-drill");r.add_argument("path");r.add_argument("--user",default=os.getenv("USERNAME") or os.getenv("USER") or "operator")
    d=sub.add_parser("dispatch-integrations");d.add_argument("--limit",type=int,default=500)
    args=parser.parse_args()
    url=os.getenv("EMS_DATABASE_URL","sqlite:///equipment_manager.db")

    if args.command=="version":
        print(__version__);return 0
    if args.command=="preflight":
        result=run_preflight()
        for check in result["checks"]:print(f"{check['status']:<4} {check['name']}: {check['detail']}")
        return 0 if result["ok"] else 2
    if args.command=="backup":
        root=os.getenv("EMS_BACKUP_ROOT","equipment_backups")
        path=args.path or default_backup_path(url,root)
        result=create_backup(url,path)
        print(json.dumps(result,indent=2,default=str));return 0
    if args.command=="verify-backup":
        ok,detail=verify_backup(url,args.path);print(("PASS: " if ok else "FAIL: ")+detail);return 0 if ok else 2
    if args.command=="restore-drill":
        ok,detail=run_restore_drill(url,args.path,args.user);print(("PASS: " if ok else "FAIL: ")+detail);return 0 if ok else 2
    if args.command=="dispatch-integrations":
        result=dispatch_pending(Database(url),args.limit);print(json.dumps(result,sort_keys=True));return 0 if result["failed"]==0 else 2
    return 2


if __name__=="__main__":
    raise SystemExit(main())
