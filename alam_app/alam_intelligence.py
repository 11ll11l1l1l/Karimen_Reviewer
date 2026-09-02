import re
from collections import Counter
from datetime import datetime, timedelta, timezone

import streamlit as st

import alam_local_state as localstate
from alam_core import feed_score, parse_dt, source_quality, story_versions
from alam_personas import comments_for_story


LIFECYCLE = ("NEW", "DEVELOPING", "CONFIRMED", "FADING", "RESOLVED")
DEFAULT_INTERESTS = {
    "Japan life & policy": True,
    "Household money": True,
    "Safety & risk": True,
    "Engineering & semiconductors": True,
    "Technology & AI": True,
    "Markets & economy": True,
    "Career & immigration": True,
    "Family impact": True,
}

KEYWORDS = {
    "Japan life & policy": ("japan", "japanese", "visa", "residence", "immigration", "pension", "tax", "subsid", "municipal", "yen", "boj"),
    "Household money": ("price", "cost", "saving", "yen", "gasoline", "fuel", "utility", "insurance", "tax", "benefit", "household", "fee"),
    "Safety & risk": ("risk", "safety", "scam", "recall", "earthquake", "typhoon", "heat", "fraud", "warning", "avoid"),
    "Engineering & semiconductors": ("semiconductor", "chip", "wafer", "fab", "equipment", "process", "engineering", "manufacturing", "robot", "automation", "metrology", "photonics"),
    "Technology & AI": (" ai ", "artificial intelligence", "agent", "robot", "software", "cyber", "technology", "autonomous"),
    "Markets & economy": ("market", "nikkei", "topix", "jgb", "yield", "stock", "inflation", "economy", "fed", "boj", "oil", "fx", "usd/jpy"),
    "Career & immigration": ("job", "career", "employer", "salary", "immigration", "visa", "residence", "worker", "engineer", "relocation"),
    "Family impact": ("family", "child", "children", "parent", "household", "school", "childcare", "spouse", "dependent"),
}


def _text(record):
    parts = [
        record.get("title", ""),
        record.get("summary", ""),
        record.get("why_it_matters", ""),
        " ".join(str(x) for x in record.get("tags", []) or []),
        " ".join(str(x) for x in record.get("geography", []) or []),
        str(record.get("content") or {}),
    ]
    return " " + " ".join(str(x).lower() for x in parts) + " "


def init_preferences():
    st.session_state.setdefault("alam_interest_preferences", dict(DEFAULT_INTERESTS))
    st.session_state.setdefault("alam_alert_min_importance", 85)
    st.session_state.setdefault("alam_alert_only_actionable", False)
    st.session_state.setdefault("alam_alert_material_change", True)


def interest_hits(record):
    text = _text(record)
    hits = []
    for name, words in KEYWORDS.items():
        if any(word in text for word in words):
            hits.append(name)
    return hits


def personal_relevance(record):
    init_preferences()
    prefs = st.session_state.get("alam_interest_preferences", DEFAULT_INTERESTS)
    all_hits = interest_hits(record)
    enabled = [name for name, value in prefs.items() if value]
    hits = [name for name in all_hits if prefs.get(name)]
    if not enabled:
        base = float(record.get("importance", 50) or 50)
    else:
        base = 25 + min(45, len(hits) * 13)
        base += 0.20 * float(record.get("importance", 50) or 50)
        if str((record.get("content") or {}).get("action", "")).upper() in {"DO NOW", "APPLY", "PREPARE", "AVOID"}:
            base += 8
    base += localstate.adaptive_boost(record, all_hits)
    return int(max(0, min(100, base)))


def evidence_health(record):
    sources = record.get("sources") or []
    total, strong = source_quality(record)
    claims = record.get("claims") or []
    facts = [c for c in claims if isinstance(c, dict) and str(c.get("kind", "")).upper() == "FACT"]
    sourced = sum(bool(c.get("source_refs")) for c in facts)
    independent_publishers = len({str(s.get("publisher", "")).strip().lower() for s in sources if isinstance(s, dict) and s.get("publisher")})
    if total >= 4 and strong >= 2 and independent_publishers >= 3 and (not facts or sourced == len(facts)):
        return "STRONG", f"{strong} primary/official · {independent_publishers} publishers"
    if total >= 2 and independent_publishers >= 2 and (not facts or sourced >= max(1, len(facts) - 1)):
        return "GOOD", f"{total} sources · {independent_publishers} publishers"
    if total >= 1:
        return "EARLY", f"{total} source{'s' if total != 1 else ''} · needs more independent confirmation"
    return "WEAK", "No usable source metadata"


def story_lifecycle(record, all_records):
    explicit = str(record.get("status", "")).upper().replace(" ", "_")
    if explicit in LIFECYCLE:
        return explicit
    if explicit in {"CLOSED", "DONE", "RESOLVED", "EXPIRED"}:
        return "RESOLVED"
    versions = story_versions(all_records, record.get("id"))
    age_days = (datetime.now(timezone.utc) - parse_dt(record.get("created_at")).astimezone(timezone.utc)).total_seconds() / 86400
    health, _ = evidence_health(record)
    if age_days <= 2 and len(versions) <= 1:
        return "NEW"
    if len(versions) > 1 and age_days <= 10:
        return "DEVELOPING"
    if health == "STRONG" and float(record.get("confidence", 0) or 0) >= 85:
        return "CONFIRMED"
    if age_days > 14:
        return "FADING"
    return "DEVELOPING"


def change_snapshot(record, all_records):
    versions = story_versions(all_records, record.get("id"))
    content = record.get("content") or {}
    supplied = content.get("change_summary")
    if isinstance(supplied, dict):
        before = supplied.get("previous") or supplied.get("before")
        now = supplied.get("now") or supplied.get("current")
        if before or now:
            return str(before or "Earlier state not stated"), str(now or "Current state updated")
    if len(versions) < 2:
        return None
    prev, cur = versions[-2], versions[-1]
    before_bits, now_bits = [], []
    for label, key in (("Confidence", "confidence"), ("Importance", "importance"), ("Status", "status")):
        if prev.get(key) != cur.get(key):
            before_bits.append(f"{label} {prev.get(key)}")
            now_bits.append(f"{label} {cur.get(key)}")
    pa = str((prev.get("content") or {}).get("action", ""))
    ca = str((cur.get("content") or {}).get("action", ""))
    if pa != ca and (pa or ca):
        before_bits.append(f"Action {pa or '—'}")
        now_bits.append(f"Action {ca or '—'}")
    if not before_bits and prev.get("summary") != cur.get("summary"):
        before_bits.append(str(prev.get("summary", ""))[:180])
        now_bits.append(str(cur.get("summary", ""))[:180])
    if not before_bits:
        return None
    return " · ".join(before_bits), " · ".join(now_bits)


def impact_matrix(record):
    text = _text(record)
    c = record.get("content") or {}
    explicit = c.get("impact")
    labels = {
        "money": "💴 Money",
        "family": "👨‍👩‍👧 Family",
        "career": "💼 Career",
        "japan": "🇯🇵 Japan",
        "urgency": "⏱ Urgency",
    }
    if isinstance(explicit, dict):
        result = {}
        for key, label in labels.items():
            value = str(explicit.get(key, "LOW")).upper()
            result[label] = value if value in {"LOW", "MED", "HIGH"} else "LOW"
        return result

    def level(score):
        return "HIGH" if score >= 3 else "MED" if score >= 1 else "LOW"

    money = sum(x in text for x in ("price", "cost", "yen", "saving", "tax", "fee", "salary", "fuel", "utility"))
    family = sum(x in text for x in ("family", "child", "spouse", "dependent", "school", "household", "childcare"))
    career = sum(x in text for x in ("job", "career", "engineer", "employer", "salary", "semiconductor", "immigration", "visa"))
    japan = sum(x in text for x in ("japan", "tokyo", "yen", "boj", "jgb", "residence", "japanese"))
    urgency = 3 if str(c.get("action", "")).upper() in {"DO NOW", "APPLY", "AVOID", "PREPARE"} else 1 if c.get("deadline") else 0
    return {
        "💴 Money": level(money),
        "👨‍👩‍👧 Family": level(family),
        "💼 Career": level(career),
        "🇯🇵 Japan": level(japan),
        "⏱ Urgency": level(urgency),
    }


def disagreement_signal(record, comments):
    thread = comments_for_story(comments or [], record.get("id"))
    agents = {str(c.get("agent", "")) for c in thread}
    explicit_challenges = sum(str(c.get("stance", "")).upper() == "CHALLENGE" for c in thread)
    explicit_mixed = sum(str(c.get("stance", "")).upper() == "MIXED" for c in thread)
    challenge_words = ("pero", "but ", "caution", "challenge", "not justified", "weak", "risk", "hype", "uncertain", "overfit", "false", "however")
    inferred = sum(
        not c.get("stance") and any(w in (" " + str(c.get("body", "")).lower() + " ") for w in challenge_words)
        for c in thread
    )
    challenging = explicit_challenges + explicit_mixed + inferred
    if len(agents) >= 3 and challenging >= 2:
        return "HIGH", f"{len(agents)} lenses · {challenging} challenge/mixed views"
    if len(agents) >= 2 and challenging >= 1:
        return "USEFUL", f"{len(agents)} lenses are not fully aligned"
    return None


def _connection_tokens(record):
    c = record.get("content") or {}
    explicit = {str(x).lower() for x in (c.get("connection_tags") or []) if x}
    tags = {str(x).lower() for x in (record.get("tags") or []) if x}
    if explicit or tags:
        return explicit | tags
    return set(re.findall(r"[a-zA-Z]{5,}", record.get("title", "").lower()))


def connected_stories(record, records, limit=3):
    base = _connection_tokens(record)
    scored = []
    for other in records:
        if str(other.get("id")) == str(record.get("id")):
            continue
        overlap = base & _connection_tokens(other)
        if overlap:
            scored.append((len(overlap), feed_score(other), other, sorted(overlap)))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return scored[:limit]


def _actionable(record):
    return str((record.get("content") or {}).get("action", "")).upper() in {"DO NOW", "APPLY", "AVOID", "PREPARE", "BUY", "WAIT"}


def alert_matches(records, all_records):
    init_preferences()
    threshold = int(st.session_state.get("alam_alert_min_importance", 85))
    only_action = bool(st.session_state.get("alam_alert_only_actionable", False))
    material = bool(st.session_state.get("alam_alert_material_change", True))
    matches = []
    for r in records:
        if float(r.get("importance", 0) or 0) < threshold:
            continue
        if only_action and not _actionable(r):
            continue
        if material and len(story_versions(all_records, r.get("id"))) > 1 and not change_snapshot(r, all_records):
            continue
        matches.append(r)
    return sorted(matches, key=lambda r: (personal_relevance(r), feed_score(r)), reverse=True)


def daily_three(records):
    if not records:
        return []
    ranked = sorted(records, key=lambda r: (personal_relevance(r), feed_score(r)), reverse=True)
    know = next((r for r in ranked if r.get("_category") == "discover"), ranked[0])
    do = next((r for r in ranked if r.get("_category") == "practical" and _actionable(r)), None)
    watch = next((r for r in ranked if r.get("_category") in {"trend", "reflection"} and str(r.get("id")) != str(know.get("id"))), None)
    rows = [("KNOW", know)]
    if do and str(do.get("id")) != str(know.get("id")):
        rows.append(("DO", do))
    if watch and all(str(watch.get("id")) != str(x[1].get("id")) for x in rows):
        rows.append(("WATCH", watch))
    return rows[:3]


def render_daily_brief(records, all_records):
    rows = daily_three(records)
    if not rows:
        return
    st.markdown("<div class='intel-title'>Today in 3 lines</div>", unsafe_allow_html=True)
    html = ["<div class='intel-brief-grid'>"]
    for label, r in rows:
        text = (r.get("content") or {}).get("action") if label == "DO" else r.get("summary")
        html.append(
            f"<div class='intel-brief-card'><div class='intel-kicker'>{label}</div>"
            f"<div class='intel-brief-head'>{r.get('title','')}</div>"
            f"<div class='intel-brief-copy'>{str(text or r.get('why_it_matters',''))[:190]}</div>"
            f"<div class='intel-mini'>Relevance {personal_relevance(r)}/100 · {story_lifecycle(r, all_records)}</div></div>"
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_alert_ribbon(records, all_records):
    matches = alert_matches(records, all_records)
    if not matches:
        return
    top = matches[0]
    st.markdown(
        f"<div class='intel-alert'><strong>🔔 Rule match:</strong> {top.get('title','')} "
        f"<span>Importance {int(top.get('importance',0) or 0)} · Relevance {personal_relevance(top)}/100</span></div>",
        unsafe_allow_html=True,
    )


def render_story_snapshot(record, all_records, records, comments):
    lifecycle = story_lifecycle(record, all_records)
    health, evidence = evidence_health(record)
    relevance = personal_relevance(record)
    impacts = impact_matrix(record)
    change = change_snapshot(record, all_records)
    disagreement = disagreement_signal(record, comments)
    st.markdown("#### Intelligence snapshot")
    chips = [f"{lifecycle}", f"Relevance {relevance}/100", f"Evidence {health}"]
    st.markdown(" ".join(f"`{x}`" for x in chips))
    st.caption(evidence)
    st.markdown(" ".join(f"**{k}:** {v}" for k, v in impacts.items()))
    if change:
        st.markdown(
            f"<div class='intel-change'><div><strong>Before</strong><br>{change[0]}</div>"
            f"<div class='intel-arrow'>→</div><div><strong>Now</strong><br>{change[1]}</div></div>",
            unsafe_allow_html=True,
        )
    if disagreement:
        st.markdown(
            f"<div class='intel-disagree'>⚡ <strong>ALAM disagreement: {disagreement[0]}</strong> — {disagreement[1]}</div>",
            unsafe_allow_html=True,
        )
    connected = connected_stories(record, records)
    if connected:
        with st.expander("Connect the dots"):
            for _, _, other, overlap in connected:
                st.markdown(f"**{other.get('title','')}**  \nShared signal: {', '.join(overlap[:4])}")


def render_weekly(records, all_records):
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent = [r for r in records if parse_dt(r.get("created_at")).astimezone(timezone.utc) >= cutoff]
    st.markdown(
        "<div class='hero mobile-hero'><div class='hero-kicker'>📅 WEEKLY INTELLIGENCE</div>"
        "<div class='hero-title'>What actually mattered?</div>"
        "<div class='hero-copy'>A rolling seven-day accountability view. Sunday Trend reports can add deeper synthesis.</div></div>",
        unsafe_allow_html=True,
    )
    if not recent:
        st.info("Not enough recent records yet.")
        return
    top = sorted(recent, key=lambda r: (float(r.get("importance", 0) or 0), personal_relevance(r)), reverse=True)[:5]
    st.markdown("#### What mattered")
    for r in top:
        st.markdown(f"- **{r.get('title','')}** — relevance {personal_relevance(r)}/100 · {story_lifecycle(r, all_records)}")
    changed = [r for r in recent if change_snapshot(r, all_records)]
    if changed:
        st.markdown("#### Conclusions that changed")
        for r in changed[:5]:
            before, now = change_snapshot(r, all_records)
            st.markdown(f"- **{r.get('title','')}** — {before} → {now}")
    predictions = []
    for r in recent:
        c = r.get("content") or {}
        status = str(c.get("status", r.get("status", ""))).upper()
        if str(r.get("type", "")).lower() in {"prediction", "correction"} or status in {"CONFIRMED", "PARTLY_CONFIRMED", "WRONG", "EXPIRED"}:
            predictions.append((status, r))
    if predictions:
        st.markdown("#### Forecast accountability")
        counts = Counter(x[0] or "OPEN" for x in predictions)
        st.caption(" · ".join(f"{k} {v}" for k, v in counts.items()))
        for status, r in predictions[:5]:
            st.markdown(f"- **{status or 'OPEN'}:** {r.get('title','')}")


def render_preferences(manager=None):
    init_preferences()
    st.markdown("#### Personal relevance")
    st.caption("Used to rank and label stories; it never changes factual content or hides high-importance general intelligence.")
    prefs = dict(st.session_state.get("alam_interest_preferences", DEFAULT_INTERESTS))
    cols = st.columns(2)
    for i, name in enumerate(DEFAULT_INTERESTS):
        with cols[i % 2]:
            prefs[name] = st.toggle(name, value=bool(prefs.get(name, True)), key=f"interest_{i}")
    st.session_state["alam_interest_preferences"] = prefs
    st.markdown("#### Alert rules")
    st.session_state["alam_alert_min_importance"] = st.slider(
        "Minimum importance", 50, 100, int(st.session_state.get("alam_alert_min_importance", 85)), 5
    )
    st.session_state["alam_alert_only_actionable"] = st.toggle(
        "Only actionable stories", value=bool(st.session_state.get("alam_alert_only_actionable", False))
    )
    st.session_state["alam_alert_material_change"] = st.toggle(
        "Prioritize new/material changes", value=bool(st.session_state.get("alam_alert_material_change", True))
    )
    st.caption("These are in-app rules. They do not create phone push notifications.")
    localstate.persist_settings(manager)


INTEL_CSS = r"""
<style>
.intel-title{font-size:.76rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;color:#667085;margin:8px 0 7px}
.intel-brief-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin:0 0 13px}.intel-brief-card{background:rgba(255,255,255,.9);border:1px solid rgba(23,32,42,.09);border-radius:17px;padding:13px}.intel-kicker{font-size:.64rem;font-weight:950;color:#5968F2;letter-spacing:.08em}.intel-brief-head{font-size:.92rem;font-weight:900;line-height:1.23;margin:4px 0}.intel-brief-copy{font-size:.78rem;line-height:1.42;color:#667085}.intel-mini{font-size:.66rem;color:#98A2B3;margin-top:7px}.intel-alert{border:1px solid rgba(89,104,242,.18);background:#F4F5FF;border-radius:14px;padding:9px 12px;margin:7px 0 12px;font-size:.79rem}.intel-alert span{color:#667085;margin-left:6px}.intel-change{display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center;background:#F7F8FA;border:1px solid rgba(23,32,42,.08);border-radius:15px;padding:12px;margin:10px 0;font-size:.82rem}.intel-arrow{font-size:1.2rem;color:#98A2B3}.intel-disagree{background:#FFF7E8;border:1px solid #F5D995;border-radius:14px;padding:10px 12px;margin:10px 0;font-size:.82rem}
@media(max-width:760px){.intel-brief-grid{grid-template-columns:1fr}.intel-change{grid-template-columns:1fr}.intel-arrow{transform:rotate(90deg);text-align:center}}
</style>
"""
