import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ERRORS = []
V4_CUTOFF = datetime.fromisoformat("2026-09-02T13:20:00+09:00")
V5_CUTOFF = datetime.fromisoformat("2026-09-02T14:30:00+09:00")
LIFECYCLE = {"NEW", "DEVELOPING", "CONFIRMED", "FADING", "RESOLVED"}
IMPACT_LEVELS = {"LOW", "MED", "HIGH"}


def err(path, msg):
    ERRORS.append(f"{path.relative_to(ROOT)}: {msg}")


def valid_url(value):
    try:
        p = urlparse(str(value))
        return p.scheme in {"http", "https"} and bool(p.netloc)
    except Exception:
        return False


def record_time(row):
    try:
        value = datetime.fromisoformat(str(row.get("created_at", "")).replace("Z", "+00:00"))
        return value if value.tzinfo is not None else None
    except Exception:
        return None


def is_v4(row):
    value = record_time(row)
    return bool(value and value >= V4_CUTOFF)


def is_v5(row):
    value = record_time(row)
    return bool(value and value >= V5_CUTOFF)


def validate_article(path, row):
    required = ["id", "agent", "created_at", "type", "title", "summary", "importance", "confidence", "sources", "content"]
    if is_v4(row):
        required.append("claims")
    if is_v5(row):
        required.extend(["why_it_matters", "status"])
    for key in required:
        if key not in row:
            err(path, f"missing {key}")
    if is_v5(row) and str(row.get("status", "")).upper() not in LIFECYCLE:
        err(path, f"status must be one of {sorted(LIFECYCLE)}")
    for key in ("importance", "confidence"):
        value = row.get(key)
        if not isinstance(value, int) or not 0 <= value <= 100:
            err(path, f"{key} must be integer 0-100")
    sources = row.get("sources") or []
    if not isinstance(sources, list):
        err(path, "sources must be list")
        sources = []
    for i, source in enumerate(sources, 1):
        if not isinstance(source, dict) or not valid_url(source.get("url")):
            err(path, f"source {i} missing valid http(s) url")
    claims = row.get("claims") or []
    if not isinstance(claims, list):
        err(path, "claims must be list")
        return
    for i, claim in enumerate(claims, 1):
        if not isinstance(claim, dict):
            err(path, f"claim {i} must be object")
            continue
        kind = str(claim.get("kind", "")).upper()
        if kind not in {"FACT", "INFERENCE", "ESTIMATE", "ASSUMPTION", "OPINION"}:
            err(path, f"claim {i} invalid kind")
        refs = claim.get("source_refs") or []
        if kind == "FACT" and is_v4(row) and not refs:
            err(path, f"FACT claim {i} has no source_refs")
        for ref in refs:
            if not isinstance(ref, int) or ref < 1 or ref > len(sources):
                err(path, f"claim {i} source_ref {ref!r} out of range")
    content = row.get("content") or {}
    if not isinstance(content, dict):
        err(path, "content must be object")
        return
    impact = content.get("impact")
    if impact is not None:
        if not isinstance(impact, dict):
            err(path, "content.impact must be object")
        else:
            for key in ("money", "family", "career", "japan", "urgency"):
                if key in impact and str(impact[key]).upper() not in IMPACT_LEVELS:
                    err(path, f"content.impact.{key} must be LOW/MED/HIGH")
    change = content.get("change_summary")
    if change is not None and not isinstance(change, dict):
        err(path, "content.change_summary must be object")


def validate_comment(path, row):
    for key in ("id", "story_id", "created_at", "agent", "persona_id", "body"):
        if not row.get(key):
            err(path, f"missing {key}")
    if is_v5(row) and row.get("stance") and str(row.get("stance")).upper() not in {"SUPPORT", "CHALLENGE", "MIXED"}:
        err(path, "stance must be SUPPORT/CHALLENGE/MIXED")


def validate_wisdom(path, row):
    for key in ("date", "based_on", "question", "verses"):
        if not row.get(key):
            err(path, f"missing {key}")
    verses = row.get("verses") or []
    if not isinstance(verses, list) or not 1 <= len(verses) <= 2:
        err(path, "verses must contain 1-2 entries")
    for i, verse in enumerate(verses, 1):
        if not isinstance(verse, dict) or not verse.get("reference") or not verse.get("text"):
            err(path, f"verse {i} missing reference/text")


for path in sorted(DATA.rglob("*.json")):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        err(path, f"invalid JSON: {exc}")
        continue
    rows = payload if isinstance(payload, list) else [payload]
    for row in rows:
        if not isinstance(row, dict):
            err(path, "record must be object")
            continue
        parts = set(path.relative_to(DATA).parts)
        if "wisdom" in parts:
            validate_wisdom(path, row)
        elif "comments" in parts:
            validate_comment(path, row)
        else:
            validate_article(path, row)

if ERRORS:
    print("ALAM data validation failed:")
    for item in ERRORS:
        print(" -", item)
    raise SystemExit(1)
print("ALAM data validation passed")
