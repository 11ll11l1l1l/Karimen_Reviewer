from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

JAPAN_TZ = ZoneInfo("Asia/Tokyo")

# Light, low-contrast anchors intentionally preserve ALAM's existing content and
# category colors. The app interpolates between anchors so the atmosphere changes
# gradually instead of flipping at fixed boundaries.
THEME_ANCHORS = [
    (0.0, {"name": "midnight", "bg": "#F0F2F7", "bg2": "#ECEFF5", "surface": "#FAFBFD", "glow1": "#6878AA", "glow2": "#8A739E", "accent": "#5E6D99"}),
    (5.0, {"name": "dawn", "bg": "#F7F2F2", "bg2": "#F3ECEE", "surface": "#FFFDFC", "glow1": "#C98FA3", "glow2": "#D7A46F", "accent": "#9B6E7E"}),
    (8.0, {"name": "morning", "bg": "#F7F5EF", "bg2": "#F2F4EE", "surface": "#FFFFFC", "glow1": "#DDB36A", "glow2": "#79AFA5", "accent": "#8D794C"}),
    (12.0, {"name": "midday", "bg": "#F3F6F3", "bg2": "#EEF3F2", "surface": "#FFFFFF", "glow1": "#7FA9D8", "glow2": "#6CAF91", "accent": "#527FA8"}),
    (16.0, {"name": "golden", "bg": "#F8F4ED", "bg2": "#F5EFE8", "surface": "#FFFCF8", "glow1": "#D6A46D", "glow2": "#C9826D", "accent": "#A46B48"}),
    (19.0, {"name": "evening", "bg": "#F4F1F6", "bg2": "#EFEDF4", "surface": "#FCFAFD", "glow1": "#8B76B2", "glow2": "#BA7994", "accent": "#765F98"}),
    (22.0, {"name": "late", "bg": "#F1F3F7", "bg2": "#ECEFF5", "surface": "#FAFBFD", "glow1": "#6577A8", "glow2": "#7C6D99", "accent": "#5F6E98"}),
    (24.0, {"name": "midnight", "bg": "#F0F2F7", "bg2": "#ECEFF5", "surface": "#FAFBFD", "glow1": "#6878AA", "glow2": "#8A739E", "accent": "#5E6D99"}),
]


def _rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(channel))):02X}" for channel in rgb)


def _mix_hex(left, right, amount):
    a = _rgb(left)
    b = _rgb(right)
    return _hex(tuple(a[i] + (b[i] - a[i]) * amount for i in range(3)))


def _mix_rgb_string(left, right, amount):
    a = _rgb(left)
    b = _rgb(right)
    mixed = tuple(round(a[i] + (b[i] - a[i]) * amount) for i in range(3))
    return ",".join(str(v) for v in mixed)


def theme_for_time(now=None):
    now = now or datetime.now(JAPAN_TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=JAPAN_TZ)
    else:
        now = now.astimezone(JAPAN_TZ)

    hour = now.hour + now.minute / 60.0 + now.second / 3600.0
    left_hour, left = THEME_ANCHORS[0]
    right_hour, right = THEME_ANCHORS[-1]
    for index in range(len(THEME_ANCHORS) - 1):
        candidate_left_hour, candidate_left = THEME_ANCHORS[index]
        candidate_right_hour, candidate_right = THEME_ANCHORS[index + 1]
        if candidate_left_hour <= hour <= candidate_right_hour:
            left_hour, left = candidate_left_hour, candidate_left
            right_hour, right = candidate_right_hour, candidate_right
            break

    span = max(0.001, right_hour - left_hour)
    amount = max(0.0, min(1.0, (hour - left_hour) / span))
    return {
        "name": left["name"] if amount < 0.5 else right["name"],
        "hour": hour,
        "bg": _mix_hex(left["bg"], right["bg"], amount),
        "bg2": _mix_hex(left["bg2"], right["bg2"], amount),
        "surface": _mix_hex(left["surface"], right["surface"], amount),
        "surface_rgb": _mix_rgb_string(left["surface"], right["surface"], amount),
        "glow1": _mix_hex(left["glow1"], right["glow1"], amount),
        "glow2": _mix_hex(left["glow2"], right["glow2"], amount),
        "glow1_rgb": _mix_rgb_string(left["glow1"], right["glow1"], amount),
        "glow2_rgb": _mix_rgb_string(left["glow2"], right["glow2"], amount),
        "accent": _mix_hex(left["accent"], right["accent"], amount),
    }


def theme_css(now=None):
    theme = theme_for_time(now)
    return f"""
<style>
:root{{
  --bg:{theme['bg']};
  --time-bg-deep:{theme['bg2']};
  --time-surface:{theme['surface']};
  --time-surface-rgb:{theme['surface_rgb']};
  --time-glow-a:{theme['glow1']};
  --time-glow-b:{theme['glow2']};
  --time-glow-a-rgb:{theme['glow1_rgb']};
  --time-glow-b-rgb:{theme['glow2_rgb']};
  --time-accent:{theme['accent']};
  --time-shadow:0 14px 42px rgba(23,32,42,.07);
}}
.stApp{{
  background:
    radial-gradient(circle at 5% -1%,rgba(var(--time-glow-a-rgb),.13),transparent 30rem),
    radial-gradient(circle at 96% 3%,rgba(var(--time-glow-b-rgb),.11),transparent 29rem),
    linear-gradient(180deg,var(--bg),var(--time-bg-deep)) !important;
  color:var(--ink);
}}
.hero{{
  background:
    linear-gradient(135deg,rgba(var(--time-surface-rgb),.98),rgba(var(--time-surface-rgb),.86)),
    linear-gradient(120deg,rgba(var(--time-glow-a-rgb),.13),rgba(var(--time-glow-b-rgb),.11)) !important;
  box-shadow:var(--time-shadow) !important;
}}
.hero:after{{
  background:linear-gradient(135deg,rgba(var(--time-glow-a-rgb),.18),rgba(var(--time-glow-b-rgb),.14)) !important;
}}
.story-card,.detail-shell{{
  background:rgba(var(--time-surface-rgb),.94) !important;
}}
.category-tile,.metric-mini,.pulse-card,.claim-box,.source-card,.pr-cell,.reading-box,.mind-change,
.panel-card,.panel-thread-item{{
  background:rgba(var(--time-surface-rgb),.84) !important;
}}
.empty-box{{background:rgba(var(--time-surface-rgb),.48) !important}}
.so-what{{background:rgba(var(--time-surface-rgb),.72) !important}}
div[data-testid="stRadio"] label{{background:rgba(var(--time-surface-rgb),.76) !important}}
.live-pill{{background:rgba(var(--time-glow-b-rgb),.11) !important}}
.article-visual,.article-visual img{{background:var(--time-bg-deep) !important}}
.stButton>button{{box-shadow:0 4px 14px rgba(var(--time-glow-a-rgb),.06)}}
</style>
"""


def install_time_theme(now=None):
    st.markdown(theme_css(now), unsafe_allow_html=True)
    return theme_for_time(now)
