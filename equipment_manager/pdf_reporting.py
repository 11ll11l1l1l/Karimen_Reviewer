from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)


def _text(value: Any) -> str:
    if value is None:return ""
    if isinstance(value,datetime):return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _esc(value: Any) -> str:
    return _text(value).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")


def _styles():
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="EMS_H1",parent=styles["Heading1"],fontSize=18,leading=22,spaceAfter=7))
    styles.add(ParagraphStyle(name="EMS_H2",parent=styles["Heading2"],fontSize=13,leading=16,spaceBefore=7,spaceAfter=5))
    styles.add(ParagraphStyle(name="EMS_Body",parent=styles["BodyText"],fontSize=8.5,leading=11))
    styles.add(ParagraphStyle(name="EMS_Small",parent=styles["BodyText"],fontSize=7,leading=9,textColor=colors.HexColor("#4f5f6b")))
    return styles


def _header_footer(canvas,doc):
    canvas.saveState()
    canvas.setFont("Helvetica",7)
    canvas.setFillColor(colors.HexColor("#5a6872"))
    canvas.drawString(15*mm,9*mm,f"EMS controlled report - generated {datetime.now():%Y-%m-%d %H:%M}")
    canvas.drawRightString(A4[0]-15*mm,9*mm,f"Page {doc.page}")
    canvas.restoreState()


def _paragraph(value,style):
    return Paragraph(_esc(value).replace("\n","<br/>"),style)


def _kv_table(rows,styles):
    data=[[_paragraph(k,styles["EMS_Small"]),_paragraph(v,styles["EMS_Body"])] for k,v in rows]
    table=Table(data,colWidths=[45*mm,135*mm],hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#eef2f5")),
        ("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#d8e0e6")),
        ("LEFTPADDING",(0,0),(-1,-1),5),
        ("RIGHTPADDING",(0,0),(-1,-1),5),
        ("TOPPADDING",(0,0),(-1,-1),4),
        ("BOTTOMPADDING",(0,0),(-1,-1),4),
    ]))
    return table


def _data_table(headers,rows,styles,widths=None):
    body=[[_paragraph(h,styles["EMS_Small"]) for h in headers]]
    for row in rows:
        body.append([_paragraph(v,styles["EMS_Small"]) for v in row])
    if widths is None:
        total=180*mm
        widths=[total/max(1,len(headers))]*len(headers)
    table=Table(body,colWidths=widths,repeatRows=1,hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#dfe9ef")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.HexColor("#172431")),
        ("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#cbd5dc")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),3),
        ("RIGHTPADDING",(0,0),(-1,-1),3),
        ("TOPPADDING",(0,0),(-1,-1),3),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),
    ]))
    return table


def _attachments_story(attachments,styles,title="Evidence"):
    story=[]
    images=[x for x in attachments if (x.media_type or "").startswith("image/") and Path(x.stored_path).is_file()]
    if not images:return story
    story.extend([Paragraph(title,styles["EMS_H2"])])
    for row in images[:12]:
        try:
            img=Image(row.stored_path)
            img._restrictSize(165*mm,105*mm)
            caption=_paragraph(f"{row.category}: {row.caption or row.original_name} | by {row.created_by}",styles["EMS_Small"])
            story.append(KeepTogether([img,Spacer(1,2*mm),caption,Spacer(1,5*mm)]))
        except Exception:
            continue
    return story


def _build(path,title,subtitle,story):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    styles=_styles()
    doc=SimpleDocTemplate(
        path,pagesize=A4,rightMargin=15*mm,leftMargin=15*mm,
        topMargin=15*mm,bottomMargin=16*mm,title=title,author="Equipment Management System",
    )
    full=[Paragraph(_esc(title),styles["EMS_H1"]),Paragraph(_esc(subtitle),styles["EMS_Small"]),Spacer(1,4*mm)]
    full.extend(story)
    doc.build(full,onFirstPage=_header_footer,onLaterPages=_header_footer)
    return str(path)


def export_incident_pdf(db,ticket_no: str,path: str) -> str:
    styles=_styles();t=next((x for x in db.list_tickets() if x.ticket_no==ticket_no),None)
    if not t:raise ValueError("Ticket not found")
    control=db.ticket_operational_control(ticket_no);whys=db.list_incident_whys(ticket_no)
    factors=db.list_incident_causal_factors(ticket_no);actions=db.list_incident_actions(ticket_no)
    lifecycle=db.list_ticket_state_events(ticket_no);attachments=db.list_attachments("TICKET",ticket_no)
    story=[
        Paragraph("Operational Summary",styles["EMS_H2"]),
        _kv_table([
            ("Equipment",t.equipment_id),("Priority / Severity",f"{t.priority} / {t.severity}"),("Status",t.status),("Owner",t.owner),
            ("Problem",t.description),("Containment",getattr(control,"containment","") if control else ""),
            ("Production impact",getattr(control,"production_impact","") if control else ""),
            ("Affected lots/material",getattr(control,"affected_lots","") if control else ""),
            ("Safety / quality risk",getattr(control,"safety_quality_risk","") if control else ""),
            ("Root cause",t.root_cause),("Corrective action",t.corrective_action),("Verification",t.verification),
        ],styles),
        Paragraph("5-Why",styles["EMS_H2"]),
        _data_table(["#","Question","Answer"],[[x.sequence,x.question,x.answer] for x in whys],styles,[12*mm,70*mm,98*mm]),
        Paragraph("Causal Factors",styles["EMS_H2"]),
        _data_table(["Category","Type","Description","Evidence","Status"],[[x.category,x.factor_type,x.description,x.evidence,x.status] for x in factors],styles),
        Paragraph("CAPA / Actions",styles["EMS_H2"]),
        _data_table(["Type","Action","Owner","Due","Status","Effectiveness"],[[x.action_type,x.description,x.owner,x.due_at,x.status,x.effectiveness_criteria] for x in actions],styles),
        Paragraph("Lifecycle",styles["EMS_H2"]),
        _data_table(["From","To","Reason","Owner","By","Time"],[[x.from_state,x.to_state,x.reason_code,x.owner,x.changed_by,x.changed_at] for x in lifecycle],styles),
    ]
    story.extend(_attachments_story(attachments,styles))
    return _build(path,f"{t.ticket_no} - {t.title}",f"{t.equipment_id} | {t.priority} | {t.status}",story)


def export_equipment_pdf(db,equipment_id: str,path: str) -> str:
    styles=_styles();eq=db.get_equipment(equipment_id)
    if not eq:raise ValueError("Equipment not found")
    rel=db.reliability_summary(equipment_id)
    tickets=[x for x in db.list_tickets() if x.equipment_id==equipment_id and x.status not in {"Closed","Cancelled"}]
    pm=[x for x in db.list_pm_tasks() if x.equipment_id==equipment_id and x.status not in {"Completed","Cancelled"}]
    work_orders=db.list_work_orders(equipment_id,True);alarms=db.list_alarms(equipment_id,True,100)
    timeline=db.equipment_activity_timeline(equipment_id,120);attachments=db.list_attachments("EQUIPMENT",equipment_id)
    story=[
        Paragraph("Current Status",styles["EMS_H2"]),
        _kv_table([
            ("State",eq.status),("Disposition",eq.disposition),("Owner",eq.owner),("Criticality",eq.criticality),
            ("Location",f"{eq.site} / {eq.building} / {eq.floor} / {eq.area} / {eq.line_cell}"),
            ("Model / serial",f"{eq.model} / {eq.serial_number}"),
            ("Availability 30d",f"{rel['availability_pct']:.1f}%"),("MTBF 30d",f"{rel['mtbf_hours']:.1f} h"),
            ("MTTR 30d",f"{rel['mttr_hours']:.1f} h"),("Unplanned downtime 30d",f"{rel['unplanned_downtime_hours']:.1f} h"),
        ],styles),
        Paragraph("Open Incidents",styles["EMS_H2"]),
        _data_table(["Ticket","Priority","Status","Title","Owner"],[[x.ticket_no,x.priority,x.status,x.title,x.owner] for x in tickets],styles),
        Paragraph("Maintenance / Work Orders",styles["EMS_H2"]),
        _data_table(["Type","Key","Status","Owner","Summary"],[
            *[["PM",x.id,x.status,x.assigned_to,f"{x.pm_id} - {x.pm_name}"] for x in pm],
            *[["WO",x.work_order_no,x.status,x.owner,x.title] for x in work_orders],
        ],styles),
        Paragraph("Active Alarms",styles["EMS_H2"]),
        _data_table(["Code","Severity","Message","Occurred"],[[x.alarm_code,x.severity,x.message,x.occurred_at] for x in alarms],styles),
        Paragraph("Recent Activity",styles["EMS_H2"]),
        _data_table(["Time","Type","Key","Activity","Status"],[[x["occurred_at"],x["kind"],x["key"],x["summary"],x["status"]] for x in timeline[:60]],styles),
    ]
    story.extend(_attachments_story(attachments,styles))
    return _build(path,f"{eq.equipment_id} - {eq.name}",f"{eq.status} | {eq.disposition} | {eq.area}",story)


def export_pm_execution_pdf(db,task_id: int,path: str) -> str:
    styles=_styles();task=db.get_pm_task(int(task_id))
    if not task:raise ValueError("PM task not found")
    ex=db.get_pm_execution_for_task(task.id)
    if not ex:raise ValueError("PM execution has not started.")
    specs=db.list_pm_execution_specs(ex.id);results={x.step_no:x for x in db.list_pm_results(ex.id)}
    reqs=db.list_pm_execution_requirements(ex.id);acks={x.requirement_id:x for x in db.list_pm_requirement_acks(ex.id)}
    reservations=[x for x in db.list_reservations() if x.pm_task_id==task.id]
    attachments=db.list_attachments("PM_EXECUTION",str(ex.id))
    step_rows=[]
    for spec in specs:
        r=results.get(spec.step_no);value=r.value_text if r and r.value_text else (r.value_numeric if r else "")
        step_rows.append([spec.step_no,spec.activity,spec.method,spec.unit,r.result if r else "OPEN",value,r.comment if r else ""])
    story=[
        Paragraph("Execution Summary",styles["EMS_H2"]),
        _kv_table([("Equipment",task.equipment_id),("PM",f"{task.pm_id} - {task.pm_name}"),("Task",task.id),("Status",ex.status),("Started",f"{_text(ex.started_at)} by {ex.started_by}"),("Completed",f"{_text(ex.completed_at)} by {ex.completed_by}")],styles),
        Paragraph("Checklist / Measurements",styles["EMS_H2"]),
        _data_table(["Step","Activity","Method","Unit","Result","Value","Comment"],step_rows,styles),
        Paragraph("Requirements",styles["EMS_H2"]),
        _data_table(["Type","Key","Description","Qty","Mandatory","Acknowledged"],[[x.requirement_type,x.requirement_key,x.description,x.quantity,x.mandatory,(acks.get(x.requirement_id).acknowledged_by if acks.get(x.requirement_id) else "")] for x in reqs],styles),
        Paragraph("Parts / Reservations",styles["EMS_H2"]),
        _data_table(["Part","Location","Qty","Status","Reserved By"],[[x.part_number,x.location_code,x.quantity,x.status,x.reserved_by] for x in reservations],styles),
    ]
    story.extend(_attachments_story(attachments,styles))
    return _build(path,f"PM - {task.pm_id} - {task.pm_name}",f"{task.equipment_id} | Task {task.id} | {ex.status}",story)


def export_work_order_pdf(db,work_order_no: str,path: str) -> str:
    styles=_styles();wo=db.get_work_order(work_order_no)
    if not wo:raise ValueError("Work order not found")
    events=db.list_work_order_events(work_order_no);links=db.list_work_order_links(work_order_no)
    logs=[x for x in db.list_work_logs(wo.equipment_id,False,1000) if x.entity_type=="WORK_ORDER" and x.entity_key==work_order_no]
    close=db.work_order_closeout_status(work_order_no);attachments=db.list_attachments("WORK_ORDER",work_order_no)
    story=[
        Paragraph("Work Scope / Closeout",styles["EMS_H2"]),
        _kv_table([("Equipment",wo.equipment_id),("Priority",wo.priority),("Status",wo.status),("Owner",wo.owner),("Team",wo.team),("Source",f"{wo.source_type}:{wo.source_key}"),("Description",wo.description),("Qualification required",wo.qualification_required),("Release required",wo.release_required),("Closeout blockers","; ".join(close.get("blockers",[])) or "None")],styles),
        Paragraph("Linked Records",styles["EMS_H2"]),
        _data_table(["Type","Key","Relation","Created By","Created"],[[x.entity_type,x.entity_key,x.relation,x.created_by,x.created_at] for x in links],styles),
        Paragraph("Lifecycle",styles["EMS_H2"]),
        _data_table(["From","To","Reason","Owner","By","Time"],[[x.from_state,x.to_state,x.reason,x.owner,x.changed_by,x.occurred_at] for x in events],styles),
        Paragraph("Labor",styles["EMS_H2"]),
        _data_table(["User","Type","Start","End","Minutes","Status","Note"],[[x.username,x.work_type,x.started_at,x.ended_at,x.duration_minutes,x.status,x.note] for x in logs],styles),
    ]
    story.extend(_attachments_story(attachments,styles))
    return _build(path,f"{wo.work_order_no} - {wo.title}",f"{wo.equipment_id} | {wo.priority} | {wo.status}",story)


def export_qualification_pdf(db,run_no: str,path: str) -> str:
    styles=_styles();run=next((x for x in db.list_qualification_runs() if x.run_no==run_no),None)
    if not run:raise ValueError("Qualification run not found")
    checks=json.loads(run.frozen_checks_json or "[]");results=json.loads(run.results_json or "{}");attachments=db.list_attachments("QUALIFICATION",run.run_no)
    rows=[]
    for check in checks:
        cid=str(check.get("check_id") or check.get("id") or check.get("name") or "")
        r=results.get(cid,{}) if isinstance(results,dict) else {}
        rows.append([cid,check.get("name") or check.get("description") or "",check.get("acceptance") or "",r.get("result",""),r.get("value",""),r.get("comment","")])
    story=[
        Paragraph("Qualification Summary",styles["EMS_H2"]),
        _kv_table([("Equipment",run.equipment_id),("Protocol",f"{run.protocol_id} R{run.protocol_revision}"),("Status",run.status),("Started",f"{_text(run.started_at)} by {run.started_by}"),("Verified",f"{_text(run.verified_at)} by {run.verified_by}"),("Approved",f"{_text(run.approved_at)} by {run.approved_by}"),("Expires",run.expires_at),("Conclusion",run.conclusion)],styles),
        Paragraph("Checks / Results",styles["EMS_H2"]),
        _data_table(["Check","Description","Acceptance","Result","Value","Comment"],rows,styles),
    ]
    story.extend(_attachments_story(attachments,styles))
    return _build(path,f"Qualification - {run.run_no}",f"{run.equipment_id} | {run.protocol_id} R{run.protocol_revision} | {run.status}",story)


def export_release_pdf(db,release_id: int,path: str) -> str:
    styles=_styles();rel=next((x for x in db.list_release_requests() if x.id==int(release_id)),None)
    if not rel:raise ValueError("Release request not found")
    checks=json.loads(rel.checks_json or "{}");attachments=db.list_attachments("RELEASE",str(rel.id))
    story=[
        Paragraph("Release Summary",styles["EMS_H2"]),
        _kv_table([("Equipment",rel.equipment_id),("Status",rel.status),("Related ticket",rel.related_ticket),("Requested",f"{_text(rel.requested_at)} by {rel.requested_by}"),("Verified",f"{_text(rel.verified_at)} by {rel.verified_by}"),("Approved",f"{_text(rel.approved_at)} by {rel.approved_by}"),("Notes",rel.notes)],styles),
        Paragraph("Release Checklist",styles["EMS_H2"]),
        _data_table(["Check","Result"],[[key,"PASS" if value else "FAIL"] for key,value in checks.items()],styles,[120*mm,60*mm]),
    ]
    story.extend(_attachments_story(attachments,styles))
    return _build(path,f"Equipment Release - {rel.equipment_id}",f"Release #{rel.id} | {rel.status}",story)


def export_weekly_review_pdf(db,path: str,days: int=7) -> str:
    styles=_styles();data=db.engineering_analytics(days);pm=data["pm"]
    critical=[x for x in db.list_tickets() if x.status not in {"Closed","Cancelled"} and x.priority in {"P1","P2"}]
    attention=db.operations_attention_queue(100)
    fleet=sum(float(x["availability_pct"]) for x in data["tool_matrix"])/len(data["tool_matrix"]) if data["tool_matrix"] else 100.0
    story=[
        Paragraph("Fleet Scorecard",styles["EMS_H2"]),
        _kv_table([("Period",f"{data['start']:%Y-%m-%d} to {data['end']:%Y-%m-%d}"),("Fleet availability",f"{fleet:.1f}%"),("PM compliance",f"{pm['compliance_pct']:.1f}%"),("PM overdue",pm["overdue"]),("PM deferred",pm["deferred"]),("Open P1/P2",len(critical))],styles),
        Paragraph("Chronic / High-Downtime Tools",styles["EMS_H2"]),
        _data_table(["Equipment","Avail %","Failures","Unplanned h","MTTR h","MTBF h","Open Inc","Alarms","State"],[[x["equipment_id"],f"{x['availability_pct']:.1f}",x["failure_count"],f"{x['unplanned_downtime_hours']:.1f}",f"{x['mttr_hours']:.1f}",f"{x['mtbf_hours']:.1f}",x["open_incidents"],x["active_alarms"],x["current_state"]] for x in data["tool_matrix"][:20]],styles),
        Paragraph("Alarm Pareto",styles["EMS_H2"]),
        _data_table(["Alarm","Message","Count"],[[x["alarm_code"],x["message"],x["count"]] for x in data["alarm_pareto"][:20]],styles),
        Paragraph("Open Critical Incidents",styles["EMS_H2"]),
        _data_table(["Ticket","Equipment","Priority","Status","Owner","Title"],[[x.ticket_no,x.equipment_id,x.priority,x.status,x.owner,x.title] for x in critical[:25]],styles),
        Paragraph("Operational Priorities",styles["EMS_H2"]),
        _data_table(["Severity","Type","Equipment","Key","Condition / Action","Owner"],[[x.get("severity"),x.get("kind"),x.get("equipment_id"),x.get("key"),x.get("summary"),x.get("owner")] for x in attention[:30]],styles),
    ]
    return _build(path,"Equipment Engineering Review",f"{data['start']:%Y-%m-%d} to {data['end']:%Y-%m-%d}",story)
