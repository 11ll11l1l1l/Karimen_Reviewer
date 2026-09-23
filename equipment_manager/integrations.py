from __future__ import annotations

import json
import os
import tempfile
import urllib.request
from pathlib import Path

from database import Database


def _deliver_file(endpoint, event) -> None:
    root=Path(endpoint.target).expanduser().resolve()
    root.mkdir(parents=True,exist_ok=True)
    payload={
        "event_id":event.event_id,
        "topic":event.topic,
        "entity_type":event.entity_type,
        "entity_key":event.entity_key,
        "created_at":event.created_at.isoformat(),
        "payload":json.loads(event.payload_json or "{}"),
    }
    final=root/f"{event.created_at:%Y%m%dT%H%M%S}_{event.event_id}_{event.topic.replace('.','_')}.json"
    fd,tmp=tempfile.mkstemp(prefix=".ems_evt_",suffix=".tmp",dir=str(root))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,ensure_ascii=False,sort_keys=True,indent=2)
            fh.flush();os.fsync(fh.fileno())
        os.replace(tmp,final)
    finally:
        try:os.remove(tmp)
        except OSError:pass


def _deliver_http(endpoint, event) -> None:
    body=json.dumps({
        "event_id":event.event_id,
        "topic":event.topic,
        "entity_type":event.entity_type,
        "entity_key":event.entity_key,
        "created_at":event.created_at.isoformat(),
        "payload":json.loads(event.payload_json or "{}"),
    },sort_keys=True).encode("utf-8")
    headers={"Content-Type":"application/json","User-Agent":"EMS-Integration-Outbox/1"}
    if endpoint.auth_env:
        token=os.getenv(endpoint.auth_env,"")
        if not token:
            raise RuntimeError(f"Authentication environment variable '{endpoint.auth_env}' is not set")
        headers["Authorization"]=token
    req=urllib.request.Request(endpoint.target,data=body,headers=headers,method="POST")
    with urllib.request.urlopen(req,timeout=15) as response:
        status=getattr(response,"status",200)
        if not 200<=status<300:
            raise RuntimeError(f"HTTP integration returned {status}")


def dispatch_pending(db: Database, limit: int = 100) -> dict[str,int]:
    stats={"sent":0,"failed":0,"pending":0}
    deliveries=db.pending_integration_deliveries(limit)
    stats["pending"]=len(deliveries)
    for delivery,event,endpoint in deliveries:
        try:
            if endpoint.adapter_type=="FILE":_deliver_file(endpoint,event)
            elif endpoint.adapter_type=="HTTP":_deliver_http(endpoint,event)
            else:raise RuntimeError(f"Unsupported integration adapter: {endpoint.adapter_type}")
            db.mark_integration_delivery(delivery.id,True)
            stats["sent"]+=1
        except Exception as exc:
            db.mark_integration_delivery(delivery.id,False,str(exc))
            stats["failed"]+=1
    return stats


def main() -> int:
    db=Database(os.getenv("EMS_DATABASE_URL"))
    result=dispatch_pending(db,500)
    print(json.dumps(result,sort_keys=True))
    return 0 if result["failed"]==0 else 2


if __name__=="__main__":
    raise SystemExit(main())
