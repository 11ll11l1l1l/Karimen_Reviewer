from __future__ import annotations

import json
import os
import platform
import socket
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from preflight import run_preflight


PERFORMANCE_TARGETS={
    "dashboard_counts_s":2.0,
    "attention_queue_s":2.0,
    "global_search_s":0.75,
    "equipment_timeline_s":1.5,
}

REQUIRED_UAT_SCENARIOS=[
    ("UAT-EE-01","Equipment Engineer","Alarm to incident to RCA/CAPA to work order to qualification to release"),
    ("UAT-MT-01","Maintenance Technician","Execute PM with frozen SOP/spec, evidence, parts and abnormal result"),
    ("UAT-OP-01","Operator","Acknowledge alarm, create/link incident, review tool state and handover"),
    ("UAT-PE-01","Process Engineer","Review qualification evidence and independent verification"),
    ("UAT-SL-01","Shift Leader","Publish handover from automatically assembled operational work"),
    ("UAT-EM-01","Equipment Manager","Review reliability/Pareto, weekly report and action queue"),
    ("UAT-DC-01","Document Controller","Create, approve, supersede and integrity-check controlled document"),
    ("UAT-AD-01","Administrator","Configure scope, form/template, workflow rule and integration mapping"),
    ("UAT-RTS-01","Independent Approver","Verify independent return-to-service approval controls"),
    ("UAT-OFFICE-01","Engineer","Excel round-trip plus editable PPTX/PDF report generation"),
    ("UAT-REC-01","Site Admin","Verified backup and scratch restore drill"),
    ("UAT-RES-01","Site Admin","DB/file-server interruption and client recovery"),
    ("UAT-MW-01","Site Team","Concurrent two-workstation edit conflict and recovery"),
]


@dataclass
class Check:
    name: str
    status: str
    detail: str
    seconds: float | None = None


def _timed(name: str, target: float, fn: Callable[[],Any]) -> Check:
    start=time.perf_counter()
    try:
        fn()
        elapsed=time.perf_counter()-start
        return Check(name,"PASS" if elapsed<=target else "FAIL",f"{elapsed:.3f}s; target <= {target:.3f}s",elapsed)
    except Exception as exc:
        elapsed=time.perf_counter()-start
        return Check(name,"FAIL",f"{type(exc).__name__}: {exc}",elapsed)


def generate_uat_template(path: str | os.PathLike[str]) -> dict[str,Any]:
    payload={
        "schema":"EMS_UAT_EVIDENCE_V1",
        "site":"",
        "pilot_scope":"",
        "ems_version":"",
        "started_at":"",
        "completed_at":"",
        "participants":[],
        "defects":{"p0":[],"p1":[],"p2":[]},
        "restore_drill":{"passed":False,"evidence":""},
        "upgrade_rollback":{"passed":False,"evidence":""},
        "site_integrations":{"passed":False,"evidence":""},
        "training":{"complete":False,"evidence":""},
        "support_owner":"",
        "milestone_acceptance":{f"M{i}":False for i in range(15)},
        "scenarios":[
            {"id":sid,"role":role,"scenario":scenario,"status":"NOT_RUN","tester":"","evidence":"","notes":""}
            for sid,role,scenario in REQUIRED_UAT_SCENARIOS
        ],
        "signoff":{"approved":False,"approved_by":[],"date":"","notes":""},
    }
    Path(path).write_text(json.dumps(payload,indent=2),encoding="utf-8")
    return payload


def evaluate_uat(payload: dict[str,Any], max_open_p2: int = 0) -> list[Check]:
    checks=[]
    by_id={str(x.get("id")):x for x in payload.get("scenarios",[])}
    missing=[sid for sid,_,_ in REQUIRED_UAT_SCENARIOS if by_id.get(sid,{}).get("status")!="PASS"]
    checks.append(Check("uat_required_scenarios","PASS" if not missing else "FAIL", "all required scenarios passed" if not missing else "not passed: "+", ".join(missing)))
    defects=payload.get("defects",{})
    checks.append(Check("uat_no_p0","PASS" if not defects.get("p0") else "FAIL",f"open P0={len(defects.get('p0',[]))}"))
    checks.append(Check("uat_no_p1","PASS" if not defects.get("p1") else "FAIL",f"open P1={len(defects.get('p1',[]))}"))
    p2=len(defects.get("p2",[]))
    checks.append(Check("uat_p2_threshold","PASS" if p2<=max_open_p2 else "FAIL",f"open P2={p2}; allowed={max_open_p2}"))
    for key,label in [("restore_drill","restore drill"),("upgrade_rollback","upgrade rollback"),("site_integrations","site integrations")]:
        item=payload.get(key,{})
        checks.append(Check(key,"PASS" if item.get("passed") else "FAIL",item.get("evidence") or f"{label} evidence not recorded"))
    training=payload.get("training",{})
    checks.append(Check("training_complete","PASS" if training.get("complete") else "FAIL",training.get("evidence") or "training evidence not recorded"))
    checks.append(Check("support_owner","PASS" if str(payload.get("support_owner","")).strip() else "FAIL",str(payload.get("support_owner","") or "support owner not assigned")))
    milestones=payload.get("milestone_acceptance",{})
    missing_milestones=[f"M{i}" for i in range(15) if not milestones.get(f"M{i}")]
    checks.append(Check("milestone_acceptance","PASS" if not missing_milestones else "FAIL","M0-M14 accepted" if not missing_milestones else "not accepted: "+", ".join(missing_milestones)))
    signoff=payload.get("signoff",{})
    checks.append(Check("uat_signoff","PASS" if signoff.get("approved") else "FAIL",", ".join(signoff.get("approved_by",[])) or "site signoff not approved"))
    return checks


def run_production_readiness(db, uat_evidence: str = "", max_open_p2: int = 0) -> dict[str,Any]:
    checks:list[Check]=[]
    pre=run_preflight()
    for row in pre["checks"]:
        status=row["status"]
        # Production readiness is stricter than ordinary preflight. SQLite is
        # valid for demo/development but never for a multi-user production gate.
        if row["name"]=="production_database_mode":
            status="FAIL"
        checks.append(Check("preflight:"+row["name"],status,row["detail"]))

    checks.extend([
        _timed("performance:dashboard_counts",PERFORMANCE_TARGETS["dashboard_counts_s"],db.dashboard_counts),
        _timed("performance:attention_queue",PERFORMANCE_TARGETS["attention_queue_s"],lambda:db.operations_attention_queue(200)),
        _timed("performance:global_search",PERFORMANCE_TARGETS["global_search_s"],lambda:db.global_search("__ems_readiness_probe__",100)),
    ])
    equipment=db.list_equipment()
    if equipment:
        eid=equipment[0].equipment_id
        checks.append(_timed("performance:equipment_timeline",PERFORMANCE_TARGETS["equipment_timeline_s"],lambda:db.equipment_activity_timeline(eid,700)))
    else:
        checks.append(Check("performance:equipment_timeline","WARN","no equipment exists; timeline target not exercised"))

    if uat_evidence:
        try:
            payload=json.loads(Path(uat_evidence).read_text(encoding="utf-8"))
            if payload.get("schema")!="EMS_UAT_EVIDENCE_V1":
                checks.append(Check("uat_schema","FAIL","unsupported UAT evidence schema"))
            else:
                checks.extend(evaluate_uat(payload,max_open_p2))
        except Exception as exc:
            checks.append(Check("uat_evidence","FAIL",str(exc)))
    else:
        checks.append(Check("uat_evidence","FAIL","site UAT evidence file not supplied"))

    hard_fail=[x for x in checks if x.status=="FAIL"]
    warnings=[x for x in checks if x.status=="WARN"]
    return {
        "schema":"EMS_PRODUCTION_READINESS_V1",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "host":socket.gethostname(),
        "platform":platform.platform(),
        "release_ready":not hard_fail,
        "failure_count":len(hard_fail),
        "warning_count":len(warnings),
        "checks":[asdict(x) for x in checks],
    }


def write_readiness_report(result: dict[str,Any], path: str | os.PathLike[str]) -> None:
    Path(path).write_text(json.dumps(result,indent=2,default=str),encoding="utf-8")
