import base64
import mimetypes
from pathlib import Path

from alam_editorial_visual import editorial_data_uri

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
GENERATED_ROOT = (APP_DIR / "assets" / "editorial" / "generated").resolve()


def _safe_generated_path(record):
    generated = record.get("generated_image") or {}
    if not isinstance(generated, dict) or generated.get("status") != "ready":
        return None
    value = generated.get("path")
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
