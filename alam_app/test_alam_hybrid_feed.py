from alam_hybrid_feed import merge_missing_audit_versions, version_key


def _record(story_id, created_at, storage):
    return {
        "id": story_id,
        "title": f"Story {story_id}",
        "created_at": created_at,
        "_storage": storage,
    }


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

    print("ALAM hybrid feed regression test passed")


if __name__ == "__main__":
    main()
