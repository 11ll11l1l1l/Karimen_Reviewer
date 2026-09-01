import json
from pathlib import Path

import streamlit as st

from alam_core import DATA_DIR, parse_dt

COMMENTS_DIR = DATA_DIR / "comments"

PERSONAS = {
    "discover": [
        {
            "id": "kiko-kuryoso",
            "name": "Kiko Kuryoso",
            "emoji": "🔭",
            "role": "Curious Scout",
            "pole": "explore",
            "tagline": "Uy, interesting 'to. Pero ano talaga ang bago?",
            "description": "Energetic, novelty-seeking and optimistic about useful discoveries, but still evidence-aware.",
        },
        {
            "id": "mara-teka",
            "name": "Mara Teka",
            "emoji": "🧐",
            "role": "Evidence Skeptic",
            "pole": "challenge",
            "tagline": "Teka lang. Source muna bago excitement.",
            "description": "Suspicious of hype, PR framing and weak comparisons; asks what would falsify the exciting story.",
        },
    ],
    "reflection": [
        {
            "id": "jiro-daloy",
            "name": "Jiro Daloy",
            "emoji": "📈",
            "role": "Market Transmission Analyst",
            "pole": "transmit",
            "tagline": "Ano ang chain reaction papunta sa Japan market?",
            "description": "Traces how macro, policy, yields, FX and global risk appetite transmit into Japanese sectors and indices.",
        },
        {
            "id": "aya-presyo",
            "name": "Aya Presyo",
            "emoji": "⚖️",
            "role": "Valuation & Risk Skeptic",
            "pole": "calibrate",
            "tagline": "Magandang narrative. Pero priced in na ba?",
            "description": "Challenges one-day extrapolation, crowded narratives, valuation blindness, positioning effects and false causality.",
        },
    ],
    "practical": [
        {
            "id": "mika-sulit",
            "name": "Mika Sulit",
            "emoji": "💸",
            "role": "Value Optimizer",
            "pole": "maximize",
            "tagline": "Magkano ang tipid, gaano katagal, at sulit ba talaga?",
            "description": "Looks for measurable savings, low-effort wins and good value; allergic to fake discounts.",
        },
        {
            "id": "ramon-ingat",
            "name": "Ramon Ingat",
            "emoji": "🛡️",
            "role": "Risk Planner",
            "pole": "protect",
            "tagline": "Okay ang tipid. Pero ano ang catch?",
            "description": "Prioritizes downside protection, paperwork, deadlines, safety, scams and hidden long-term costs.",
        },
    ],
    "trend": [
        {
            "id": "nico-signal",
            "name": "Nico Signal",
            "emoji": "📡",
            "role": "Pattern Hunter",
            "pole": "detect",
            "tagline": "Isa lang? Noise. Tatlo? Hmm, may signal na yata.",
            "description": "Connects weak signals across time and categories and is willing to make calibrated forecasts.",
        },
        {
            "id": "bea-base-rate",
            "name": "Bea Base Rate",
            "emoji": "📊",
            "role": "Statistical Skeptic",
            "pole": "calibrate",
            "tagline": "Cute pattern. Pero ilang beses na ba tayong naloko ng pattern?",
            "description": "Challenges overfitting, recency bias, tiny samples and false causal stories; protects calibration.",
        },
    ],
}

PRIVATE_JOB_PERSONAS = [
    {
        "id": "ace-apply",
        "name": "Ace Apply",
        "emoji": "🚀",
        "role": "Career Upside",
        "tagline": "If the ceiling is higher, let's quantify it.",
    },
    {
        "id": "rina-reality",
        "name": "Rina Reality",
        "emoji": "🧾",
        "role": "Relocation Reality Check",
        "tagline": "Gross salary is not a lifestyle. Show me the net, visa and housing.",
    },
]

PERSONA_BY_ID = {
    p["id"]: p
    for group in PERSONAS.values()
    for p in group
}


@st.cache_data(ttl=60)
def load_comments():
    comments = []
    if not COMMENTS_DIR.exists():
        return comments
    for path in sorted(COMMENTS_DIR.rglob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            batch = payload if isinstance(payload, list) else [payload]
            for idx, item in enumerate(batch):
                if not isinstance(item, dict):
                    continue
                if not item.get("id") or not item.get("story_id") or not item.get("body"):
                    continue
                copy = dict(item)
                copy["_path"] = str(path.relative_to(DATA_DIR))
                copy["_record_key"] = f"{copy['_path']}::{idx}"
                comments.append(copy)
        except Exception:
            continue
    return sorted(comments, key=lambda c: parse_dt(c.get("created_at")))


def comments_for_story(comments, story_id):
    return [c for c in comments if str(c.get("story_id")) == str(story_id)]


def persona_for_comment(comment):
    pid = str(comment.get("persona_id") or "")
    if pid in PERSONA_BY_ID:
        return PERSONA_BY_ID[pid]
    return {
        "id": pid or "unknown",
        "name": comment.get("persona_name") or "ALAM Voice",
        "emoji": "💬",
        "role": comment.get("persona_role") or "Editorial Persona",
        "tagline": "",
        "description": "",
    }