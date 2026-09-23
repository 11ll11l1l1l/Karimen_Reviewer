import unittest
from datetime import datetime, timedelta

from database import Database


class EngineeringAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("ee","Equipment Engineer","engineer-password-123","Equipment Engineer")
        self.db.save_equipment({"equipment_id":"ETCH-A","name":"Etcher A"},user="ee")
        self.db.save_equipment({"equipment_id":"CVD-B","name":"CVD B"},user="ee")
        self.db.save_ticket({
            "ticket_no":"INC-ANA-1","equipment_id":"ETCH-A","title":"Vacuum issue",
            "description":"Vacuum instability","severity":"S2","priority":"P2","owner":"ee",
            "root_cause":"","corrective_action":"","verification":"","created_by":"ee",
        })
        self.db.ingest_alarm("ETCH-A","VAC-ANA",severity="Warning",message="Vacuum warning",source="Tool")
        now=datetime.utcnow()
        self.db.upsert_pm_task({
            "equipment_id":"ETCH-A","pm_id":"PM-ANA-1","pm_name":"Analytics PM",
            "original_due_date":now-timedelta(days=2),"scheduled_date":now-timedelta(days=2),
            "status":"Overdue","assigned_to":"ee","estimated_hours":2.0,"priority":"Normal",
        })
        self.db.upsert_pm_task({
            "equipment_id":"CVD-B","pm_id":"PM-ANA-2","pm_name":"Completed Analytics PM",
            "original_due_date":now-timedelta(days=4),"scheduled_date":now-timedelta(days=4),
            "last_completion_date":now-timedelta(days=3),"status":"Completed",
            "assigned_to":"ee","estimated_hours":1.0,"priority":"Normal",
        })

    def test_engineering_analytics_combines_reliability_incidents_alarms_and_pm(self):
        data=self.db.engineering_analytics(30)
        self.assertEqual(data["days"],30)
        row=next(x for x in data["tool_matrix"] if x["equipment_id"]=="ETCH-A")
        self.assertEqual(row["open_incidents"],1)
        self.assertEqual(row["critical_open"],1)
        self.assertEqual(row["active_alarms"],1)
        self.assertTrue(any(x["alarm_code"]=="VAC-ANA" for x in data["alarm_pareto"]))
        self.assertTrue(any(x["equipment_id"]=="ETCH-A" and x["count"]==1 for x in data["incident_pareto"]))
        self.assertEqual(data["pm"]["due"],2)
        self.assertEqual(data["pm"]["completed"],1)
        self.assertGreaterEqual(data["pm"]["overdue"],1)


if __name__=="__main__":
    unittest.main()
