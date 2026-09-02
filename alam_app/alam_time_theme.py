import math
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

JAPAN_TZ = ZoneInfo("Asia/Tokyo")

# The palette is intentionally more noticeable than the first ALAM time theme.
# Surfaces remain light/readable, while the ambient sky and moving light source
# make reopening the app at different times feel visibly different.
THEME_ANCHORS = [
    (0.0, {"name": "midnight", "bg": "#E8ECF7", "bg2": "#E1E6F2", "surface": "#F9FAFD", "glow1": "#7286C3", "glow2": "#9176B2", "accent": "#586B9E", "sun": "#A9B8E8"}),
    (5.0, {"name": "dawn", "bg": "#F9E9E4", "bg2": "#F4E4EC", "surface": "#FFFAF8", "glow1": "#E49A8D", "glow2": "#EAB268", "accent": "#A96E6D", "sun": "#FFB36B"}),
    (8.0, {"name": "morning", "bg": "#FFF1D5", "bg2": "#F6F0DF", "surface": "#FFFEF9", "glow1": "#E7B64E", "glow2": "#75B5A7", "accent": "#97733D", "sun": "#FFD55F"}),
    (12.0, {"name": "midday", "bg": "#E9F4FA", "bg2": "#EAF5F2", "surface": "#FCFFFF", "glow1": "#6EA7DB", "glow2": "#67B79A", "accent": "#447FAE", "sun": "#FFF0A6"}),
    (16.0, {"name": "golden", "bg": "#FBE5C9", "bg2": "#F3E2DA", "surface": "#FFFAF4", "glow1": "#E49A4E", "glow2": "#D17867", "accent": "#A7653C", "sun": "#FFB34D"}),
    (19.0, {"name": "evening", "bg": "#EEE3F5", "bg2": "#E8E3F1", "surface": "#FBF8FD", "glow1": "#9075C0", "glow2": "#D07891", "accent": "#735A9B", "sun": "#FF8D82"}),
    (22.0, {"name": "late", "bg": "#E8EBF5", "bg2": "#E0E5F0", "surface": "#F8FAFD", "glow1": "#6278B2", "glow2": "#806C9F", "accent": "#566A9B", "sun": "#A7B5E5"}),
    (24.0, {"name": "midnight", "bg": "#E8ECF7", "bg2": "#E1E6F2", "surface": "#F9FAFD", "glow1": "#7286C3", "glow2": "#9176B2", "accent": "#586B9E", "sun": "#A9B8E8"}),
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


def _light_position(hour):
    # A visual sun-path proxy for Japan: low-left near dawn, high around noon,
    # low-right near sunset. At night a softer moon-like glow crosses the upper sky.
    sunrise = 5.0
    sunset = 19.0
    if sunrise <= hour <= sunset:
        progress = (hour - sunrise) / (sunset - sunrise)
        x = 6.0 + 88.0 * progress
        altitude = math.sin(math.pi * progress)
        y = 72.0 - 64.0 * altitude
        # Strong enough to be noticed on reopen, but still behind readable surfaces.
        strength = 0.30 + 0.20 * altitude
        return x, y, strength, "sun"

    if hour > sunset:
        progress = (hour - sunset) / (24.0 - sunset + sunrise)
    else:
        progress = (hour + 24.0 - sunset) / (24.0 - sunset + sunrise)
    x = 88.0 - 70.0 * progress
    altitude = max(0.0, math.sin(math.pi * progress))
    y = 34.0 - 18.0 * altitude
    strength = 0.19 + 0.09 * altitude
    return x, y, strength, "moon"


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
    light_x, light_y, light_strength, light_kind = _light_position(hour)
    sun = _mix_hex(left["sun"], right["sun"], amount)
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
        "sun": sun,
        "sun_rgb": ",".join(str(v) for v in _rgb(sun)),
        "light_x": light_x,
        "light_y": light_y,
        "light_strength": light_strength,
        "light_kind": light_kind,
    }


def theme_css(now=None):
    theme = theme_for_time(now)
    light_alpha = theme["light_strength"]
    inner_alpha = min(0.56, light_alpha + 0.08)
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
  --time-light:{theme['sun']};
  --time-light-rgb:{theme['sun_rgb']};
  --time-light-x:{theme['light_x']:.1f}%;
  --time-light-y:{theme['light_y']:.1f}%;
  --time-shadow:0 16px 44px rgba(23,32,42,.085);
}}
.stApp{{
  background:
    radial-gradient(circle at var(--time-light-x) var(--time-light-y),
      rgba(var(--time-light-rgb),{inner_alpha:.3f}) 0,
      rgba(var(--time-light-rgb),{light_alpha:.3f}) 7rem,
      rgba(var(--time-light-rgb),.12) 19rem,
      transparent 35rem),
    radial-gradient(circle at 7% 7%,rgba(var(--time-glow-a-rgb),.23),transparent 33rem),
    radial-gradient(circle at 95% 8%,rgba(var(--time-glow-b-rgb),.18),transparent 32rem),
    linear-gradient(180deg,var(--bg),var(--time-bg-deep)) !important;
  color:var(--ink);
  transition:background .7s ease;
}}
.hero{{
  background:
    linear-gradient(135deg,rgba(var(--time-surface-rgb),.96),rgba(var(--time-surface-rgb),.80)),
    linear-gradient(120deg,rgba(var(--time-glow-a-rgb),.20),rgba(var(--time-glow-b-rgb),.17)) !important;
  border-color:rgba(var(--time-glow-a-rgb),.15) !important;
  box-shadow:var(--time-shadow) !important;
}}
.hero:after{{
  background:linear-gradient(135deg,rgba(var(--time-light-rgb),.27),rgba(var(--time-glow-b-rgb),.20)) !important;
}}
.hero-kicker{{color:var(--time-accent) !important}}
.story-card,.detail-shell{{
  background:rgba(var(--time-surface-rgb),.90) !important;
  box-shadow:0 10px 30px rgba(23,32,42,.055);
}}
.category-tile,.metric-mini,.pulse-card,.claim-box,.source-card,.pr-cell,.reading-box,.mind-change,
.panel-card,.panel-thread-item{{
  background:rgba(var(--time-surface-rgb),.79) !important;
}}
.empty-box{{background:rgba(var(--time-surface-rgb),.52) !important}}
.so-what{{background:rgba(var(--time-surface-rgb),.68) !important}}
div[data-testid="stRadio"] label{{background:rgba(var(--time-surface-rgb),.72) !important}}
.live-pill{{background:rgba(var(--time-light-rgb),.19) !important}}
.article-visual,.article-visual img{{background:var(--time-bg-deep) !important}}
.st-key-main_nav{{
  background:rgba(var(--time-surface-rgb),.88) !important;
  border-color:rgba(var(--time-glow-a-rgb),.13) !important;
}}
.stButton>button{{
  box-shadow:0 5px 16px rgba(var(--time-glow-a-rgb),.09);
  border-color:rgba(var(--time-glow-a-rgb),.15);
}}
[data-testid="stHeader"]{{background:rgba(var(--time-surface-rgb),.72) !important}}
</style>
"""


def install_time_theme(now=None):
    st.markdown(theme_css(now), unsafe_allow_html=True)
    return theme_for_time(now)
