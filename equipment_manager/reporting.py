from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from pptx import Presentation
from pptx.util import Inches, Pt


def _text(value: Any) -> str:
    if value is None:return ""
    if isinstance(value,datetime):return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _ticket(db,ticket_no: str):
    row=next((x for x in db.list_tickets() if x.ticket_no==ticket_no),None)
    if not row:raise ValueError("Ticket not found")
    return row


def _set_title(slide,title: str):
    if slide.shapes.title:
        slide.shapes.title.text=title
        slide.shapes.title.text_frame.paragraphs[0].font.size=Pt(26)


def _add_bullets(slide,title: str,lines: list[str]):
    _set_title(slide,title)
    box=slide.placeholders[1] if len(slide.placeholders)>1 else slide.shapes.add_textbox(Inches(.8),Inches(1.5),Inches(11.5),Inches(5.5))
    tf=box.text_frame;tf.clear()
    for i,line in enumerate([x for x in lines if x]):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph()
        p.text=line;p.level=0;p.font.size=Pt(18)


def _add_table(slide,title: str,headers: list[str],rows: list[list[Any]],max_rows: int=14):
    _set_title(slide,title)
    rows=rows[:max_rows]
    shape=slide.shapes.add_table(len(rows)+1,len(headers),Inches(.45),Inches(1.45),Inches(12.4),Inches(5.65))
    table=shape.table
    for c,h in enumerate(headers):
        cell=table.cell(0,c);cell.text=str(h)
        for p in cell.text_frame.paragraphs:p.font.bold=True;p.font.size=Pt(12)
    for r,row in enumerate(rows,1):
        for c,val in enumerate(row):
            table.cell(r,c).text=_text(val)
            for p in table.cell(r,c).text_frame.paragraphs:p.font.size=Pt(10)


def _add_evidence_slides(prs: Presentation,attachments,title_prefix: str):
    images=[x for x in attachments if (x.media_type or "").startswith("image/") and Path(x.stored_path).is_file()]
    for index,row in enumerate(images[:6],1):
        slide=prs.slides.add_slide(prs.slide_layouts[5]);_set_title(slide,f"{title_prefix} Evidence {index}")
        slide.shapes.add_picture(row.stored_path,Inches(.7),Inches(1.4),width=Inches(7.7),height=Inches(5.2))
        tb=slide.shapes.add_textbox(Inches(8.7),Inches(1.5),Inches(4),Inches(4.8))
        tf=tb.text_frame;tf.text=row.caption or row.original_name
        p=tf.add_paragraph();p.text=f"Category: {row.category}"
        p=tf.add_paragraph();p.text=f"Added by: {row.created_by}"
        if row.tags:
            p=tf.add_paragraph();p.text=f"Tags: {row.tags}"


def export_incident_pptx(db,ticket_no: str,path: str) -> str:
    t=_ticket(db,ticket_no);control=db.ticket_operational_control(ticket_no)
    whys=db.list_incident_whys(ticket_no);factors=db.list_incident_causal_factors(ticket_no)
    actions=db.list_incident_actions(ticket_no);lifecycle=db.list_ticket_state_events(ticket_no)
    attachments=db.list_attachments("TICKET",ticket_no)

    prs=Presentation()
    slide=prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text=f"{t.ticket_no} — {t.title}"
    slide.placeholders[1].text=f"{t.equipment_id} | {t.priority} | {t.status} | Owner: {t.owner or '—'}"

    slide=prs.slides.add_slide(prs.slide_layouts[1])
    _add_bullets(slide,"Problem / Operational Impact",[
        f"Problem: {t.description}",
        f"Production impact: {getattr(control,'production_impact','') if control else ''}",
        f"Affected lots/material: {getattr(control,'affected_lots','') if control else ''}",
        f"Safety/quality risk: {getattr(control,'safety_quality_risk','') if control else ''}",
        f"Containment: {getattr(control,'containment','') if control else ''}",
    ])

    slide=prs.slides.add_slide(prs.slide_layouts[5])
    _add_table(slide,"5-Why / Causal Analysis",["#","Question","Answer"],[[x.sequence,x.question,x.answer] for x in whys],10)

    slide=prs.slides.add_slide(prs.slide_layouts[5])
    _add_table(slide,"Causal Factors",["Category","Type","Description","Evidence","Status"],[
        [x.category,x.factor_type,x.description,x.evidence,x.status] for x in factors
    ],10)

    slide=prs.slides.add_slide(prs.slide_layouts[5])
    _add_table(slide,"Corrective / Preventive Actions",["Type","Action","Owner","Due","Status","Effectiveness"],[
        [x.action_type,x.description,x.owner,x.due_at,x.status,x.effectiveness_criteria] for x in actions
    ],12)

    slide=prs.slides.add_slide(prs.slide_layouts[1])
    _add_bullets(slide,"Resolution / Verification",[
        f"Root cause summary: {t.root_cause or 'Open'}",
        f"Corrective action summary: {t.corrective_action or 'Open'}",
        f"Verification: {t.verification or 'Pending'}",
        f"Current status: {t.status}",
    ])

    slide=prs.slides.add_slide(prs.slide_layouts[5])
    _add_table(slide,"Lifecycle Timeline",["From","To","Reason","Owner","By","Time"],[
        [x.from_state,x.to_state,x.reason_code,x.owner,x.changed_by,x.changed_at] for x in lifecycle
    ],16)

    _add_evidence_slides(prs,attachments,"Incident")
    Path(path).parent.mkdir(parents=True,exist_ok=True);prs.save(path);return str(path)


def export_equipment_pptx(db,equipment_id: str,path: str) -> str:
    eq=db.get_equipment(equipment_id)
    if not eq:raise ValueError("Equipment not found")
    rel=db.reliability_summary(equipment_id)
    tickets=[x for x in db.list_tickets() if x.equipment_id==equipment_id and x.status not in {"Closed","Cancelled"}]
    pm=[x for x in db.list_pm_tasks() if x.equipment_id==equipment_id and x.status not in {"Completed","Cancelled"}]
    wo=db.list_work_orders(equipment_id,True)
    alarms=db.list_alarms(equipment_id,True,100)
    timeline=db.equipment_activity_timeline(equipment_id,80)
    attachments=db.list_attachments("EQUIPMENT",equipment_id)

    prs=Presentation()
    slide=prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text=f"{eq.equipment_id} — {eq.name}"
    slide.placeholders[1].text=f"{eq.status} | {eq.disposition} | {eq.area} | Owner: {eq.owner or '—'}"

    slide=prs.slides.add_slide(prs.slide_layouts[1])
    _add_bullets(slide,"Current Equipment Summary",[
        f"Equipment type: {eq.equipment_type}",
        f"Model / serial: {eq.model} / {eq.serial_number}",
        f"Location: {eq.site} / {eq.building} / {eq.floor} / {eq.area} / {eq.line_cell}",
        f"Availability (30d): {rel['availability_pct']:.1f}%",
        f"MTBF (30d): {rel['mtbf_hours']:.1f} h",
        f"MTTR (30d): {rel['mttr_hours']:.1f} h",
        f"Unplanned downtime (30d): {rel['unplanned_downtime_hours']:.1f} h",
    ])

    slide=prs.slides.add_slide(prs.slide_layouts[5])
    _add_table(slide,"Open Incidents",["Ticket","Priority","Status","Title","Owner"],[[x.ticket_no,x.priority,x.status,x.title,x.owner] for x in tickets],12)

    slide=prs.slides.add_slide(prs.slide_layouts[5])
    _add_table(slide,"Maintenance / Work Orders",["Type","Key","Status","Owner / Assigned","Summary"],[
        *[["PM",x.id,x.status,x.assigned_to,f"{x.pm_id} — {x.pm_name}"] for x in pm],
        *[["WO",x.work_order_no,x.status,x.owner,x.title] for x in wo],
    ],14)

    slide=prs.slides.add_slide(prs.slide_layouts[5])
    _add_table(slide,"Active Alarms",["Code","Severity","Message","State","Occurred"],[[x.alarm_code,x.severity,x.message,x.state,x.occurred_at] for x in alarms],14)

    slide=prs.slides.add_slide(prs.slide_layouts[5])
    _add_table(slide,"Recent Activity",["Time","Type","Key","Activity","Status"],[
        [x["occurred_at"],x["kind"],x["key"],x["summary"],x["status"]] for x in timeline
    ],18)

    _add_evidence_slides(prs,attachments,"Equipment")
    Path(path).parent.mkdir(parents=True,exist_ok=True);prs.save(path);return str(path)


def _sheet(ws,headers: list[str],rows: list[list[Any]]):
    for c,h in enumerate(headers,1):
        cell=ws.cell(1,c,h);cell.font=Font(bold=True);cell.fill=PatternFill("solid",fgColor="D9E2F3")
    for r,row in enumerate(rows,2):
        for c,val in enumerate(row,1):ws.cell(r,c,_text(val))
    ws.freeze_panes="A2";ws.auto_filter.ref=ws.dimensions
    for c,h in enumerate(headers,1):
        width=max([len(h)]+[len(_text(ws.cell(r,c).value)) for r in range(2,min(ws.max_row,300)+1)])
        ws.column_dimensions[get_column_letter(c)].width=min(max(width+2,10),60)


def export_incident_xlsx(db,ticket_no: str,path: str) -> str:
    t=_ticket(db,ticket_no);control=db.ticket_operational_control(ticket_no)
    wb=Workbook();summary=wb.active;summary.title="Summary"
    rows=[
        ["Ticket",t.ticket_no],["Equipment",t.equipment_id],["Title",t.title],["Priority",t.priority],["Status",t.status],
        ["Owner",t.owner],["Problem",t.description],["Containment",getattr(control,"containment","") if control else ""],
        ["Production impact",getattr(control,"production_impact","") if control else ""],["Affected lots",getattr(control,"affected_lots","") if control else ""],
        ["Root cause",t.root_cause],["Corrective action",t.corrective_action],["Verification",t.verification],
    ]
    _sheet(summary,["Field","Value"],rows)
    ws=wb.create_sheet("5-Why");_sheet(ws,["#","Question","Answer","Updated By","Updated"],[[x.sequence,x.question,x.answer,x.updated_by,x.updated_at] for x in db.list_incident_whys(ticket_no)])
    ws=wb.create_sheet("Causal Factors");_sheet(ws,["Category","Type","Description","Evidence","Status"],[[x.category,x.factor_type,x.description,x.evidence,x.status] for x in db.list_incident_causal_factors(ticket_no)])
    ws=wb.create_sheet("CAPA");_sheet(ws,["Type","Action","Owner","Due","Status","Effectiveness","Completed","Verified"],[[x.action_type,x.description,x.owner,x.due_at,x.status,x.effectiveness_criteria,x.completed_at,x.verified_at] for x in db.list_incident_actions(ticket_no)])
    ws=wb.create_sheet("Lifecycle");_sheet(ws,["From","To","Reason","Note","Owner","By","Time"],[[x.from_state,x.to_state,x.reason_code,x.note,x.owner,x.changed_by,x.changed_at] for x in db.list_ticket_state_events(ticket_no)])
    ws=wb.create_sheet("Attachments");_sheet(ws,["Name","Category","Caption","Tags","Path","Added By","Added"],[[x.original_name,x.category,x.caption,x.tags,x.stored_path,x.created_by,x.created_at] for x in db.list_attachments("TICKET",ticket_no)])
    Path(path).parent.mkdir(parents=True,exist_ok=True);wb.save(path);return str(path)


def export_equipment_xlsx(db,equipment_id: str,path: str) -> str:
    eq=db.get_equipment(equipment_id)
    if not eq:raise ValueError("Equipment not found")
    wb=Workbook();summary=wb.active;summary.title="Summary"
    rel=db.reliability_summary(equipment_id)
    _sheet(summary,["Field","Value"],[
        ["Equipment",eq.equipment_id],["Name",eq.name],["Status",eq.status],["Disposition",eq.disposition],
        ["Area",eq.area],["Line/Cell",eq.line_cell],["Owner",eq.owner],["Criticality",eq.criticality],
        ["Availability 30d",f"{rel['availability_pct']:.2f}%"],["MTBF 30d",rel["mtbf_hours"]],["MTTR 30d",rel["mttr_hours"]],
    ])
    timeline=db.equipment_activity_timeline(equipment_id,5000)
    ws=wb.create_sheet("Activity");_sheet(ws,["Time","Type","Key","Summary","User","Status","Source"],[[x["occurred_at"],x["kind"],x["key"],x["summary"],x["user"],x["status"],x["source"]] for x in timeline])
    tickets=[x for x in db.list_tickets() if x.equipment_id==equipment_id]
    ws=wb.create_sheet("Incidents");_sheet(ws,["Ticket","Title","Priority","Status","Owner","Created","Updated"],[[x.ticket_no,x.title,x.priority,x.status,x.owner,x.created_at,x.updated_at] for x in tickets])
    pm=[x for x in db.list_pm_tasks() if x.equipment_id==equipment_id]
    ws=wb.create_sheet("PM");_sheet(ws,["Task","PM","Name","Due","Scheduled","Status","Assigned","Hours"],[[x.id,x.pm_id,x.pm_name,x.original_due_date,x.scheduled_date,x.status,x.assigned_to,x.estimated_hours] for x in pm])
    wo=db.list_work_orders(equipment_id)
    ws=wb.create_sheet("Work Orders");_sheet(ws,["WO","Source","Title","Priority","Status","Owner","Created","Completed"],[[x.work_order_no,f"{x.source_type}:{x.source_key}",x.title,x.priority,x.status,x.owner,x.created_at,x.completed_at] for x in wo])
    alarms=db.list_alarms(equipment_id,False,5000)
    ws=wb.create_sheet("Alarms");_sheet(ws,["Code","Severity","Message","State","Occurred","Cleared","Ticket"],[[x.alarm_code,x.severity,x.message,x.state,x.occurred_at,x.cleared_at,x.related_ticket] for x in alarms])
    ws=wb.create_sheet("Attachments");_sheet(ws,["Name","Category","Caption","Tags","Path","Added By","Added"],[[x.original_name,x.category,x.caption,x.tags,x.stored_path,x.created_by,x.created_at] for x in db.list_attachments("EQUIPMENT",equipment_id)])
    Path(path).parent.mkdir(parents=True,exist_ok=True);wb.save(path);return str(path)
