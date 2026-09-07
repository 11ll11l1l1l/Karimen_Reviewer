from alam_hybrid_feed import merge_missing_audit_versions, version_key


def _record(story_id, created_at, storage, published_at=None):
    record = {
        "id": story_id,
        "title": f"Story {story_id}",
        "created_at": created_at,
        "_storage": storage,
    }
    if published_at is not None:
        record["published_at"] = published_at
    return record


def main():
    mirrored = _record("story-a", "2026-09-03T06:00:00+09:00", "supabase")
    same_audit = _record("story-a", "2026-09-03T06:00:00+09:00", "local")
    newer_audit = _record("story-a", "2026-09-03T07:00:00+09:00", "local")
    new_story = _record("story-b", "2026-09-03T06:30:00+09:00", "local")

    merged, overlay_count = merge_missing_audit_versions(
        [mirrored],
        [same_audit, newer_audit, new_story],
    )

    assert overlay_count == 2, overlay_count
    assert len(merged) == 3, merged
    assert version_key(merged[0]) == version_key(newer_audit)
    assert version_key(merged[1]) == version_key(new_story)
    assert version_key(merged[2]) == version_key(mirrored)
    assert merged[2]["_storage"] == "supabase"
    assert merged[0]["_storage"] == "verified_audit_overlay"
    assert merged[1]["_storage"] == "verified_audit_overlay"

    clean, clean_count = merge_missing_audit_versions([mirrored], [same_audit])
    assert clean_count == 0
    assert len(clean) == 1
    assert clean[0]["_storage"] == "supabase"

    # Postgres commonly serializes a Japan-time audit timestamp in UTC. These are
    # the same instant and therefore the same material story version.
    utc_mirror = _record("story-c", "2026-09-03T10:11:04+00:00", "supabase")
    japan_audit = _record("story-c", "2026-09-03T19:11:04+09:00", "local")
    timezone_clean, timezone_count = merge_missing_audit_versions([utc_mirror], [japan_audit])
    assert version_key(utc_mirror) == version_key(japan_audit)
    assert timezone_count == 0, timezone_count
    assert len(timezone_clean) == 1
    assert timezone_clean[0]["_storage"] == "supabase"

    # Public chronology is publication chronology, not agent/ingestion creation
    # chronology. A delayed GitHub overlay must not jump ahead merely because its
    # record was created later than an already-published database story.
    published_first = _record(
        "story-d",
        "2026-09-03T12:00:00+09:00",
        "supabase",
        published_at="2026-09-03T11:30:00+09:00",
    )
    created_later_but_published_earlier = _record(
        "story-e",
        "2026-09-03T12:30:00+09:00",
        "local",
        published_at="2026-09-03T11:00:00+09:00",
    )
    publication_order, publication_overlay_count = merge_missing_audit_versions(
        [published_first],
        [created_later_but_published_earlier],
    )
    assert publication_overlay_count == 1
    assert [record["id"] for record in publication_order] == ["story-d", "story-e"]

    print("ALAM hybrid feed regression test passed")


if __name__ == "__main__":
    main()
