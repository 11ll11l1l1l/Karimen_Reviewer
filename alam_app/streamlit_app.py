import streamlit as st

from alam_core import CSS, init_browser_state, latest_by_story, load_all_records, mark_visit
from alam_personas import load_comments
from alam_views import (
    render_action_center,
    render_brand,
    render_category,
    render_detail,
    render_following,
    render_footer,
    render_prediction_lab,
    render_today,
)

st.set_page_config(
    page_title="ALAM — Ano'ng bago. Bakit mahalaga.",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(CSS, unsafe_allow_html=True)

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
    page = st.radio(
        "Navigation",
        ["Today", "Discover", "Action Center", "Reflect", "Trends", "Predictions", "Following"],
        horizontal=True,
        label_visibility="collapsed",
        key="main_nav",
    )
    if page == "Today":
        render_today(all_records, records, manager)
    elif page == "Discover":
        render_category(records, "discover", manager)
    elif page == "Action Center":
        render_action_center(records, manager)
    elif page == "Reflect":
        render_category(records, "reflection", manager)
    elif page == "Trends":
        render_category(records, "trend", manager)
    elif page == "Predictions":
        render_prediction_lab(records)
    else:
        render_following(records, manager)

mark_visit(manager)
render_footer(all_records, records, comments)
