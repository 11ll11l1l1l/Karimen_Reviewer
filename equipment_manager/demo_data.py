from __future__ import annotations

from dataclasses import dataclass

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


def seed_demo_data(db: Database) -> bool:
    """Create deterministic demo records once and preserve later user edits."""
    if any((e.equipment_id or "").startswith("FAB-") for e in db.list_equipment()):
        return False

    for tool in demo_tools():
        db.save_equipment(
            {
                "equipment_id": tool.equipment_id,
                "name": tool.name,
                "equipment_type": tool.equipment_type,
                "manufacturer": tool.manufacturer,
                "model": tool.model,
                "serial_number": f"DEMO-{tool.equipment_id}",
                "asset_number": f"ASSET-{tool.equipment_id[-2:]}",
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
            }
        )

    tickets = [
        {
            "ticket_no": "DEMO-ISSUE-001",
            "equipment_id": "FAB-PVD-04",
            "title": "Vacuum recovery timeout after wafer transfer",
            "description": "Load-lock pressure recovery exceeds control limit. Tool stopped to prevent repeat wafer handling alarms.",
            "severity": "S1",
            "priority": "P1",
            "status": "Open",
            "owner": "Equipment Eng",
            "created_by": "demo",
        },
        {
            "ticket_no": "DEMO-ISSUE-002",
            "equipment_id": "FAB-FURN-08",
            "title": "Replacement MFC awaiting kitting",
            "description": "Gas-flow drift confirmed during verification. Replacement part is reserved but not yet delivered to the bay.",
            "severity": "S2",
            "priority": "P2",
            "status": "Waiting Parts",
            "owner": "Equipment Eng",
            "created_by": "demo",
        },
        {
            "ticket_no": "DEMO-ISSUE-003",
            "equipment_id": "FAB-CMP-13",
            "title": "Quarterly PM in progress",
            "description": "Scheduled preventive maintenance. Pad, conditioner and slurry delivery checks are being executed.",
            "severity": "S4",
            "priority": "P4",
            "status": "In Progress",
            "owner": "PM Team",
            "created_by": "demo",
        },
        {
            "ticket_no": "DEMO-ISSUE-004",
            "equipment_id": "FAB-CVD-19",
            "title": "Particle excursion containment",
            "description": "Post-maintenance particle result exceeded the internal action level. Tool is on quality hold pending chamber-clean verification.",
            "severity": "S2",
            "priority": "P2",
            "status": "Open",
            "owner": "Process Eng",
            "created_by": "demo",
        },
        {
            "ticket_no": "DEMO-ISSUE-005",
            "equipment_id": "FAB-ETCH-26",
            "title": "Qualification lot required",
            "description": "Hardware change completed. Tool remains in qualification until monitor-lot and matching checks are accepted.",
            "severity": "S3",
            "priority": "P3",
            "status": "Open",
            "owner": "Process Eng",
            "created_by": "demo",
        },
    ]
    existing_tickets = {t.ticket_no for t in db.list_tickets()}
    for ticket in tickets:
        if ticket["ticket_no"] not in existing_tickets:
            db.save_ticket(ticket)
    return True


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
