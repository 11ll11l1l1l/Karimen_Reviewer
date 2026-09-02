"""Deterministic failure-injection tests for ALAM article-topic convergence.

No network or real Supabase project is used. The fake query client is intentionally
small: it models only the PostgREST operations used by ``_sync_topics`` so CI can
prove ordering and retry safety without credentials.
"""

from types import SimpleNamespace

from alam_supabase_ingest import _sync_topics, _topic_tags


class FakeClient:
    def __init__(self, *, fail_topic_slug=None):
        self.fail_topic_slug = fail_topic_slug
        self.topics = {
            "old-topic": {"id": "topic-old", "slug": "old-topic", "label": "Old Topic"},
        }
        self.article_topics = {
            ("story-1", "topic-old"): {"article_id": "story-1", "topic_id": "topic-old", "weight": 1},
        }
        self.operations = []
        self._next_topic_id = 1

    def table(self, name):
        return FakeQuery(self, name)


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table_name = table
        self.action = None
        self.payload = None
        self.filters = []
        self.limit_count = None

    def select(self, columns):
        self.action = "select"
        self.payload = columns
        return self

    def upsert(self, payload, on_conflict=None):
        self.action = "upsert"
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def delete(self):
        self.action = "delete"
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def _matches(self, row):
        return all(str(row.get(column)) == str(value) for column, value in self.filters)

    def execute(self):
        self.client.operations.append((self.table_name, self.action, tuple(self.filters), self.payload))

        if self.table_name == "topics":
            if self.action == "upsert":
                row = dict(self.payload)
                existing = self.client.topics.get(row["slug"])
                if existing:
                    existing["label"] = row["label"]
                else:
                    topic_id = f"topic-{self.client._next_topic_id}"
                    self.client._next_topic_id += 1
                    self.client.topics[row["slug"]] = {
                        "id": topic_id,
                        "slug": row["slug"],
                        "label": row["label"],
                    }
                return SimpleNamespace(data=[])

            if self.action == "select":
                slug = next((value for column, value in self.filters if column == "slug"), None)
                if slug == self.client.fail_topic_slug:
                    raise RuntimeError("injected topic lookup failure")
                row = self.client.topics.get(slug)
                return SimpleNamespace(data=[{"id": row["id"]}] if row else [])

        if self.table_name == "article_topics":
            if self.action == "upsert":
                row = dict(self.payload)
                key = (str(row["article_id"]), str(row["topic_id"]))
                self.client.article_topics[key] = row
                return SimpleNamespace(data=[])

            if self.action == "select":
                rows = [
                    dict(row)
                    for row in self.client.article_topics.values()
                    if self._matches(row)
                ]
                return SimpleNamespace(data=rows[: self.limit_count] if self.limit_count else rows)

            if self.action == "delete":
                stale = [
                    key
                    for key, row in self.client.article_topics.items()
                    if self._matches(row)
                ]
                for key in stale:
                    del self.client.article_topics[key]
                return SimpleNamespace(data=[])

        raise AssertionError(f"Unhandled fake query: {self.table_name} {self.action} {self.filters}")


def main():
    record = {
        "id": "story-1",
        "title": "Topic test",
        "tags": ["Japan", "japan", "Semiconductors", "AI & Robotics"],
    }

    # Normalization is stable and de-duplicates by database slug rather than label.
    assert _topic_tags(record) == [
        ("japan", "Japan"),
        ("semiconductors", "Semiconductors"),
        ("ai-robotics", "AI & Robotics"),
    ]

    success = FakeClient()
    assert _sync_topics(success, record) == 3
    linked_ids = {
        topic_id for article_id, topic_id in success.article_topics if article_id == "story-1"
    }
    expected_ids = {success.topics[slug]["id"] for slug, _ in _topic_tags(record)}
    assert linked_ids == expected_ids, (linked_ids, expected_ids)
    assert ("story-1", "topic-old") not in success.article_topics

    # Failure injection: the old implementation deleted ``topic-old`` before it
    # attempted any replacement. The new ordering may add already-confirmed desired
    # joins before a later failure, but it must not perform stale cleanup until every
    # desired topic has been resolved and upserted successfully.
    failing = FakeClient(fail_topic_slug="semiconductors")
    try:
        _sync_topics(failing, record)
    except RuntimeError as exc:
        assert "injected topic lookup failure" in str(exc)
    else:
        raise AssertionError("failure injection did not interrupt topic synchronization")

    assert ("story-1", "topic-old") in failing.article_topics
    delete_ops = [op for op in failing.operations if op[0] == "article_topics" and op[1] == "delete"]
    assert not delete_ops, delete_ops

    # A retry without the transient failure converges cleanly and removes stale state.
    failing.fail_topic_slug = None
    assert _sync_topics(failing, record) == 3
    retry_ids = {
        topic_id for article_id, topic_id in failing.article_topics if article_id == "story-1"
    }
    expected_retry_ids = {failing.topics[slug]["id"] for slug, _ in _topic_tags(record)}
    assert retry_ids == expected_retry_ids
    assert ("story-1", "topic-old") not in failing.article_topics

    # An empty tag list intentionally removes old joins, but only after the desired
    # set (which is empty) has been established. This preserves explicit tag removal.
    empty = FakeClient()
    assert _sync_topics(empty, {"id": "story-1", "tags": []}) == 0
    assert not empty.article_topics

    print("ALAM topic sync failure-injection tests passed")


if __name__ == "__main__":
    main()
