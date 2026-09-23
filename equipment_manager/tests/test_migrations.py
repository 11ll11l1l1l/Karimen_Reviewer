import tempfile
import unittest
from pathlib import Path

from sqlalchemy import select

from database import Database, SchemaMigration


class MigrationLifecycleTests(unittest.TestCase):
    def test_new_database_records_migration_history_and_reopens_cleanly(self):
        with tempfile.TemporaryDirectory() as root:
            url=f"sqlite:///{Path(root)/'ems.db'}"
            db=Database(url)
            rows=db.list_schema_migrations()
            self.assertEqual([x.revision for x in rows],["20260923_001","20260923_002","20260923_003"])
            reopened=Database(url)
            self.assertEqual(len(reopened.list_schema_migrations()),2)

    def test_migration_checksum_tampering_stops_startup(self):
        with tempfile.TemporaryDirectory() as root:
            url=f"sqlite:///{Path(root)/'ems.db'}"
            db=Database(url)
            with db.session() as s:
                row=s.scalar(select(SchemaMigration).where(SchemaMigration.revision=="20260923_001"))
                row.checksum="0"*64
            with self.assertRaises(RuntimeError) as ctx:
                Database(url)
            self.assertIn("MIGRATION CHECKSUM MISMATCH",str(ctx.exception))


if __name__=="__main__":
    unittest.main()
