from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parent
DOC = json.loads((ROOT / "data" / "questions.json").read_text(encoding="utf-8"))
qs = DOC["questions"]
errors = []

if len(qs) != 650:
    errors.append(f"Expected 650 questions, found {len(qs)}")
ids = [q.get("id") for q in qs]
if len(ids) != len(set(ids)):
    errors.append("Duplicate question IDs found")
if set(q.get("bank") for q in qs) != {"A1", "B1"}:
    errors.append(f"Unexpected bank labels: {sorted(set(q.get('bank') for q in qs))}")
if sum(q.get("bank") == "A1" for q in qs) != 150:
    errors.append("A1 count is not 150")
if sum(q.get("bank") == "B1" for q in qs) != 500:
    errors.append("B1 count is not 500")

image_refs = []
for q in qs:
    for field in ["id", "bank", "question_en", "explanation", "category"]:
        if not q.get(field):
            errors.append(f"{q.get('id')}: missing {field}")
    if not isinstance(q.get("answer"), bool):
        errors.append(f"{q.get('id')}: answer is not boolean")
    for img in q.get("images") or []:
        image_refs.append(img)
        if not (ROOT / img).exists():
            errors.append(f"Missing image: {img}")

if len(image_refs) != 133:
    errors.append(f"Expected 133 image references, found {len(image_refs)}")

# Privacy/provenance scrub check. Search deployable text and filenames for a removed source-site label.
# We intentionally derive the token so the literal itself is not stored in this package.
blocked = "men" + "kyo" + "blog"
for p in ROOT.rglob("*"):
    if blocked.lower() in p.name.lower():
        errors.append(f"Blocked label in filename: {p.relative_to(ROOT)}")
    if p.is_file() and p.suffix.lower() in {".py", ".json", ".md", ".txt", ".toml", ".sql"}:
        text = p.read_text(encoding="utf-8", errors="ignore")
        if blocked.lower() in text.lower():
            errors.append(f"Blocked label in text: {p.relative_to(ROOT)}")

print(f"Questions: {len(qs)}")
print(f"A1: {sum(q.get('bank') == 'A1' for q in qs)}")
print(f"B1: {sum(q.get('bank') == 'B1' for q in qs)}")
print(f"Image refs: {len(image_refs)}")
print(f"Errors: {len(errors)}")
for e in errors:
    print("-", e)
sys.exit(1 if errors else 0)
