import base64
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
HEADER_DIR = APP_DIR / "assets" / "headers"
JAPAN_TZ = ZoneInfo("Asia/Tokyo")

# Six stable visual chapters across a Japan day. The background theme still moves
# continuously between color anchors; these images give the reader a more obvious
# change in atmosphere when reopening ALAM at a different time.
DAYPARTS = [
    (0.0, "night", "Night", "Tahimik ang feed, pero tuloy ang signals."),
    (5.0, "dawn", "Dawn", "Bagong araw bago dumami ang ingay."),
    (8.0, "morning", "Morning", "Fresh light. Fresh context."),
    (12.0, "midday", "Midday", "Clear view. Check what changed."),
    (16.0, "golden", "Golden hour", "The day is turning. Recheck the signal."),
    (19.0, "evening", "Evening", "Close the day with better context."),
]

HEADER_CSS = r"""
<style>
.alam-time-header{
  min-height:176px;
  border-radius:26px;
  margin:0 0 15px;
  padding:24px 27px;
  display:flex;
  align-items:flex-end;
  overflow:hidden;
  position:relative;
  background-position:center;
  background-size:cover;
  background-repeat:no-repeat;
  border:1px solid rgba(255,255,255,.34);
  box-shadow:0 16px 38px rgba(23,32,42,.12);
  isolation:isolate;
}
.alam-time-header:after{
  content:"";
  position:absolute;
  inset:0;
  background:linear-gradient(90deg,rgba(8,16,30,.50) 0%,rgba(8,16,30,.18) 55%,rgba(8,16,30,.03) 100%);
  z-index:-1;
}
.alam-time-header-copy{max-width:640px;color:white;text-shadow:0 2px 14px rgba(0,0,0,.34)}
.alam-time-header-kicker{font-size:.68rem;font-weight:950;letter-spacing:.11em;text-transform:uppercase;opacity:.88}
.alam-time-header-title{font-size:clamp(1.42rem,3vw,2.1rem);font-weight:950;letter-spacing:-.035em;margin-top:3px}
.alam-time-header-sub{font-size:.86rem;font-weight:650;opacity:.91;margin-top:4px}
@media(max-width:760px){
  .alam-time-header{min-height:132px;border-radius:19px;padding:17px 18px;margin-bottom:11px;background-position:center}
  .alam-time-header-title{font-size:1.34rem}
  .alam-time-header-sub{font-size:.78rem;max-width:78%}
}
</style>
"""


def _japan_now(now=None):
    value = now or datetime.now(JAPAN_TZ)
    if value.tzinfo is None:
        return value.replace(tzinfo=JAPAN_TZ)
    return value.astimezone(JAPAN_TZ)


def header_for_time(now=None):
    value = _japan_now(now)
    hour = value.hour + value.minute / 60.0 + value.second / 3600.0
    selected = DAYPARTS[0]
    for entry in DAYPARTS:
        if hour >= entry[0]:
            selected = entry
        else:
            break
    start, key, label, copy = selected
    return {
        "key": key,
        "label": label,
        "copy": copy,
        "hour": hour,
        "start": start,
        "path": HEADER_DIR / f"{key}.webp",
    }


def _image_data_uri(path):
    try:
        payload = path.read_bytes()
    except OSError:
        return ""
    return "data:image/webp;base64," + base64.b64encode(payload).decode("ascii")


def render_time_header(now=None):
    info = header_for_time(now)
    uri = _image_data_uri(info["path"])
    if not uri:
        return info
    st.markdown(HEADER_CSS, unsafe_allow_html=True)
    st.markdown(
        f'''<div class="alam-time-header" data-daypart="{info['key']}" style="background-image:url('{uri}')">
<div class="alam-time-header-copy">
<div class="alam-time-header-kicker">Japan time · {info['label']}</div>
<div class="alam-time-header-title">See the day differently.</div>
<div class="alam-time-header-sub">{info['copy']}</div>
</div>
</div>''',
        unsafe_allow_html=True,
    )
    return info
