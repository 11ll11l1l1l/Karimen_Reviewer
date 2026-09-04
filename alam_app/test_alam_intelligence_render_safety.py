import alam_intelligence as intelligence


def test_daily_brief_escapes_story_text_before_unsafe_html(monkeypatch):
    record = {
        "id": "story-1",
        "title": "Price <script>alert(1)</script> & family",
        "summary": "Costs <b>rose</b> & changed",
        "why_it_matters": "Fallback <em>text</em>",
        "content": {},
    }
    rendered = []
    monkeypatch.setattr(intelligence, "daily_three", lambda records: [("KNOW", record)])
    monkeypatch.setattr(intelligence, "personal_relevance", lambda record: 88)
    monkeypatch.setattr(intelligence, "story_lifecycle", lambda record, all_records: "NEW")
    monkeypatch.setattr(
        intelligence.st,
        "markdown",
        lambda body, **kwargs: rendered.append((body, kwargs)),
    )

    intelligence.render_daily_brief([record], [record])

    html, kwargs = rendered[-1]
    assert kwargs["unsafe_allow_html"] is True
    assert "<script>" not in html
    assert "<b>rose</b>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Costs &lt;b&gt;rose&lt;/b&gt; &amp; changed" in html


def test_alert_ribbon_escapes_story_title_before_unsafe_html(monkeypatch):
    record = {"id": "story-2", "title": "Alert <img src=x> & notice", "importance": 95}
    rendered = []
    monkeypatch.setattr(intelligence, "alert_matches", lambda records, all_records: [record])
    monkeypatch.setattr(intelligence, "personal_relevance", lambda record: 91)
    monkeypatch.setattr(
        intelligence.st,
        "markdown",
        lambda body, **kwargs: rendered.append((body, kwargs)),
    )

    intelligence.render_alert_ribbon([record], [record])

    html, kwargs = rendered[-1]
    assert kwargs["unsafe_allow_html"] is True
    assert "<img src=x>" not in html
    assert "Alert &lt;img src=x&gt; &amp; notice" in html


def test_change_snapshot_escapes_explicit_change_summary_before_unsafe_html(monkeypatch):
    record = {"id": "story-3"}
    rendered = []
    monkeypatch.setattr(intelligence, "story_lifecycle", lambda record, all_records: "NEW")
    monkeypatch.setattr(intelligence, "evidence_health", lambda record: ("GOOD", "2 sources"))
    monkeypatch.setattr(intelligence, "personal_relevance", lambda record: 80)
    monkeypatch.setattr(intelligence, "impact_matrix", lambda record: {})
    monkeypatch.setattr(
        intelligence,
        "change_snapshot",
        lambda record, all_records: ("Before <strong>unsafe</strong>", "Now A & B"),
    )
    monkeypatch.setattr(intelligence, "disagreement_signal", lambda record, comments: None)
    monkeypatch.setattr(intelligence, "connected_stories", lambda record, records: [])
    monkeypatch.setattr(
        intelligence.st,
        "markdown",
        lambda body, **kwargs: rendered.append((body, kwargs)),
    )
    monkeypatch.setattr(intelligence.st, "caption", lambda *args, **kwargs: None)

    intelligence.render_story_snapshot(record, [record], [record], [])

    unsafe_html = [body for body, kwargs in rendered if kwargs.get("unsafe_allow_html")]
    assert len(unsafe_html) == 1
    assert "<strong>unsafe</strong>" not in unsafe_html[0]
    assert "Before &lt;strong&gt;unsafe&lt;/strong&gt;" in unsafe_html[0]
    assert "Now A &amp; B" in unsafe_html[0]
