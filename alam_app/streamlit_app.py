import streamlit as st

from alam_core import (
    CATEGORY_META,
    FIELD_LABELS,
    TYPE_LABELS,
    CSS,
    init_browser_state,
    latest_by_story,
    load_all_records,
    mark_visit,
)
import alam_mobile_views as views
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
install_visual_system(views)

all_records = load_all_records()
records = latest_by_story(all_records)
# Keep legacy philosophical Reflection records in history, but remove them from the
# current live feed now that Agent 3 has been repurposed. New Agent 3 records use
# explicit market_* types and remain visible under Market.
records = [r for r in records if r.get("_category") != "reflection" or is_market_record(r)]
comments = load_comments()
manager = init_browser_state()

views.render_brand(records)

if records and all(r.get("demo") for r in records):
    st.markdown(
        '<div class="demo-banner"><strong>Prototype mode:</strong> '
        'Sample content muna ito. Live agent records automatically appear as GitHub updates arrive.</div>',
        unsafe_allow_html=True,
    )

selected_id = st.session_state.get("selected_story")
selected = next((r for r in records if str(r.get("id")) == str(selected_id)), None)

if selected:
    views.render_detail(all_records, selected, comments, manager)
else:
    page = st.pills(
        "Navigation",
        ["Today", "Discover", "Action", "Market", "Trends", "More"],
        default="Today",
        required=True,
        label_visibility="collapsed",
        key="main_nav",
        width="stretch",
        bind="query-params",
    )

    if page == "Today":
        views.render_today(all_records, records, comments, manager)
    elif page == "Discover":
        views.render_category(records, "discover", manager, comments)
    elif page == "Action":
        views.render_action_center(records, manager, comments)
    elif page == "Market":
        render_market(records, manager, comments, views)
    elif page == "Trends":
        views.render_category(records, "trend", manager, comments)
    else:
        secondary = st.segmented_control(
            "More",
            ["Predictions", "Following"],
            default="Predictions",
            key="more_nav",
            label_visibility="collapsed",
            width="stretch",
        )
        if secondary == "Following":
            views.render_following(records, manager, comments)
        else:
            views.render_prediction_lab(records)

mark_visit(manager)
views.render_footer(all_records, records, comments)