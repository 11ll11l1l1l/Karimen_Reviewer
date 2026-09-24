import json
import unittest
from datetime import datetime, timedelta

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
        self.assertEqual(ticket.priority, "P1")
        rows = {row.event_key: row for row in self.db.list_alarms("ETCH-01")}
        self.assertEqual(rows[first.event_key].related_ticket, ticket.ticket_no)
        self.assertEqual(rows[second.event_key].related_ticket, ticket.ticket_no)

    def test_automatic_burst_workflow_threshold_cooldown_and_linkage(self):
        self.db.save_alarm_burst_policy(300,3,"WARNING",True)
        self.db.save_workflow_rule({
            "rule_id":"BURST-AUTO",
            "name":"Burst auto response",
            "trigger":"ALARM_BURST",
            "priority":10,
            "enabled":True,
            "match_json":"{}",
            "actions_json":json.dumps([
                {"type":"CREATE_INCIDENT","priority":"P2","severity":"S2","title":"Repeated vacuum alarm","owner":"ee"},
                {"type":"CREATE_WORK_ORDER","priority":"High","title":"Investigate repeated alarm"},
                {"type":"SET_DISPOSITION","state":"Hold","reason":"Alarm burst"},
            ]),
        },"ee")
        t0=datetime(2026,9,24,10,0,0)
        a1=self.db.ingest_alarm("ETCH-01","VAC",severity="Warning",event_key="burst-1",occurred_at=t0)
        a2=self.db.ingest_alarm("ETCH-01","VAC",severity="Warning",event_key="burst-2",occurred_at=t0+timedelta(seconds=30))
        self.assertEqual(len(self.db.list_tickets()),0)
        a3=self.db.ingest_alarm("ETCH-01","VAC",severity="Critical",event_key="burst-3",occurred_at=t0+timedelta(seconds=60))
        tickets=self.db.list_tickets()
        self.assertEqual(len(tickets),1)
        ticket=tickets[0]
        alarms={x.event_key:x for x in self.db.list_alarms("ETCH-01")}
        for key in ["burst-1","burst-2","burst-3"]:
            self.assertEqual(alarms[key].related_ticket,ticket.ticket_no)
        work=self.db.list_work_orders("ETCH-01")
        self.assertEqual(len(work),1)
        self.assertEqual(work[0].source_type,"TICKET")
        self.assertEqual(work[0].source_key,ticket.ticket_no)
        disposition=next(x for x in self.db.list_dispositions() if x.equipment_id=="ETCH-01" and x.active)
        self.assertEqual(disposition.related_ticket,ticket.ticket_no)

        self.db.ingest_alarm("ETCH-01","VAC",severity="Warning",event_key="burst-4",occurred_at=t0+timedelta(seconds=90))
        self.assertEqual(len(self.db.list_tickets()),1)
        self.assertEqual(len(self.db.list_work_orders("ETCH-01")),1)
        alarms={x.event_key:x for x in self.db.list_alarms("ETCH-01")}
        self.assertEqual(alarms["burst-4"].related_ticket,ticket.ticket_no)
        executions=[x for x in self.db.list_workflow_automation_executions() if x.trigger=="ALARM_BURST"]
        self.assertEqual(len(executions),1)

    def test_burst_policy_ignores_below_minimum_severity(self):
        self.db.save_alarm_burst_policy(300,2,"CRITICAL",True)
        self.db.save_workflow_rule({
            "rule_id":"BURST-CRITICAL",
            "name":"Critical burst",
            "trigger":"ALARM_BURST","priority":10,"enabled":True,
            "match_json":"{}","actions_json":json.dumps([{"type":"CREATE_INCIDENT"}]),
        },"ee")
        t0=datetime(2026,9,24,11,0,0)
        self.db.ingest_alarm("ETCH-01","TEMP",severity="Warning",event_key="temp-1",occurred_at=t0)
        self.db.ingest_alarm("ETCH-01","TEMP",severity="Warning",event_key="temp-2",occurred_at=t0+timedelta(seconds=10))
        self.assertEqual(len(self.db.list_tickets()),0)

    def test_burst_rejects_mixed_equipment(self):
        first = self.db.ingest_alarm("ETCH-01", "VAC")
        second = self.db.ingest_alarm("CVD-01", "VAC")
        with self.assertRaisesRegex(ValueError, "one equipment"):
            self.db.create_incident_from_alarm_burst(
                [first.event_key, second.event_key], "ee"
            )


if __name__ == "__main__":
    unittest.main()
