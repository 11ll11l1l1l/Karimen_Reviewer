from __future__ import annotations

CRITICAL_STATES={"Down"}
ATTENTION_STATES={"Hold","Waiting Parts","Waiting Vendor","Restricted"}
PLANNED_STATES={"PM","Engineering","Qualification"}
OFFLINE_STATES={"Offline","Decommissioned"}
CRITICAL_ALARM_SEVERITIES={"CRITICAL","FATAL","EMERGENCY","S1","HIGH"}
WARNING_ALARM_SEVERITIES={"WARNING","WARN","MEDIUM","S2"}


def classify_health(
    equipment_status: str,
    *,
    ticket_priorities=(),
    alarm_severities=(),
    abnormal_pm: bool=False,
) -> str:
    """Return one canonical FAB health class.

    Order is deliberate: a manually reported critical problem can make a
    currently-production-labelled tool red before someone updates its formal
    equipment state.
    """
    status=(equipment_status or "").strip()
    priorities={str(x or "").upper() for x in ticket_priorities}
    alarms={str(x or "").upper() for x in alarm_severities}
    if status in CRITICAL_STATES or "P1" in priorities or alarms & CRITICAL_ALARM_SEVERITIES or abnormal_pm:
        return "critical"
    if "P2" in priorities or status in ATTENTION_STATES or alarms & WARNING_ALARM_SEVERITIES or bool(alarms):
        return "attention"
    if status in PLANNED_STATES:
        return "planned"
    if status in OFFLINE_STATES:
        return "offline"
    return "good"


def health_rank(value: str) -> int:
    return {"critical":0,"attention":1,"planned":2,"offline":3,"good":4}.get(value,9)


def health_label(value: str) -> str:
    return {
        "critical":"Critical / down",
        "attention":"Attention",
        "planned":"Planned work",
        "offline":"Offline",
        "good":"Running / good",
    }.get(value,value)
