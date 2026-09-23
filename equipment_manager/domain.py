from __future__ import annotations

from dataclasses import dataclass


EQUIPMENT_STATES = (
    "Available",
    "Production",
    "Down",
    "PM",
    "Engineering",
    "Standby",
    "Waiting Parts",
    "Waiting Vendor",
    "Qualification",
    "Hold",
    "Restricted",
    "Offline",
    "Decommissioned",
)

STATE_CLASS = {
    "Available": "READY",
    "Production": "PRODUCTIVE",
    "Down": "UNPLANNED_DOWNTIME",
    "PM": "PLANNED_DOWNTIME",
    "Engineering": "ENGINEERING",
    "Standby": "STANDBY",
    "Waiting Parts": "UNPLANNED_DOWNTIME",
    "Waiting Vendor": "UNPLANNED_DOWNTIME",
    "Qualification": "QUALIFICATION",
    "Hold": "HOLD",
    "Restricted": "RESTRICTED",
    "Offline": "OFFLINE",
    "Decommissioned": "DECOMMISSIONED",
}

ALLOWED_TRANSITIONS = {
    "Available": {"Production", "PM", "Engineering", "Standby", "Qualification", "Hold", "Offline"},
    "Production": {"Down", "PM", "Engineering", "Standby", "Hold", "Restricted", "Offline"},
    "Down": {"Engineering", "Waiting Parts", "Waiting Vendor", "Qualification", "Hold", "Offline"},
    "PM": {"Qualification", "Engineering", "Waiting Parts", "Hold", "Available"},
    "Engineering": {"Qualification", "Waiting Parts", "Waiting Vendor", "Hold", "Available"},
    "Standby": {"Production", "PM", "Engineering", "Hold", "Offline"},
    "Waiting Parts": {"Engineering", "PM", "Down", "Hold"},
    "Waiting Vendor": {"Engineering", "Down", "Hold"},
    "Qualification": {"Available", "Production", "Hold", "Engineering"},
    "Hold": {"Engineering", "PM", "Qualification", "Restricted", "Offline"},
    "Restricted": {"Production", "Engineering", "Qualification", "Hold"},
    "Offline": {"Available", "Engineering", "PM", "Decommissioned"},
    "Decommissioned": {"Offline"},
}

REASON_CODES = {
    "INITIAL_STATE": "Initial equipment state",
    "FAILURE": "Equipment failure / alarm",
    "PROCESS_CONCERN": "Process concern",
    "QUALITY_CONCERN": "Quality concern",
    "SAFETY_CONCERN": "Safety concern",
    "PM_SCHEDULED": "Scheduled preventive maintenance",
    "PM_UNSCHEDULED": "Unscheduled maintenance",
    "ENGINEERING_WORK": "Engineering work / troubleshooting",
    "PARTS_SHORTAGE": "Waiting for spare parts",
    "VENDOR_SUPPORT": "Waiting for vendor support",
    "QUALIFICATION": "Qualification / verification",
    "PRODUCTION_PLAN": "Production plan / standby",
    "RELEASED": "Verified and released to service",
    "RESTRICTION": "Restricted operation",
    "OFFLINE": "Planned offline state",
    "DECOMMISSION": "Decommissioning",
    "OTHER": "Other",
}

DOWNTIME_STATES = {"Down", "PM", "Waiting Parts", "Waiting Vendor", "Hold", "Offline"}
OWNER_REQUIRED_STATES = {"Down", "Engineering", "Waiting Parts", "Waiting Vendor", "Qualification", "Hold", "Restricted"}
TICKET_REQUIRED_STATES = {"Down", "Waiting Parts", "Waiting Vendor"}
PRODUCTION_ALLOWED_DISPOSITIONS = {"Released", "Released With Conditions", "Monitoring"}


class TransitionRuleViolation(ValueError):
    pass


@dataclass(frozen=True)
class TransitionDecision:
    current_state: str
    target_state: str
    state_class: str
    downtime: bool


def allowed_targets(current_state: str) -> list[str]:
    return sorted(ALLOWED_TRANSITIONS.get(current_state, set()), key=EQUIPMENT_STATES.index)


def validate_transition(
    current_state: str,
    target_state: str,
    *,
    reason_code: str,
    reason_text: str = "",
    related_ticket: str = "",
    related_pm_task_id: int | None = None,
    owner: str = "",
    disposition: str = "Released",
    override: bool = False,
) -> TransitionDecision:
    if current_state not in EQUIPMENT_STATES:
        raise TransitionRuleViolation(f"Unknown current equipment state: {current_state}")
    if target_state not in EQUIPMENT_STATES:
        raise TransitionRuleViolation(f"Unknown target equipment state: {target_state}")
    if current_state == target_state:
        raise TransitionRuleViolation("Equipment is already in the requested state.")

    if not override and target_state not in ALLOWED_TRANSITIONS[current_state]:
        raise TransitionRuleViolation(
            f"Transition {current_state} -> {target_state} is not permitted. "
            f"Allowed: {', '.join(allowed_targets(current_state)) or 'none'}"
        )

    if reason_code not in REASON_CODES:
        raise TransitionRuleViolation("A valid reason code is required.")

    if target_state in OWNER_REQUIRED_STATES and not owner.strip():
        raise TransitionRuleViolation(f"An accountable owner is required for state '{target_state}'.")

    if target_state in TICKET_REQUIRED_STATES and not related_ticket.strip():
        raise TransitionRuleViolation(f"A related issue ticket is required for state '{target_state}'.")

    if target_state == "PM":
        if reason_code not in {"PM_SCHEDULED", "PM_UNSCHEDULED"}:
            raise TransitionRuleViolation("PM state requires a PM reason code.")
        if reason_code == "PM_SCHEDULED" and not related_pm_task_id:
            raise TransitionRuleViolation("Scheduled PM state requires a related PM task.")

    if target_state == "Waiting Parts" and reason_code != "PARTS_SHORTAGE":
        raise TransitionRuleViolation("Waiting Parts requires reason code PARTS_SHORTAGE.")

    if target_state == "Waiting Vendor" and reason_code != "VENDOR_SUPPORT":
        raise TransitionRuleViolation("Waiting Vendor requires reason code VENDOR_SUPPORT.")

    if target_state == "Qualification" and reason_code != "QUALIFICATION":
        raise TransitionRuleViolation("Qualification state requires reason code QUALIFICATION.")

    if target_state == "Decommissioned" and reason_code != "DECOMMISSION":
        raise TransitionRuleViolation("Decommissioned state requires reason code DECOMMISSION.")

    if target_state == "Production" and disposition not in PRODUCTION_ALLOWED_DISPOSITIONS:
        raise TransitionRuleViolation(
            f"Equipment disposition '{disposition}' does not permit Production state."
        )

    if reason_code in {"FAILURE", "PROCESS_CONCERN", "QUALITY_CONCERN", "SAFETY_CONCERN", "OTHER"} and not reason_text.strip():
        raise TransitionRuleViolation("Detailed reason text is required for this reason code.")

    return TransitionDecision(
        current_state=current_state,
        target_state=target_state,
        state_class=STATE_CLASS[target_state],
        downtime=target_state in DOWNTIME_STATES,
    )

TICKET_STATES = (
    "Open",
    "Assigned",
    "Investigation",
    "Waiting Parts",
    "Waiting Vendor",
    "Waiting Production",
    "Monitoring",
    "Resolved",
    "Verification",
    "Closed",
    "Cancelled",
)

TICKET_ALLOWED_TRANSITIONS = {
    "Open": {"Assigned", "Investigation", "Cancelled"},
    "Assigned": {"Investigation", "Waiting Parts", "Waiting Vendor", "Waiting Production", "Cancelled"},
    "Investigation": {"Waiting Parts", "Waiting Vendor", "Waiting Production", "Monitoring", "Resolved", "Cancelled"},
    "Waiting Parts": {"Investigation", "Waiting Vendor", "Resolved", "Cancelled"},
    "Waiting Vendor": {"Investigation", "Waiting Parts", "Resolved", "Cancelled"},
    "Waiting Production": {"Investigation", "Monitoring", "Resolved", "Cancelled"},
    "Monitoring": {"Investigation", "Resolved", "Cancelled"},
    "Resolved": {"Verification", "Investigation"},
    "Verification": {"Closed", "Investigation"},
    "Closed": {"Investigation"},
    "Cancelled": set(),
}

TICKET_REASON_CODES = {
    "INITIAL_STATE": "Initial ticket state",
    "ASSIGN": "Assign owner",
    "START_INVESTIGATION": "Start / resume investigation",
    "WAIT_PARTS": "Waiting for spare parts",
    "WAIT_VENDOR": "Waiting for vendor support",
    "WAIT_PRODUCTION": "Waiting for production window or confirmation",
    "MONITOR": "Monitor after action",
    "RESOLVE": "Repair / corrective action completed",
    "VERIFY_START": "Begin independent verification",
    "VERIFY_PASS": "Verification passed",
    "VERIFY_FAIL": "Verification failed; return to investigation",
    "REOPEN": "Reopen a resolved or closed incident",
    "CANCEL": "Cancel invalid / duplicate / no-longer-applicable ticket",
}


@dataclass(frozen=True)
class TicketTransitionDecision:
    current_state: str
    target_state: str


def allowed_ticket_targets(current_state: str) -> list[str]:
    return sorted(TICKET_ALLOWED_TRANSITIONS.get(current_state, set()), key=TICKET_STATES.index)


def validate_ticket_transition(
    current_state: str,
    target_state: str,
    *,
    reason_code: str,
    owner: str = "",
    note: str = "",
    override: bool = False,
) -> TicketTransitionDecision:
    if current_state not in TICKET_STATES:
        raise TransitionRuleViolation(f"Unknown current ticket state: {current_state}")
    if target_state not in TICKET_STATES:
        raise TransitionRuleViolation(f"Unknown target ticket state: {target_state}")
    if current_state == target_state:
        raise TransitionRuleViolation("Ticket is already in the requested state.")
    if not override and target_state not in TICKET_ALLOWED_TRANSITIONS[current_state]:
        raise TransitionRuleViolation(
            f"Ticket transition {current_state} -> {target_state} is not permitted. "
            f"Allowed: {', '.join(allowed_ticket_targets(current_state)) or 'none'}"
        )
    if reason_code not in TICKET_REASON_CODES:
        raise TransitionRuleViolation("A valid ticket lifecycle reason code is required.")

    expected = {
        "Assigned": {"ASSIGN"},
        "Waiting Parts": {"WAIT_PARTS"},
        "Waiting Vendor": {"WAIT_VENDOR"},
        "Waiting Production": {"WAIT_PRODUCTION"},
        "Monitoring": {"MONITOR"},
        "Resolved": {"RESOLVE"},
        "Verification": {"VERIFY_START"},
        "Closed": {"VERIFY_PASS"},
        "Cancelled": {"CANCEL"},
    }
    if target_state in expected and reason_code not in expected[target_state]:
        raise TransitionRuleViolation(
            f"Ticket state '{target_state}' requires reason code {', '.join(sorted(expected[target_state]))}."
        )

    if target_state == "Investigation":
        allowed = {"START_INVESTIGATION"}
        if current_state == "Verification":
            allowed.add("VERIFY_FAIL")
        if current_state in {"Resolved", "Closed"}:
            allowed.add("REOPEN")
        if reason_code not in allowed:
            raise TransitionRuleViolation(
                f"Returning to Investigation from '{current_state}' requires an investigation/reopen reason."
            )

    if target_state in {"Assigned", "Investigation", "Waiting Parts", "Waiting Vendor", "Waiting Production", "Monitoring"} and not owner.strip():
        raise TransitionRuleViolation(f"An accountable owner is required for ticket state '{target_state}'.")

    if reason_code in {"CANCEL", "VERIFY_FAIL", "REOPEN"} and not note.strip():
        raise TransitionRuleViolation("Detailed lifecycle notes are required for this transition.")

    return TicketTransitionDecision(current_state=current_state, target_state=target_state)

