import os
import unittest
from datetime import datetime, timedelta

from database import Database


@unittest.skipUnless(os.getenv("EMS_TEST_POSTGRES_URL"),"PostgreSQL test URL not configured")
class PostgreSQLRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=Database(os.environ["EMS_TEST_POSTGRES_URL"])

    def test_governed_workflows_on_postgresql(self):
        suffix=datetime.utcnow().strftime("%H%M%S%f")
        equipment_id=f"PG-ETCH-{suffix}"
        ticket_no=f"PG-INC-{suffix}"
        self.db.save_equipment(
            {"equipment_id":equipment_id,"name":"PostgreSQL CI Etcher","owner":"EE-PG"},
            user="pg_ci",workstation="GHA",
        )
        eq=self.db.get_equipment(equipment_id)
        self.db.save_ticket({
            "ticket_no":ticket_no,
            "equipment_id":equipment_id,
            "title":"PostgreSQL workflow validation",
            "description":"CI transaction test",
            "severity":"S2",
            "priority":"P2",
            "owner":"EE-PG",
            "root_cause":"",
            "corrective_action":"",
            "verification":"",
            "created_by":"pg_ci",
        },workstation="GHA")
        self.db.transition_equipment_state(
            equipment_id,"Production",
            reason_code="RELEASED",reason_text="Qualified",
            user="pg_ci",workstation="GHA",expected_version=eq.version,
        )
        eq=self.db.get_equipment(equipment_id)
        self.db.transition_equipment_state(
            equipment_id,"Down",
            reason_code="FAILURE",reason_text="CI simulated interlock",
            related_ticket=ticket_no,owner="EE-PG",
            user="pg_ci",workstation="GHA",expected_version=eq.version,
        )
        self.assertEqual(self.db.get_equipment(equipment_id).status,"Down")
        events=self.db.list_equipment_state_events(equipment_id)
        self.assertEqual(events[0].related_ticket,ticket_no)

    def test_pm_deferral_transaction_on_postgresql(self):
        suffix=datetime.utcnow().strftime("%H%M%S%f")
        equipment_id=f"PG-CVD-{suffix}"
        self.db.save_equipment({"equipment_id":equipment_id,"name":"CVD"},user="pg_ci")
        due=datetime.utcnow()+timedelta(days=1)
        task=self.db.upsert_pm_task({
            "equipment_id":equipment_id,
            "pm_id":f"PG-PM-{suffix}",
            "pm_name":"PostgreSQL PM",
            "original_due_date":due,
            "scheduled_date":due,
            "status":"Scheduled",
        })
        req=self.db.request_pm_deferral(
            task.id,due+timedelta(days=2),
            "CI deferral reason","CI risk assessment","CI mitigation",
            "requester",workstation="GHA",expected_task_version=task.version,
        )
        approved=self.db.review_pm_deferral(
            req.id,True,"reviewer","CI approved",
            workstation="GHA",expected_version=req.version,
        )
        self.assertEqual(approved.status,"Approved")
        self.assertEqual(self.db.get_pm_task(task.id).status,"Deferred")


if __name__=="__main__":
    unittest.main()
