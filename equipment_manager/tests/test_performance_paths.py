import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

from database import Database


class PerformancePathTests(unittest.TestCase):
    def test_read_batch_reuses_one_session_for_multiple_queries(self):
        with tempfile.TemporaryDirectory() as root:
            db=Database(f"sqlite:///{Path(root)/'ems.db'}")
            original=db.Session
            calls={"count":0}

            def counted_session(*args,**kwargs):
                calls["count"]+=1
                return original(*args,**kwargs)

            db.Session=counted_session
            with db.read_batch():
                db.list_equipment()
                db.list_pm_tasks()
                db.list_inventory()
            self.assertEqual(calls["count"],1)

    def test_read_batch_rows_remain_usable_after_close(self):
        with tempfile.TemporaryDirectory() as root:
            db=Database(f"sqlite:///{Path(root)/'ems.db'}")
            db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"})
            with db.read_batch():
                rows=db.list_equipment()
            self.assertEqual(rows[0].equipment_id,"ETCH-01")
            self.assertEqual(rows[0].name,"Etcher")

    def test_foreground_read_does_not_wait_for_background_manifest_probe(self):
        with tempfile.TemporaryDirectory() as root:
            db=Database(f"sqlite:///{Path(root)/'ems.db'}")
            started=threading.Event()
            release=threading.Event()

            class SlowProbe:
                def __init__(self):
                    self.pending_path=Path(root)/"no-pending.json"
                    self._last_refresh_error=""
                def refresh_due(self):
                    return True
                def probe_remote(self):
                    started.set()
                    release.wait(2)
                    return None

            db.shared_workspace=SlowProbe()
            db._background_refresh_enabled=True
            t0=time.monotonic()
            db.list_equipment()
            elapsed=time.monotonic()-t0
            self.assertLess(elapsed,0.5)
            self.assertTrue(started.wait(1))
            release.set()
            thread=db._background_refresh_thread
            if thread is not None:
                thread.join(1)

    def test_local_sqlite_performance_pragmas_are_applied(self):
        with tempfile.TemporaryDirectory() as root:
            db=Database(f"sqlite:///{Path(root)/'ems.db'}")
            with db.engine.connect() as conn:
                cache_size=int(conn.exec_driver_sql("PRAGMA cache_size").scalar_one())
                temp_store=int(conn.exec_driver_sql("PRAGMA temp_store").scalar_one())
                busy_timeout=int(conn.exec_driver_sql("PRAGMA busy_timeout").scalar_one())
            self.assertLess(cache_size,0)
            self.assertEqual(temp_store,2)
            self.assertGreaterEqual(busy_timeout,1000)

    def test_startup_data_bootstrap_is_version_gated(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"ems.db"
            Database(f"sqlite:///{path}")
            with sqlite3.connect(path) as conn:
                before=conn.execute(
                    "SELECT count(*) FROM schema_migrations WHERE revision='20261001_perf_bootstrap_v1'"
                ).fetchone()[0]
                config_before=conn.execute("SELECT count(*) FROM config_options").fetchone()[0]
                indexes={
                    row[1] for row in conn.execute("PRAGMA index_list('pm_tasks')").fetchall()
                }
            self.assertEqual(before,1)
            self.assertIn("ix_pm_task_status_due",indexes)

            Database(f"sqlite:///{path}")
            with sqlite3.connect(path) as conn:
                after=conn.execute(
                    "SELECT count(*) FROM schema_migrations WHERE revision='20261001_perf_bootstrap_v1'"
                ).fetchone()[0]
                config_after=conn.execute("SELECT count(*) FROM config_options").fetchone()[0]
            self.assertEqual(after,1)
            self.assertEqual(config_after,config_before)

    def test_escalation_evaluation_is_throttled(self):
        with tempfile.TemporaryDirectory() as root:
            db=Database(f"sqlite:///{Path(root)/'ems.db'}")
            calls={"count":0}
            def fake_evaluate(now=None):
                calls["count"]+=1
                return []
            db.evaluate_ticket_escalations=fake_evaluate
            db._escalation_check_interval=60
            db.evaluate_ticket_escalations_if_due()
            db.evaluate_ticket_escalations_if_due()
            self.assertEqual(calls["count"],1)
            db.evaluate_ticket_escalations_if_due(force=True)
            self.assertEqual(calls["count"],2)


if __name__=="__main__":
    unittest.main()
