from pathlib import Path

import alam_image_renderer as renderer
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

    rendered = renderer.article_image_html(record)
    lowered = rendered.lower()
    assert '<img class="article-img-fallback"' in lowered, "article visual must contain a real fallback image element"
    assert "background-image:" not in lowered, "base64 fallback must not depend on CSS background-image"
    assert "data:image/" in rendered, "rendered article must contain an actual fallback visual"

    app_source = (Path(__file__).resolve().parent / "streamlit_app.py").read_text(encoding="utf-8")
    safe_assignment = "visual_system.article_image_html = image_renderer.article_image_html"
    install_call = "visual_system.install_visual_system(views)"
    assert safe_assignment in app_source, "streamlit entry point must explicitly install the reliable image renderer"
    assert app_source.index(safe_assignment) < app_source.index(install_call), (
        "reliable article renderer must be installed before visual-system closures are created"
    )

    print("ALAM article image regression test passed")


if __name__ == "__main__":
    main()
