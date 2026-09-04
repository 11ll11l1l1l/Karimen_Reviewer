import re
import sys

import streamlit as st

import alam_core
import alam_hybrid_feed
import alam_mobile_shell
import alam_auth


EXPECTED_SUPABASE_PROJECT_REF = "zecztyabmmoqzjumhxxf"


def numeric_score(value, default=50.0):
    """Convert loose ALAM score fields into a safe 0-100 number.

    New records occasionally carry semantic values such as HIGH/MEDIUM/LOW or
    nested score objects. Ranking should degrade gracefully instead of taking the
    entire Streamlit app down.
    """
    if value is None or value == "":
        return float(default)
    if isinstance(value, bool):
        return 100.0 if value else 0.0
    if isinstance(value, (int, float)):
        return max(0.0, min(100.0, float(value)))
    if isinstance(value, dict):
        for key in ("score", "value", "percent", "percentage", "rating"):
            if key in value:
                return numeric_score(value.get(key), default)
        return float(default)
    text = str(value).strip().upper()
    semantic = {
        "VERY HIGH": 90.0,
        "HIGH": 80.0,
        "MEDIUM-HIGH": 70.0,
        "MED-HIGH": 70.0,
        "MEDIUM": 55.0,
        "MED": 55.0,
        "LOW-MEDIUM": 40.0,
        "LOW": 30.0,
        "VERY LOW": 15.0,
    }
    if text in semantic:
        return semantic[text]
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return float(default)
    try:
        return max(0.0, min(100.0, float(match.group(0))))
    except (TypeError, ValueError):
        return float(default)


def _recency_bonus(record):
    """Strong age bonus that keeps fresh reporting ahead of stale high-score stories."""
    record = record if isinstance(record, dict) else {}
    created = alam_core.parse_dt(record.get("created_at"))
    age_hours = max(
        0.0,
        (alam_core.current_utc() - created).total_seconds() / 3600.0,
    )
    # Freshness is intentionally dominant. Quality still matters inside each age band.
    knots = (
        (0.0, 80.0),
        (24.0, 60.0),
        (72.0, 35.0),
        (168.0, 10.0),
        (336.0, 0.0),
    )
    if age_hours <= knots[0][0]:
        return knots[0][1]
    for (age0, score0), (age1, score1) in zip(knots, knots[1:]):
        if age_hours <= age1:
            ratio = (age_hours - age0) / (age1 - age0)
            return score0 + (score1 - score0) * ratio
    return 0.0


def safe_feed_score(record):
    """Rank every ALAM feed with recency first and quality as the secondary signal."""
    record = record if isinstance(record, dict) else {}
    content = record.get("content")
    content = content if isinstance(content, dict) else {}
    sources = record.get("sources")
    source_count = len(sources) if isinstance(sources, list) else 0
    return (
        _recency_bonus(record)
        + 0.20 * numeric_score(record.get("importance"), 50)
        + 0.10 * numeric_score(content.get("usefulness"), 55)
        + 0.08 * numeric_score(record.get("confidence"), 50)
        + 0.05 * numeric_score(content.get("novelty"), 55)
        + min(5.0, source_count * 1.25)
    )


def _sort_feed_records(records):
    return sorted(
        list(records or []),
        key=lambda record: (
            safe_feed_score(record),
            alam_core.parse_dt((record or {}).get("created_at")).timestamp(),
        ),
        reverse=True,
    )


def _normalize_intelligence_scores(record):
    """Normalize score fields before legacy personalization/lifecycle float casts.

    ALAM's v5 data contract accepts semantic and nested score shapes, while the
    personalization module still has a few mature code paths that cast these fields
    directly with ``float``. Copying the record keeps the source/audit object intact
    while making those calculations use the same bounded score semantics as feeds.
    """
    if not isinstance(record, dict):
        return record
    normalized = dict(record)
    normalized["importance"] = numeric_score(record.get("importance"), 50)
    normalized["confidence"] = numeric_score(record.get("confidence"), 0)
    return normalized


def _install_intelligence_score_guard():
    """Keep personalization and lifecycle calculations compatible with v5 scores."""
    intelligence = sys.modules.get("alam_intelligence")
    if intelligence is None:
        return

    personal_relevance = getattr(intelligence, "personal_relevance", None)
    if personal_relevance is not None and not getattr(personal_relevance, "_alam_score_guard", False):
        original_personal_relevance = personal_relevance

        def guarded_personal_relevance(record):
            return original_personal_relevance(_normalize_intelligence_scores(record))

        guarded_personal_relevance._alam_score_guard = True
        intelligence.personal_relevance = guarded_personal_relevance

    story_lifecycle = getattr(intelligence, "story_lifecycle", None)
    if story_lifecycle is not None and not getattr(story_lifecycle, "_alam_score_guard", False):
        original_story_lifecycle = story_lifecycle

        def guarded_story_lifecycle(record, all_records):
            return original_story_lifecycle(_normalize_intelligence_scores(record), all_records)

        guarded_story_lifecycle._alam_score_guard = True
        intelligence.story_lifecycle = guarded_story_lifecycle


def _install_recency_priority_hooks():
    """Make recency-first ordering apply to custom Today and Trend renderers too."""
    today_page = sys.modules.get("alam_today_page")
    intelligence = sys.modules.get("alam_intelligence")
    current_rank = getattr(today_page, "_rank", None) if today_page else None
    if (
        current_rank is not None
        and intelligence is not None
        and not getattr(current_rank, "_alam_recency_first", False)
    ):
        def recency_first_rank(record):
            return (
                safe_feed_score(record),
                intelligence.personal_relevance(record),
            )

        recency_first_rank._alam_recency_first = True
        today_page._rank = recency_first_rank

    mobile_views = sys.modules.get("alam_mobile_views")
    current_render = getattr(mobile_views, "render_category", None) if mobile_views else None
    if current_render is None or getattr(current_render, "_alam_recency_first", False):
        return
    original_render = current_render

    def render_category_recency_first(records, category, manager=None, comments=None):
        if category != "trend":
            return original_render(records, category, manager, comments)

        meta = mobile_views.CATEGORY_META[category]
        descriptions = {
            "discover": "Fresh developments na worth knowing — hindi basta trending lang.",
            "practical": "Tipid, safety, risk at Japan life advice na may totoong action.",
            "reflection": "Psychology, philosophy at modern Christian life — mas malalim kaysa headline.",
            "trend": "Patterns, predictions at signals na lumalakas, humihina, o bumabaliktad.",
        }
        mobile_views.st.markdown(
            f'<div class="hero mobile-hero"><div class="hero-kicker" style="color:{meta["accent"]}">'
            f'{meta["emoji"]} {mobile_views.esc(meta["label"])}</div>'
            f'<div class="hero-title">{mobile_views.esc(meta["question"])}</div>'
            f'<div class="hero-copy">{mobile_views.esc(descriptions[category])}</div></div>',
            unsafe_allow_html=True,
        )
        search = mobile_views.st.text_input(
            "Hanapin",
            placeholder="Search Japan, AI, money, faith…",
            key=f"search_{category}_mobile",
            type="search",
            label_visibility="collapsed",
        )
        selected_filter = mobile_views.st.pills(
            "Filter",
            ["All", "New", "High confidence", "Following"],
            default="All",
            required=True,
            key=f"filter_{category}_mobile",
            label_visibility="collapsed",
            width="stretch",
        )
        subset = [r for r in records if r.get("_category") == category]
        if search:
            q = search.lower().strip()
            subset = [
                r
                for r in subset
                if q in mobile_views.json.dumps(r, ensure_ascii=False).lower()
            ]
        if selected_filter == "New":
            ref = mobile_views.st.session_state.get("visit_reference")
            if ref:
                subset = [
                    r
                    for r in subset
                    if mobile_views.parse_dt(r.get("created_at")).astimezone(
                        mobile_views.timezone.utc
                    )
                    > ref.astimezone(mobile_views.timezone.utc)
                ]
        elif selected_filter == "High confidence":
            subset = [r for r in subset if int(r.get("confidence", 0) or 0) >= 85]
        elif selected_filter == "Following":
            subset = [r for r in subset if mobile_views.is_followed(r.get("id"))]
        if not subset:
            mobile_views.st.markdown(
                '<div class="empty-box">Walang matching items ngayon.</div>',
                unsafe_allow_html=True,
            )
            return
        subset.sort(key=safe_feed_score, reverse=True)
        cols = mobile_views.st.columns(2, wrap=True)
        for i, record in enumerate(subset):
            with cols[i % 2]:
                mobile_views.render_card(
                    record,
                    f"{category}_mobile_{i}",
                    manager,
                    comments,
                )

    render_category_recency_first._alam_recency_first = True
    mobile_views.render_category = render_category_recency_first
    for name, module in list(sys.modules.items()):
        if not name.startswith("alam_") or module is None:
            continue
        if getattr(module, "render_category", None) is original_render:
            setattr(module, "render_category", render_category_recency_first)


def _is_expected_supabase_url(url):
    """True only for ALAM's production Project2 host.

    The account also contains an older Supabase project. A valid publishable key for
    that older project can make a shallow connection check look healthy while ALAM
    silently reads the wrong empty schema. Pinning only the project host prevents that
    class of deployment drift without exposing or hard-coding any private credential.
    """
    text = str(url or "").strip().lower()
    text = re.sub(r"^https?://", "", text)
    host = text.split("/", 1)[0].split(":", 1)[0]
    return host == f"{EXPECTED_SUPABASE_PROJECT_REF}.supabase.co"


def _install_supabase_project_guard():
    """Refuse a silently wrong Supabase project across public and Auth clients."""
    supabase_module = sys.modules.get("alam_supabase")
    current = getattr(supabase_module, "get_supabase_public", None) if supabase_module else None
    if current is not None and not getattr(current, "_alam_project_guard", False):
        original = current

        def guarded_get_supabase_public(*args, **kwargs):
            try:
                configured_url = st.secrets["SUPABASE_URL"]
            except Exception:
                return original(*args, **kwargs)
            if not _is_expected_supabase_url(configured_url):
                raise RuntimeError(
                    "ALAM Supabase configuration points to an unexpected project. "
                    "Use the production ALAM Project2 deployment."
                )
            return original(*args, **kwargs)

        guarded_get_supabase_public._alam_project_guard = True
        supabase_module.get_supabase_public = guarded_get_supabase_public

        for name, module in list(sys.modules.items()):
            if not name.startswith("alam_") or module is None:
                continue
            if getattr(module, "get_supabase_public", None) is original:
                setattr(module, "get_supabase_public", guarded_get_supabase_public)

    auth_credentials = getattr(alam_auth, "_credentials", None)
    if auth_credentials is not None and not getattr(auth_credentials, "_alam_project_guard", False):
        original_auth_credentials = auth_credentials

        def guarded_auth_credentials():
            url, key = original_auth_credentials()
            if not _is_expected_supabase_url(url):
                raise RuntimeError(
                    "ALAM Auth configuration points to an unexpected Supabase project. "
                    "Use the production ALAM Project2 deployment."
                )
            return url, key

        guarded_auth_credentials._alam_project_guard = True
        alam_auth._credentials = guarded_auth_credentials


def _install_cookie_layout_guard():
    """Keep CookieManager functional without allowing its iframe to move the page."""
    if alam_core.stx is None:
        return
    current = getattr(alam_core.stx, "CookieManager", None)
    if current is None or getattr(current, "_alam_layout_guard", False):
        return

    original = current

    def guarded_cookie_manager(*args, **kwargs):
        alam_mobile_shell.install_cookie_guard()
        with st.container(key="alam_cookie_host"):
            return original(*args, **kwargs)

    guarded_cookie_manager._alam_layout_guard = True
    alam_core.stx.CookieManager = guarded_cookie_manager


def _overlay_verified_audit(records, extras):
    """Add only GitHub versions missing from an otherwise live Supabase result."""
    if st.session_state.get("alam_content_source") != "supabase":
        return records
    local_loader = getattr(extras, "_load_local_article_records", None)
    if local_loader is None:
        return records
    audit_records = local_loader()
    merged, overlay_count = alam_hybrid_feed.merge_missing_audit_versions(records, audit_records)
    if overlay_count:
        st.session_state["alam_content_source"] = "hybrid_fallback"
        st.session_state["alam_audit_overlay_versions"] = int(overlay_count)
        return merged
    st.session_state.pop("alam_audit_overlay_versions", None)
    return records


def _install_hybrid_feed_hooks():
    """Keep verified hourly agent output visible while the trusted mirror lags."""
    extras = sys.modules.get("alam_extras")
    if extras is None:
        return

    full_loader = getattr(extras, "load_article_records", None)
    if full_loader is not None and not getattr(full_loader, "_alam_hybrid_overlay", False):
        original_full = full_loader

        def load_article_records_with_overlay(*args, **kwargs):
            records = original_full(*args, **kwargs)
            records = _overlay_verified_audit(records, extras)
            return _sort_feed_records(records)

        load_article_records_with_overlay._alam_hybrid_overlay = True
        extras.load_article_records = load_article_records_with_overlay

    article_scope = sys.modules.get("alam_article_scope")
    current_loader = getattr(article_scope, "load_current_article_records", None) if article_scope else None
    if current_loader is not None and not getattr(current_loader, "_alam_hybrid_overlay", False):
        original_current = current_loader

        def load_current_article_records_with_overlay(*args, **kwargs):
            records = original_current(*args, **kwargs)
            records = _overlay_verified_audit(records, extras)
            return _sort_feed_records(records)

        load_current_article_records_with_overlay._alam_hybrid_overlay = True
        article_scope.load_current_article_records = load_current_article_records_with_overlay


def _install_mobile_shell_hooks():
    """Apply compact mobile chrome through modules already called by streamlit_app."""
    extras = sys.modules.get("alam_extras")
    if extras is not None:
        current = getattr(extras, "install_extras_css", None)
        if current is not None and not getattr(current, "_alam_mobile_shell", False):
            original = current

            def install_extras_and_mobile_shell():
                original()
                alam_mobile_shell.install_mobile_shell()

            install_extras_and_mobile_shell._alam_mobile_shell = True
            extras.install_extras_css = install_extras_and_mobile_shell

    readiness = sys.modules.get("alam_readiness")
    if readiness is not None:
        readiness.render_runtime_status = alam_mobile_shell.render_runtime_status


def _install_account_settings_hook():
    """Add optional account controls only inside Settings, never above the mobile shell.

    This placement deliberately avoids creating another custom-component or auth surface
    above the ALAM brand/Today content. Anonymous readers see no login wall; Settings
    owns the explicit distinction between browser recognition and an optional account.
    """
    extras = sys.modules.get("alam_extras")
    if extras is None:
        return
    current = getattr(extras, "render_settings", None)
    if current is None or getattr(current, "_alam_account_settings", False):
        return
    original = current

    def render_settings_with_account(*args, **kwargs):
        result = original(*args, **kwargs)
        st.divider()
        alam_auth.render_account_settings()
        return result

    render_settings_with_account._alam_account_settings = True
    extras.render_settings = render_settings_with_account


def install_runtime_safety():
    """Install score hardening, recency priority, project pinning and UI guards."""
    alam_core.feed_score = safe_feed_score
    for name, module in list(sys.modules.items()):
        if not name.startswith("alam_") or module is None:
            continue
        if hasattr(module, "feed_score"):
            setattr(module, "feed_score", safe_feed_score)

    _install_intelligence_score_guard()
    _install_recency_priority_hooks()
    _install_supabase_project_guard()
    _install_cookie_layout_guard()
    _install_hybrid_feed_hooks()
    _install_mobile_shell_hooks()
    _install_account_settings_hook()
