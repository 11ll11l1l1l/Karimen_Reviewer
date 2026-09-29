import unittest
from datetime import datetime, timedelta

from database import Database


class EquipmentPMLinkTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("planner","Planner","strong-password-123","Equipment Engineer")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"},user="planner")
        self.definition={
            "pm_id":"ETCH-PM","name":"Chamber PM","equipment_id":"ETCH-01",
            "schedule_type":"Interval","frequency_value":30,"frequency_unit":"days",
            "anchor_mode":"Original Due","early_window_days":2,"grace_days":1,
            "estimated_hours":2.0,"required_people":1,"required_skill":"",
            "required_parts":"","sop_path":"","active":True,
        }

    def test_registration_to_pm_schedule_and_next_task(self):
        due=datetime(2026,10,10,9)
        first=self.db.create_equipment_pm("ETCH-01",self.definition,due,"planner")
        self.assertEqual(first.equipment_id,"ETCH-01")
        self.assertEqual(self.db.get_pm_task_schedule(first.id).scheduled_end_at,due+timedelta(hours=2))
        self.assertEqual(len(self.db.list_pm_schedule_events(first.id)),1)
        rows=self.db.operational_calendar_rows(due-timedelta(hours=1),due+timedelta(days=1))
        self.assertTrue(any(row["entity_key"]==str(first.id) for row in rows))
        second=self.db.generate_next_pm_task("ETCH-PM",due+timedelta(days=30),"planner")
        self.assertNotEqual(first.id,second.id)
        with self.assertRaisesRegex(ValueError,"already exists"):
            self.db.generate_next_pm_task("ETCH-PM",due+timedelta(days=30),"planner")
        self.assertEqual(self.db.get_pm_task(first.id).status,"Scheduled")

    def test_unregistered_equipment_cannot_create_or_bind_pm(self):
        definition=dict(self.definition,equipment_id="MISSING")
        with self.assertRaisesRegex(ValueError,"not registered"):
            self.db.save_pm_definition(definition)
        with self.assertRaises(ValueError):
            self.db.create_equipment_pm("MISSING",definition,datetime(2026,10,10),"planner")
        self.assertEqual(self.db.list_pm_definitions(),[])
