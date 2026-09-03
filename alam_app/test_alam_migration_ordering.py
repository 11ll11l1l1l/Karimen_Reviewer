"""Regression guard for repository Supabase migration identity.

ALAM development agents write migrations concurrently. Reusing an existing numeric
prefix makes repository ordering ambiguous and can cause live schema history to drift
from the audited SQL files. Every migration prefix must therefore be unique.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path


MIGRATION_DIR = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
MIGRATION_RE = re.compile(r"^(\d+)_.*\.sql$")


def test_supabase_migration_prefixes_are_unique() -> None:
    by_prefix: dict[str, list[str]] = defaultdict(list)
    for path in sorted(MIGRATION_DIR.glob("*.sql")):
        match = MIGRATION_RE.match(path.name)
        assert match is not None, f"Migration filename lacks numeric prefix: {path.name}"
        by_prefix[match.group(1)].append(path.name)

    duplicates = {prefix: names for prefix, names in by_prefix.items() if len(names) > 1}
    assert not duplicates, f"Duplicate Supabase migration prefixes: {duplicates}"
