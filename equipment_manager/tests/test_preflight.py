import os
import tempfile
import unittest
from pathlib import Path

from preflight import run_preflight


class PreflightTests(unittest.TestCase):
    def test_local_preflight_reports_sqlite_warning_but_passes(self):
        with tempfile.TemporaryDirectory() as root:
            db=str(Path(root)/"ems.db")
            result=run_preflight(
                f"sqlite:///{db}",
                str(Path(root)/"files"),
                str(Path(root)/"backups"),
            )
            self.assertTrue(result["ok"])
            statuses={x["name"]:x["status"] for x in result["checks"]}
            self.assertEqual(statuses["database_connection"],"PASS")
            self.assertEqual(statuses["database_schema"],"PASS")
            self.assertEqual(statuses["production_database_mode"],"WARN")
            self.assertEqual(statuses["file_root_write"],"PASS")
            self.assertEqual(statuses["backup_root_write"],"PASS")

    def test_unwritable_path_fails_preflight(self):
        if os.name=="nt":
            self.skipTest("POSIX permission semantics test")
        with tempfile.TemporaryDirectory() as root:
            blocker=Path(root)/"not_a_directory"
            blocker.write_text("file",encoding="utf-8")
            result=run_preflight(
                f"sqlite:///{Path(root)/'ems.db'}",
                str(blocker),
                str(Path(root)/"backups"),
            )
            statuses={x["name"]:x["status"] for x in result["checks"]}
            self.assertEqual(statuses["file_root_write"],"FAIL")
            self.assertFalse(result["ok"])


if __name__=="__main__":
    unittest.main()
