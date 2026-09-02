import alam_image_renderer as renderer


def main():
    missing_generated = {
        "id": "missing-generated-asset-test",
        "_category": "discover",
        "title": "Missing generated image must still render",
        "summary": "Renderer fallback test.",
        "tags": ["ALAM", "test"],
        "generated_image": {
            "status": "ready",
            "path": "alam_app/assets/editorial/generated/2099/01/does-not-exist.webp",
        },
    }
    html = renderer.article_image_html(missing_generated)
    assert '<img class="article-img-fallback"' in html
    assert "data:image/" in html
    assert "background-image:" not in html

    dead_remote = dict(missing_generated)
    dead_remote["image_url"] = "https://example.invalid/definitely-missing.jpg"
    layered = renderer.article_image_html(dead_remote)
    assert layered.count("<img") == 2
    assert 'class="article-img-fallback"' in layered
    assert 'class="article-img-external"' in layered
    assert "data:image/" in layered

    print("ALAM reliable image renderer test passed")


if __name__ == "__main__":
    main()
