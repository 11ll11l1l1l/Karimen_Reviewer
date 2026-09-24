from __future__ import annotations

from typing import Any

EQUIPMENT_FIELDS=[
    "name","equipment_type","manufacturer","model","serial_number","asset_number",
    "site","building","floor","area","line_cell","owner","criticality",
]
INVENTORY_FIELDS=[
    "description","category","manufacturer","model","compatible_equipment","quantity",
    "min_quantity","unit","condition","image_path","notes",
]
TICKET_FIELDS=[
    "equipment_id","title","description","severity","priority","owner",
    "root_cause","corrective_action","verification",
]


def _norm(value):
    if value is None:return ""
    if isinstance(value,float):return round(value,9)
    return str(value)


def _validate_keys(rows, fields, label):
    seen=set()
    key_fields=("equipment_id",) if label=="equipment" else ("part_number","location_code")
    for index,row in enumerate(rows,1):
        missing=[field for field in key_fields if not str(row.get(field,"")).strip()]
        if missing: raise ValueError(f"{label} row {index} is missing: {', '.join(missing)}")
        key=tuple(str(row[field]).strip() for field in key_fields)
        if key in seen: raise ValueError(f"Duplicate {label} key at row {index}: {' @ '.join(key)}")
        seen.add(key)


def reconcile_equipment(db,imported_rows: list[dict[str,Any]],mapping: dict[str,str]):
    _validate_keys(imported_rows,EQUIPMENT_FIELDS,"equipment")
    mapped={x for x in EQUIPMENT_FIELDS if x in mapping}
    actions=[]
    for source in imported_rows:
        key=source["equipment_id"];current=db.get_equipment(key)
        if current:
            merged={"equipment_id":key}
            for field in EQUIPMENT_FIELDS:
                merged[field]=source.get(field) if field in mapped else getattr(current,field,"")
            changes=[
                {"field":field,"current":getattr(current,field,""),"incoming":merged[field]}
                for field in mapped if _norm(getattr(current,field,""))!=_norm(merged[field])
            ]
            status="UPDATE" if changes else "UNCHANGED"
        else:
            merged={"equipment_id":key}
            for field in EQUIPMENT_FIELDS:
                if field=="criticality":merged[field]=source.get(field) if field in mapped else "Normal"
                else:merged[field]=source.get(field,"") if field in mapped else ""
            changes=[{"field":field,"current":"","incoming":merged[field]} for field in mapped if _norm(merged[field])!=""]
            status="CREATE"
        actions.append({"key":key,"status":status,"current":current,"data":merged,"changes":changes})
    return actions


def reconcile_tickets(db,imported_rows: list[dict[str,Any]],mapping: dict[str,str]):
    seen=set();mapped={x for x in TICKET_FIELDS if x in mapping};existing={x.ticket_no:x for x in db.list_tickets()};actions=[]
    for index,source in enumerate(imported_rows,1):
        key=str(source.get("ticket_no","")).strip()
        if not key:raise ValueError(f"incident row {index} is missing ticket number")
        if key in seen:raise ValueError(f"Duplicate incident key at row {index}: {key}")
        seen.add(key);current=existing.get(key)
        if current:
            merged={"ticket_no":key}
            for field in TICKET_FIELDS:merged[field]=source.get(field) if field in mapped else getattr(current,field,"")
            merged["created_by"]=current.created_by
            changes=[{"field":field,"current":getattr(current,field,""),"incoming":merged[field]} for field in mapped if _norm(getattr(current,field,""))!=_norm(merged[field])]
            status="UPDATE" if changes else "UNCHANGED"
        else:
            merged={"ticket_no":key}
            defaults={"severity":"S3","priority":"P3"}
            for field in TICKET_FIELDS:merged[field]=source.get(field) if field in mapped else defaults.get(field,"")
            merged["created_by"]=""
            changes=[{"field":field,"current":"","incoming":merged[field]} for field in mapped if _norm(merged[field])!=""]
            status="CREATE"
        actions.append({"key":key,"status":status,"current":current,"data":merged,"changes":changes})
    return actions


def reconcile_inventory(db,imported_rows: list[dict[str,Any]],mapping: dict[str,str]):
    _validate_keys(imported_rows,INVENTORY_FIELDS,"inventory")
    mapped={x for x in INVENTORY_FIELDS if x in mapping}
    existing={(x.part_number,x.location_code):x for x in db.list_inventory()}
    actions=[]
    for source in imported_rows:
        key=(source["part_number"],source["location_code"]);current=existing.get(key)
        if current:
            merged={"part_number":key[0],"location_code":key[1]}
            for field in INVENTORY_FIELDS:
                merged[field]=source.get(field) if field in mapped else getattr(current,field,"")
            changes=[
                {"field":field,"current":getattr(current,field,""),"incoming":merged[field]}
                for field in mapped if _norm(getattr(current,field,""))!=_norm(merged[field])
            ]
            status="UPDATE" if changes else "UNCHANGED"
        else:
            merged={"part_number":key[0],"location_code":key[1]}
            defaults={"quantity":0.0,"min_quantity":0.0,"unit":"ea","condition":"Available"}
            for field in INVENTORY_FIELDS:
                merged[field]=source.get(field) if field in mapped else defaults.get(field,"")
            changes=[{"field":field,"current":"","incoming":merged[field]} for field in mapped if _norm(merged[field])!=""]
            status="CREATE"
        actions.append({"key":f"{key[0]} @ {key[1]}","status":status,"current":current,"data":merged,"changes":changes})
    return actions


def apply_reconciliation(db,actions:list[dict[str,Any]],*,entity:str,user:str,allow_deletes:bool=False):
    """Apply only validated CREATE/UPDATE actions.

    Deletions are deliberately refused until an explicit, separately reviewed
    delete workflow is implemented. This prevents an incomplete workbook from
    deleting live maintenance records.
    """
    if any(action.get("status")=="DELETE" for action in actions):
        if not allow_deletes:
            raise ValueError("Workbook contains deletions; explicit delete approval is required")
        raise NotImplementedError("Bulk deletion workflow is not enabled")
    actionable=[action for action in actions if action.get("status") in {"CREATE","UPDATE"}]
    if entity=="equipment":
        saver=db.save_equipment
    elif entity=="inventory":
        saver=db.save_inventory_item
    elif entity=="ticket":
        saver=db.save_ticket
    else:
        raise ValueError(f"Unsupported reconciliation entity: {entity}")
    applied=0
    for action in actionable:
        data=dict(action["data"])
        current=action.get("current")
        if entity=="ticket":
            data["created_by"]=data.get("created_by") or user
            saver(data,current.version if current else None)
        elif entity=="equipment":
            saver(data,current.version if current else None,user=user)
        elif entity=="inventory":
            saver(data,current.version if current else None)
        applied+=1
    return {"applied":applied,"skipped":len(actions)-applied,"entity":entity}


def _reconciliation_dialog_class():
    from PySide6.QtWidgets import (
        QAbstractItemView,QDialog,QDialogButtonBox,QHeaderView,QLabel,
        QTableWidget,QTableWidgetItem,QVBoxLayout,
    )

    class ReconciliationDialog(QDialog):
        def __init__(self,title: str,actions,parent=None):
            super().__init__(parent);self.actions=actions;self.setWindowTitle(title);self.resize(1100,700)
            root=QVBoxLayout(self)
            creates=sum(1 for x in actions if x["status"]=="CREATE");updates=sum(1 for x in actions if x["status"]=="UPDATE");unchanged=sum(1 for x in actions if x["status"]=="UNCHANGED")
            label=QLabel(f"Preview: {creates} create · {updates} update · {unchanged} unchanged. Only mapped columns will change existing records.")
            label.setWordWrap(True);root.addWidget(label)
            self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(["Record","Status","Field","Current","Incoming"])
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            rows=[]
            for action in actions:
                if action["changes"]:
                    for change in action["changes"]:rows.append((action["key"],action["status"],change["field"],change["current"],change["incoming"]))
                else:rows.append((action["key"],action["status"],"","",""))
            self.table.setRowCount(len(rows))
            for r,row in enumerate(rows):
                for col,value in enumerate(row):self.table.setItem(r,col,QTableWidgetItem("" if value is None else str(value)))
            root.addWidget(self.table,1)
            buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Apply|QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);root.addWidget(buttons)
    return ReconciliationDialog


def confirm_reconciliation(parent,title: str,actions) -> bool:
    actionable=[x for x in actions if x["status"] in {"CREATE","UPDATE"}]
    if not actionable:return False
    dialog_class=_reconciliation_dialog_class()
    dialog=dialog_class(title,actions,parent)
    return dialog.exec()==dialog_class.DialogCode.Accepted


QUALIFICATION_PROTOCOL_FIELDS=["name","equipment_id","equipment_type"]
ENDORSEMENT_FIELDS=["equipment_id","current_condition","work_completed","pending_work","restrictions","next_action","next_owner"]


def _mapped_rows(df,mapping: dict[str,str]) -> list[dict[str,Any]]:
    rows=[]
    for _,source in df.iterrows():
        row={}
        for field,column in mapping.items():
            if column in df.columns:
                value=source[column]
                try:
                    import pandas as pd
                    if pd.isna(value):value=""
                except Exception:pass
                row[field]=value
        if any(str(v).strip() for v in row.values()):rows.append(row)
    return rows


def dataframe_rows(df,mapping: dict[str,str]) -> list[dict[str,Any]]:
    return _mapped_rows(df,mapping)


def reconcile_endorsements(db,imported_rows: list[dict[str,Any]],mapping: dict[str,str]):
    seen=set();mapped={x for x in ENDORSEMENT_FIELDS if x in mapping}
    existing={x.endorsement_no:x for x in db.list_endorsements()};actions=[]
    for index,source in enumerate(imported_rows,1):
        key=str(source.get("endorsement_no","")).strip()
        if not key:raise ValueError(f"handover row {index} is missing endorsement number")
        if key in seen:raise ValueError(f"Duplicate handover key at row {index}: {key}")
        seen.add(key);current=existing.get(key)
        if current:
            merged={"endorsement_no":key}
            for field in ENDORSEMENT_FIELDS:
                merged[field]=source.get(field) if field in mapped else getattr(current,field,"")
            merged.update({
                "status":current.status,"created_by":current.created_by,"created_at":current.created_at,
                "acknowledged_by":current.acknowledged_by,"acknowledged_at":current.acknowledged_at,
            })
            changes=[{"field":field,"current":getattr(current,field,""),"incoming":merged[field]} for field in mapped if _norm(getattr(current,field,""))!=_norm(merged[field])]
            status="UPDATE" if changes else "UNCHANGED"
        else:
            equipment_id=str(source.get("equipment_id","")).strip()
            if not equipment_id:raise ValueError(f"handover row {index} is missing equipment ID")
            merged={"endorsement_no":key}
            for field in ENDORSEMENT_FIELDS:merged[field]=source.get(field,"") if field in mapped else ""
            merged.update({"status":"Open","created_by":"","acknowledged_by":"","acknowledged_at":None})
            changes=[{"field":field,"current":"","incoming":merged[field]} for field in mapped if _norm(merged[field])!=""]
            status="CREATE"
        actions.append({"key":key,"status":status,"current":current,"data":merged,"changes":changes})
    return actions


def reconcile_qualification_protocols(db,imported_rows: list[dict[str,Any]],mapping: dict[str,str]):
    required={"protocol_id","name","check_id","label"}
    missing=required-set(mapping)
    if missing:raise ValueError("Qualification protocol import requires mapped fields: "+", ".join(sorted(missing)))
    grouped={}
    for index,source in enumerate(imported_rows,1):
        protocol_id=str(source.get("protocol_id","")).strip()
        if not protocol_id:raise ValueError(f"qualification row {index} is missing protocol ID")
        group=grouped.setdefault(protocol_id,{
            "protocol_id":protocol_id,"name":str(source.get("name","")).strip(),
            "equipment_id":str(source.get("equipment_id","")).strip(),
            "equipment_type":str(source.get("equipment_type","")).strip(),"checks":[],
        })
        if str(source.get("name","")).strip() and group["name"]!=str(source.get("name","")).strip():
            raise ValueError(f"Protocol {protocol_id} has inconsistent names in the workbook")
        for field in ["equipment_id","equipment_type"]:
            incoming=str(source.get(field,"")).strip()
            if incoming and group[field] and group[field]!=incoming:
                raise ValueError(f"Protocol {protocol_id} has inconsistent {field} values")
            if incoming:group[field]=incoming
        check_id=str(source.get("check_id","")).strip();label=str(source.get("label","")).strip()
        if not check_id or not label:raise ValueError(f"qualification row {index} needs check ID and check label")
        if any(x["check_id"]==check_id for x in group["checks"]):raise ValueError(f"Duplicate check {check_id} in protocol {protocol_id}")
        group["checks"].append({"check_id":check_id,"label":label,"acceptance":str(source.get("acceptance","Pass") or "Pass").strip()})
    active={x.protocol_id:x for x in db.list_qualification_protocols()}
    actions=[]
    import json
    for protocol_id,data in grouped.items():
        current=active.get(protocol_id)
        incoming_checks=data["checks"]
        if current:
            current_checks=json.loads(current.checks_json or "[]")
            changes=[]
            for field in QUALIFICATION_PROTOCOL_FIELDS:
                if _norm(getattr(current,field,""))!=_norm(data[field]):
                    changes.append({"field":field,"current":getattr(current,field,""),"incoming":data[field]})
            if current_checks!=incoming_checks:
                changes.append({"field":"checks","current":current_checks,"incoming":incoming_checks})
            status="CREATE_REVISION" if changes else "UNCHANGED"
        else:
            changes=[{"field":"protocol","current":"","incoming":data}]
            status="CREATE"
        actions.append({"key":protocol_id,"status":status,"current":current,"data":data,"changes":changes})
    return actions


def apply_extended_reconciliation(db,actions:list[dict[str,Any]],*,entity:str,user:str,workstation:str=""):
    actionable=[x for x in actions if x.get("status") in {"CREATE","UPDATE","CREATE_REVISION"}]
    applied=0
    for action in actionable:
        data=dict(action["data"]);current=action.get("current")
        if entity=="endorsement":
            data["created_by"]=data.get("created_by") or (current.created_by if current else user)
            db.save_endorsement(data,current.version if current else None)
        elif entity=="qualification_protocol":
            db.save_qualification_protocol(
                protocol_id=data["protocol_id"],name=data["name"],checks=data["checks"],
                user=user,equipment_id=data.get("equipment_id",""),equipment_type=data.get("equipment_type",""),
                create_revision=bool(current),workstation=workstation,
            )
        else:
            raise ValueError(f"Unsupported extended reconciliation entity: {entity}")
        applied+=1
    return {"applied":applied,"skipped":len(actions)-applied,"entity":entity}


def qualification_protocol_export_rows(db) -> list[dict[str,Any]]:
    import json
    rows=[]
    for protocol in db.list_qualification_protocols():
        for check in json.loads(protocol.checks_json or "[]"):
            rows.append({
                "protocol_id":protocol.protocol_id,"name":protocol.name,
                "equipment_id":protocol.equipment_id,"equipment_type":protocol.equipment_type,
                "revision":protocol.revision,"check_id":check.get("check_id",""),
                "label":check.get("label",""),"acceptance":check.get("acceptance","Pass"),
            })
    return rows


def endorsement_export_rows(db) -> list[dict[str,Any]]:
    return [{
        "endorsement_no":x.endorsement_no,"equipment_id":x.equipment_id,
        "current_condition":x.current_condition,"work_completed":x.work_completed,
        "pending_work":x.pending_work,"restrictions":x.restrictions,
        "next_action":x.next_action,"next_owner":x.next_owner,
        "status":x.status,"created_by":x.created_by,"created_at":x.created_at,
        "acknowledged_by":x.acknowledged_by,"acknowledged_at":x.acknowledged_at,
    } for x in db.list_endorsements()]
