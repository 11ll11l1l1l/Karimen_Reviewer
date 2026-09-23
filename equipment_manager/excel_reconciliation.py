"""Round-trip workbook reconciliation primitives for EMS bulk workflows.

The UI/import studio can use these pure functions to compare an edited workbook
with the exported baseline before any database mutation occurs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence
import hashlib
import json


@dataclass(frozen=True)
class RowChange:
    key: str
    kind: str  # added, changed, unchanged, deleted, conflict
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    changed_fields: tuple[str, ...] = ()


def _normalise(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.strip().split())
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def canonical_row(row: Mapping[str, Any], *, ignored_fields: Iterable[str] = ()) -> dict[str, Any]:
    ignored = set(ignored_fields)
    return {
        str(key): _normalise(value)
        for key, value in row.items()
        if str(key) not in ignored
    }


def row_fingerprint(row: Mapping[str, Any], *, ignored_fields: Iterable[str] = ()) -> str:
    payload = canonical_row(row, ignored_fields=ignored_fields)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def reconcile_rows(
    baseline: Sequence[Mapping[str, Any]],
    edited: Sequence[Mapping[str, Any]],
    *,
    key_field: str,
    ignored_fields: Iterable[str] = (),
    reject_duplicates: bool = True,
) -> list[RowChange]:
    """Compare baseline and edited rows without mutating either input.

    Deleted rows are included so callers can require explicit confirmation.
    Duplicate keys are rejected because silently merging them can corrupt bulk
    maintenance updates.
    """
    ignored = set(ignored_fields)

    def index(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for source in rows:
            row = canonical_row(source, ignored_fields=())
            key = str(row.get(key_field, "")).strip()
            if not key:
                raise ValueError(f"Missing required key field: {key_field}")
            if reject_duplicates and key in result:
                raise ValueError(f"Duplicate key in workbook: {key}")
            result[key] = row
        return result

    before = index(baseline)
    after = index(edited)
    changes: list[RowChange] = []

    for key in sorted(set(before) | set(after)):
        old = before.get(key)
        new = after.get(key)
        if old is None:
            changes.append(RowChange(key, "added", None, new))
            continue
        if new is None:
            changes.append(RowChange(key, "deleted", old, None))
            continue

        fields = sorted(set(old) | set(new))
        changed = tuple(
            field for field in fields
            if field not in ignored and _normalise(old.get(field)) != _normalise(new.get(field))
        )
        changes.append(
            RowChange(key, "changed" if changed else "unchanged", old, new, changed)
        )

    return changes


def summarise_changes(changes: Sequence[RowChange]) -> dict[str, int]:
    summary = {"added": 0, "changed": 0, "unchanged": 0, "deleted": 0, "conflict": 0}
    for change in changes:
        summary[change.kind] = summary.get(change.kind, 0) + 1
    return summary
