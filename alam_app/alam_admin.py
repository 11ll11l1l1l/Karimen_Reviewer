"""Private ALAM operator dashboard.

The admin password is never stored in GitHub. It is verified by the Supabase
``alam-admin`` Edge Function, which returns only admin-authorized aggregate data.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib import error, request

import pandas as pd
import streamlit as st

JST = timezone(timedelta(hours=9))
SESSION_AUTH_KEY = "_alam_admin_authenticated"
SESSION_PASSWORD_KEY = "_alam_admin_password"
SESSION_PAYLOAD_KEY = "_alam_admin_payload"
SESSION_ERROR_KEY = "_alam_admin_error"

ADMIN_CSS = """
<style>
.alam-admin-hero{padding:1.05rem 1.15rem;border:1px solid rgba(23,32,42,.10);border-radius:22px;background:linear-gradient(135deg,rgba(14,30,53,.97),rgba(30,67,105,.95));color:white;margin:.35rem 0 1rem;box-shadow:0 12px 30px rgba(10,30,55,.15)}
.alam-admin-kicker{font-size:.72rem;font-weight:900;letter-spacing:.11em;text-transform:uppercase;opacity:.72}.alam-admin-title{font-size:1.65rem;font-weight:950;letter-spacing:-.035em;margin:.18rem 0}.alam-admin-copy{font-size:.88rem;opacity:.86;line-height:1.45}.alam-admin-note{padding:.75rem .9rem;border-radius:14px;background:rgba(47,111,176,.08);border:1px solid rgba(47,111,176,.15);font-size:.84rem;line-height:1.45}
</style>
"""


def _fmt_time(value):
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(JST).strftime("%Y-%m-%d %H:%M JST")
    except Exception:
        return str(value)


def _fmt_seconds(value):
    try:
        seconds = float(value or 0)
    except (TypeError, ValueError):
        return "—"
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes, sec = divmod(int(round(seconds)), 60)
    if minutes < 60:
        return f"{minutes}m {sec:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


def _admin_endpoint():
    try:
        base = str(st.secrets["SUPABASE_URL"]).strip().rstrip("/")
    except Exception as exc:
        raise RuntimeError("ALAM Supabase URL is not configured on this deployment.") from exc
    if not base:
        raise RuntimeError("ALAM Supabase URL is empty.")
    return f"{base}/functions/v1/alam-admin"


def _fetch_dashboard(password):
    payload = json.dumps({"password": str(password)}).encode("utf-8")
    req = request.Request(
        _admin_endpoint(),
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        if exc.code == 401:
            return None, "Incorrect admin password."
        if exc.code == 405:
            return None, "Admin endpoint rejected the request method."
        return None, f"Admin backend returned HTTP {exc.code}."
    except error.URLError:
        return None, "Could not reach the ALAM admin backend."
    except Exception:
        return None, "Could not load the admin dashboard."

    if not isinstance(data, dict) or not data.get("ok") or not isinstance(data.get("data"), dict):
        return None, "Admin backend returned an invalid response."
    return data["data"], None


def _refresh():
    password = st.session_state.get(SESSION_PASSWORD_KEY, "")
    if not password:
        return None, "Admin session expired. Sign in again."
    payload, err = _fetch_dashboard(password)
    if payload is not None:
        st.session_state[SESSION_PAYLOAD_KEY] = payload
        st.session_state[SESSION_ERROR_KEY] = None
    else:
        st.session_state[SESSION_ERROR_KEY] = err
    return payload, err


def _logout():
    for key in (SESSION_AUTH_KEY, SESSION_PASSWORD_KEY, SESSION_PAYLOAD_KEY, SESSION_ERROR_KEY):
        st.session_state.pop(key, None)


def _login_gate():
    st.markdown(ADMIN_CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="alam-admin-hero">
          <div class="alam-admin-kicker">Private operator access</div>
          <div class="alam-admin-title">ALAM Admin</div>
          <div class="alam-admin-copy">Usage, content operations, agent health and system diagnostics. Password required.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.session_state.get(SESSION_AUTH_KEY):
        return True

    with st.form("alam_admin_login", clear_on_submit=True):
        password = st.text_input("Admin password", type="password", autocomplete="off")
        submitted = st.form_submit_button("Unlock admin", type="primary", width="stretch")
    if submitted:
        dashboard, err = _fetch_dashboard(password)
        if dashboard is None:
            st.error(err or "Admin login failed.")
            return False
        st.session_state[SESSION_AUTH_KEY] = True
        st.session_state[SESSION_PASSWORD_KEY] = password
        st.session_state[SESSION_PAYLOAD_KEY] = dashboard
        st.session_state[SESSION_ERROR_KEY] = None
        st.rerun()
    st.caption("The password is verified server-side. It is not written to GitHub or Supabase tables.")
    return False


def _metric_row(overview):
    cols = st.columns(5)
    cols[0].metric("Visitors", int(overview.get("visitors") or 0))
    cols[1].metric("Active today", int(overview.get("active_today") or 0))
    cols[2].metric("Sessions", int(overview.get("sessions") or 0))
    cols[3].metric("Events", int(overview.get("events") or 0))
    cols[4].metric("Article opens", int(overview.get("article_opens") or 0))


def _overview_tab(data):
    overview = data.get("overview") or {}
    durations = data.get("session_duration") or {}
    system = data.get("system") or {}
    _metric_row(overview)

    visitors = int(overview.get("visitors") or 0)
    returning = int(overview.get("returning_visitors") or 0)
    return_rate = (100 * returning / visitors) if visitors else 0
    readers = int(overview.get("article_readers") or 0)
    reader_rate = (100 * readers / visitors) if visitors else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Returning visitors", f"{returning} ({return_rate:.0f}%)")
    c2.metric("Article readers", f"{readers} ({reader_rate:.0f}%)")
    c3.metric("Published articles", int(overview.get("published_articles") or 0))
    c4.metric("Failed agent runs · 24h", int(overview.get("failed_runs_24h") or 0))

    st.markdown("#### Current signals")
    left, right = st.columns([1.15, 1])
    with left:
        daily = pd.DataFrame(data.get("daily") or [])
        if not daily.empty:
            daily["day"] = pd.to_datetime(daily["day"])
            st.line_chart(daily.set_index("day")[["visitors", "sessions", "article_opens"]], height=280)
        else:
            st.info("No daily usage data yet.")
    with right:
        st.metric("Median observed session", _fmt_seconds(durations.get("median_seconds")))
        st.metric("Average observed session", _fmt_seconds(durations.get("avg_seconds")))
        st.metric("90th percentile", _fmt_seconds(durations.get("p90_seconds")))
        st.caption("Session duration is currently inferred from first-to-last logged event, so passive reading time can be undercounted.")

    problems = []
    if not system.get("article_reads_instrumented"):
        problems.append("Article reading duration/completion is not being populated yet.")
    if not system.get("saves_instrumented"):
        problems.append("No saved-article events are being recorded yet.")
    if not system.get("feedback_instrumented"):
        problems.append("No article-feedback events are being recorded yet.")
    if int(overview.get("failed_runs_24h") or 0) > 0:
        problems.append("At least one agent run failed in the last 24 hours.")
    if problems:
        st.warning("Admin attention: " + " ".join(problems))
    else:
        st.success("No current admin alerts from the tracked health checks.")

    st.markdown("#### Top opened articles")
    top = pd.DataFrame(data.get("top_articles") or [])
    if top.empty:
        st.caption("No article opens recorded yet.")
    else:
        keep = [c for c in ["title", "category", "opens", "readers", "last_opened_at"] if c in top.columns]
        if "last_opened_at" in top.columns:
            top["last_opened_at"] = top["last_opened_at"].map(_fmt_time)
        st.dataframe(top[keep], hide_index=True, width="stretch")


def _users_tab(data):
    overview = data.get("overview") or {}
    visitors = pd.DataFrame(data.get("visitors") or [])
    platforms = pd.DataFrame(data.get("platforms") or [])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tracked visitors", int(overview.get("visitors") or 0))
    c2.metric("Returning", int(overview.get("returning_visitors") or 0))
    c3.metric("5+ sessions", int(overview.get("five_plus_session_visitors") or 0))
    c4.metric("Registered accounts", int(overview.get("accounts") or 0))

    if not platforms.empty:
        st.markdown("#### Device mix")
        st.bar_chart(platforms.set_index("platform")[["devices"]], height=230)

    st.markdown("#### Visitor summary")
    if visitors.empty:
        st.info("No visitors recorded yet.")
        return
    for col in ("created_at", "last_seen_at"):
        if col in visitors.columns:
            visitors[col] = visitors[col].map(_fmt_time)
    cols = [c for c in ["display_name", "platform", "sessions", "events", "interaction_count", "created_at", "last_seen_at"] if c in visitors.columns]
    st.dataframe(visitors[cols], hide_index=True, width="stretch")
    st.caption("Names shown here are the names visitors supplied during ALAM onboarding; this page is password-protected and not available through the public data API.")


def _engagement_tab(data):
    daily = pd.DataFrame(data.get("daily") or [])
    page_mix = pd.DataFrame(data.get("page_mix") or [])
    event_mix = pd.DataFrame(data.get("event_mix") or [])
    durations = data.get("session_duration") or {}

    if not daily.empty:
        daily["day"] = pd.to_datetime(daily["day"])
        st.markdown("#### 14-day activity")
        st.line_chart(daily.set_index("day")[["visitors", "sessions", "events", "article_opens"]], height=300)

    left, right = st.columns(2)
    with left:
        st.markdown("#### Navigation")
        if not page_mix.empty:
            st.dataframe(page_mix, hide_index=True, width="stretch")
    with right:
        st.markdown("#### Event mix")
        if not event_mix.empty:
            st.dataframe(event_mix, hide_index=True, width="stretch")

    st.markdown("#### Observed session-duration buckets")
    bucket = pd.DataFrame([
        {"bucket": "< 5 sec", "sessions": durations.get("under_5s", 0)},
        {"bucket": "5–30 sec", "sessions": durations.get("s5_30", 0)},
        {"bucket": "31–120 sec", "sessions": durations.get("s31_120", 0)},
        {"bucket": "> 120 sec", "sessions": durations.get("over_120s", 0)},
    ])
    st.bar_chart(bucket.set_index("bucket")[["sessions"]], height=240)


def _content_tab(data):
    overview = data.get("overview") or {}
    status = pd.DataFrame(data.get("content_status") or [])
    recent = pd.DataFrame(data.get("recent_articles") or [])
    predictions = pd.DataFrame(data.get("prediction_status") or [])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Articles", int(overview.get("total_articles") or 0))
    c2.metric("Sources", int(overview.get("sources") or 0))
    c3.metric("Agent comments", int(overview.get("agent_comments") or 0))
    c4.metric("Article opens", int(overview.get("article_opens") or 0))

    left, right = st.columns(2)
    with left:
        st.markdown("#### Publication status")
        if not status.empty:
            st.dataframe(status, hide_index=True, width="stretch")
    with right:
        st.markdown("#### Prediction status")
        if not predictions.empty:
            st.dataframe(predictions, hide_index=True, width="stretch")

    st.markdown("#### Latest content updates")
    if recent.empty:
        st.info("No article records available.")
        return
    for col in ("published_at", "updated_at"):
        if col in recent.columns:
            recent[col] = recent[col].map(_fmt_time)
    cols = [c for c in ["title", "category", "status", "lifecycle_status", "urgency", "importance_score", "confidence_score", "updated_at"] if c in recent.columns]
    st.dataframe(recent[cols], hide_index=True, width="stretch")


def _agents_tab(data):
    overview = data.get("overview") or {}
    summary = pd.DataFrame(data.get("agent_summary") or [])
    recent = pd.DataFrame(data.get("recent_agent_runs") or [])

    c1, c2, c3 = st.columns(3)
    c1.metric("Agent runs", int(overview.get("agent_runs") or 0))
    c2.metric("Failures · 24h", int(overview.get("failed_runs_24h") or 0))
    c3.metric("Latest run", _fmt_time(overview.get("last_agent_run_at")))

    st.markdown("#### Agent health summary")
    if not summary.empty:
        if "last_run_at" in summary.columns:
            summary["last_run_at"] = summary["last_run_at"].map(_fmt_time)
        st.dataframe(summary, hide_index=True, width="stretch")

    st.markdown("#### Recent runs")
    if not recent.empty:
        for col in ("started_at", "finished_at"):
            if col in recent.columns:
                recent[col] = recent[col].map(_fmt_time)
        if "duration_seconds" in recent.columns:
            recent["duration"] = recent["duration_seconds"].map(_fmt_seconds)
        cols = [c for c in ["agent", "status", "stories_found", "stories_published", "stories_rejected", "duration", "started_at", "error_message"] if c in recent.columns]
        st.dataframe(recent[cols], hide_index=True, width="stretch")


def _system_tab(data):
    overview = data.get("overview") or {}
    system = data.get("system") or {}
    st.markdown("#### Data pipeline")
    rows = [
        {"check": "Last user event", "value": _fmt_time(overview.get("last_event_at"))},
        {"check": "Last agent run", "value": _fmt_time(overview.get("last_agent_run_at"))},
        {"check": "Article read timing", "value": "Active" if system.get("article_reads_instrumented") else "Not populated"},
        {"check": "Saved articles", "value": "Active" if system.get("saves_instrumented") else "No records"},
        {"check": "Article feedback", "value": "Active" if system.get("feedback_instrumented") else "No records"},
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    st.markdown("#### Supporting database objects")
    support = pd.DataFrame([
        {"object": "Topics", "rows": system.get("topics", 0)},
        {"object": "Relationships", "rows": system.get("relationships", 0)},
        {"object": "Predictions", "rows": system.get("predictions", 0)},
        {"object": "Prediction updates", "rows": system.get("prediction_updates", 0)},
        {"object": "Daily briefings", "rows": system.get("daily_briefings", 0)},
        {"object": "Media assets", "rows": system.get("media_assets", 0)},
        {"object": "Notifications", "rows": system.get("notifications", 0)},
    ])
    st.dataframe(support, hide_index=True, width="stretch")
    st.markdown(
        '<div class="alam-admin-note">Admin analytics is returned through a password-verified Supabase Edge Function. The underlying database RPC is executable only by the service-role backend, not anon or authenticated public clients.</div>',
        unsafe_allow_html=True,
    )


def render_admin():
    """Render ALAM's private operator console."""
    if not _login_gate():
        return

    st.markdown(ADMIN_CSS, unsafe_allow_html=True)
    top_a, top_b, top_c = st.columns([1, 1, 4])
    with top_a:
        if st.button("Refresh", key="alam_admin_refresh", width="stretch"):
            _refresh()
    with top_b:
        if st.button("Lock", key="alam_admin_logout", width="stretch"):
            _logout()
            st.rerun()

    data = st.session_state.get(SESSION_PAYLOAD_KEY)
    if not isinstance(data, dict):
        data, err = _refresh()
        if data is None:
            st.error(err or "Admin dashboard unavailable.")
            return
    err = st.session_state.get(SESSION_ERROR_KEY)
    if err:
        st.warning(err)

    st.markdown(
        """
        <div class="alam-admin-hero">
          <div class="alam-admin-kicker">Private operator access</div>
          <div class="alam-admin-title">ALAM Admin</div>
          <div class="alam-admin-copy">Live usage, user summaries, content updates, agent runs and system instrumentation.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"Dashboard generated: {_fmt_time(data.get('generated_at'))}")

    tabs = st.tabs(["Overview", "Users", "Engagement", "Content", "Agents", "System"])
    with tabs[0]:
        _overview_tab(data)
    with tabs[1]:
        _users_tab(data)
    with tabs[2]:
        _engagement_tab(data)
    with tabs[3]:
        _content_tab(data)
    with tabs[4]:
        _agents_tab(data)
    with tabs[5]:
        _system_tab(data)
