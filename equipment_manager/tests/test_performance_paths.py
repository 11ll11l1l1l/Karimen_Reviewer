import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

from database import (
    Database, Equipment, PMDefinition, PMTask, PMRequirement,
    InventoryItem, InventoryReservation, PartAlternate,
)


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

    def test_pm_kit_status_batches_inventory_and_alternate_queries(self):
        with tempfile.TemporaryDirectory() as root:
            db=Database(f"sqlite:///{Path(root)/'ems.db'}")
            with db.session() as s:
                s.add(Equipment(equipment_id="ETCH-01",name="Etcher"))
                s.add(PMDefinition(pm_id="PM-1",name="Weekly PM",equipment_id="ETCH-01"))
                task=PMTask(equipment_id="ETCH-01",pm_id="PM-1",pm_name="Weekly PM")
                s.add(task);s.flush()
                s.add_all([
                    PMRequirement(
                        requirement_id="REQ-P1",pm_id="PM-1",requirement_type="PART",
                        requirement_key="P1",description="Part 1",quantity=8,
                    ),
                    PMRequirement(
                        requirement_id="REQ-P2",pm_id="PM-1",requirement_type="PART",
                        requirement_key="P2",description="Part 2",quantity=2,
                    ),
                    InventoryItem(part_number="P1",location_code="A",quantity=10,condition="Available"),
                    InventoryItem(part_number="P2",location_code="A",quantity=2,condition="Available"),
                    InventoryReservation(
                        part_number="P1",location_code="A",quantity=4,pm_task_id=task.id,
                        equipment_id="ETCH-01",status="Reserved",reserved_by="planner",
                    ),
                    InventoryReservation(
                        part_number="P1",location_code="A",quantity=3,pm_task_id=None,
                        equipment_id="OTHER",status="Reserved",reserved_by="other",
                    ),
                    PartAlternate(part_number="P1",alternate_part_number="P1A",approved=True),
                    PartAlternate(part_number="P2",alternate_part_number="P2A",approved=True),
                ])
                task_id=task.id

            def should_not_run(*args,**kwargs):
                raise AssertionError("per-part query helper should not be called")

            db.inventory_available=should_not_run
            db.list_part_alternates=should_not_run
            db.list_reservations=should_not_run
            result=db.pm_kit_status(task_id)

            by_part={row["part_number"]:row for row in result["parts"]}
            self.assertEqual(by_part["P1"]["reserved"],4)
            self.assertEqual(by_part["P1"]["available_unreserved"],3)
            self.assertEqual(by_part["P1"]["shortage"],1)
            self.assertEqual(by_part["P1"]["alternates"],["P1A"])
            self.assertTrue(by_part["P2"]["ready"])
            self.assertEqual(by_part["P2"]["alternates"],["P2A"])
            self.assertEqual(len(result["reservations"]),1)
            self.assertEqual(result["reservations"][0]["part_number"],"P1")

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
