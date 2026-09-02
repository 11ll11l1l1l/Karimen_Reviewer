import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ERRORS = []


def err(path, msg):
    ERRORS.append(f"{path.relative_to(ROOT)}: {msg}")


def valid_url(value):
    try:
        p = urlparse(str(value))
        return p.scheme in {"http", "https"} and bool(p.netloc)
    except Exception:
        return False


def validate_article(path, row):
    for key in ("id", "agent", "created_at", "type", "title", "summary", "importance", "confidence", "sources", "claims", "content"):
        if key not in row:
            err(path, f"missing {key}")
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
        if kind == "FACT" and not refs:
            err(path, f"FACT claim {i} has no source_refs")
        for ref in refs:
            if not isinstance(ref, int) or ref < 1 or ref > len(sources):
                err(path, f"claim {i} source_ref {ref!r} out of range")


def validate_comment(path, row):
    for key in ("id", "story_id", "created_at", "agent", "persona_id", "body"):
        if not row.get(key):
            err(path, f"missing {key}")


def validate_wisdom(path, row):
    for key in ("date", "based_on", "question", "verses"):
        if not row.get(key):
            err(path, f"missing {key}")
    verses = row.get("verses") or []
    if not isinstance(verses, list) or not 1 <= len(verses) <= 3:
        err(path, "verses must contain 1-3 entries")
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
