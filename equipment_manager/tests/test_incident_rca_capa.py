import unittest
from datetime import datetime, timedelta

from database import Database


class IncidentRcaCapaTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("ee","Equipment Engineer","engineer-password-123","Equipment Engineer")
        self.db.create_user("sup","Supervisor","supervisor-password-123","Supervisor")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher 01"},user="ee")
        for no,title in [("INC-001","Vacuum instability"),("INC-000","Previous vacuum issue")]:
            self.db.save_ticket({
                "ticket_no":no,"equipment_id":"ETCH-01","title":title,"description":"Pressure unstable",
                "severity":"S2","priority":"P2","owner":"ee","root_cause":"","corrective_action":"",
                "verification":"","created_by":"ee",
            })

    def test_structured_why_and_causal_factor(self):
        why=self.db.save_incident_why("INC-001",1,"Why did pressure oscillate?","Throttle response was unstable.","ee")
        self.assertEqual(why.sequence,1)
        factor=self.db.save_incident_causal_factor("INC-001",{
            "category":"Machine","factor_type":"Suspected","description":"Throttle valve response lag",
            "evidence":"Command/position mismatch","status":"Under Review",
        },"ee")
        self.assertEqual(factor.category,"Machine")
        self.assertEqual(len(self.db.list_incident_whys("INC-001")),1)
        self.assertEqual(len(self.db.list_incident_causal_factors("INC-001")),1)

    def test_action_requires_independent_effectiveness_verification(self):
        action=self.db.save_incident_action("INC-001",{
            "action_type":"Corrective","description":"Replace throttle actuator","owner":"ee",
            "due_at":datetime.utcnow()+timedelta(days=1),
            "effectiveness_criteria":"No pressure oscillation in 3 verification runs",
        },"ee")
        completed=self.db.complete_incident_action(action.id,"ee","Actuator replaced; three dry runs complete.",action.version)
        with self.assertRaises(ValueError):
            self.db.verify_incident_action(completed.id,"ee","Looks good",completed.version)
        verified=self.db.verify_incident_action(completed.id,"sup","Three independent product-equivalent verification runs passed.",completed.version)
        self.assertEqual(verified.status,"Verified")
        self.assertEqual(verified.verified_by,"sup")

    def test_recurrence_history_returns_same_equipment_incidents(self):
        rows=self.db.incident_similar_history("INC-001")
        self.assertTrue(any(x.ticket_no=="INC-000" for x in rows))


if __name__=="__main__":
    unittest.main()
