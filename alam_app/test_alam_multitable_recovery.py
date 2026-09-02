"""Higher-fidelity recovery test for ALAM multi-table Supabase partial writes.

This test models the production failure mode where the current ``articles`` row is
accepted but the following ``article_versions`` insert fails. A normal incremental
retry then sees the equal timestamp and returns ``unchanged``; correctness therefore
depends on archive reconciliation repairing history and the remaining derived rows.
No network or real Supabase project is used.
"""

from pathlib import Path
from types import SimpleNamespace

from alam_supabase_ingest import sync_article
from alam_supabase_reconcile import reconcile_public_archive


class InjectedFailure(RuntimeError):
    pass


class FakeClient:
    def __init__(self):
        self.fail_next_version_insert = True
        self.tables = {
            "articles": {},
            "article_versions": {},
            "article_sources": {},
            "article_topics": {},
            "topics": {},
            "predictions": {},
        }
        self.operations = []
        self._source_seq = 0

    def table(self, name):
        return FakeQuery(self, name)


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table_name = table
        self.op = None
        self.payload = None
        self.filters = []
        self.order_field = None
        self.order_desc = False
        self.limit_count = None

    def select(self, fields):
        self.op = "select"
        self.fields = fields
        return self

    def insert(self, payload):
        self.op = "insert"
        self.payload = payload
        return self

    def upsert(self, payload, on_conflict=None):
        self.op = "upsert"
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def update(self, payload):
        self.op = "update"
        self.payload = payload
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, field, value):
        self.filters.append(("eq", field, value))
        return self

    def gt(self, field, value):
        self.filters.append(("gt", field, value))
        return self

    def order(self, field, desc=False):
        self.order_field = field
        self.order_desc = desc
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def _matches(self, row):
        for operator, field, value in self.filters:
            current = row.get(field)
            if operator == "eq" and current != value:
                return False
            if operator == "gt" and not (current is not None and current > value):
                return False
        return True

    def _rows(self):
        table = self.client.tables[self.table_name]
        rows = list(table.values()) if isinstance(table, dict) else list(table)
        rows = [dict(row) for row in rows if self._matches(row)]
        if self.order_field:
            rows.sort(key=lambda row: row.get(self.order_field), reverse=self.order_desc)
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        return rows

    def execute(self):
        self.client.operations.append((self.table_name, self.op, self.payload, tuple(self.filters)))
        if self.op == "select":
            return SimpleNamespace(data=self._rows())
        if self.op == "insert":
            return SimpleNamespace(data=self._write(insert_only=True))
        if self.op == "upsert":
            return SimpleNamespace(data=self._write(insert_only=False))
        if self.op == "update":
            updated = []
            table = self.client.tables[self.table_name]
            for key, row in list(table.items()):
                if self._matches(row):
                    row = dict(row)
                    row.update(self.payload)
                    table[key] = row
                    updated.append(dict(row))
            return SimpleNamespace(data=updated)
        if self.op == "delete":
            table = self.client.tables[self.table_name]
            deleted = []
            for key, row in list(table.items()):
                if self._matches(row):
                    deleted.append(dict(row))
                    del table[key]
            return SimpleNamespace(data=deleted)
        raise AssertionError(f"Unsupported fake operation: {self.op}")

    def _write(self, insert_only):
        payloads = self.payload if isinstance(self.payload, list) else [self.payload]
        written = []
        for payload in payloads:
            row = dict(payload)
            if self.table_name == "article_versions":
                if insert_only and self.client.fail_next_version_insert:
                    self.client.fail_next_version_insert = False
                    raise InjectedFailure("simulated article_versions insert failure")
                key = (str(row["article_id"]), int(row["version_no"]))
            elif self.table_name == "articles":
                key = str(row["id"])
            elif self.table_name == "article_sources":
                existing_key = next(
                    (
                        key
                        for key, existing in self.client.tables["article_sources"].items()
                        if existing.get("article_id") == row.get("article_id")
                        and existing.get("url") == row.get("url")
                    ),
                    None,
                )
                if existing_key is None:
                    self.client._source_seq += 1
                    key = f"source-{self.client._source_seq}"
                    row.setdefault("id", key)
                else:
                    key = existing_key
                    row.setdefault("id", key)
            elif self.table_name == "article_topics":
                key = (str(row["article_id"]), str(row["topic_id"]))
            elif self.table_name == "topics":
                key = str(row.get("id") or row.get("slug"))
                row.setdefault("id", key)
            elif self.table_name == "predictions":
                key = str(row.get("id") or row.get("article_id"))
                row.setdefault("id", key)
            else:
                raise AssertionError(f"Unsupported fake table: {self.table_name}")

            table = self.client.tables[self.table_name]
            if insert_only and key in table:
                raise AssertionError(f"duplicate fake insert into {self.table_name}: {key}")
            table[key] = row
            written.append(dict(row))
        return written


def main():
    record = {
        "id": "story-partial-1",
        "story_key": "story-partial-1",
        "title": "A material update",
        "summary": "The current row should survive while reconciliation repairs history.",
        "created_at": "2026-09-03T00:00:00+00:00",
        "status": "DEVELOPING",
        "claims": [
            {
                "text": "A verified claim",
                "classification": "FACT",
                "source_refs": [1],
            }
        ],
        "sources": [
            {
                "url": "https://official.example/update",
                "publisher": "Official Example",
                "source_type": "official",
            }
        ],
        "content": {
            "change_summary": {
                "previous": "Earlier state",
                "now": "Updated state",
                "why_change_matters": "It changes the reader decision.",
            }
        },
    }
    archive = {
        record["id"]: [
            ("discover", Path("data/discover/story-partial-1.json"), record)
        ]
    }
    client = FakeClient()

    try:
        sync_article(client, record, "discover")
    except InjectedFailure:
        pass
    else:
        raise AssertionError("failure injection did not interrupt article_versions")

    # The user-facing current article has advanced, but the derived mirror is empty.
    assert client.tables["articles"][record["id"]]["title"] == record["title"]
    assert not client.tables["article_versions"]
    assert not client.tables["article_sources"]

    # A plain incremental retry cannot repair the partial mirror because the timestamp
    # is already current. This assertion protects the exact recovery dependency that
    # the trusted sync wrapper is designed around.
    assert sync_article(client, record, "discover") == "unchanged"
    assert not client.tables["article_versions"]
    assert not client.tables["article_sources"]

    stats = reconcile_public_archive(client, prepared_archive=archive)

    version_key = (record["id"], 1)
    assert version_key in client.tables["article_versions"]
    assert client.tables["article_versions"][version_key]["record"] == record
    source_rows = list(client.tables["article_sources"].values())
    assert len(source_rows) == 1
    assert source_rows[0]["url"] == "https://official.example/update"
    assert source_rows[0]["supports_claims"] == [1]
    assert client.tables["articles"][record["id"]]["record"] == record
    assert stats["reconcile_articles"] == 1
    assert stats["reconcile_versions_written"] == 1
    assert stats["reconcile_sources_upserted"] == 1

    # Once repaired, another reconciliation must not manufacture another history slot.
    stats_again = reconcile_public_archive(client, prepared_archive=archive)
    assert len(client.tables["article_versions"]) == 1
    assert stats_again["reconcile_versions_written"] == 0

    print("ALAM multi-table partial-write recovery test passed")


if __name__ == "__main__":
    main()
