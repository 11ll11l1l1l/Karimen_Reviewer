import re
import sys

import alam_core


def numeric_score(value, default=50.0):
    """Convert loose ALAM score fields into a safe 0-100 number.

    New records occasionally carry semantic values such as HIGH/MEDIUM/LOW or
    nested score objects. Ranking should degrade gracefully instead of taking the
    entire Streamlit app down.
    """
    if value is None or value == "":
        return float(default)
    if isinstance(value, bool):
        return 100.0 if value else 0.0
    if isinstance(value, (int, float)):
        return max(0.0, min(100.0, float(value)))
    if isinstance(value, dict):
        for key in ("score", "value", "percent", "percentage", "rating"):
            if key in value:
                return numeric_score(value.get(key), default)
        return float(default)
    text = str(value).strip().upper()
    semantic = {
        "VERY HIGH": 90.0,
        "HIGH": 80.0,
        "MEDIUM-HIGH": 70.0,
        "MED-HIGH": 70.0,
        "MEDIUM": 55.0,
        "MED": 55.0,
        "LOW-MEDIUM": 40.0,
        "LOW": 30.0,
        "VERY LOW": 15.0,
    }
    if text in semantic:
        return semantic[text]
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return float(default)
    try:
        return max(0.0, min(100.0, float(match.group(0))))
    except (TypeError, ValueError):
        return float(default)


def safe_feed_score(record):
    record = record if isinstance(record, dict) else {}
    content = record.get("content")
    content = content if isinstance(content, dict) else {}
    sources = record.get("sources")
    source_count = len(sources) if isinstance(sources, list) else 0
    return (
        0.35 * numeric_score(record.get("importance"), 50)
        + 0.20 * alam_core.freshness_score(record.get("created_at"))
        + 0.15 * numeric_score(content.get("usefulness"), 55)
        + 0.10 * numeric_score(record.get("confidence"), 50)
        + 0.10 * numeric_score(content.get("novelty"), 55)
        + 10
        + min(8, source_count * 2)
    )


def install_runtime_safety():
    """Patch modules that imported feed_score before startup safety was installed."""
    alam_core.feed_score = safe_feed_score
    for name, module in list(sys.modules.items()):
        if not name.startswith("alam_") or module is None:
            continue
        if hasattr(module, "feed_score"):
            setattr(module, "feed_score", safe_feed_score)
