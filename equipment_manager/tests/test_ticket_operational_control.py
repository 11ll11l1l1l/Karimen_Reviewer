import unittest
from datetime import datetime, timedelta

from database import Database


class TicketOperationalControlTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("ee","Equipment Engineer","engineer-password-123","Equipment Engineer")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"},user="ee")
        self.db.save_ticket({
            "ticket_no":"INC-001","equipment_id":"ETCH-01","title":"Vacuum instability",
            "description":"Pressure oscillation","severity":"S2","priority":"P2","owner":"ee",
            "root_cause":"","corrective_action":"","verification":"","created_by":"ee",
        })

    def test_operational_control_and_sla_escalation(self):
        now=datetime(2026,9,23,9,0,0)
        row=self.db.save_ticket_operational_control(
            "INC-001",
            {
                "containment":"",
                "production_impact":"Tool unavailable",
                "affected_lots":"LOT-A123",
                "safety_quality_risk":"Potential process drift",
                "response_due_at":now-timedelta(hours=1),
                "containment_due_at":now-timedelta(minutes=30),
                "resolution_due_at":now+timedelta(hours=4),
            },
            "ee",
        )
        self.assertEqual(row.escalation_level,0)
        escalated=self.db.evaluate_ticket_escalations(now)
        self.assertIn("INC-001",escalated)
        current=self.db.ticket_operational_control("INC-001")
        self.assertEqual(current.escalation_level,2)
        self.assertIn("Response SLA overdue",current.escalation_reason)
        self.assertIn("Containment overdue",current.escalation_reason)

    def test_resolution_overdue_reaches_level_three(self):
        now=datetime(2026,9,23,9,0,0)
        self.db.save_ticket_operational_control(
            "INC-001",
            {
                "containment":"Tool held and lot stopped",
                "production_impact":"Tool down",
                "affected_lots":"",
                "safety_quality_risk":"",
                "response_due_at":now-timedelta(hours=2),
                "containment_due_at":now-timedelta(hours=1),
                "resolution_due_at":now-timedelta(minutes=1),
            },
            "ee",
        )
        self.db.evaluate_ticket_escalations(now)
        current=self.db.ticket_operational_control("INC-001")
        self.assertEqual(current.escalation_level,3)

    def test_attention_queue_surfaces_critical_incident(self):
        self.db.save_ticket_operational_control(
            "INC-001",
            {
                "containment":"",
                "production_impact":"Tool down",
                "affected_lots":"",
                "safety_quality_risk":"",
                "response_due_at":datetime.utcnow()-timedelta(hours=1),
                "containment_due_at":datetime.utcnow()-timedelta(minutes=20),
                "resolution_due_at":datetime.utcnow()+timedelta(hours=2),
            },
            "ee",
        )
        queue=self.db.operations_attention_queue()
        hits=[x for x in queue if x["kind"]=="INCIDENT" and x["key"]=="INC-001"]
        self.assertEqual(len(hits),1)
        self.assertIn("Esc L",hits[0]["summary"])


if __name__=="__main__":
    unittest.main()
