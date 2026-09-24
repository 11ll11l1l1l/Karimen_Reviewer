from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from database import Database


def _destination(root: Path, bucket: str, source: Path) -> Path:
    folder=root/bucket/datetime.now().strftime("%Y%m%d")
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/source.name
    if target.exists():
        target=folder/f"{source.stem}_{datetime.now():%H%M%S%f}{source.suffix}"
    return target


def process_drop(db: Database, root: str | Path, limit: int = 500) -> dict[str,int]:
    root=Path(root).expanduser().resolve();root.mkdir(parents=True,exist_ok=True)
    stats={"processed":0,"duplicate":0,"rejected":0,"found":0}
    files=sorted(
        [p for p in root.iterdir() if p.is_file() and p.suffix.lower()==".json" and not p.name.startswith(".")],
        key=lambda p:(p.stat().st_mtime,p.name),
    )[:max(1,min(int(limit),5000))]
    stats["found"]=len(files)
    for path in files:
        try:
            data=json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data,dict):raise ValueError("Inbound file root must be a JSON object.")
            source_id=str(data.get("source_id","")).strip()
            external_id=str(data.get("external_event_id","")).strip()
            topic=str(data.get("topic","")).strip()
            entity_type=str(data.get("entity_type","EXTERNAL")).strip()
            entity_key=str(data.get("entity_key","")).strip()
            payload=data.get("payload",{})
            if not isinstance(payload,dict):raise ValueError("payload must be a JSON object.")
            _,created=db.receive_integration_event(source_id,external_id,topic,entity_type,entity_key,payload)
            bucket="_processed" if created else "_duplicate"
            shutil.move(str(path),str(_destination(root,bucket,path)))
            stats["processed" if created else "duplicate"]+=1
        except Exception as exc:
            target=_destination(root,"_rejected",path)
            try:shutil.move(str(path),str(target))
            except Exception:target=path
            try:Path(str(target)+".error.txt").write_text(str(exc),encoding="utf-8")
            except Exception:pass
            stats["rejected"]+=1
    return stats


def main() -> int:
    root=os.getenv("EMS_INBOUND_ROOT","").strip()
    if not root:
        print("EMS_INBOUND_ROOT is not configured.")
        return 2
    db=Database(os.getenv("EMS_DATABASE_URL"))
    result=process_drop(db,root,1000)
    print(json.dumps(result,sort_keys=True))
    return 0 if result["rejected"]==0 else 2


if __name__=="__main__":
    raise SystemExit(main())
