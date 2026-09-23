import unittest
from datetime import datetime, timedelta

from database import Database


class MaintenancePlanningTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("planner","Planner","planner-password-123","Equipment Engineer")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher 01"},user="planner")
        self.db.save_pm_definition({
            "pm_id":"PM-MONTHLY","name":"Monthly chamber PM","equipment_id":"ETCH-01",
            "schedule_type":"Interval","frequency_value":30,"frequency_unit":"days",
            "anchor_mode":"Original Due","early_window_days":2,"grace_days":1,
            "estimated_hours":4.0,"required_people":1,"required_skill":"",
            "required_parts":"","sop_path":"","active":True,"revision":1,
        })
        self.due=datetime(2026,10,10,8,0)
        self.task=self.db.upsert_pm_task({
            "equipment_id":"ETCH-01","pm_id":"PM-MONTHLY","pm_name":"Monthly chamber PM",
            "original_due_date":self.due,"scheduled_date":self.due,"status":"Scheduled",
            "assigned_to":"","estimated_hours":4.0,"priority":"Normal","sop_path":"",
        })

    def test_planner_can_assign_and_reschedule_within_controlled_window(self):
        planned=self.db.plan_pm_task(
            self.task.id,"planner",scheduled_date=self.due-timedelta(days=1),
            assigned_to="planner",expected_version=self.task.version,
        )
        self.assertEqual(planned.assigned_to,"planner")
        self.assertEqual(planned.scheduled_date,self.due-timedelta(days=1))

    def test_planner_cannot_bypass_deferral_by_scheduling_beyond_grace(self):
        with self.assertRaises(ValueError) as ctx:
            self.db.plan_pm_task(
                self.task.id,"planner",scheduled_date=self.due+timedelta(days=3),
                expected_version=self.task.version,
            )
        self.assertIn("deferral",str(ctx.exception).lower())

    def test_planning_rows_expose_window_and_load_fields(self):
        rows=self.db.pm_planning_rows(365,True)
        row=next(x for x in rows if x["id"]==self.task.id)
        self.assertEqual(row["equipment_id"],"ETCH-01")
        self.assertEqual(row["estimated_hours"],4.0)
        self.assertIn(row["window"],{"IN WINDOW","OVERDUE"})


if __name__=="__main__":
    unittest.main()
