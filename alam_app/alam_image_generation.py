import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
DATA_DIR = APP_DIR / "data"
GENERATED_DIR = APP_DIR / "assets" / "editorial" / "generated"
ARTICLE_DIRS = {
    "discover": DATA_DIR / "discover",
    "reflection": DATA_DIR / "reflection",
    "practical": DATA_DIR / "practical",
    "trend": DATA_DIR / "trend",
}
JAPAN_TZ = ZoneInfo("Asia/Tokyo")

DEFAULT_MODEL = os.environ.get("ALAM_IMAGE_MODEL", "gpt-image-2")
DEFAULT_SIZE = os.environ.get("ALAM_IMAGE_SIZE", "1536x864")
DEFAULT_QUALITY = os.environ.get("ALAM_IMAGE_QUALITY", "medium")
DEFAULT_COMPRESSION = int(os.environ.get("ALAM_IMAGE_COMPRESSION", "82"))

SERIOUS_TERMS = {
    "death", "died", "fatal", "killed", "injury", "injured", "accident", "disaster",
    "earthquake", "tsunami", "typhoon", "flood", "fire", "recall", "medical", "disease",
    "crime", "abuse", "war", "attack", "scam", "fraud", "legal", "warning", "risk",
}
CATEGORY_STYLE = {
    "discover": "modern science-and-technology magazine editorial illustration",
    "reflection": "sophisticated financial newspaper editorial illustration",
    "practical": "clear consumer-advice magazine editorial illustration",
    "trend": "forward-looking analytical magazine editorial illustration",
}


def _external_image(record):
    candidates = [
        record.get("image_url"),
        record.get("hero_image"),
        record.get("thumbnail_url"),
    ]
    content = record.get("content") or {}
    image_obj = record.get("image") or content.get("image") or {}
    if isinstance(image_obj, dict):
        candidates.extend([image_obj.get("url"), image_obj.get("image_url")])
    candidates.extend([content.get("image_url"), content.get("hero_image")])
    for candidate in candidates:
        if candidate and urlparse(str(candidate)).scheme in {"http", "https"}:
            return str(candidate)
    return ""


def _editorial_visual(record):
    content = record.get("content") or {}
    value = record.get("editorial_visual") or content.get("editorial_visual") or {}
    return value if isinstance(value, dict) else {}


def _slug(value):
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return cleaned[:72] or "alam-story"


def _signature(record):
    editorial = _editorial_visual(record)
    payload = {
        "id": record.get("id"),
        "title": record.get("title"),
        "summary": record.get("summary"),
        "why_it_matters": record.get("why_it_matters"),
        "editorial_visual": editorial,
        "category": record.get("_category") or record.get("agent"),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _relative_asset_path(record, signature):
    created = str(record.get("created_at") or "")
    try:
        dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JAPAN_TZ)
        dt = dt.astimezone(JAPAN_TZ)
        year, month = f"{dt.year:04d}", f"{dt.month:02d}"
    except Exception:
        year, month = "undated", "00"
    name = f"{_slug(record.get('id') or record.get('title'))}-{signature[:8]}.webp"
    return Path("alam_app") / "assets" / "editorial" / "generated" / year / month / name


def _is_serious(record, editorial):
    text = " ".join(
        [
            str(record.get("title", "")),
            str(record.get("summary", "")),
            " ".join(str(x) for x in (record.get("tags") or [])),
        ]
    ).lower()
    try:
        silliness = int(editorial.get("silliness", 18))
    except (TypeError, ValueError):
        silliness = 18
    return silliness <= 10 or any(term in text for term in SERIOUS_TERMS)


def build_prompt(record):
    editorial = _editorial_visual(record)
    category = str(record.get("_category") or record.get("agent") or "discover")
    style = CATEGORY_STYLE.get(category, "high-quality magazine editorial illustration")
    serious = _is_serious(record, editorial)

    scene = str(editorial.get("scene") or "").strip()
    caption = str(editorial.get("caption") or "").strip()
    motif = str(editorial.get("motif") or "").strip()
    secondary = str(editorial.get("secondary_motif") or "").strip()
    try:
        silliness = max(0, min(100, int(editorial.get("silliness", 18))))
    except (TypeError, ValueError):
        silliness = 18
    try:
        exaggeration = max(0, min(100, int(editorial.get("exaggeration", 42))))
    except (TypeError, ValueError):
        exaggeration = 42

    if serious:
        silliness = min(silliness, 8)
        tone = (
            "Restrained, respectful, calm and factual in tone. Avoid comedy, caricature of victims, "
            "sensationalism, gore, fear-mongering, or dramatic disaster spectacle."
        )
    elif silliness >= 60:
        tone = "Playful and witty editorial metaphor, visually surprising but still intelligent and readable."
    elif silliness >= 30:
        tone = "Lightly playful editorial metaphor with a smart magazine feel."
    else:
        tone = "Serious but visually expressive editorial metaphor."

    title = str(record.get("title") or "").strip()
    summary = str(record.get("summary") or "").strip()
    why = str(record.get("why_it_matters") or "").strip()
    prompt = f"""
Create a unique 16:9 landscape ALAM editorial image for this verified news/intelligence article.

Editorial style: {style}.
Article headline: {title}
Article summary: {summary}
Why it matters: {why}

Art direction from the publishing agent:
- Primary motif: {motif or "choose the clearest symbolic motif from the story"}
- Secondary motif: {secondary or "optional"}
- Scene/metaphor: {scene or "translate the article into one immediately understandable visual metaphor"}
- Intended caption idea (do NOT render this as text): {caption or "none"}
- Silliness level: {silliness}/100
- Exaggeration level: {exaggeration}/100

Tone: {tone}

Composition requirements:
- Strong single editorial concept, not a collage.
- Magazine-quality illustration with depth, intentional lighting and a clear focal point.
- Crop-safe 16:9 composition; keep the main subject away from extreme edges.
- Use symbolic objects and metaphor instead of fabricating documentary evidence.
- Do not depict an unverified factual event as if it were a real photograph.
- Do not create recognizable real people unless absolutely necessary; prefer symbolic or anonymous figures.
- No text, letters, numbers, captions, logos, trademarks, UI, charts with readable labels, or watermarks inside the image.
- Avoid generic stock-photo aesthetics.
- The image is an illustration accompanying reporting, not evidence.
""".strip()
    return prompt


def _generated_is_current(record, signature):
    generated = record.get("generated_image") or {}
    if not isinstance(generated, dict):
        return False
    if generated.get("status") != "ready" or generated.get("prompt_signature") != signature:
        return False
    rel = generated.get("path")
    if not rel:
        return False
    return (REPO_ROOT / str(rel)).is_file()


def _load_payload(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_payload(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _article_json_paths():
    for directory in ARTICLE_DIRS.values():
        if not directory.exists():
            continue
        yield from sorted(directory.glob("*.json"))


def _changed_paths(revision):
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", revision, "HEAD", "--", "alam_app/data"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        print(f"Could not inspect changed files from {revision}: {exc}", file=sys.stderr)
        return []
    allowed_roots = {str(path.relative_to(REPO_ROOT)) for path in ARTICLE_DIRS.values()}
    selected = []
    for line in result.stdout.splitlines():
        rel = line.strip()
        if not rel.endswith(".json"):
            continue
        if any(rel.startswith(root + "/") for root in allowed_roots):
            path = REPO_ROOT / rel
            if path.is_file():
                selected.append(path)
    return selected


def _latest_per_agent_paths():
    selected = []
    for directory in ARTICLE_DIRS.values():
        files = sorted(directory.glob("*.json"))
        if files:
            selected.append(files[-1])
    return selected


def select_paths(changed_since=None, latest_per_agent=False, latest_if_empty=False, all_files=False):
    if all_files:
        return list(_article_json_paths())
    selected = _changed_paths(changed_since) if changed_since else []
    if latest_per_agent or (latest_if_empty and not selected):
        selected.extend(_latest_per_agent_paths())
    unique = []
    seen = set()
    for path in selected:
        resolved = path.resolve()
        if resolved not in seen:
            unique.append(path)
            seen.add(resolved)
    return unique


def _generate_bytes(client, prompt, model, size, quality, compression):
    result = client.images.generate(
        model=model,
        prompt=prompt,
        n=1,
        size=size,
        quality=quality,
        background="opaque",
        output_format="webp",
        output_compression=compression,
        moderation="auto",
    )
    if not result.data or not result.data[0].b64_json:
        raise RuntimeError("Image API returned no image data")
    return base64.b64decode(result.data[0].b64_json)


def process_file(path, client=None, dry_run=False):
    payload = _load_payload(path)
    rows = payload if isinstance(payload, list) else [payload]
    changed = False
    generated_count = 0

    for record in rows:
        if not isinstance(record, dict) or not record.get("id"):
            continue
        category = path.parent.name
        record.setdefault("_category", category)
        if _external_image(record):
            record.pop("_category", None)
            continue

        editorial = _editorial_visual(record)
        if not editorial:
            # Legacy records continue to use the local SVG fallback. New publishing
            # agents are expected to provide editorial_visual art direction.
            record.pop("_category", None)
            continue

        signature = _signature(record)
        if _generated_is_current(record, signature):
            record.pop("_category", None)
            continue

        rel_asset = _relative_asset_path(record, signature)
        prompt = build_prompt(record)
        if dry_run:
            print(f"WOULD GENERATE {record.get('id')} -> {rel_asset}")
            record.pop("_category", None)
            continue
        if client is None:
            raise RuntimeError("OpenAI client is required for generation")

        try:
            image_bytes = _generate_bytes(
                client,
                prompt,
                DEFAULT_MODEL,
                DEFAULT_SIZE,
                DEFAULT_QUALITY,
                DEFAULT_COMPRESSION,
            )
            asset_path = REPO_ROOT / rel_asset
            asset_path.parent.mkdir(parents=True, exist_ok=True)
            asset_path.write_bytes(image_bytes)
            record["generated_image"] = {
                "status": "ready",
                "path": rel_asset.as_posix(),
                "model": DEFAULT_MODEL,
                "size": DEFAULT_SIZE,
                "quality": DEFAULT_QUALITY,
                "format": "webp",
                "prompt_signature": signature,
                "generated_at": datetime.now(JAPAN_TZ).isoformat(timespec="seconds"),
            }
            changed = True
            generated_count += 1
            print(f"GENERATED {record.get('id')} -> {rel_asset}")
        except Exception as exc:
            # Publishing must remain resilient. The app will render the deterministic
            # SVG editorial fallback while a later run can retry image generation.
            print(f"IMAGE GENERATION FAILED for {record.get('id')}: {exc}", file=sys.stderr)

        record.pop("_category", None)

    for record in rows:
        if isinstance(record, dict):
            record.pop("_category", None)

    if changed:
        _write_payload(path, payload)
    return generated_count


def self_test():
    sample = {
        "id": "sample-chip-story",
        "agent": "discover",
        "_category": "discover",
        "created_at": "2026-09-02T19:22:00+09:00",
        "title": "A chip does something useful",
        "summary": "A short verified summary.",
        "why_it_matters": "It could simplify a process.",
        "tags": ["Japan", "semiconductor"],
        "editorial_visual": {
            "style": "editorial",
            "motif": "chip",
            "secondary_motif": "factory",
            "scene": "an oversized chip calmly slots into a factory line",
            "caption": "Smaller architecture, bigger effect",
            "silliness": 20,
            "exaggeration": 60,
        },
    }
    prompt = build_prompt(sample)
    signature = _signature(sample)
    path = _relative_asset_path(sample, signature)
    assert "No text" in prompt
    assert path.suffix == ".webp"
    assert "2026/09" in path.as_posix()
    print("ALAM editorial image generation self-test passed")


def main():
    parser = argparse.ArgumentParser(description="Generate persistent ALAM editorial images for articles without real images.")
    parser.add_argument("--changed-since", help="Git revision to diff against, e.g. HEAD^")
    parser.add_argument("--latest-per-agent", action="store_true", help="Process the latest JSON file in each article directory")
    parser.add_argument("--latest-if-empty", action="store_true", help="Use latest-per-agent if the revision changed no article JSON")
    parser.add_argument("--all", action="store_true", help="Process all article JSON files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated without calling the API")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    paths = select_paths(
        changed_since=args.changed_since,
        latest_per_agent=args.latest_per_agent,
        latest_if_empty=args.latest_if_empty,
        all_files=args.all,
    )
    if not paths:
        print("No eligible ALAM article files selected.")
        return 0

    client = None
    if not args.dry_run:
        if not os.environ.get("OPENAI_API_KEY"):
            print("OPENAI_API_KEY is not configured; generated-image step skipped.", file=sys.stderr)
            return 0
        try:
            from openai import OpenAI
        except ImportError:
            print("The openai package is required for image generation.", file=sys.stderr)
            return 2
        client = OpenAI()

    total = 0
    for path in paths:
        total += process_file(path, client=client, dry_run=args.dry_run)
    print(f"Generated {total} editorial image(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
