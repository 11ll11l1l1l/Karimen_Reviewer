import base64
import mimetypes
from pathlib import Path

from alam_editorial_visual import editorial_data_uri

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
GENERATED_ROOT = (APP_DIR / "assets" / "editorial" / "generated").resolve()

# Persistent visual backfills for the four manual publishing-test stories. These
# are display fallbacks only: a later successful generated_image record still
# takes priority and can replace them without rewriting this map.
BACKFILL_BY_ID = {
    "discover-spin-filter-quantum-dot-2026": "alam_app/assets/editorial/generated/2026/09/spin-filter-backfill.webp",
    "practical-store-gold-buyback-pressure-2026": "alam_app/assets/editorial/generated/2026/09/gold-buyback-backfill.webp",
    "japan-bond-oil-risk-regime-2026-09": "alam_app/assets/editorial/generated/2026/09/japan-bond-oil-backfill.webp",
    "trend-boj-flexible-tightening-regime-2026": "alam_app/assets/editorial/generated/2026/09/boj-flexible-backfill.webp",
}


def _safe_asset_path(value):
    if not value:
        return None
    candidate = (REPO_ROOT / str(value)).resolve()
    try:
        candidate.relative_to(GENERATED_ROOT)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def _safe_generated_path(record):
    generated = record.get("generated_image") or {}
    if isinstance(generated, dict) and generated.get("status") == "ready":
        candidate = _safe_asset_path(generated.get("path"))
        if candidate is not None:
            return candidate

    # A current backfill is intentionally lower priority than system-managed
    # generated_image metadata but higher priority than the deterministic SVG.
    return _safe_asset_path(BACKFILL_BY_ID.get(str(record.get("id") or "")))


def generated_image_data_uri(record):
    path = _safe_generated_path(record)
    if path is None:
        return ""
    mime = mimetypes.guess_type(path.name)[0] or "image/webp"
    try:
        payload = path.read_bytes()
    except OSError:
        return ""
    return f"data:{mime};base64," + base64.b64encode(payload).decode("ascii")


def generated_or_editorial_data_uri(record):
    return generated_image_data_uri(record) or editorial_data_uri(record)
