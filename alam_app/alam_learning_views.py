"""Beginner-friendly learning and action views for opened ALAM stories.

Feed cards stay concise. This module is intentionally used only on the opened-story
route, where the reader has signalled that they want enough context to understand
and use the information. Structured fields are preferred, but older v5 records get
safe, non-inventive fallbacks from information that is already present.
"""

from __future__ import annotations

from typing import Any

import streamlit as st


_ACTIONABLE_LABELS = {"DO NOW", "PREPARE", "APPLY", "AVOID", "BUY", "WAIT"}


def _content(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("content")
    return value if isinstance(value, dict) else {}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    if isinstance(value, list):
        return [item for item in value if item not in (None, "", [], {})]
    if value not in (None, "", [], {}):
        return [value]
    return []


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    return ""


def _bullet_list(items: list[Any]) -> None:
    for item in items:
        if isinstance(item, dict):
            label = _text(item.get("label") or item.get("title") or item.get("term"))
            body = _text(item.get("text") or item.get("meaning") or item.get("action"))
            if label and body:
                st.markdown(f"- **{label}:** {body}")
            elif body:
                st.markdown(f"- {body}")
        else:
            text = _text(item)
            if text:
                st.markdown(f"- {text}")


def _fallback_takeaways(record: dict[str, Any], content: dict[str, Any]) -> list[str]:
    """Build takeaways only from existing record statements; never synthesize facts."""
    values = [
        content.get("key_message"),
        record.get("why_it_matters"),
        content.get("bottom_line"),
        content.get("what_next"),
        content.get("watch_next"),
    ]
    result: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in result:
            result.append(text)
        if len(result) >= 4:
            break
    return result


def _render_terms(terms: list[Any]) -> None:
    if not terms:
        return
    st.markdown("#### Mga salitang dapat alam")
    for item in terms:
        if not isinstance(item, dict):
            text = _text(item)
            if text:
                st.markdown(f"- {text}")
            continue
        term = _text(item.get("term"))
        meaning = _text(item.get("meaning"))
        why = _text(item.get("why_it_matters"))
        if not (term or meaning):
            continue
        line = f"**{term}** — {meaning}" if term else meaning
        if why:
            line += f"  \n*Bakit relevant dito:* {why}"
        st.markdown(f"- {line}")


def _render_learning(record: dict[str, Any], learning: dict[str, Any]) -> None:
    content = _content(record)
    outcomes = _items(learning.get("outcomes"))
    background = _text(learning.get("background"))
    terms = _items(learning.get("terms"))
    mechanism = _items(learning.get("how_it_works"))
    example = _text(learning.get("example"))
    takeaways = _items(learning.get("takeaways")) or _fallback_takeaways(record, content)

    if outcomes:
        st.markdown("#### Pagkatapos basahin, dapat kaya mong…")
        _bullet_list(outcomes)

    if background:
        st.markdown("#### Simula sa basics")
        st.markdown(background)

    _render_terms(terms)

    if mechanism:
        st.markdown("#### Paano ito gumagana")
        for number, item in enumerate(mechanism, 1):
            if isinstance(item, dict):
                title = _text(item.get("title") or item.get("step"))
                body = _text(item.get("text") or item.get("explanation"))
                if title and body:
                    st.markdown(f"{number}. **{title}** — {body}")
                elif body:
                    st.markdown(f"{number}. {body}")
            else:
                text = _text(item)
                if text:
                    st.markdown(f"{number}. {text}")

    if example:
        st.markdown("#### Isang konkretong example")
        st.info(example)

    if takeaways:
        st.markdown("#### Dapat mong maalala")
        _bullet_list(takeaways[:5])


def _step_title(step: dict[str, Any], number: int) -> str:
    name = _text(step.get("step") or step.get("title"))
    return f"Step {number} — {name}" if name else f"Step {number}"


def _render_action_plan(record: dict[str, Any], plan: dict[str, Any]) -> None:
    content = _content(record)
    action_label = _text(content.get("action")).upper()
    goal = _text(plan.get("goal"))
    who = _text(plan.get("who_should_act") or content.get("who_is_affected"))
    deadline = _text(plan.get("deadline") or content.get("deadline"))
    prepare = _items(plan.get("prepare"))
    steps = _items(plan.get("steps"))
    mistakes = _items(plan.get("mistakes_to_avoid"))
    rules = _items(plan.get("decision_rules"))
    follow_up = _text(plan.get("follow_up"))

    # Do not create fake procedural detail for legacy records. If no structured plan
    # exists, the compact "What to do" card remains the authoritative guidance.
    if not plan:
        return

    label = action_label or "ACTION"
    st.markdown(f"### Gagawin mo: {label}")
    if goal:
        st.success(f"**Goal:** {goal}")
    if who:
        st.markdown(f"**Sino ang kailangang gumawa nito:** {who}")
    if deadline:
        st.markdown(f"**Deadline / timing:** {deadline}")

    if prepare:
        st.markdown("#### Ihanda muna")
        _bullet_list(prepare)

    if steps:
        st.markdown("#### Exact steps")
        for number, raw in enumerate(steps, 1):
            if not isinstance(raw, dict):
                text = _text(raw)
                if text:
                    st.markdown(f"**Step {number}** — {text}")
                continue
            action = _text(raw.get("action"))
            how = _text(raw.get("how"))
            needed = _items(raw.get("needed"))
            done_when = _text(raw.get("done_when"))
            time_minutes = raw.get("time_minutes")
            cost_yen = raw.get("cost_yen")

            st.markdown(f"**{_step_title(raw, number)}**")
            if action:
                st.markdown(action)
            if how:
                st.markdown(f"*Paano:* {how}")
            if needed:
                st.markdown("*Kailangan:* ")
                _bullet_list(needed)
            meta = []
            if isinstance(time_minutes, (int, float)):
                meta.append(f"~{time_minutes:g} min")
            if isinstance(cost_yen, (int, float)):
                meta.append(f"~¥{cost_yen:,.0f}")
            if meta:
                st.caption(" · ".join(meta))
            if done_when:
                st.markdown(f"**Tapos ka na kapag:** {done_when}")

    if mistakes:
        st.markdown("#### Iwasan ito")
        _bullet_list(mistakes)

    if rules:
        st.markdown("#### Kung ganito, gawin ito")
        for item in rules:
            if isinstance(item, dict):
                condition = _text(item.get("if") or item.get("condition"))
                action = _text(item.get("then") or item.get("action"))
                if condition and action:
                    st.markdown(f"- **Kung {condition}:** {action}")
            else:
                text = _text(item)
                if text:
                    st.markdown(f"- {text}")

    if follow_up:
        st.markdown("#### Pagkatapos")
        st.markdown(follow_up)


def render_learning_section(record: dict[str, Any]) -> None:
    """Render the opened-story teaching layer without lengthening feed summaries."""
    content = _content(record)
    learning = _dict(content.get("learning"))
    action_plan = _dict(content.get("action_plan"))
    action_label = _text(content.get("action")).upper()

    # New records should normally contain structured learning. For legacy records,
    # show a small takeaway block only when existing fields can support it safely.
    has_learning = bool(learning)
    fallback_takeaways = _fallback_takeaways(record, content)
    if not has_learning and not action_plan and not fallback_takeaways:
        return

    st.divider()
    st.markdown("## Intindihin at iuwi")
    st.caption("Hindi kailangan may background ka. Dito ine-explain ang context, mechanics, at practical takeaway ng story.")

    if has_learning:
        _render_learning(record, learning)
    elif fallback_takeaways:
        st.markdown("#### Dapat mong maalala")
        _bullet_list(fallback_takeaways[:5])

    if action_plan:
        st.divider()
        _render_action_plan(record, action_plan)
    elif action_label in _ACTIONABLE_LABELS:
        # This is an intentional migration cue, not generated advice. Existing
        # actionable stories keep their old concise action until their next material
        # version supplies the detailed plan required by the new contract.
        st.caption("May action ang story na ito, pero legacy record pa ang detailed checklist. Sundin muna ang verified guidance sa ‘What to do’ at source details sa ibaba.")
