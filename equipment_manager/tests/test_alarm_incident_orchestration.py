import unittest

from database import Database


class AlarmIncidentOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("ee","Equipment Engineer","engineer-password-123","Equipment Engineer")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher 01"},user="ee")
        self.db.save_equipment({"equipment_id":"CVD-01","name":"CVD 01"},user="ee")

    def test_critical_alarm_creates_and_links_p1_incident(self):
        alarm=self.db.ingest_alarm(
            "ETCH-01","VAC-001",severity="Critical",message="Vacuum trip",source="Tool"
        )
        ticket=self.db.create_incident_from_alarm(alarm.event_key,"ee",owner="ee")
        self.assertEqual(ticket.equipment_id,"ETCH-01")
        self.assertEqual(ticket.priority,"P1")
        self.assertEqual(ticket.status,"Open")
        refreshed=self.db.list_alarms("ETCH-01",False)
        linked=next(x for x in refreshed if x.event_key==alarm.event_key)
        self.assertEqual(linked.related_ticket,ticket.ticket_no)

    def test_create_from_already_linked_alarm_is_idempotent(self):
        alarm=self.db.ingest_alarm("ETCH-01","TEMP-002",severity="Warning",message="Temperature high")
        first=self.db.create_incident_from_alarm(alarm.event_key,"ee")
        second=self.db.create_incident_from_alarm(alarm.event_key,"ee")
        self.assertEqual(first.ticket_no,second.ticket_no)
        self.assertEqual(len([x for x in self.db.list_tickets() if x.ticket_no==first.ticket_no]),1)

    def test_alarm_can_link_existing_incident_on_same_equipment(self):
        alarm=self.db.ingest_alarm("ETCH-01","RF-003",severity="Warning",message="RF mismatch")
        ticket=self.db.save_ticket({
            "ticket_no":"INC-EXISTING","equipment_id":"ETCH-01","title":"RF instability",
            "description":"Existing investigation","severity":"S2","priority":"P2","owner":"ee",
            "root_cause":"","corrective_action":"","verification":"","created_by":"ee",
        })
        linked,_=self.db.link_alarm_to_ticket(alarm.event_key,ticket.ticket_no,"ee")
        self.assertEqual(linked.related_ticket,"INC-EXISTING")

    def test_cross_equipment_link_is_rejected(self):
        alarm=self.db.ingest_alarm("ETCH-01","FLOW-004",severity="Warning",message="Flow warning")
        ticket=self.db.save_ticket({
            "ticket_no":"INC-CVD","equipment_id":"CVD-01","title":"CVD issue",
            "description":"Different equipment","severity":"S2","priority":"P2","owner":"ee",
            "root_cause":"","corrective_action":"","verification":"","created_by":"ee",
        })
        with self.assertRaises(ValueError):
            self.db.link_alarm_to_ticket(alarm.event_key,ticket.ticket_no,"ee")


if __name__=="__main__":
    unittest.main()
