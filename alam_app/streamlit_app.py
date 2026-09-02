import streamlit as st

from alam_core import (
    CATEGORY_META,
    FIELD_LABELS,
    TYPE_LABELS,
    CSS,
    init_browser_state,
    latest_by_story,
    mark_visit,
)
import alam_mobile_views as views
import alam_extras as extras
import alam_intelligence as intelligence
import alam_local_state as localstate
import alam_reader_views as reader
import alam_story_page as story_page
import alam_panel_views as panel_views
import alam_saved_views as saved_views
import alam_today_page as today_page
import alam_polish as polish
import alam_image_renderer as image_renderer
import alam_portraits as portraits
import alam_visual_system as visual_system
import alam_time_theme as time_theme
import alam_time_headers as time_headers
import alam_supabase_views as dbviews
import alam_readiness as readiness
import alam_evidence_views as evidence_views
from alam_generated_images import generated_or_editorial_data_uri
from alam_market_views import is_market_record, render_market
from alam_personas import load_comments
from alam_runtime_safety import install_runtime_safety

# Harden ranking against loose score fields in newly generated records before any
# feed sorting happens. A malformed usefulness/novelty label must never crash ALAM.
install_runtime_safety()

# The legacy `reflection` storage key now powers the Market section.
CATEGORY_META["reflection"].update({
    "emoji": "📊",
    "label": "Market",
    "question": "Ano ang gumagalaw sa market?",
    "accent": "#2F6FB0",
    "soft": "#EAF2FB",
})
TYPE_LABELS.update({
    "market_outlook": "📊 MARKET OUTLOOK",
    "market_recap": "🏁 MARKET CLOSE",
    "market_risk": "⚠️ MARKET RISK",
    "market_regime": "🧭 MARKET REGIME",
    "weekly_intelligence": "📅 WEEKLY INTELLIGENCE",
})
FIELD_LABELS.update({
    "session": "Session",
    "market_regime": "Market regime",
    "what_moved": "Ano ang gumalaw",
    "why_it_moved": "Bakit gumalaw",
    "japan_transmission": "Paano tumatama sa Japan",
    "breadth_and_sectors": "Breadth at sectors",
    "fx_rates_cross_asset": "FX, rates at cross-asset",
    "fundamental_vs_positioning": "Fundamentals vs positioning",
    "bull_case": "Bull case",
    "bear_case": "Bear case",
    "market_pricing_inference": "Ano ang posibleng pine-price ng market",
    "opening_bias": "Opening bias",
    "forecast_next_session": "Next-session outlook",
    "forecast_5d": "Next 5 trading days",
    "forecast_1_3m": "1–3 month outlook",
    "catalysts": "Next catalysts",
    "practical_guidelines": "Practical investor guidelines",
    "forecast_scorecard": "Forecast scorecard",
})

st.set_page_config(
    page_title="ALAM — See · Understand · Act",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(views.MOBILE_CSS, unsafe_allow_html=True)
st.markdown(visual_system.BRAND_CSS, unsafe_allow_html=True)
st.markdown(intelligence.INTEL_CSS, unsafe_allow_html=True)
st.markdown(reader.READER_CSS, unsafe_allow_html=True)
st.markdown(story_page.STORY_PAGE_CSS, unsafe_allow_html=True)
st.markdown(panel_views.PANEL_CSS, unsafe_allow_html=True)
st.markdown(saved_views.SAVED_CSS, unsafe_allow_html=True)
st.markdown(today_page.TODAY_CSS, unsafe_allow_html=True)
st.markdown(readiness.RUNTIME_STATUS_CSS, unsafe_allow_html=True)
st.markdown(evidence_views.EVIDENCE_CSS, unsafe_allow_html=True)
st.markdown(polish.POLISH_CSS, unsafe_allow_html=True)
st.markdown(portraits.PORTRAIT_CSS, unsafe_allow_html=True)

# Load browser-local state before display-specific CSS so persisted preferences can
# take effect on the first useful render without a backend.
manager = init_browser_state()
localstate.init_local_profile(manager)
intelligence.init_preferences()
extras.install_extras_css()


def _sanitize_preference_state():
    """Repair stale/invalid browser preference values before Streamlit builds widgets."""
    prefs = st.session_state.get("alam_interest_preferences")
    if not isinstance(prefs, dict):
        st.session_state["alam_interest_preferences"] = dict(intelligence.DEFAULT_INTERESTS)
    else:
        cleaned = dict(intelligence.DEFAULT_INTERESTS)
        for name in cleaned:
            if name in prefs:
                cleaned[name] = bool(prefs[name])
        st.session_state["alam_interest_preferences"] = cleaned

    try:
        minimum = int(st.session_state.get("alam_alert_min_importance", 85))
    except (TypeError, ValueError):
        minimum = 85
    minimum = max(50, min(100, minimum))
    # The slider uses increments of five; normalize old values to a valid step.
    minimum = int(round(minimum / 5) * 5)
    st.session_state["alam_alert_min_importance"] = minimum
    st.session_state["alam_alert_only_actionable"] = bool(
        st.session_state.get("alam_alert_only_actionable", False)
    )
    st.session_state["alam_alert_material_change"] = bool(
        st.session_state.get("alam_alert_material_change", True)
    )

    # Streamlit widget keys can survive reruns in a malformed state after an older
    # app version. Remove only values with the wrong type so the widgets recreate.
    for i in range(len(intelligence.DEFAULT_INTERESTS)):
        key = f"interest_{i}"
        if key in st.session_state and not isinstance(st.session_state[key], bool):
            del st.session_state[key]


# Always render a genuine image element for the ALAM fallback. Source/official
# images are layered over it, so a dead remote image can never leave a blank card.
# Persistent generated WebPs still take priority inside the fallback resolver;
# when they do not exist, a deterministic editorial SVG is rendered underneath.
visual_system._svg_data_uri = generated_or_editorial_data_uri
polish.article_image_html = image_renderer.article_image_html
visual_system.article_image_html = image_renderer.article_image_html
visual_system.install_visual_system(views)
polish.install(views, reader)
# Reassert the reliable renderer after plugin installation so future install-order
# changes cannot silently restore the old CSS-background implementation.
visual_system.article_image_html = image_renderer.article_image_html
# The detailed panel is installed over the original compact renderer instead of
# duplicating panel call sites. Story page, Deep view, and any future caller all get
# the same stance/reply/evidence-aware discussion behavior automatically.
panel_views.install(views)
# Replace the old generic sprite with the fixed generated character portraits.
portraits.install(views)
# Apply this last so the moving sun/moon atmosphere tints the full app without
# replacing category/story identity colors. It uses Japan local time on rerun.
time_theme.install_time_theme()

# Supabase is now the preferred source of truth. During migration the loader keeps
# the existing local article folders as a safe fallback until published DB content
# exists, so the live app never goes blank during cutover. Historical DB versions are
# also folded into all_records so existing Before/Now timelines keep working.
all_records = extras.load_article_records()
current_records = latest_by_story(all_records)
# Preserve older philosophical records in history while the current public section
# shows only explicit market_* records from this storage slot.
current_records = [r for r in current_records if r.get("_category") != "reflection" or is_market_record(r)]
# Muting is local to the reader. It hides future feed appearances without changing
# or deleting shared ALAM intelligence.
records = [r for r in current_records if not localstate.is_muted(r)]
# When the feed is Supabase-backed, cross-agent perspectives are loaded from the DB
# for these story IDs; otherwise the existing local comment archive remains active.
comments = load_comments([r.get("id") for r in current_records])

views.render_brand(records)
# Make the active persistence mode visible. A healthy-looking header should never
# imply "database live" while ALAM is deliberately serving the GitHub audit fallback.
readiness.render_runtime_status()
# A six-scene Japan-time header makes the daypart immediately visible; the continuous
# palette/sun-position theme underneath still changes smoothly between these scenes.
time_headers.render_time_header()
extras.render_wisdom_strip()

selected_id = st.session_state.get("selected_story")
# Allow a muted story that is already open to remain accessible so it can be
# unmuted from its detail page.
selected = next((r for r in current_records if str(r.get("id")) == str(selected_id)), None)

if selected:
    # The page-level reader now puts the four decision questions ahead of the depth
    # selector: why it matters, what to do, what changed, and how strong the evidence
    # is. Panel/Evidence/Deep still reuse the mature renderers underneath.
    story_page.render_story_page(all_records, selected, comments, manager)
    dbviews.render_story_connections(selected, current_records)
    reader.render_detail_reader_controls(selected, manager)
    extras.render_share_tools(selected)
else:
    page = st.pills(
        "Navigation",
        ["Today", "Discover", "Action", "Market", "More"],
        default="Today",
        required=True,
        label_visibility="collapsed",
        key="main_nav",
        width="stretch",
        bind="query-params",
    )

    if page == "Today":
        # Today now owns one decision hierarchy instead of stacking a second urgent
        # strip/top-story/briefing after the existing 3-line brief and inbox.
        today_page.render_today(records, all_records, comments, manager, views, reader)
    elif page == "Discover":
        views.render_category(records, "discover", manager, comments)
    elif page == "Action":
        views.render_action_center(records, manager, comments)
    elif page == "Market":
        render_market(records, manager, comments, views)
    else:
        secondary = st.segmented_control(
            "More",
            ["Trends", "Weekly", "Search", "Saved", "Predictions", "Settings"],
            default="Trends",
            key="more_nav",
            label_visibility="collapsed",
            width="stretch",
        )
        if secondary == "Weekly":
            intelligence.render_weekly(records, all_records)
            dbviews.render_connect_the_dots(records)
            st.divider()
            reader.render_agent_audit(records, all_records, comments)
        elif secondary == "Search":
            extras.render_search(records, comments, manager, views)
        elif secondary == "Saved":
            saved_views.render_saved(records, manager, comments, views)
        elif secondary == "Predictions":
            dbviews.render_prediction_lab(records, views.render_prediction_lab)
        elif secondary == "Settings":
            extras.render_settings()
            # Connectivity and feed-source labels are useful but insufficient during
            # migration. The readiness panel independently compares the committed
            # GitHub audit archive with public Supabase rows so a failed/stale mirror
            # cannot be mistaken for a successful production cutover.
            readiness.render_cutover_readiness()
            _sanitize_preference_state()
            try:
                intelligence.render_preferences(manager)
            except Exception:
                # Settings must never take down the whole ALAM app. The database
                # status above remains usable even if a local preference widget fails.
                st.warning("Personal relevance controls were reset because the saved browser state was invalid. Reload Settings once.")
                st.session_state["alam_interest_preferences"] = dict(intelligence.DEFAULT_INTERESTS)
                st.session_state["alam_alert_min_importance"] = 85
                st.session_state["alam_alert_only_actionable"] = False
                st.session_state["alam_alert_material_change"] = True
            st.divider()
            reader.render_local_profile(current_records, manager)
            st.divider()
            reader.render_offline_pack(records, all_records)
        else:
            views.render_category(records, "trend", manager, comments)

mark_visit(manager)
views.render_footer(all_records, records, comments)