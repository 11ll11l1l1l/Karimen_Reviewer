from pathlib import Path

import alam_polish as polish
from alam_generated_images import generated_or_editorial_data_uri


def main():
    record = {
        "id": "image-regression-fire-recall",
        "_category": "practical",
        "title": "Fire recall check: test fallback article",
        "summary": "A safety story with no external or generated image.",
        "tags": ["Japan", "Safety", "Recall"],
        "content": {"action": "DO NOW"},
    }

    fallback = generated_or_editorial_data_uri(record)
    assert fallback.startswith("data:image/"), "fallback must be a browser-embeddable data URI"

    rendered = polish.article_image_html(record)
    lowered = rendered.lower()
    assert "background-image:" in lowered, "article visual must use fail-safe CSS background rendering"
    assert "<img" not in lowered, "fallback article visual must never emit a broken-image <img> element"
    assert "data:image/" in rendered, "rendered article must contain an actual fallback visual"

    app_source = (Path(__file__).resolve().parent / "streamlit_app.py").read_text(encoding="utf-8")
    safe_assignment = "visual_system.article_image_html = polish.article_image_html"
    install_call = "visual_system.install_visual_system(views)"
    assert safe_assignment in app_source, "streamlit entry point must explicitly install the safe renderer"
    assert app_source.index(safe_assignment) < app_source.index(install_call), (
        "safe article renderer must be installed before visual-system closures are created"
    )

    print("ALAM article image regression test passed")


if __name__ == "__main__":
    main()
