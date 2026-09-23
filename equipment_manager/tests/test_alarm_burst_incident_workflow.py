import unittest

from database import Database


class AlarmBurstIncidentWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.db.create_user("ee", "Equipment Engineer", "engineer-password-123", "Equipment Engineer")
        self.db.save_equipment({"equipment_id": "ETCH-01", "name": "Etcher"}, user="ee")
        self.db.save_equipment({"equipment_id": "CVD-01", "name": "CVD"}, user="ee")

    def test_burst_creates_one_incident_and_links_every_alarm(self):
        first = self.db.ingest_alarm("ETCH-01", "VAC", severity="Warning")
        second = self.db.ingest_alarm("ETCH-01", "VAC", severity="Critical")
        ticket = self.db.create_incident_from_alarm_burst(
            [first.event_key, second.event_key], "ee", owner="ee"
        )
        self.assertEqual(ticket.equipment_id, "ETCH-01")
        self.assertEqual(ticket.priority, "P2")
        rows = {row.event_key: row for row in self.db.list_alarms("ETCH-01")}
        self.assertEqual(rows[first.event_key].related_ticket, ticket.ticket_no)
        self.assertEqual(rows[second.event_key].related_ticket, ticket.ticket_no)

    def test_burst_rejects_mixed_equipment(self):
        first = self.db.ingest_alarm("ETCH-01", "VAC")
        second = self.db.ingest_alarm("CVD-01", "VAC")
        with self.assertRaisesRegex(ValueError, "one equipment"):
            self.db.create_incident_from_alarm_burst(
                [first.event_key, second.event_key], "ee"
            )


if __name__ == "__main__":
    unittest.main()
