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
import alam_polish as polish
from alam_market_views import is_market_record, render_market
from alam_personas import load_comments
from alam_visual_system import BRAND_CSS, install_visual_system

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
st.markdown(BRAND_CSS, unsafe_allow_html=True)
st.markdown(intelligence.INTEL_CSS, unsafe_allow_html=True)
st.markdown(reader.READER_CSS, unsafe_allow_html=True)
st.markdown(polish.POLISH_CSS, unsafe_allow_html=True)

# Load browser-local state before display-specific CSS so persisted dark mode and
# preferences can take effect on the first useful render without a backend.
manager = init_browser_state()
localstate.init_local_profile(manager)
intelligence.init_preferences()
extras.install_extras_css()
install_visual_system(views)
polish.install(views, reader)

# Article loading is intentionally limited to the four article directories so
# growing discussion/wisdom archives do not slow the main feed scan.
all_records = extras.load_article_records()
current_records = latest_by_story(all_records)
# Preserve older philosophical records in history while the current public section
# shows only explicit market_* records from this storage slot.
current_records = [r for r in current_records if r.get("_category") != "reflection" or is_market_record(r)]
# Muting is local to the reader. It hides future feed appearances without changing
# or deleting shared ALAM intelligence.
records = [r for r in current_records if not localstate.is_muted(r)]
comments = load_comments()

views.render_brand(records)
extras.render_wisdom_strip()

selected_id = st.session_state.get("selected_story")
# Allow a muted story that is already open to remain accessible so it can be
# unmuted from its detail page.
selected = next((r for r in current_records if str(r.get("id")) == str(selected_id)), None)

if selected:
    views.render_detail(all_records, selected, comments, manager)
    intelligence.render_story_snapshot(selected, all_records, records, comments)
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
        intelligence.render_alert_ribbon(records, all_records)
        intelligence.render_daily_brief(records, all_records)
        reader.render_inbox(records, all_records, manager)
        views.render_today(all_records, records, comments, manager)
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
            st.divider()
            reader.render_agent_audit(records, all_records, comments)
        elif secondary == "Search":
            extras.render_search(records, comments, manager, views)
        elif secondary == "Saved":
            extras.render_saved(records, manager, comments, views)
        elif secondary == "Predictions":
            views.render_prediction_lab(records)
        elif secondary == "Settings":
            extras.render_settings()
            intelligence.render_preferences(manager)
            st.divider()
            reader.render_local_profile(current_records, manager)
            st.divider()
            reader.render_offline_pack(records, all_records)
        else:
            views.render_category(records, "trend", manager, comments)

mark_visit(manager)
views.render_footer(all_records, records, comments)
