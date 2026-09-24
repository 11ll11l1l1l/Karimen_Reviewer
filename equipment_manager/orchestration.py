from __future__ import annotations

import json
import os

from database import Database


def _topic_matches(pattern: str, topic: str) -> bool:
    pattern=(pattern or "").strip()
    if pattern=="*":return True
    if pattern.endswith("*"):return topic.startswith(pattern[:-1])
    return topic==pattern


def _resolve(data, path: str):
    value=data
    for part in (path or "").split("."):
        if not part:continue
        if not isinstance(value,dict) or part not in value:return None
        value=value[part]
    return value


def _condition_matches(condition: dict, event, payload: dict) -> bool:
    envelope={
        "event_id":event.event_id,"topic":event.topic,"entity_type":event.entity_type,
        "entity_key":event.entity_key,"payload":payload,
    }
    for path,expected in (condition or {}).items():
        actual=_resolve(envelope,str(path))
        if isinstance(expected,list):
            if actual not in expected:return False
        elif isinstance(expected,dict) and "in" in expected:
            if actual not in expected["in"]:return False
        elif actual!=expected:return False
    return True


def process_pending_rules(db: Database, limit: int = 250) -> dict[str,int]:
    stats={"evaluated":0,"matched":0,"executed":0,"skipped":0,"failed":0}
    for event,rule in db.orchestration_candidates(limit):
        stats["evaluated"]+=1
        if not _topic_matches(rule.topic_pattern,event.topic):
            db.mark_orchestration_execution(event.event_id,rule.rule_id,"SKIPPED","Topic does not match")
            stats["skipped"]+=1;continue
        try:condition=json.loads(rule.condition_json or "{}")
        except Exception as exc:
            db.mark_orchestration_execution(event.event_id,rule.rule_id,"FAILED",f"Invalid condition JSON: {exc}")
            stats["failed"]+=1;continue
        payload=json.loads(event.payload_json or "{}")
        if not _condition_matches(condition,event,payload):
            db.mark_orchestration_execution(event.event_id,rule.rule_id,"SKIPPED","Condition does not match")
            stats["skipped"]+=1;continue
        stats["matched"]+=1
        try:
            action=json.loads(rule.action_json or "{}")
            if rule.action_type=="CREATE_INCIDENT_FROM_ALARM":
                if event.entity_type!="ALARM":
                    raise ValueError("CREATE_INCIDENT_FROM_ALARM requires an ALARM event.")
                actor=str(action.get("actor","")).strip()
                if not actor:raise ValueError("Rule action requires an active EMS actor username.")
                owner=str(action.get("owner") or actor).strip()
                ticket=db.create_incident_from_alarm(
                    event.entity_key,actor,owner=owner,workstation="ORCHESTRATION"
                )
                detail=f"Created/linked incident {ticket.ticket_no}"
            else:
                raise ValueError(f"Unsupported orchestration action: {rule.action_type}")
            db.mark_orchestration_execution(event.event_id,rule.rule_id,"EXECUTED",detail)
            stats["executed"]+=1
        except Exception as exc:
            db.mark_orchestration_execution(event.event_id,rule.rule_id,"FAILED",str(exc))
            stats["failed"]+=1
    return stats


def main() -> int:
    db=Database(os.getenv("EMS_DATABASE_URL"))
    result=process_pending_rules(db,500)
    print(json.dumps(result,sort_keys=True))
    return 0 if result["failed"]==0 else 2


if __name__=="__main__":
    raise SystemExit(main())
