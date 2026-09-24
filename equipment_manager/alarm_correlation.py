"""Deterministic alarm burst correlation for the EMS alarm console.

Raw alarms are preserved; callers can use the returned IDs to drill down or
create one incident for a correlated burst.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable

_SEVERITY_RANK = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


@dataclass(frozen=True)
class AlarmBurst:
    burst_key: str
    equipment_id: str
    alarm_code: str
    severity: str
    first_seen: datetime
    last_seen: datetime
    alarm_ids: tuple[str, ...]
    count: int

    @property
    def duration_seconds(self) -> float:
        return max(0.0, (self.last_seen - self.first_seen).total_seconds())


def correlate_alarm_bursts(
    alarms: Iterable[dict[str, Any]], *, window_seconds: int = 300
) -> list[AlarmBurst]:
    """Group temporally adjacent alarms without losing event identity."""
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")

    normalised = []
    for index, alarm in enumerate(alarms):
        equipment = str(alarm.get("equipment_id", "")).strip()
        code = str(alarm.get("alarm_code", "")).strip()
        occurred = alarm.get("occurred_at")
        if not equipment or not code or not isinstance(occurred, datetime):
            raise ValueError(f"Alarm {index + 1} is missing correlation fields")
        normalised.append((
            equipment, code, occurred,
            str(alarm.get("severity", "UNKNOWN")).upper(),
            str(alarm.get("id", index + 1)),
        ))

    normalised.sort(key=lambda item: (item[0], item[1], item[2], item[4]))
    result = []
    current = []

    def flush():
        if not current:
            return
        first, last = current[0], current[-1]
        severity = max(
            (item[3] for item in current),
            key=lambda value: _SEVERITY_RANK.get(value, 0),
        )
        result.append(AlarmBurst(
            burst_key=f"{first[0]}:{first[1]}:{first[2].isoformat()}",
            equipment_id=first[0],
            alarm_code=first[1],
            severity=severity,
            first_seen=first[2],
            last_seen=last[2],
            alarm_ids=tuple(item[4] for item in current),
            count=len(current),
        ))

    for item in normalised:
        if (
            current
            and (
                item[0] != current[-1][0]
                or item[1] != current[-1][1]
                or item[2] - current[-1][2] > timedelta(seconds=window_seconds)
            )
        ):
            flush()
            current = []
        current.append(item)
    flush()
    # Correlation is grouped by equipment/code internally, but callers consume
    # bursts as an operational time stream. Return a deterministic chronological
    # order independent of equipment/alarm-code lexical ordering.
    result.sort(key=lambda burst: (
        burst.first_seen,
        burst.equipment_id,
        burst.alarm_code,
        burst.burst_key,
    ))
    return result
