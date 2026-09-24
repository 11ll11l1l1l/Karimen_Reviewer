from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from database import Database


def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()


def _nested(record: dict[str,Any], key: str):
    value: Any=record
    for part in str(key or "").split("."):
        if not part:return None
        if not isinstance(value,dict) or part not in value:return None
        value=value[part]
    return value


def _records(path: Path, adapter_type: str) -> list[dict[str,Any]]:
    if adapter_type=="FILE_CSV":
        with path.open("r",encoding="utf-8-sig",newline="") as fh:
            return [dict(row) for row in csv.DictReader(fh)]
    with path.open("r",encoding="utf-8-sig") as fh:
        payload=json.load(fh)
    if isinstance(payload,list):
        rows=payload
    elif isinstance(payload,dict) and isinstance(payload.get("records"),list):
        rows=payload["records"]
    elif isinstance(payload,dict):
        rows=[payload]
    else:
        raise ValueError("JSON inbound payload must be an object, a list of objects, or {'records':[...]}." )
    if not all(isinstance(x,dict) for x in rows):raise ValueError("Every inbound record must be an object.")
    return [dict(x) for x in rows]


def _parse_datetime(value):
    if value in (None,""):return None
    if isinstance(value,datetime):return value
    text=str(value).strip()
    if text.endswith("Z"):text=text[:-1]+"+00:00"
    dt=datetime.fromisoformat(text)
    if dt.tzinfo is not None:
        # Existing EMS storage is naive UTC; normalize offset-aware source timestamps.
        dt=dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _bool(value) -> bool:
    if isinstance(value,bool):return value
    return str(value or "").strip().lower() in {"1","true","yes","y","on","reset"}


def _map_record(record: dict[str,Any], mapping: dict[str,str], defaults: dict[str,Any]) -> dict[str,Any]:
    out=dict(defaults)
    for target,source in mapping.items():
        value=_nested(record,source)
        if value is not None and value!="":out[target]=value
    return out


def _required(mapped: dict[str,Any], fields: list[str], row_index: int):
    missing=[x for x in fields if str(mapped.get(x,"")).strip()==""]
    if missing:raise ValueError(f"Row {row_index}: missing required field(s): {', '.join(missing)}")


def _validate_target(db: Database, entity_type: str, mapped: dict[str,Any], row_index: int):
    if entity_type=="ALARM":
        _required(mapped,["equipment_id","alarm_code"],row_index)
        if not db.get_equipment(str(mapped["equipment_id"]).strip()):
            raise ValueError(f"Row {row_index}: equipment not found: {mapped['equipment_id']}")
    elif entity_type=="METER":
        _required(mapped,["equipment_id","meter_code","value"],row_index)
        equipment_id=str(mapped["equipment_id"]).strip();meter_code=str(mapped["meter_code"]).strip()
        if not db.get_equipment(equipment_id):raise ValueError(f"Row {row_index}: equipment not found: {equipment_id}")
        if not any(x.meter_code==meter_code for x in db.list_meters(equipment_id)):
            raise ValueError(f"Row {row_index}: meter not found: {equipment_id}/{meter_code}")
        float(mapped["value"])
    else:
        raise ValueError(f"Unsupported inbound entity type: {entity_type}")


def _apply_target(db: Database, endpoint, mapped: dict[str,Any], record_key: str):
    actor=f"integration:{endpoint.endpoint_id}"
    if endpoint.entity_type=="ALARM":
        equipment_id=str(mapped["equipment_id"]).strip()
        alarm_code=str(mapped["alarm_code"]).strip()
        occurred=_parse_datetime(mapped.get("occurred_at"))
        event_key=str(mapped.get("event_key") or f"IN-{record_key[:36]}")
        row=db.ingest_alarm(
            equipment_id,alarm_code,
            state=str(mapped.get("state") or "ACTIVE"),
            severity=str(mapped.get("severity") or "Warning"),
            message=str(mapped.get("message") or ""),
            source=str(mapped.get("source") or endpoint.endpoint_id),
            event_key=event_key,
            occurred_at=occurred,
            related_ticket=str(mapped.get("related_ticket") or ""),
            raw_payload={"inbound_endpoint":endpoint.endpoint_id,"record_key":record_key},
        )
        return f"ALARM:{row.event_key}"
    equipment_id=str(mapped["equipment_id"]).strip();meter_code=str(mapped["meter_code"]).strip()
    reading,created=db.record_meter_reading(
        equipment_id,meter_code,float(mapped["value"]),actor,
        note=str(mapped.get("note") or f"Inbound {endpoint.endpoint_id}"),
        reset=_bool(mapped.get("reset")),
        workstation=f"INBOUND:{endpoint.endpoint_id}",
    )
    return f"METER:{equipment_id}:{meter_code}:{reading.id}"


def _move_file(source: Path, destination_root: str, default_folder: str) -> Path:
    root=Path(destination_root).expanduser() if destination_root else source.parent/default_folder
    root.mkdir(parents=True,exist_ok=True)
    target=root/source.name
    if target.exists():
        target=root/f"{source.stem}_{datetime.now():%Y%m%d_%H%M%S_%f}{source.suffix}"
    if source.resolve()!=target.resolve():shutil.move(str(source),str(target))
    return target


def preview_inbound_file(db: Database, endpoint_id: str, file_path: str, limit: int=50) -> dict[str,Any]:
    endpoint=db.get_inbound_endpoint(endpoint_id)
    if not endpoint:raise ValueError("Inbound endpoint not found.")
    path=Path(file_path).expanduser().resolve()
    if not path.is_file():raise FileNotFoundError(path)
    mapping=json.loads(endpoint.mapping_json or "{}");defaults=json.loads(endpoint.defaults_json or "{}")
    rows=_records(path,endpoint.adapter_type)
    preview=[];errors=[]
    for index,record in enumerate(rows[:max(1,min(int(limit),500))],1):
        mapped=_map_record(record,mapping,defaults)
        error=""
        try:_validate_target(db,endpoint.entity_type,mapped,index)
        except Exception as exc:error=str(exc);errors.append({"row":index,"error":error})
        preview.append({"row":index,"raw":record,"mapped":mapped,"valid":not bool(error),"error":error})
    return {
        "endpoint_id":endpoint.endpoint_id,"entity_type":endpoint.entity_type,
        "adapter_type":endpoint.adapter_type,"source":str(path),"records_total":len(rows),
        "previewed":len(preview),"valid":sum(1 for x in preview if x["valid"]),
        "invalid":sum(1 for x in preview if not x["valid"]),"rows":preview,"errors":errors,
    }


def process_inbound_file(db: Database, endpoint_id: str, file_path: str, *, replay: bool=False) -> dict[str,Any]:
    endpoint=db.get_inbound_endpoint(endpoint_id)
    if not endpoint:raise ValueError("Inbound endpoint not found.")
    path=Path(file_path).expanduser().resolve()
    if not path.is_file():raise FileNotFoundError(path)
    digest=_sha256(path)
    previous=db.inbound_receipt_by_hash(endpoint.endpoint_id,digest)
    if previous and previous.status=="Processed" and not replay:
        final=_move_file(path,endpoint.archive_path,"_archive")
        return {"status":"Duplicate","receipt_id":previous.id,"applied":0,"rejected":0,"skipped":0,"path":str(final)}
    mapping=json.loads(endpoint.mapping_json or "{}");defaults=json.loads(endpoint.defaults_json or "{}")
    rows=_records(path,endpoint.adapter_type)
    # Validate the whole payload before applying any row to reduce partial-file writes.
    mapped_rows=[]
    validation_errors=[]
    for index,record in enumerate(rows,1):
        try:
            mapped=_map_record(record,mapping,defaults)
            _validate_target(db,endpoint.entity_type,mapped,index)
            mapped_rows.append((index,mapped,record))
        except Exception as exc:validation_errors.append({"row":index,"error":str(exc)})
    if validation_errors:
        final=_move_file(path,endpoint.quarantine_path,"_quarantine")
        receipt=db.save_inbound_receipt({
            "endpoint_id":endpoint.endpoint_id,"source_name":path.name,"source_sha256":digest,
            "status":"Quarantined","records_total":len(rows),"records_applied":0,
            "records_rejected":len(validation_errors),"error":"Validation failed",
            "detail_json":json.dumps({"errors":validation_errors,"final_path":str(final)},default=str,sort_keys=True),
            "processed_at":datetime.utcnow(),
        })
        return {"status":"Quarantined","receipt_id":receipt.id,"applied":0,"rejected":len(validation_errors),"skipped":0,"path":str(final)}

    applied=0;rejected=0;skipped=0;details=[]
    receipt=db.save_inbound_receipt({
        "endpoint_id":endpoint.endpoint_id,"source_name":path.name,"source_sha256":digest,
        "status":"Processing","records_total":len(rows),"records_applied":0,"records_rejected":0,
        "error":"","detail_json":"{}","processed_at":datetime.utcnow(),
    })
    for index,mapped,raw in mapped_rows:
        canonical=json.dumps(raw,default=str,sort_keys=True,separators=(",",":"))
        record_key=hashlib.sha256(f"{endpoint.endpoint_id}|{digest}|{index}|{canonical}".encode("utf-8")).hexdigest()
        existing=db.inbound_record(record_key)
        if existing and existing.status in {"Applied","Processing"}:
            skipped+=1;details.append({"row":index,"record_key":record_key,"status":existing.status,"entity_key":existing.entity_key});continue
        db.save_inbound_record({
            "endpoint_id":endpoint.endpoint_id,"receipt_id":receipt.id,"record_key":record_key,
            "row_index":index,"target_entity":endpoint.entity_type,"status":"Processing",
            "entity_key":"","error":"","processed_at":datetime.utcnow(),
        })
        try:
            entity_key=_apply_target(db,endpoint,mapped,record_key)
            db.save_inbound_record({
                "endpoint_id":endpoint.endpoint_id,"receipt_id":receipt.id,"record_key":record_key,
                "row_index":index,"target_entity":endpoint.entity_type,"status":"Applied",
                "entity_key":entity_key,"error":"","processed_at":datetime.utcnow(),
            })
            applied+=1;details.append({"row":index,"record_key":record_key,"status":"Applied","entity_key":entity_key})
        except Exception as exc:
            db.save_inbound_record({
                "endpoint_id":endpoint.endpoint_id,"receipt_id":receipt.id,"record_key":record_key,
                "row_index":index,"target_entity":endpoint.entity_type,"status":"Rejected",
                "entity_key":"","error":str(exc)[:4000],"processed_at":datetime.utcnow(),
            })
            rejected+=1;details.append({"row":index,"record_key":record_key,"status":"Rejected","error":str(exc)})
    status="Processed" if rejected==0 else ("Partial" if applied else "Quarantined")
    final=_move_file(path,endpoint.archive_path if status=="Processed" else endpoint.quarantine_path,"_archive" if status=="Processed" else "_quarantine")
    receipt=db.save_inbound_receipt({
        "endpoint_id":endpoint.endpoint_id,"source_name":path.name,
        "source_sha256":digest,"status":status,"records_total":len(rows),
        "records_applied":applied,"records_rejected":rejected,
        "error":"" if rejected==0 else f"{rejected} record(s) rejected",
        "detail_json":json.dumps({"records":details,"final_path":str(final),"skipped":skipped},default=str,sort_keys=True),
        "processed_at":datetime.utcnow(),
    })
    return {"status":status,"receipt_id":receipt.id,"applied":applied,"rejected":rejected,"skipped":skipped,"path":str(final)}


def process_inbound_endpoint(db: Database, endpoint_id: str, limit: int=100) -> dict[str,Any]:
    endpoint=db.get_inbound_endpoint(endpoint_id)
    if not endpoint:raise ValueError("Inbound endpoint not found.")
    if not endpoint.enabled:return {"endpoint_id":endpoint_id,"files":0,"processed":0,"quarantined":0,"duplicates":0,"applied":0,"rejected":0}
    root=Path(endpoint.source_path).expanduser().resolve()
    if not root.is_dir():raise ValueError(f"Inbound source directory does not exist: {root}")
    files=sorted(x for x in root.glob(endpoint.file_pattern or "*") if x.is_file())[:max(1,min(int(limit),1000))]
    stats={"endpoint_id":endpoint_id,"files":len(files),"processed":0,"quarantined":0,"duplicates":0,"applied":0,"rejected":0}
    for path in files:
        result=process_inbound_file(db,endpoint_id,str(path))
        status=result["status"]
        if status=="Processed":stats["processed"]+=1
        elif status in {"Quarantined","Partial"}:stats["quarantined"]+=1
        elif status=="Duplicate":stats["duplicates"]+=1
        stats["applied"]+=int(result.get("applied",0));stats["rejected"]+=int(result.get("rejected",0))
    return stats


def process_all_inbound(db: Database, limit_per_endpoint: int=100) -> list[dict[str,Any]]:
    return [process_inbound_endpoint(db,row.endpoint_id,limit_per_endpoint) for row in db.list_inbound_endpoints(True)]
