import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

from sqlalchemy import event

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

    def test_startup_bootstrap_is_idempotent_and_indexes_exist(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"ems.db"
            db=Database(f"sqlite:///{path}")
            with sqlite3.connect(path) as conn:
                config_before=conn.execute("SELECT count(*) FROM config_options").fetchone()[0]
                indexes={
                    row[1] for row in conn.execute("PRAGMA index_list('pm_tasks')").fetchall()
                }
                migration_before=conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
            self.assertIn("ix_pm_task_status_due",indexes)
            with sqlite3.connect(path) as conn:
                equipment_indexes={row[1] for row in conn.execute("PRAGMA index_list('equipment')").fetchall()}
                storage_indexes={row[1] for row in conn.execute("PRAGMA index_list('storage_locations')").fetchall()}
            self.assertIn("ix_equipment_building_floor_area",equipment_indexes)
            self.assertIn("ix_storage_building_floor_area",storage_indexes)

            reopened=Database(f"sqlite:///{path}")
            with sqlite3.connect(path) as conn:
                config_after=conn.execute("SELECT count(*) FROM config_options").fetchone()[0]
                migration_after=conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
            self.assertEqual(config_after,config_before)
            self.assertEqual(migration_after,migration_before)
            self.assertEqual(
                [x.revision for x in reopened.list_schema_migrations()],
                [revision for revision,_description,_apply in reopened._migration_plan()],
            )
    def test_dashboard_counts_use_one_select_statement(self):
        with tempfile.TemporaryDirectory() as root:
            db=Database(f"sqlite:///{Path(root)/'ems.db'}")
            db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"})
            statements=[]

            def before_cursor_execute(conn,cursor,statement,parameters,context,executemany):
                if statement.lstrip().upper().startswith("SELECT"):
                    statements.append(statement)

            event.listen(db.engine,"before_cursor_execute",before_cursor_execute)
            try:
                counts=db.dashboard_counts()
            finally:
                event.remove(db.engine,"before_cursor_execute",before_cursor_execute)

            self.assertEqual(counts["equipment_total"],1)
            self.assertEqual(len(statements),1)

    def test_layout_queries_filter_in_sqlite(self):
        with tempfile.TemporaryDirectory() as root:
            db=Database(f"sqlite:///{Path(root)/'ems.db'}")
            db.save_equipment({
                "equipment_id":"ETCH-A","name":"Etcher A",
                "building":"FAB-1","floor":"1F","area":"ETCH",
            })
            db.save_equipment({
                "equipment_id":"CMP-B","name":"Polisher B",
                "building":"FAB-2","floor":"2F","area":"CMP",
            })
            db.save_storage_location({
                "location_code":"ST-A","name":"Storage A",
                "building":"FAB-1","floor":"1F","area":"ETCH",
            })
            db.save_storage_location({
                "location_code":"ST-B","name":"Storage B",
                "building":"FAB-2","floor":"2F","area":"CMP",
            })

            equipment=db.list_equipment(building="FAB-1",floor="1F")
            storage=db.list_storage_locations(building="FAB-1",floor="1F")
            self.assertEqual([row.equipment_id for row in equipment],["ETCH-A"])
            self.assertEqual([row.location_code for row in storage],["ST-A"])

    def test_unchanged_layout_position_does_not_increment_version(self):
        with tempfile.TemporaryDirectory() as root:
            db=Database(f"sqlite:///{Path(root)/'ems.db'}")
            eq=db.save_equipment({
                "equipment_id":"ETCH-01","name":"Etcher","map_x":10.0,"map_y":20.0
            })
            original_version=eq.version
            row=db.update_map_position(
                "equipment","ETCH-01",10.0,20.0,expected_version=original_version
            )
            self.assertEqual(row.version,original_version)
            persisted=db.get_equipment("ETCH-01")
            self.assertEqual(persisted.version,original_version)
            self.assertEqual((persisted.map_x,persisted.map_y),(10.0,20.0))

    def test_layout_position_batch_is_atomic(self):
        with tempfile.TemporaryDirectory() as root:
            db=Database(f"sqlite:///{Path(root)/'ems.db'}")
            eq=db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"})
            loc=db.save_storage_location({"location_code":"ST-01","name":"Storage"})
            db.update_map_positions_batch([
                {
                    "entity_type":"equipment","key":"ETCH-01",
                    "x":10,"y":20,"expected_version":eq.version,
                },
                {
                    "entity_type":"storage","key":"ST-01",
                    "x":30,"y":40,"expected_version":loc.version,
                },
            ],user="planner",layout_key="FAB-1/1F",workstation="TEST-PC")

            eq_after=db.get_equipment("ETCH-01")
            loc_after=db.list_storage_locations()[0]
            self.assertEqual((eq_after.map_x,eq_after.map_y),(10.0,20.0))
            self.assertEqual((loc_after.map_x,loc_after.map_y),(30.0,40.0))

            stale_equipment_version=eq.version
            storage_version=loc_after.version
            with self.assertRaises(RuntimeError):
                db.update_map_positions_batch([
                    {
                        "entity_type":"equipment","key":"ETCH-01",
                        "x":100,"y":200,"expected_version":stale_equipment_version,
                    },
                    {
                        "entity_type":"storage","key":"ST-01",
                        "x":300,"y":400,"expected_version":storage_version,
                    },
                ],user="planner",layout_key="FAB-1/1F",workstation="TEST-PC")

            eq_final=db.get_equipment("ETCH-01")
            loc_final=db.list_storage_locations()[0]
            self.assertEqual((eq_final.map_x,eq_final.map_y),(10.0,20.0))
            self.assertEqual((loc_final.map_x,loc_final.map_y),(30.0,40.0))

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
