"""Deterministic failure-injection tests for ALAM evidence/source convergence.

No network or real Supabase project is used. The fake query client models only the
PostgREST operations used by ``_sync_sources`` so CI can prove ordering and retry
safety without service-role credentials.
"""

from types import SimpleNamespace

from alam_supabase_ingest import _source_rows, _sync_sources


class FakeClient:
    def __init__(self, *, fail_url=None):
        self.fail_url = fail_url
        self.article_sources = {
            "source-old": {
                "id": "source-old",
                "article_id": "story-1",
                "url": "https://old.example/source",
                "publisher": "Old Source",
                "supports_claims": [1],
            }
        }
        self.operations = []
        self._next_id = 1

    def table(self, name):
        return FakeQuery(self, name)


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table_name = table
        self.action = None
        self.payload = None
        self.filters = []
        self.on_conflict = None

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

    def _matches(self, row):
        return all(str(row.get(column)) == str(value) for column, value in self.filters)

    def execute(self):
        self.client.operations.append(
            (self.table_name, self.action, tuple(self.filters), self.payload, self.on_conflict)
        )
        if self.table_name != "article_sources":
            raise AssertionError(f"Unexpected fake table: {self.table_name}")

        if self.action == "upsert":
            row = dict(self.payload)
            if row["url"] == self.client.fail_url:
                raise RuntimeError("injected source upsert failure")
            existing_id = next(
                (
                    source_id
                    for source_id, current in self.client.article_sources.items()
                    if current.get("article_id") == row.get("article_id")
                    and current.get("url") == row.get("url")
                ),
                None,
            )
            if existing_id is None:
                existing_id = f"source-{self.client._next_id}"
                self.client._next_id += 1
            stored = dict(row)
            stored["id"] = existing_id
            self.client.article_sources[existing_id] = stored
            return SimpleNamespace(data=[])

        if self.action == "select":
            rows = [
                dict(row)
                for row in self.client.article_sources.values()
                if self._matches(row)
            ]
            return SimpleNamespace(data=rows)

        if self.action == "delete":
            stale = [
                source_id
                for source_id, row in self.client.article_sources.items()
                if self._matches(row)
            ]
            for source_id in stale:
                del self.client.article_sources[source_id]
            return SimpleNamespace(data=[])

        raise AssertionError(
            f"Unhandled fake query: {self.table_name} {self.action} {self.filters}"
        )


def _record():
    return {
        "id": "story-1",
        "title": "Evidence safety test",
        "claims": [
            {"text": "Claim one", "source_refs": [1]},
            {"text": "Claim two", "source_refs": [2]},
        ],
        "sources": [
            {
                "url": "https://new.example/one",
                "publisher": "New One",
                "source_type": "official",
            },
            {
                "url": "https://new.example/two",
                "publisher": "New Two",
                "source_type": "primary",
            },
        ],
    }


def main():
    record = _record()
    normalized = _source_rows(record)
    assert [row["supports_claims"] for row in normalized] == [[1], [2]]
    assert all(row["is_primary"] for row in normalized)

    success = FakeClient()
    assert _sync_sources(success, record) == 2
    urls = {row["url"] for row in success.article_sources.values()}
    assert urls == {"https://new.example/one", "https://new.example/two"}
    assert "source-old" not in success.article_sources

    # The old implementation deleted ``source-old`` before attempting replacements.
    # Inject failure on the second desired row: the already-confirmed first source may
    # coexist temporarily, but stale cleanup must not happen before every desired row
    # has been accepted.
    failing = FakeClient(fail_url="https://new.example/two")
    try:
        _sync_sources(failing, record)
    except RuntimeError as exc:
        assert "injected source upsert failure" in str(exc)
    else:
        raise AssertionError("failure injection did not interrupt source synchronization")

    assert "source-old" in failing.article_sources
    delete_ops = [
        op for op in failing.operations if op[0] == "article_sources" and op[1] == "delete"
    ]
    assert not delete_ops, delete_ops

    # Removing the transient failure makes retry convergence deterministic: desired
    # rows remain/update and only then is the stale old source removed.
    failing.fail_url = None
    assert _sync_sources(failing, record) == 2
    retry_urls = {row["url"] for row in failing.article_sources.values()}
    assert retry_urls == {"https://new.example/one", "https://new.example/two"}
    assert "source-old" not in failing.article_sources

    # Explicitly removing all sources is still supported. Empty desired state has no
    # replacement writes to wait for, so stale evidence can be removed intentionally.
    empty = FakeClient()
    assert _sync_sources(empty, {"id": "story-1", "sources": []}) == 0
    assert not empty.article_sources

    assert _sync_sources(FakeClient(), record, dry_run=True) == 2
    print("ALAM source sync failure-injection tests passed")


if __name__ == "__main__":
    main()
