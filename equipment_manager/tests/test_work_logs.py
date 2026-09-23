import unittest
from datetime import datetime, timedelta

from sqlalchemy import select

from database import Database, WorkLog


class WorkLogTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("tech","Technician","tech-password-123","Maintenance")
        self.db.create_user("sup","Supervisor","supervisor-password-123","Supervisor")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"},user="tech")

    def test_start_is_idempotent_and_stop_records_duration(self):
        first=self.db.start_work_log("PM_TASK","1","ETCH-01","tech","Maintenance","Started chamber PM")
        same=self.db.start_work_log("PM_TASK","1","ETCH-01","tech","Maintenance","Duplicate click")
        self.assertEqual(first.id,same.id)
        with self.db.session() as s:
            row=s.get(WorkLog,first.id)
            row.started_at=datetime.utcnow()-timedelta(minutes=42)
        done=self.db.stop_work_log(first.id,"tech","Completed")
        self.assertEqual(done.status,"Completed")
        self.assertGreaterEqual(done.duration_minutes,41.9)

    def test_supervisor_can_close_workers_active_log(self):
        row=self.db.start_work_log("TICKET","INC-1","ETCH-01","tech","Troubleshooting")
        done=self.db.stop_work_log(row.id,"sup","Shift handover")
        self.assertEqual(done.status,"Completed")

    def test_unrelated_worker_cannot_close_log(self):
        self.db.create_user("other","Other","other-password-123","Maintenance")
        row=self.db.start_work_log("TICKET","INC-2","ETCH-01","tech","Troubleshooting")
        with self.assertRaises(PermissionError):
            self.db.stop_work_log(row.id,"other")

    def test_completed_work_emits_integration_event(self):
        self.db.save_integration_endpoint({
            "endpoint_id":"LABOR","name":"Labor","adapter_type":"FILE","target":".",
            "topics":"labor.work.completed","enabled":True,
        })
        row=self.db.start_work_log("EQUIPMENT","ETCH-01","ETCH-01","tech","Engineering")
        self.db.stop_work_log(row.id,"tech")
        pending=self.db.pending_integration_deliveries()
        self.assertTrue(any(event.topic=="labor.work.completed" for _,event,_ in pending))


if __name__=="__main__":
    unittest.main()
