from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from PySide6.QtGui import QColor

from database import Database

STATUS_COLORS = {
    "good": QColor("#2dba73"),
    "attention": QColor("#f0a43c"),
    "critical": QColor("#e14b4b"),
    "planned": QColor("#3c8fd9"),
    "offline": QColor("#7b8790"),
}

PLANNED_STATES = {"PM", "Engineering", "Qualification"}
ATTENTION_STATES = {"Hold", "Waiting Parts", "Waiting Vendor", "Restricted"}
OFFLINE_STATES = {"Offline", "Decommissioned"}
CLOSED_TICKET_STATES = {"Closed", "Resolved", "Completed", "Cancelled"}
DEMO_FIXTURE_CODE = "FULL_DOMAIN_V4"
DEMO_WORKSTATION = "DEMO-SEED"


@dataclass(frozen=True)
class DemoTool:
    equipment_id: str
    name: str
    equipment_type: str
    manufacturer: str
    model: str
    area: str
    bay: str
    owner: str
    criticality: str
    status: str
    disposition: str
    x: float
    y: float


def demo_tools() -> list[DemoTool]:
    rows: list[DemoTool] = []
    process = [
        ("LITHO", "Stepper", "ASML", "NXT Demo", "Lithography"),
        ("ETCH", "Plasma Etcher", "TEL", "Tactras Demo", "Dry Etch"),
        ("CVD", "CVD Reactor", "Applied Materials", "Producer Demo", "Deposition"),
        ("PVD", "PVD Cluster", "Applied Materials", "Endura Demo", "Deposition"),
        ("CMP", "CMP Tool", "EBARA", "F-REX Demo", "CMP"),
        ("WET", "Wet Bench", "SCREEN", "SU Demo", "Wet Process"),
        ("MET", "Metrology", "KLA", "Inspector Demo", "Metrology"),
        ("FURN", "Furnace", "Kokusai", "Batch Furnace Demo", "Diffusion"),
    ]
    statuses = {
        3: ("Down", "Hold", "Critical"),
        7: ("Waiting Parts", "Waiting Parts", "High"),
        12: ("PM", "PM Hold", "High"),
        16: ("Engineering", "Engineering Use", "Normal"),
        21: ("Hold", "Quality Hold", "High"),
        25: ("Qualification", "Qualification", "Normal"),
    }
    for i in range(28):
        prefix, tool_type, maker, model, area = process[i % len(process)]
        bay_no = (i // 4) + 1
        slot = i % 4
        status, disposition, crit = statuses.get(i, ("Production", "Released", "Normal"))
        rows.append(
            DemoTool(
                equipment_id=f"FAB-{prefix}-{i + 1:02d}",
                name=f"{area} Tool {i + 1:02d}",
                equipment_type=tool_type,
                manufacturer=maker,
                model=model,
                area=area,
                bay=f"BAY-{bay_no:02d}",
                owner=["Equipment Eng", "Process Eng", "Manufacturing", "Facilities"][i % 4],
                criticality=crit,
                status=status,
                disposition=disposition,
                x=135 + slot * 350,
                y=145 + (bay_no - 1) * 105,
            )
        )
    return rows


def _run(errors: list[str], label: str, fn: Callable[[], Any]):
    try:
        return fn()
    except Exception as exc:
        errors.append(f"{label}: {exc}")
        return None


def _demo_asset(name: str) -> str:
    return str(Path(__file__).with_name("demo_assets") / name)


def _already_seeded(db: Database) -> bool:
    return any(x.code == DEMO_FIXTURE_CODE for x in db.list_config_options("DEMO_FIXTURE", active_only=False))


def seed_demo_data(db: Database, username: str = "") -> dict[str, Any]:
    """Seed an isolated demo database across all operator-facing EMS domains.

    System-only tables (schema migrations, audit internals and generated delivery
    queues) are intentionally populated by their owning workflows instead of by
    direct synthetic inserts.
    """
    actor = (username or "").strip() or "demo"
    demo_url=str(getattr(db,"url","") or "")
    allow_any=os.getenv("EMS_ALLOW_DEMO_SEED","0").strip().lower() in {"1","true","yes","on"}
    if "equipment_manager_demo.db" not in demo_url and not allow_any:
        return {
            "changed":False,
            "errors":["Demo seeding blocked: database is not the isolated EMS demo database."],
            "message":"Demo data was not written to the active database.",
        }
    if _already_seeded(db):
        return {"changed": False, "errors": [], "message": "Full EMS demo fixture already present."}

    errors: list[str] = []
    now = datetime.now().replace(second=0, microsecond=0)
    today = now.replace(hour=0, minute=0)
    sop_path = _demo_asset("DEMO_PM_SOP.md")
    troubleshooting_path = _demo_asset("DEMO_TROUBLESHOOTING.md")

    # Reusable role accounts for demo/testing.  These exist only in the isolated demo DB.
    demo_password=os.getenv("EMS_DEMO_PASSWORD","DemoEMS2026!")
    existing_users={u.username for u in db.list_users()}
    for demo_user,display_name,role in [
        ("demo_operator","Demo Operator","Operator"),
        ("demo_tech","Demo Technician","Technician"),
        ("demo_engineer","Demo Equipment Engineer","Equipment Engineer"),
        ("demo_supervisor","Demo Supervisor","Supervisor"),
        ("demo_manager","Demo Manager","Manager"),
        ("demo_document","Demo Document Controller","Document Controller"),
        ("demo_inventory","Demo Inventory Controller","Inventory Controller"),
    ]:
        if demo_user not in existing_users:
            _run(errors,f"user {demo_user}",lambda demo_user=demo_user,display_name=display_name,role=role: db.create_user(
                demo_user,display_name,demo_password,role
            ))

    # Equipment master: every editable registry field is populated.
    existing_equipment = {x.equipment_id for x in db.list_equipment()}
    for tool in demo_tools():
        if tool.equipment_id in existing_equipment:
            continue
        _run(errors, f"equipment {tool.equipment_id}", lambda tool=tool: db.save_equipment(
            {
                "equipment_id": tool.equipment_id,
                "name": tool.name,
                "equipment_type": tool.equipment_type,
                "manufacturer": tool.manufacturer,
                "model": tool.model,
                "serial_number": f"DEMO-SN-{tool.equipment_id}",
                "asset_number": f"DEMO-ASSET-{tool.equipment_id[-2:]}",
                "site": "DEMO SEMICONDUCTOR FAB",
                "building": "FAB-A",
                "floor": "1F",
                "area": tool.area,
                "line_cell": tool.bay,
                "owner": tool.owner,
                "criticality": tool.criticality,
                "status": tool.status,
                "disposition": tool.disposition,
                "map_x": tool.x,
                "map_y": tool.y,
            },
            user=actor,
            workstation=DEMO_WORKSTATION,
        ))

    # Components/modules with parent-child structure and life/usage values.
    component_rows = [
        {
            "component_id": "DEMO-PVD04-CHAMBER-A", "equipment_id": "FAB-PVD-04", "parent_component_id": "",
            "name": "Process Chamber A", "component_type": "Chamber", "manufacturer": "Demo Components",
            "model": "CH-A100", "serial_number": "CH-A100-0004", "part_number": "DEMO-CHAMBER-A",
            "life_limit_value": 12000.0, "life_limit_unit": "RF h", "usage_value": 7450.0,
            "notes": "Primary PVD process chamber; demo lifecycle data.",
        },
        {
            "component_id": "DEMO-PVD04-RF-MATCH", "equipment_id": "FAB-PVD-04", "parent_component_id": "DEMO-PVD04-CHAMBER-A",
            "name": "RF Match Network", "component_type": "RF", "manufacturer": "Demo RF",
            "model": "MATCH-2K", "serial_number": "RF-04-8821", "part_number": "DEMO-RF-MATCH",
            "life_limit_value": 8000.0, "life_limit_unit": "RF h", "usage_value": 6120.0,
            "notes": "Replaceable/repairable RF match assembly.",
        },
        {
            "component_id": "DEMO-CVD03-MFC-01", "equipment_id": "FAB-CVD-03", "parent_component_id": "",
            "name": "Process Gas MFC 01", "component_type": "MFC", "manufacturer": "Demo Flow",
            "model": "MFC-500", "serial_number": "MFC-03-204", "part_number": "DEMO-MFC-001",
            "life_limit_value": 24.0, "life_limit_unit": "months", "usage_value": 18.0,
            "notes": "Gas-flow control component used by condition-based PM demo.",
        },
    ]
    existing_components = {x.component_id for x in db.list_components()}
    for row in component_rows:
        if row["component_id"] not in existing_components:
            _run(errors, f"component {row['component_id']}", lambda row=row: db.save_component(
                row, user=actor, workstation=DEMO_WORKSTATION
            ))

    # Equipment meters and readings. Includes counter and gauge behavior.
    meter_rows = [
        ("FAB-PVD-04", "WAFER_COUNT", "Processed wafer count", "wafers", "COUNTER", 125000.0, 125340.0),
        ("FAB-PVD-04", "RF_HOURS", "RF-on accumulated time", "h", "COUNTER", 6100.0, 6120.5),
        ("FAB-CVD-03", "VAC_PRESSURE", "Base vacuum pressure", "Pa", "GAUGE", 0.8, 1.35),
        ("FAB-ETCH-02", "RF_HOURS", "RF-on accumulated time", "h", "COUNTER", 4400.0, 4412.0),
    ]
    for eq, code, name, unit, mode, initial, reading in meter_rows:
        current = next((x for x in db.list_meters(eq) if x.meter_code == code), None)
        if not current:
            current = _run(errors, f"meter {eq}:{code}", lambda eq=eq,code=code,name=name,unit=unit,mode=mode,initial=initial: db.save_meter({
                "equipment_id": eq, "meter_code": code, "name": name, "unit": unit,
                "meter_mode": mode, "current_value": initial, "active": True,
            }))
        if current and not db.list_meter_readings(eq, code):
            _run(errors, f"meter reading {eq}:{code}", lambda eq=eq,code=code,reading=reading,current=current: db.record_meter_reading(
                eq, code, reading, actor, note="Deterministic demo reading", workstation=DEMO_WORKSTATION,
                expected_version=current.version,
            ))

    # Inventory/storage/catalog/PO/rotables.
    locations = [
        {"location_code":"DEMO-STORES-A1","name":"Main Spare Parts Store","site":"DEMO SEMICONDUCTOR FAB","building":"FAB-A","floor":"1F","area":"Stores","cabinet":"CAB-A","shelf":"SHELF-01","drawer_bin":"BIN-01","map_x":80.0,"map_y":930.0,"image_path":""},
        {"location_code":"DEMO-PM-STAGE","name":"PM Kitting / Staging","site":"DEMO SEMICONDUCTOR FAB","building":"FAB-A","floor":"1F","area":"Maintenance","cabinet":"STAGE-01","shelf":"RACK-A","drawer_bin":"LEVEL-02","map_x":330.0,"map_y":930.0,"image_path":""},
    ]
    location_codes = {x.location_code for x in db.list_storage_locations()}
    for row in locations:
        if row["location_code"] not in location_codes:
            _run(errors, f"location {row['location_code']}", lambda row=row: db.save_storage_location(row))

    catalog_rows = [
        {"part_number":"DEMO-MFC-001","description":"Process gas mass flow controller","category":"Gas Delivery","manufacturer":"Demo Flow","supplier":"Demo Supplier Japan","supplier_part_number":"SUP-MFC-500","barcode":"4900000000011","lead_time_days":21,"reorder_qty":2.0,"notes":"Critical spare for CVD tools","active":True},
        {"part_number":"DEMO-O-RING-KIT","description":"Chamber seal O-ring PM kit","category":"Consumable","manufacturer":"Demo Seal","supplier":"Demo Supplier Japan","supplier_part_number":"SUP-OR-100","barcode":"4900000000028","lead_time_days":7,"reorder_qty":10.0,"notes":"Standard chamber PM consumable","active":True},
        {"part_number":"DEMO-RF-MATCH","description":"Repairable RF match network","category":"Rotable","manufacturer":"Demo RF","supplier":"Demo RF Service","supplier_part_number":"SUP-RF-2K","barcode":"4900000000035","lead_time_days":30,"reorder_qty":1.0,"notes":"Tracked repairable asset","active":True},
    ]
    catalog_keys = {x.part_number for x in db.list_part_catalog()}
    for row in catalog_rows:
        if row["part_number"] not in catalog_keys:
            _run(errors, f"part catalog {row['part_number']}", lambda row=row: db.save_part_catalog(row))

    inventory_rows = [
        {"part_number":"DEMO-MFC-001","description":"Process gas mass flow controller","category":"Gas Delivery","manufacturer":"Demo Flow","model":"MFC-500","compatible_equipment":"CVD Reactor","quantity":1.0,"min_quantity":2.0,"unit":"ea","condition":"Available","location_code":"DEMO-STORES-A1","image_path":"","notes":"Below minimum to exercise reorder queue."},
        {"part_number":"DEMO-O-RING-KIT","description":"Chamber seal O-ring PM kit","category":"Consumable","manufacturer":"Demo Seal","model":"OR-100","compatible_equipment":"PVD Cluster, Plasma Etcher","quantity":18.0,"min_quantity":6.0,"unit":"kit","condition":"Available","location_code":"DEMO-STORES-A1","image_path":"","notes":"Healthy stock example."},
        {"part_number":"DEMO-RF-MATCH","description":"Repairable RF match network","category":"Rotable","manufacturer":"Demo RF","model":"MATCH-2K","compatible_equipment":"PVD Cluster, Plasma Etcher","quantity":1.0,"min_quantity":1.0,"unit":"ea","condition":"Available","location_code":"DEMO-STORES-A1","image_path":"","notes":"Rotable stock example."},
    ]
    inventory_keys={(x.part_number,x.location_code) for x in db.list_inventory()}
    for row in inventory_rows:
        if (row["part_number"],row["location_code"]) not in inventory_keys:
            _run(errors, f"inventory {row['part_number']}", lambda row=row: db.save_inventory_item(row))

    if "DEMO-O-RING-KIT-ALT" not in {x.part_number for x in db.list_part_catalog()}:
        _run(errors, "alternate catalog", lambda: db.save_part_catalog({
            "part_number":"DEMO-O-RING-KIT-ALT","description":"Alternate chamber seal kit","category":"Consumable",
            "manufacturer":"Demo Seal B","supplier":"Backup Supplier","supplier_part_number":"ALT-OR-100",
            "barcode":"4900000000042","lead_time_days":10,"reorder_qty":5.0,"notes":"Approved alternate part","active":True,
        }))
    if not db.list_part_alternates("DEMO-O-RING-KIT"):
        _run(errors, "part alternate", lambda: db.save_part_alternate(
            "DEMO-O-RING-KIT","DEMO-O-RING-KIT-ALT",actor,True,"Approved demo alternate."
        ))

    if not any(x.asset_id=="DEMO-ROT-RF-001" for x in db.list_rotables()):
        _run(errors, "rotable", lambda: db.register_rotable({
            "asset_id":"DEMO-ROT-RF-001","part_number":"DEMO-RF-MATCH","serial_number":"ROT-RF-0001",
            "description":"Repairable RF match network","current_location":"DEMO-STORES-A1",
            "notes":"Serviceable spare ready for installation.",
        }, actor))

    if not any(x.order_no=="DEMO-PO-001" for x in db.list_supplier_orders()):
        order=_run(errors, "supplier order", lambda: db.save_supplier_order({
            "order_no":"DEMO-PO-001","supplier":"Demo Supplier Japan","order_date":now-timedelta(days=2),
            "expected_at":now+timedelta(days=12),"external_reference":"ERP-DEMO-8842",
            "notes":"Demo replenishment order for critical spares.",
        }, actor))
        if order:
            _run(errors, "supplier line 1", lambda: db.add_supplier_order_line(order.order_no,{
                "part_number":"DEMO-MFC-001","supplier_part_number":"SUP-MFC-500","ordered_qty":2.0,
                "received_qty":0.0,"unit_cost":185000.0,"currency":"JPY","destination_location":"DEMO-STORES-A1",
                "status":"Open","note":"Expedite if stock reaches zero.",
            },actor))
            _run(errors, "supplier line 2", lambda: db.add_supplier_order_line(order.order_no,{
                "part_number":"DEMO-O-RING-KIT","supplier_part_number":"SUP-OR-100","ordered_qty":10.0,
                "received_qty":0.0,"unit_cost":12000.0,"currency":"JPY","destination_location":"DEMO-STORES-A1",
                "status":"Open","note":"Routine replenishment.",
            },actor))
            _run(errors, "supplier submit", lambda: db.submit_supplier_order(order.order_no,actor,order.version))

    # PM definitions, requirements, specifications and a calendar populated around today.
    pm_definitions = [
        {"pm_id":"DEMO-PM-PVD-WEEKLY","name":"Weekly PVD chamber / vacuum inspection","equipment_id":"FAB-PVD-04","schedule_type":"Interval","frequency_value":7.0,"frequency_unit":"days","anchor_mode":"Original Due","early_window_days":2,"grace_days":2,"estimated_hours":2.0,"required_people":1,"required_skill":"VACUUM-PM","required_parts":"DEMO-O-RING-KIT:1","sop_path":sop_path,"active":True,"revision":1},
        {"pm_id":"DEMO-PM-ETCH-RF","name":"Etcher RF system monthly PM","equipment_id":"FAB-ETCH-02","schedule_type":"Interval","frequency_value":30.0,"frequency_unit":"days","anchor_mode":"Original Due","early_window_days":4,"grace_days":4,"estimated_hours":3.0,"required_people":2,"required_skill":"RF-MAINT","required_parts":"DEMO-RF-MATCH:1","sop_path":sop_path,"active":True,"revision":1},
        {"pm_id":"DEMO-PM-CVD-MFC","name":"CVD MFC verification","equipment_id":"FAB-CVD-03","schedule_type":"Condition","frequency_value":90.0,"frequency_unit":"days","anchor_mode":"Completion","early_window_days":5,"grace_days":7,"estimated_hours":1.5,"required_people":1,"required_skill":"GAS-SYSTEM","required_parts":"DEMO-MFC-001:1","sop_path":sop_path,"active":True,"revision":1},
        {"pm_id":"DEMO-PM-PVD-USAGE","name":"PVD wafer-count usage PM","equipment_id":"FAB-PVD-04","schedule_type":"Usage","frequency_value":100.0,"frequency_unit":"wafers","anchor_mode":"Meter","early_window_days":0,"grace_days":1,"estimated_hours":1.0,"required_people":1,"required_skill":"","required_parts":"","sop_path":sop_path,"active":True,"revision":1},
        {"pm_id":"DEMO-PM-CVD-CONDITION","name":"CVD vacuum condition inspection","equipment_id":"FAB-CVD-03","schedule_type":"Condition","frequency_value":None,"frequency_unit":"","anchor_mode":"Condition","early_window_days":0,"grace_days":1,"estimated_hours":1.0,"required_people":1,"required_skill":"","required_parts":"","sop_path":sop_path,"active":True,"revision":1},
    ]
    existing_pm={x.pm_id for x in db.list_pm_definitions()}
    for row in pm_definitions:
        if row["pm_id"] not in existing_pm:
            _run(errors, f"PM definition {row['pm_id']}", lambda row=row: db.save_pm_definition(row))

    specs = [
        {"pm_id":"DEMO-PM-PVD-WEEKLY","step_no":1,"activity":"Inspect chamber seals","method":"Visual inspection","input_type":"Text","unit":"","target":None,"warning_low":None,"warning_high":None,"control_low":None,"control_high":None,"spec_low":None,"spec_high":None,"acceptance_text":"No damage or contamination","reaction_plan":"Create incident and replace seal if damaged.","sop_path":sop_path,"sop_page":"1","sop_section":"3","screenshot_required":True,"comment_required":True,"revision":1,"active":True},
        {"pm_id":"DEMO-PM-PVD-WEEKLY","step_no":2,"activity":"Measure base pressure","method":"Stabilized gauge reading","input_type":"Numeric","unit":"Pa","target":0.8,"warning_low":0.5,"warning_high":1.0,"control_low":0.4,"control_high":1.2,"spec_low":0.3,"spec_high":1.5,"acceptance_text":"Within specification","reaction_plan":"Leak check, inspect O-rings, escalate abnormal result.","sop_path":sop_path,"sop_page":"1","sop_section":"4","screenshot_required":False,"comment_required":False,"revision":1,"active":True},
        {"pm_id":"DEMO-PM-ETCH-RF","step_no":1,"activity":"Verify RF forward/reflected power","method":"Maintenance diagnostic","input_type":"Numeric","unit":"W","target":1000.0,"warning_low":950.0,"warning_high":1050.0,"control_low":900.0,"control_high":1100.0,"spec_low":850.0,"spec_high":1150.0,"acceptance_text":"Stable response","reaction_plan":"Inspect match network and connections.","sop_path":sop_path,"sop_page":"1","sop_section":"4","screenshot_required":True,"comment_required":True,"revision":1,"active":True},
        {"pm_id":"DEMO-PM-CVD-MFC","step_no":1,"activity":"Verify MFC response","method":"Reference flow check","input_type":"Numeric","unit":"sccm","target":500.0,"warning_low":490.0,"warning_high":510.0,"control_low":480.0,"control_high":520.0,"spec_low":475.0,"spec_high":525.0,"acceptance_text":"Within ±5%","reaction_plan":"Replace MFC and qualify gas delivery.","sop_path":sop_path,"sop_page":"1","sop_section":"4","screenshot_required":False,"comment_required":True,"revision":1,"active":True},
        {"pm_id":"DEMO-PM-PVD-USAGE","step_no":1,"activity":"Inspect high-usage wear surfaces","method":"Visual inspection at wafer-count threshold","input_type":"Text","unit":"","target":None,"warning_low":None,"warning_high":None,"control_low":None,"control_high":None,"spec_low":None,"spec_high":None,"acceptance_text":"Pass","reaction_plan":"Create corrective work order if abnormal wear is found.","sop_path":sop_path,"sop_page":"1","sop_section":"3","screenshot_required":False,"comment_required":True,"revision":1,"active":True},
        {"pm_id":"DEMO-PM-CVD-CONDITION","step_no":1,"activity":"Inspect vacuum integrity after condition trigger","method":"Leak check and pressure stabilization","input_type":"Numeric","unit":"Pa","target":0.8,"warning_low":0.5,"warning_high":1.0,"control_low":0.4,"control_high":1.2,"spec_low":0.3,"spec_high":1.5,"acceptance_text":"Within specification","reaction_plan":"Escalate recurring condition trigger to Incident / RCA.","sop_path":sop_path,"sop_page":"1","sop_section":"4","screenshot_required":False,"comment_required":True,"revision":1,"active":True},
    ]
    existing_specs={(x.pm_id,x.step_no) for x in db.list_pm_specs()}
    for row in specs:
        if (row["pm_id"],row["step_no"]) not in existing_specs:
            _run(errors, f"PM spec {row['pm_id']}:{row['step_no']}", lambda row=row: db.upsert_pm_spec(row))

    requirements = [
        {"requirement_id":"DEMO-REQ-PVD-CERT","pm_id":"DEMO-PM-PVD-WEEKLY","requirement_type":"CERTIFICATION","requirement_key":"VACUUM-PM","description":"Vacuum maintenance certification","quantity":1.0,"mandatory":True,"active":True,"revision":1},
        {"requirement_id":"DEMO-REQ-PVD-SAFETY","pm_id":"DEMO-PM-PVD-WEEKLY","requirement_type":"SAFETY","requirement_key":"LOTO","description":"Verify LOTO and stored-energy isolation","quantity":1.0,"mandatory":True,"active":True,"revision":1},
        {"requirement_id":"DEMO-REQ-PVD-PART","pm_id":"DEMO-PM-PVD-WEEKLY","requirement_type":"PART","requirement_key":"DEMO-O-RING-KIT","description":"Chamber O-ring PM kit","quantity":1.0,"mandatory":True,"active":True,"revision":1},
        {"requirement_id":"DEMO-REQ-PVD-DOC","pm_id":"DEMO-PM-PVD-WEEKLY","requirement_type":"DOCUMENT","requirement_key":"DEMO-SOP-PM-001","description":"Read current PM SOP before execution","quantity":1.0,"mandatory":True,"active":True,"revision":1},
    ]
    existing_req={x.requirement_id for x in db.list_pm_requirements(active_only=False)}
    for row in requirements:
        if row["requirement_id"] not in existing_req:
            _run(errors, f"PM requirement {row['requirement_id']}", lambda row=row: db.upsert_pm_requirement(row))

    if not any(x.username==actor and x.cert_code=="VACUUM-PM" for x in db.list_technician_certifications(actor)):
        _run(errors, "demo technician certification", lambda: db.save_technician_certification({
            "username":actor,"cert_code":"VACUUM-PM","issuer":"Demo Training Center",
            "issued_at":now-timedelta(days=120),"expires_at":now+timedelta(days=245),
            "active":True,"note":"Demo qualification used by PM readiness.",
        }))

    task_specs = [
        ("FAB-PVD-04","DEMO-PM-PVD-WEEKLY","Weekly PVD chamber / vacuum inspection",-1,9,2.0,"High"),
        ("FAB-ETCH-02","DEMO-PM-ETCH-RF","Etcher RF system monthly PM",1,13,3.0,"Normal"),
        ("FAB-CVD-03","DEMO-PM-CVD-MFC","CVD MFC verification",3,10,1.5,"High"),
        ("FAB-PVD-04","DEMO-PM-PVD-WEEKLY","Weekly PVD chamber / vacuum inspection",6,8,2.0,"Normal"),
    ]
    seeded_tasks=[]
    existing_tasks=db.list_pm_tasks()
    for eq,pm_id,name,day_offset,hour,duration,priority in task_specs:
        due=today+timedelta(days=day_offset,hours=hour)
        task=next((x for x in existing_tasks if x.equipment_id==eq and x.pm_id==pm_id and x.original_due_date and x.original_due_date.date()==due.date()),None)
        if not task:
            task=_run(errors,f"PM task {eq}:{pm_id}:{day_offset}",lambda eq=eq,pm_id=pm_id,name=name,due=due,duration=duration,priority=priority: db.upsert_pm_task({
                "equipment_id":eq,"pm_id":pm_id,"pm_name":name,"original_due_date":due,
                "scheduled_date":due,"last_completion_date":due-timedelta(days=30),
                "status":"Scheduled","assigned_to":actor,"estimated_hours":duration,"priority":priority,
                "deferral_reason":"","sop_path":sop_path,"report_path":"",
            }))
            if task:existing_tasks.append(task)
        if task:
            seeded_tasks.append(task)
            if not db.get_pm_task_schedule(task.id):
                _run(errors,f"PM calendar {task.id}",lambda task=task,due=due,duration=duration: db.schedule_pm_task(
                    task.id,actor,start_at=due,end_at=due+timedelta(hours=duration),assigned_to=actor,
                    reason="Demo calendar fixture",expected_task_version=task.version,workstation=DEMO_WORKSTATION,
                ))

    pvd_task=next((x for x in seeded_tasks if x.pm_id=="DEMO-PM-PVD-WEEKLY"),None)
    if pvd_task and not any(x.pm_task_id==pvd_task.id and x.part_number=="DEMO-O-RING-KIT" for x in db.list_reservations()):
        _run(errors,"PM part reservation",lambda: db.reserve_inventory(
            "DEMO-O-RING-KIT",1.0,actor,pm_task_id=pvd_task.id,equipment_id=pvd_task.equipment_id,
            location_code="DEMO-STORES-A1",note="Reserved for demo weekly chamber PM."
        ))

    # Secondary PM states for demo/test coverage: kit staging, execution/results,
    # deferral, usage trigger and condition trigger.
    if pvd_task:
        kit=db.pm_kit_stage(pvd_task.id)
        if not kit:
            _run(errors,"PM kit stage",lambda: db.set_pm_kit_stage(
                pvd_task.id,"Staged",actor,staging_location="DEMO-PM-STAGE",
                note="Demo kit staged with reserved chamber seal.",
            ))
        execution=db.get_pm_execution_for_task(pvd_task.id)
        if not execution:
            execution=_run(errors,"PM execution",lambda: db.start_pm_execution(pvd_task.id,actor))
        if execution:
            acked={x.requirement_id for x in db.list_pm_requirement_acks(execution.id)}
            for req in db.list_pm_execution_requirements(execution.id):
                if req.requirement_type!="CERTIFICATION" and req.requirement_id not in acked:
                    _run(errors,f"PM requirement ack {req.requirement_id}",lambda req=req: db.acknowledge_pm_requirement(
                        execution.id,req.requirement_id,actor,
                        note="Acknowledged for demo execution.",evidence_path=sop_path if req.requirement_type=="DOCUMENT" else "",
                    ))
            result_steps={x.step_no for x in db.list_pm_results(execution.id)}
            if 1 not in result_steps:
                _run(errors,"PM result step 1",lambda: db.save_pm_result(execution.id,1,{
                    "value_text":"Pass","value_numeric":None,"comment":"Seal condition acceptable for demo.",
                    "evidence_path":"","entered_by":actor,
                }))
            if 2 not in result_steps:
                _run(errors,"PM result step 2",lambda: db.save_pm_result(execution.id,2,{
                    "value_text":"0.82","value_numeric":0.82,"comment":"Base pressure within specification.",
                    "evidence_path":"","entered_by":actor,
                }))

    etch_task=next((x for x in seeded_tasks if x.pm_id=="DEMO-PM-ETCH-RF"),None)
    if etch_task and not any(x.task_id==etch_task.id for x in db.list_pm_deferrals()):
        _run(errors,"PM deferral",lambda: db.request_pm_deferral(
            etch_task.id,etch_task.original_due_date+timedelta(days=5),
            "Production campaign blocks the planned maintenance window.",
            "RF system is stable; risk increases if the task extends beyond five days.",
            "Daily RF trend review and immediate stop on reflected-power excursion.",
            actor,DEMO_WORKSTATION,expected_task_version=etch_task.version,
        ))

    if not any(x.trigger_id=="DEMO-USAGE-PVD-WAFERS" for x in db.list_pm_usage_triggers("FAB-PVD-04")):
        _run(errors,"usage PM trigger",lambda: db.save_pm_usage_trigger({
            "trigger_id":"DEMO-USAGE-PVD-WAFERS","equipment_id":"FAB-PVD-04","pm_id":"DEMO-PM-PVD-USAGE",
            "meter_code":"WAFER_COUNT","interval_value":100.0,"start_value":125300.0,"active":True,
        }))
    if not db.list_pm_usage_occurrences("DEMO-USAGE-PVD-WAFERS"):
        meter=next((x for x in db.list_meters("FAB-PVD-04") if x.meter_code=="WAFER_COUNT"),None)
        if meter and meter.current_value<125410.0:
            _run(errors,"usage trigger occurrence",lambda meter=meter: db.record_meter_reading(
                "FAB-PVD-04","WAFER_COUNT",125410.0,actor,
                note="Demo reading crosses usage-PM threshold.",workstation=DEMO_WORKSTATION,
                expected_version=meter.version,
            ))

    if not any(x.trigger_id=="DEMO-COND-CVD-VAC" for x in db.list_pm_condition_triggers("FAB-CVD-03")):
        _run(errors,"condition PM trigger",lambda: db.save_pm_condition_trigger({
            "trigger_id":"DEMO-COND-CVD-VAC","equipment_id":"FAB-CVD-03","pm_id":"DEMO-PM-CVD-CONDITION",
            "meter_code":"VAC_PRESSURE","comparator":">","threshold":1.4,"reset_threshold":1.0,
            "latched":False,"active":True,
        }))
    if not db.list_pm_condition_occurrences("DEMO-COND-CVD-VAC"):
        meter=next((x for x in db.list_meters("FAB-CVD-03") if x.meter_code=="VAC_PRESSURE"),None)
        if meter and meter.current_value<=1.4:
            _run(errors,"condition trigger occurrence",lambda meter=meter: db.record_meter_reading(
                "FAB-CVD-03","VAC_PRESSURE",1.6,actor,
                note="Demo reading crosses condition-PM threshold.",workstation=DEMO_WORKSTATION,
                expected_version=meter.version,
            ))

    # Incidents/tickets with operational context, lots, RCA, investigations and actions.
    tickets = [
        {"ticket_no":"DEMO-ISSUE-001","equipment_id":"FAB-PVD-04","title":"Vacuum recovery timeout after wafer transfer","description":"Load-lock pressure recovery exceeds control limit. Tool stopped to prevent repeat wafer handling alarms.","severity":"S1","priority":"P1","owner":actor,"root_cause":"Suspected degraded chamber seal; RCA in progress.","corrective_action":"Replace seal kit, leak-check and verify base pressure.","verification":"Post-repair qualification and monitor lot required.","created_by":actor},
        {"ticket_no":"DEMO-ISSUE-002","equipment_id":"FAB-FURN-08","title":"Replacement MFC awaiting kitting","description":"Gas-flow drift confirmed during verification. Replacement part is reserved but not yet delivered to the bay.","severity":"S2","priority":"P2","owner":actor,"root_cause":"MFC response drift beyond action limit.","corrective_action":"Replace MFC and execute gas-flow verification.","verification":"Reference flow check and monitor lot.","created_by":actor},
        {"ticket_no":"DEMO-ISSUE-003","equipment_id":"FAB-CMP-13","title":"Quarterly PM in progress","description":"Scheduled preventive maintenance. Pad, conditioner and slurry delivery checks are being executed.","severity":"S4","priority":"P4","owner":actor,"root_cause":"Not applicable — planned maintenance.","corrective_action":"Complete controlled PM steps.","verification":"PM completion checklist.","created_by":actor},
        {"ticket_no":"DEMO-ISSUE-004","equipment_id":"FAB-CVD-19","title":"Particle excursion containment","description":"Post-maintenance particle result exceeded the internal action level. Tool is on quality hold pending chamber-clean verification.","severity":"S2","priority":"P2","owner":actor,"root_cause":"Under investigation.","corrective_action":"Contain affected lots and perform chamber clean.","verification":"Particle monitor wafer acceptance.","created_by":actor},
        {"ticket_no":"DEMO-ISSUE-005","equipment_id":"FAB-ETCH-26","title":"Qualification lot required","description":"Hardware change completed. Tool remains in qualification until monitor-lot and matching checks are accepted.","severity":"S3","priority":"P3","owner":actor,"root_cause":"Planned hardware change.","corrective_action":"Execute matching and qualification protocol.","verification":"Qualification protocol approval.","created_by":actor},
    ]
    existing_tickets={x.ticket_no:x for x in db.list_tickets()}
    for payload in tickets:
        if payload["ticket_no"] not in existing_tickets:
            row=_run(errors,f"ticket {payload['ticket_no']}",lambda payload=payload: db.save_ticket(payload,workstation=DEMO_WORKSTATION))
            if row:existing_tickets[row.ticket_no]=row

    t1=existing_tickets.get("DEMO-ISSUE-001")
    if t1:
        if not db.ticket_operational_control(t1.ticket_no):
            _run(errors,"ticket controls",lambda: db.save_ticket_operational_control(t1.ticket_no,{
                "containment":"Tool stopped; affected wafers quarantined; no additional lots dispatched.",
                "production_impact":"PVD capacity reduced by one chamber.",
                "affected_lots":"DEMO-LOT-A1001, DEMO-LOT-A1002",
                "safety_quality_risk":"Quality risk: incomplete process due to unstable vacuum recovery.",
                "response_due_at":now+timedelta(minutes=30),"containment_due_at":now+timedelta(hours=1),
                "resolution_due_at":now+timedelta(hours=8),"escalation_level":1,
                "escalated_at":now,"escalation_reason":"P1 production-impacting equipment event.",
            },actor,DEMO_WORKSTATION))
        _run(errors,"ticket lots",lambda: db.replace_entity_lots("TICKET",t1.ticket_no,["DEMO-LOT-A1001","DEMO-LOT-A1002"],equipment_id=t1.equipment_id,user=actor,workstation=DEMO_WORKSTATION))
        if not db.list_incident_whys(t1.ticket_no):
            why_rows=[
                (1,"Why did transfer recovery time out?","Load-lock pressure did not recover within the control limit."),
                (2,"Why was pressure recovery slow?","Leak rate increased after chamber cycling."),
                (3,"Why did leak rate increase?","Seal compression was inconsistent during inspection."),
                (4,"Why was seal compression inconsistent?","The installed seal showed wear near the transfer interface."),
                (5,"Why was the worn seal not replaced earlier?","Usage trend was not previously connected to this inspection trigger."),
            ]
            for seq,q,a in why_rows:_run(errors,f"why {seq}",lambda seq=seq,q=q,a=a: db.save_incident_why(t1.ticket_no,seq,q,a,actor,workstation=DEMO_WORKSTATION))
        if not db.list_incident_causal_factors(t1.ticket_no):
            _run(errors,"causal factor",lambda: db.save_incident_causal_factor(t1.ticket_no,{
                "category":"Machine","factor_type":"Verified Root Cause","description":"Worn chamber seal increased leak rate.",
                "evidence":"Visual wear pattern plus elevated stabilized pressure.","status":"Open",
            },actor,workstation=DEMO_WORKSTATION))
            _run(errors,"contributing factor",lambda: db.save_incident_causal_factor(t1.ticket_no,{
                "category":"Process","factor_type":"Contributing","description":"Seal usage was tracked but not tied to a condition-based inspection threshold.",
                "evidence":"Maintenance history and meter review.","status":"Open",
            },actor,workstation=DEMO_WORKSTATION))
        if not db.list_incident_actions(t1.ticket_no):
            _run(errors,"incident action",lambda: db.save_incident_action(t1.ticket_no,{
                "action_type":"Corrective","description":"Replace chamber seal and perform leak check.",
                "owner":actor,"due_at":now+timedelta(hours=4),"effectiveness_criteria":"Base pressure <= 1.0 Pa and no repeat recovery alarms.",
            },actor,workstation=DEMO_WORKSTATION))
            _run(errors,"preventive action",lambda: db.save_incident_action(t1.ticket_no,{
                "action_type":"Preventive","description":"Connect seal inspection to RF-hours usage trigger.",
                "owner":actor,"due_at":now+timedelta(days=7),"effectiveness_criteria":"Trigger generates PM before wear limit.",
            },actor,workstation=DEMO_WORKSTATION))
        if not db.list_ticket_investigations(t1.ticket_no):
            _run(errors,"investigation",lambda: db.add_ticket_investigation(t1.ticket_no,{
                "observation":"Vacuum recovery alarm repeats after wafer transfer.",
                "check_performed":"Reviewed pressure trace, valve feedback and seal condition.",
                "result":"Pressure decay correlates with visible seal wear.",
                "conclusion":"Seal degradation is the leading failure mechanism.",
                "action":"Replace seal kit and qualify chamber.",
                "evidence_path":troubleshooting_path,"entered_by":actor,
            }))

    # Deterministic alarms, some linked to incidents.
    alarms = [
        ("DEMO-ALARM-001","FAB-PVD-04","VAC_RECOVERY_TIMEOUT","Critical","Load-lock vacuum recovery exceeded 45 s","DEMO-ISSUE-001",now-timedelta(minutes=90)),
        ("DEMO-ALARM-002","FAB-PVD-04","VAC_RECOVERY_TIMEOUT","Critical","Repeat vacuum recovery timeout","DEMO-ISSUE-001",now-timedelta(minutes=87)),
        ("DEMO-ALARM-003","FAB-PVD-04","VAC_RECOVERY_TIMEOUT","Critical","Third recovery timeout within burst window","DEMO-ISSUE-001",now-timedelta(minutes=84)),
        ("DEMO-ALARM-004","FAB-CVD-19","PARTICLE_MONITOR_HIGH","Warning","Particle monitor exceeded action level","DEMO-ISSUE-004",now-timedelta(hours=3)),
    ]
    existing_alarm={x.event_key for x in db.list_alarms(active_only=False)}
    for key,eq,code,severity,message,ticket,when in alarms:
        if key not in existing_alarm:
            _run(errors,f"alarm {key}",lambda key=key,eq=eq,code=code,severity=severity,message=message,ticket=ticket,when=when: db.ingest_alarm(
                eq,code,severity=severity,message=message,source="DEMO-EAP",event_key=key,
                occurred_at=when,related_ticket=ticket,raw_payload={"tool":eq,"alarm":code,"demo":True},
            ))

    # Work orders: ticket-driven, PM-driven and pure engineering, all visible on the calendar.
    work_orders={x.work_order_no:x for x in db.list_work_orders()}
    if "DEMO-WO-001" not in work_orders:
        wo=_run(errors,"work order 1",lambda: db.create_work_order({
            "work_order_no":"DEMO-WO-001","equipment_id":"FAB-PVD-04","source_type":"TICKET","source_key":"DEMO-ISSUE-001",
            "title":"Replace chamber seal and leak check","description":"Repair scope from P1 vacuum recovery incident.",
            "priority":"P1","owner":actor,"team":"Equipment Engineering","qualification_required":True,"release_required":True,
        },actor,DEMO_WORKSTATION))
        if wo:work_orders[wo.work_order_no]=wo
    if "DEMO-WO-002" not in work_orders and pvd_task:
        wo=_run(errors,"work order 2",lambda: db.create_work_order({
            "work_order_no":"DEMO-WO-002","equipment_id":pvd_task.equipment_id,"source_type":"PM_TASK","source_key":str(pvd_task.id),
            "title":"Execute weekly PVD PM","description":"Controlled preventive maintenance work package.",
            "priority":"Normal","owner":actor,"team":"Maintenance","qualification_required":False,"release_required":False,
        },actor,DEMO_WORKSTATION))
        if wo:work_orders[wo.work_order_no]=wo
    if "DEMO-WO-003" not in work_orders:
        wo=_run(errors,"work order 3",lambda: db.create_work_order({
            "work_order_no":"DEMO-WO-003","equipment_id":"FAB-MET-07","source_type":"ENGINEERING","source_key":"",
            "title":"Metrology recipe matching study","description":"Engineering study across reference wafers and recipe variants.",
            "priority":"Normal","owner":actor,"team":"Process / Equipment","qualification_required":False,"release_required":False,
        },actor,DEMO_WORKSTATION))
        if wo:work_orders[wo.work_order_no]=wo

    wo_slots={
        "DEMO-WO-001":today+timedelta(days=0,hours=14),
        "DEMO-WO-002":today+timedelta(days=2,hours=9),
        "DEMO-WO-003":today+timedelta(days=4,hours=13),
    }
    for no,start in wo_slots.items():
        wo=work_orders.get(no)
        if wo and wo.planned_start is None:
            _run(errors,f"schedule {no}",lambda wo=wo,start=start: db.schedule_work_order(
                wo.work_order_no,actor,start_at=start,end_at=start+timedelta(hours=2),
                owner=actor,reason="Demo operational calendar fixture",expected_version=wo.version,workstation=DEMO_WORKSTATION,
            ))

    if "DEMO-WO-001" in work_orders and not db.list_work_logs("FAB-PVD-04"):
        _run(errors,"work log",lambda: db.start_work_log("WORK_ORDER","DEMO-WO-001","FAB-PVD-04",actor,"Repair","Demo repair work in progress."))

    # Qualification, disposition and release-state examples.
    if not any(x.protocol_id=="DEMO-QUAL-PVD" for x in db.list_qualification_protocols(active_only=False)):
        _run(errors,"qualification protocol",lambda: db.save_qualification_protocol(
            "DEMO-QUAL-PVD","PVD Post-Maintenance Qualification",
            [
                {"check_id":"Q01","label":"Base pressure within specification","acceptance":"<= 1.0 Pa"},
                {"check_id":"Q02","label":"RF match stable","acceptance":"Pass"},
                {"check_id":"Q03","label":"Monitor wafer particle result","acceptance":"Pass"},
            ],actor,equipment_type="PVD Cluster",workstation=DEMO_WORKSTATION,
        ))
    if not any(x.run_no=="DEMO-QUAL-RUN-001" for x in db.list_qualification_runs()):
        _run(errors,"qualification run",lambda: db.start_qualification_run(
            "FAB-PVD-04","DEMO-QUAL-PVD",actor,run_no="DEMO-QUAL-RUN-001",workstation=DEMO_WORKSTATION
        ))

    if not any(x.protocol_id=="DEMO-QUAL-MET" for x in db.list_qualification_protocols(active_only=False)):
        _run(errors,"metrology qualification protocol",lambda: db.save_qualification_protocol(
            "DEMO-QUAL-MET","Metrology Post-Service Verification",
            [
                {"check_id":"M01","label":"Reference wafer repeatability","acceptance":"Pass"},
                {"check_id":"M02","label":"Recipe matching within control limit","acceptance":"Pass"},
            ],actor,equipment_type="Metrology",workstation=DEMO_WORKSTATION,
        ))
    met_run=next((x for x in db.list_qualification_runs("FAB-MET-07") if x.run_no=="DEMO-QUAL-RUN-VERIFIED"),None)
    if not met_run:
        met_run=_run(errors,"verified qualification start",lambda: db.start_qualification_run(
            "FAB-MET-07","DEMO-QUAL-MET",actor,run_no="DEMO-QUAL-RUN-VERIFIED",workstation=DEMO_WORKSTATION
        ))
    if met_run and met_run.status=="In Progress":
        for check_id in ["M01","M02"]:
            met_run=_run(errors,f"qualification result {check_id}",lambda met_run=met_run,check_id=check_id: db.save_qualification_result(
                met_run.id,check_id,"PASS","Demo measurement accepted.",actor,
                evidence_path=troubleshooting_path,workstation=DEMO_WORKSTATION,
                expected_version=met_run.version,
            )) or met_run
        if met_run.status=="In Progress":
            met_run=_run(errors,"qualification submit",lambda met_run=met_run: db.submit_qualification_run(
                met_run.id,actor,"Demo checks complete; independent verification requested.",
                workstation=DEMO_WORKSTATION,expected_version=met_run.version,
            )) or met_run
    if met_run and met_run.status=="Submitted":
        _run(errors,"qualification verify",lambda met_run=met_run: db.verify_qualification_run(
            met_run.id,"demo_engineer","Independent review complete; awaiting final approval.",
            workstation=DEMO_WORKSTATION,expected_version=met_run.version,
        ))

    if not db.list_dispositions(active_only=True,equipment_id="FAB-CVD-19"):
        _run(errors,"disposition",lambda: db.set_disposition({
            "equipment_id":"FAB-CVD-19","state":"Hold","reason":"Particle excursion containment",
            "restrictions":"No production lots until particle verification is accepted.",
            "release_criteria":"Chamber clean complete; monitor wafer passes particle criteria.",
            "related_ticket":"DEMO-ISSUE-004","effective_at":now,"expires_at":now+timedelta(days=2),
            "created_by":actor,"approved_by":actor,"active":True,
        }))
    if not db.list_release_requests("FAB-WET-06"):
        _run(errors,"release request",lambda: db.create_release_request(
            "FAB-WET-06","",{
                "maintenance_complete":True,"measurements_pass":True,"calibration_valid":True,
                "safety_check":True,"verification_run":False,"critical_tickets_cleared":True,
            },"Demo release request awaiting independent verification.",actor,DEMO_WORKSTATION,
        ))
    wet_release=next(iter(db.list_release_requests("FAB-WET-06")),None)
    if wet_release and wet_release.status=="Pending Verification":
        _run(errors,"release verification",lambda wet_release=wet_release: db.verify_release(
            wet_release.id,{
                "maintenance_complete":True,"measurements_pass":True,"calibration_valid":True,
                "safety_check":True,"verification_run":True,"critical_tickets_cleared":True,
            },"demo_supervisor",expected_version=wet_release.version,workstation=DEMO_WORKSTATION,
        ))

    # Shift handover records.
    if not any(x.endorsement_no=="DEMO-HO-001" for x in db.list_endorsements()):
        _run(errors,"handover",lambda: db.save_endorsement({
            "endorsement_no":"DEMO-HO-001","equipment_id":"FAB-PVD-04",
            "current_condition":"Tool Down; vacuum recovery incident active.",
            "work_completed":"Pressure trace reviewed; seal wear confirmed.",
            "pending_work":"Replace chamber seal, leak-check, qualify and release.",
            "restrictions":"No production operation.",
            "next_action":"Complete DEMO-WO-001 then execute qualification.",
            "next_owner":actor,"status":"Open","created_by":actor,
        }))
    if not any(x.endorsement_no=="DEMO-HO-002" for x in db.list_endorsements()):
        _run(errors,"handover 2",lambda: db.save_endorsement({
            "endorsement_no":"DEMO-HO-002","equipment_id":"FAB-CVD-19",
            "current_condition":"Quality Hold after particle excursion.",
            "work_completed":"Affected lots contained and chamber clean started.",
            "pending_work":"Complete particle monitor wafer.",
            "restrictions":"Engineering/qualification activity only.",
            "next_action":"Review particle result with Process Engineering.",
            "next_owner":"Process Eng","status":"Open","created_by":actor,
        }))

    # Documents and controlled SOP records.
    if not any(x.document_id=="DEMO-SOP-PM-001" for x in db.list_controlled_documents()):
        doc=_run(errors,"controlled document",lambda: db.create_controlled_document({
            "document_id":"DEMO-SOP-PM-001","entity_type":"Equipment","entity_key":"FAB-PVD-04",
            "document_type":"SOP","title":"PVD Preventive Maintenance — Demo","owner":"Equipment Engineering",
        },actor,DEMO_WORKSTATION))
        if doc:
            _run(errors,"controlled revision",lambda: db.add_controlled_revision(
                doc.document_id,"A",sop_path,"Initial bilingual-ready demo PM procedure.",actor,DEMO_WORKSTATION
            ))
    demo_revisions=db.list_controlled_revisions("DEMO-SOP-PM-001")
    draft_revision=next((x for x in demo_revisions if x.status=="Draft"),None)
    if draft_revision:
        _run(errors,"controlled revision approval",lambda draft_revision=draft_revision: db.approve_controlled_revision(
            draft_revision.id,"demo_document",effective_at=now-timedelta(days=1),
            expires_at=now+timedelta(days=365),workstation=DEMO_WORKSTATION,
            expected_version=draft_revision.version,
        ))
    if not any(x.title=="Vacuum Recovery Troubleshooting — Demo" for x in db.list_documents("Equipment","FAB-PVD-04")):
        _run(errors,"document link",lambda: db.add_document({
            "entity_type":"Equipment","entity_key":"FAB-PVD-04","document_type":"Troubleshooting Guide",
            "title":"Vacuum Recovery Troubleshooting — Demo","revision":"A","path":troubleshooting_path,
            "status":"Active","added_by":actor,
        }))

    # Configurable fields, templates, collaboration and notifications.
    if not any(x.template_id=="DEMO-PVD-TOOL" for x in db.list_entity_templates("EQUIPMENT",active_only=False)):
        _run(errors,"equipment template",lambda: db.save_entity_template({
            "template_id":"DEMO-PVD-TOOL","entity_type":"EQUIPMENT","name":"Demo PVD Cluster",
            "applies_to":"PVD Cluster","defaults_json":{
                "equipment_type":"PVD Cluster","manufacturer":"Applied Materials","model":"Endura Demo",
                "site":"DEMO SEMICONDUCTOR FAB","building":"FAB-A","floor":"1F","area":"Deposition",
                "criticality":"High","owner":"Equipment Eng",
            },"active":True,
        },actor))

    if not any(x.section_id=="DEMO-EQ-PROCESS" for x in db.list_form_sections("EQUIPMENT",active_only=False)):
        _run(errors,"custom section",lambda: db.save_form_section({
            "section_id":"DEMO-EQ-PROCESS","entity_type":"EQUIPMENT","applies_to":"",
            "title":"Process / Qualification Data","description":"Demo configurable equipment fields.",
            "sort_order":50,"columns":2,"collapsible":True,"active":True,
        }))
    field_rows=[
        {"field_id":"DEMO_PROCESS_FAMILY","entity_type":"EQUIPMENT","applies_to":"PVD Cluster","label":"Process Family","field_type":"CHOICE","options_json":["Logic","Memory","R&D"],"required":True,"sort_order":10,"active":True},
        {"field_id":"DEMO_CHAMBER_COUNT","entity_type":"EQUIPMENT","applies_to":"PVD Cluster","label":"Chamber Count","field_type":"NUMBER","options_json":[],"required":False,"sort_order":20,"active":True},
        {"field_id":"DEMO_GOLDEN_TOOL","entity_type":"EQUIPMENT","applies_to":"PVD Cluster","label":"Golden Tool","field_type":"BOOLEAN","options_json":[],"required":False,"sort_order":30,"active":True},
    ]
    existing_fields={x.field_id for x in db.list_custom_field_definitions("EQUIPMENT",active_only=False)}
    for row in field_rows:
        if row["field_id"] not in existing_fields:
            _run(errors,f"custom field {row['field_id']}",lambda row=row: db.save_custom_field_definition(row))
            _run(errors,f"custom layout {row['field_id']}",lambda row=row: db.save_custom_field_layout(row["field_id"],{
                "section_id":"DEMO-EQ-PROCESS","column_index":0 if row["field_id"]!="DEMO_CHAMBER_COUNT" else 1,
                "width_span":1,"placeholder":"Demo value","help_text":"Fixture data for UI/demo testing.",
            }))
    _run(errors,"custom field values",lambda: db.save_custom_field_values(
        "EQUIPMENT","FAB-PVD-04",{"DEMO_PROCESS_FAMILY":"Logic","DEMO_CHAMBER_COUNT":4,"DEMO_GOLDEN_TOOL":True},
        user=actor,applies_to="PVD Cluster",
    ))

    if not db.list_record_comments("EQUIPMENT","FAB-PVD-04"):
        _run(errors,"comment",lambda: db.add_record_comment(
            "EQUIPMENT","FAB-PVD-04",
            "Demo collaboration note: chamber seal replacement is coordinated with qualification.",
            actor,equipment_id="FAB-PVD-04",
        ))
    _run(errors,"watch",lambda: db.set_record_watch("EQUIPMENT","FAB-PVD-04",actor,True))
    if not any(x.dedupe_key=="demo-fixture-ready" for x in db.list_notifications(actor,include_dismissed=True)):
        _run(errors,"notification",lambda: db.create_notification(
            actor,"DEMO","EMS demo dataset ready",
            "Representative records now span equipment, PM, incidents, work orders, qualification, release, inventory, documents and collaboration.",
            "INFO","EQUIPMENT","FAB-PVD-04","FAB-PVD-04","demo-fixture-ready",
        ))

    # Evidence/attachment examples across the major record surfaces.
    attachment_specs=[
        ("EQUIPMENT","FAB-PVD-04","FAB-PVD-04",troubleshooting_path,"Troubleshooting Evidence","Vacuum recovery troubleshooting reference","vacuum,rca,demo"),
        ("TICKET","DEMO-ISSUE-001","FAB-PVD-04",troubleshooting_path,"Incident Evidence","Pressure-recovery investigation notes","incident,vacuum,demo"),
        ("WORK_ORDER","DEMO-WO-001","FAB-PVD-04",sop_path,"Work Package","Controlled work-package reference","repair,work-order,demo"),
        ("QUALIFICATION","DEMO-QUAL-RUN-001","FAB-PVD-04",sop_path,"Qualification Evidence","Qualification reference procedure","qualification,demo"),
        ("ENDORSEMENT","DEMO-HO-001","FAB-PVD-04",troubleshooting_path,"Handover Evidence","Shift handover troubleshooting reference","handover,demo"),
    ]
    if pvd_task:
        execution=db.get_pm_execution_for_task(pvd_task.id)
        if execution:
            attachment_specs.append(("PM_EXECUTION",str(execution.id),"FAB-PVD-04",sop_path,"PM Evidence","PM execution controlled reference","pm,evidence,demo"))
    releases=db.list_release_requests("FAB-WET-06")
    if releases:
        attachment_specs.append(("RELEASE",str(releases[0].id),"FAB-WET-06",sop_path,"Release Evidence","Return-to-service reference","release,demo"))
    for entity_type,entity_key,equipment_id,path,category,caption,tags in attachment_specs:
        if not db.list_attachments(entity_type,entity_key):
            _run(errors,f"attachment {entity_type}:{entity_key}",lambda entity_type=entity_type,entity_key=entity_key,equipment_id=equipment_id,path=path,category=category,caption=caption,tags=tags: db.add_attachment(
                entity_type,entity_key,path,original_name=Path(path).name,media_type="text/markdown",
                category=category,caption=caption,tags=tags,equipment_id=equipment_id,created_by=actor,
            ))

    # Persisted unsaved-work example for the Incident draft recovery UX.
    if not db.get_user_draft(actor,"TICKET","DEMO-ISSUE-001","summary"):
        _run(errors,"incident draft",lambda: db.save_user_draft(
            actor,"TICKET","DEMO-ISSUE-001",{
                "description":"DEMO DRAFT: added note pending incident-summary save.",
                "root_cause":"DEMO DRAFT: seal wear remains the leading cause; verify after replacement.",
                "corrective_action":"DEMO DRAFT: replace seal, leak-check, then run qualification.",
                "verification":"DEMO DRAFT: monitor wafer and alarm recurrence review pending.",
            },"summary",
        ))

    # User/workspace history and inventory transaction examples.
    _run(errors,"demo preference",lambda: db.set_user_preference(actor,"demo.calendar.default_view","week"))
    _run(errors,"demo favorite",lambda: db.set_favorite(
        actor,"EQUIPMENT","FAB-PVD-04",True,"FAB-PVD-04 — PVD demo tool","FAB-PVD-04"
    ))
    _run(errors,"demo recent",lambda: db.record_recent_item(
        actor,"TICKET","DEMO-ISSUE-001","DEMO-ISSUE-001 — Vacuum recovery timeout","FAB-PVD-04"
    ))
    if not any(x.part_number=="DEMO-O-RING-KIT" and x.transaction_type=="Consume" and x.related_ticket=="DEMO-ISSUE-001" for x in db.list_inventory_transactions(5000)):
        _run(errors,"inventory consume transaction",lambda: db.consume_inventory(
            "DEMO-O-RING-KIT","DEMO-STORES-A1",1.0,actor,"FAB-PVD-04","DEMO-ISSUE-001"
        ))
    if not any(x.database_type=="DEMO-SIMULATED" for x in db.list_recovery_drills(1000)):
        _run(errors,"recovery drill history",lambda: db.record_recovery_drill(
            "DEMO://backup/equipment_manager_demo.db","DEMO-SIMULATED",True,
            "Simulated demo record only; no production restore was executed.",actor,DEMO_WORKSTATION,
        ))

    # Disabled integration/automation examples are safe for offline demonstration.
    if not any(x.rule_id=="DEMO-P1-HANDOVER" for x in db.list_workflow_rules()):
        _run(errors,"workflow rule",lambda: db.save_workflow_rule({
            "rule_id":"DEMO-P1-HANDOVER","name":"Demo: create handover on critical alarm",
            "trigger":"ALARM_ACTIVE","match_json":json.dumps({"severity":"Critical"}),
            "actions_json":json.dumps([{"type":"CREATE_HANDOVER","next_owner":"Equipment Eng","next_action":"Investigate critical alarm."}]),
            "enabled":False,"priority":900,
        },actor))
    if not any(x.endpoint_id=="DEMO-OUTBOUND" for x in db.list_integration_endpoints()):
        _run(errors,"outbound endpoint",lambda: db.save_integration_endpoint({
            "endpoint_id":"DEMO-OUTBOUND","name":"Disabled demo outbound file adapter","adapter_type":"FILE",
            "target":str(Path(__file__).with_name("demo_outbound")),"topics":"equipment.state.changed,work_order.created",
            "auth_env":"","enabled":False,
        }))
    if not any(x.endpoint_id=="DEMO-ALARM-IN" for x in db.list_inbound_endpoints()):
        _run(errors,"inbound endpoint",lambda: db.save_inbound_endpoint({
            "endpoint_id":"DEMO-ALARM-IN","name":"Disabled demo alarm JSON inbox","adapter_type":"FILE_JSON",
            "entity_type":"ALARM","source_path":str(Path(__file__).with_name("demo_inbound")),
            "file_pattern":"*.json","mapping_json":json.dumps({"equipment_id":"equipment_id","alarm_code":"alarm_code","severity":"severity","message":"message"}),
            "defaults_json":json.dumps({"source":"DEMO-FILE"}),"archive_path":str(Path(__file__).with_name("demo_archive")),
            "quarantine_path":str(Path(__file__).with_name("demo_quarantine")),"enabled":False,
        }))

    if not errors:
        db.save_config_option({
            "category":"DEMO_FIXTURE","code":DEMO_FIXTURE_CODE,"label":"Full-domain EMS demo fixture",
            "sort_order":1,"active":True,"system_locked":False,
            "metadata_json":{"seeded_at":now.isoformat(),"actor":actor,"equipment":28,"scope":"operator-facing domains"},
        })

    return {
        "changed": True,
        "errors": errors,
        "message": (
            "Full EMS demo fixture created."
            if not errors else f"Demo fixture created with {len(errors)} non-fatal seed warning(s)."
        ),
    }


def active_tickets(db: Database):
    return [t for t in db.list_tickets() if (t.status or "") not in CLOSED_TICKET_STATES]


def state_key(equipment, tickets) -> str:
    priorities = {(t.priority or "").upper() for t in tickets}
    if "P1" in priorities or (equipment.status or "") == "Down":
        return "critical"
    if "P2" in priorities or (equipment.status or "") in ATTENTION_STATES:
        return "attention"
    if (equipment.status or "") in PLANNED_STATES:
        return "planned"
    if (equipment.status or "") in OFFLINE_STATES:
        return "offline"
    return "good"
