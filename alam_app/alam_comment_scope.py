"""Choose the smallest safe cross-agent comment hydration scope for ALAM views.

The public feed can show discussion affordances for many cards, so feed/list views still
need comments for every current story. A selected article detail page is different:
all panel/disagreement rendering is scoped to one story, and fetching comments for the
entire feed adds avoidable Supabase payload and mobile latency.

Keep this decision as pure product logic so it can be regression-tested without a
Streamlit runtime or database. The data-access layer remains unchanged and local JSON
fallback behavior stays compatible.
"""


def _unique_story_ids(records):
    """Return stable, non-empty story IDs without changing feed order."""
    seen = set()
    ids = []
    for record in records or []:
        story_id = str((record or {}).get("id") or "").strip()
        if not story_id or story_id in seen:
            continue
        seen.add(story_id)
        ids.append(story_id)
    return ids


def comment_scope_ids(current_records, selected_story_id=None):
    """Return IDs whose published agent comments are needed for this render.

    A valid selected story collapses the query to exactly that story. If the selected
    ID is stale or unknown, fall back to the full current-feed scope instead of
    returning an empty discussion set; this protects rolling deployments and browser
    sessions whose selected-story state outlives a content refresh.
    """
    current_ids = _unique_story_ids(current_records)
    selected_id = str(selected_story_id or "").strip()
    if selected_id and selected_id in set(current_ids):
        return [selected_id]
    return current_ids
