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
