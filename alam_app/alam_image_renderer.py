"""Reliable ALAM article image rendering.

The renderer intentionally uses real <img> elements instead of putting base64
images inside CSS background-image declarations. The fallback image is always
rendered first; an external/source image is layered over it when available.
If the external image cannot be hot-linked or returns an error, the underlying
ALAM editorial image remains visible.
"""

import base64
from pathlib import Path
from urllib.parse import urlparse

from alam_core import esc
from alam_generated_images import generated_or_editorial_data_uri

APP_DIR = Path(__file__).resolve().parent
EDITORIAL_DIR = APP_DIR / "assets" / "editorial"


def _asset_data_uri(path):
    try:
        payload = Path(path).read_bytes()
    except OSError:
        return ""
    suffix = Path(path).suffix.lower()
    mime = "image/svg+xml" if suffix == ".svg" else "image/png" if suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(payload).decode("ascii")


STATIC_FALLBACKS = {
    "discover": _asset_data_uri(EDITORIAL_DIR / "discover.svg"),
    "practical": _asset_data_uri(EDITORIAL_DIR / "practical.svg"),
    "reflection": _asset_data_uri(EDITORIAL_DIR / "market.svg"),
    "trend": _asset_data_uri(EDITORIAL_DIR / "trend.svg"),
}


def _fallback(record):
    """Return a browser-renderable image even when generated assets are missing."""
    try:
        value = generated_or_editorial_data_uri(record)
    except Exception:
        value = ""
    if str(value).startswith("data:image/"):
        return value
    category = str(record.get("_category") or "discover")
    return STATIC_FALLBACKS.get(category) or STATIC_FALLBACKS.get("discover", "")


def _external_image(record):
    candidates = [record.get("image_url"), record.get("hero_image"), record.get("thumbnail_url")]
    content = record.get("content") or {}
    image_obj = record.get("image") or content.get("image") or {}
    if isinstance(image_obj, dict):
        candidates.extend([image_obj.get("url"), image_obj.get("image_url")])
    candidates.extend([content.get("image_url"), content.get("hero_image")])
    for value in candidates:
        if value and urlparse(str(value)).scheme in {"http", "https"}:
            return str(value)
    return ""


def _image_credit(record):
    content = record.get("content") or {}
    image_obj = record.get("image") or content.get("image") or {}
    values = [record.get("image_credit"), content.get("image_credit")]
    if isinstance(image_obj, dict):
        values.extend([image_obj.get("credit"), image_obj.get("caption")])
    return next((str(v) for v in values if v), "")


def article_image_html(record, hero=False, show_credit=False):
    """Render source image over a guaranteed editorial fallback without JS."""
    fallback = _fallback(record)
    external = _external_image(record)
    hero_class = " hero" if hero else ""
    alt = record.get("image_alt") or f"Visual for {record.get('title', 'ALAM story')}"

    base_style = (
        "position:absolute;inset:0;width:100%;height:100%;"
        "display:block;object-fit:cover;object-position:center;"
    )

    fallback_html = (
        f'<img class="article-img-fallback" src="{esc(fallback)}" alt="{esc(alt)}" '
        f'loading="lazy" decoding="async" style="{base_style}z-index:0">'
    )

    external_html = ""
    if external:
        # Empty alt prevents a dead remote URL from exposing headline-like broken
        # image text. The guaranteed fallback remains directly underneath.
        external_html = (
            f'<img class="article-img-external" src="{esc(external)}" alt="" aria-hidden="true" '
            f'loading="lazy" decoding="async" style="{base_style}z-index:1;color:transparent;font-size:0;background:transparent">'
        )

    credit_html = ""
    if external and show_credit:
        credit = _image_credit(record)
        if credit:
            credit_html = f'<div class="image-credit" style="z-index:2">{esc(credit)}</div>'

    return (
        f'<div class="article-visual{hero_class}" role="img" aria-label="{esc(alt)}">'
        f'{fallback_html}{external_html}{credit_html}</div>'
    )
