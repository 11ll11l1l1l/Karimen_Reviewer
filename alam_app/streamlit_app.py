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
from alam_market_views import is_market_record, render_market
from alam_personas import load_comments
from alam_visual_system import BRAND_CSS, install_visual_system

# Agent 3 keeps the internal `reflection` category key for backward compatibility,
# but the live product role is now Japan Market Intelligence.
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
extras.install_extras_css()
install_visual_system(views)
intelligence.init_preferences()

# Article loading is intentionally limited to the four article directories so
# growing comment/wisdom archives do not slow the main feed scan.
all_records = extras.load_article_records()
records = latest_by_story(all_records)
# Preserve legacy philosophical Reflection records in history but keep the current
# public feed focused on Agent 3's explicit market_* records.
records = [r for r in records if r.get("_category") != "reflection" or is_market_record(r)]
comments = load_comments()
manager = init_browser_state()

views.render_brand(records)
extras.render_wisdom_strip()

selected_id = st.session_state.get("selected_story")
selected = next((r for r in records if str(r.get("id")) == str(selected_id)), None)

if selected:
    views.render_detail(all_records, selected, comments, manager)
    intelligence.render_story_snapshot(selected, all_records, records, comments)
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
        elif secondary == "Search":
            extras.render_search(records, comments, manager, views)
        elif secondary == "Saved":
            extras.render_saved(records, manager, comments, views)
        elif secondary == "Predictions":
            views.render_prediction_lab(records)
        elif secondary == "Settings":
            extras.render_settings()
            intelligence.render_preferences()
        else:
            views.render_category(records, "trend", manager, comments)

mark_visit(manager)
views.render_footer(all_records, records, comments)
