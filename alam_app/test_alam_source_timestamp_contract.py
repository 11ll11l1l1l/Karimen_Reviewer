"""Regression guard for source metadata written into Supabase timestamptz columns.

Source publication dates are optional. ALAM must never invent a day when a source only
provides a year, but incomplete/non-ISO values also cannot be sent to Postgres as
``timestamptz``. Content agents therefore either provide a DB-compatible ISO date/time
or omit the field. This keeps trusted reconciliation fail-fast before a malformed
metadata value can produce another partial mirror write.
"""

from __future__ import annotations

from datetime import datetime
import re

from alam_supabase_ingest import ARTICLE_DIRS, _load_json


_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[Tt ].*)?$")


def _is_db_compatible_timestamp(value) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    if not _DATE_PREFIX.fullmatch(text):
        return False
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def test_source_published_at_matches_supabase_timestamp_contract() -> None:
    violations = []
    for category, folder in ARTICLE_DIRS.items():
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*.json")):
            if path.name.startswith("_"):
                continue
            for record in _load_json(path):
                if not isinstance(record, dict):
                    continue
                for index, source in enumerate(record.get("sources") or [], start=1):
                    if not isinstance(source, dict):
                        continue
                    value = source.get("published_at")
                    if not _is_db_compatible_timestamp(value):
                        violations.append(
                            f"{path.relative_to(folder.parent)} source[{index}] published_at={value!r}"
                        )

    assert not violations, (
        "Source published_at must be an ISO date/time accepted by Supabase timestamptz "
        "or be omitted; do not invent a day for year-only metadata:\n"
        + "\n".join(violations)
    )
