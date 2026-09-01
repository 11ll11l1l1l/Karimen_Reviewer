import streamlit as st

from alam_core import CSS, init_browser_state, latest_by_story, load_all_records, mark_visit
from alam_mobile_views import (
    MOBILE_CSS,
    render_action_center,
    render_brand,
    render_category,
    render_detail,
    render_following,
    render_footer,
    render_prediction_lab,
    render_today,
)
from alam_personas import load_comments

st.set_page_config(
    page_title="ALAM — Ano'ng bago. Bakit mahalaga.",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(MOBILE_CSS, unsafe_allow_html=True)

all_records = load_all_records()
records = latest_by_story(all_records)
comments = load_comments()
manager = init_browser_state()

render_brand(records)

if records and all(r.get("demo") for r in records):
    st.markdown(
        '<div class="demo-banner"><strong>Prototype mode:</strong> '
        'Sample content muna ito. Live agent records automatically appear as GitHub updates arrive.</div>',
        unsafe_allow_html=True,
    )

selected_id = st.session_state.get("selected_story")
selected = next((r for r in records if str(r.get("id")) == str(selected_id)), None)

if selected:
    render_detail(all_records, selected, comments, manager)
else:
    page = st.pills(
        "Navigation",
        ["Today", "Discover", "Action", "Reflect", "Trends", "More"],
        default="Today",
        required=True,
        label_visibility="collapsed",
        key="main_nav",
        width="stretch",
        bind="query-params",
    )

    if page == "Today":
        render_today(all_records, records, comments, manager)
    elif page == "Discover":
        render_category(records, "discover", manager, comments)
    elif page == "Action":
        render_action_center(records, manager, comments)
    elif page == "Reflect":
        render_category(records, "reflection", manager, comments)
    elif page == "Trends":
        render_category(records, "trend", manager, comments)
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
            render_following(records, manager, comments)
        else:
            render_prediction_lab(records)

mark_visit(manager)
render_footer(all_records, records, comments)
